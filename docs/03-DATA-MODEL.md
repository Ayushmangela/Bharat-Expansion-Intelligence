# 03 — Data Model

PostgreSQL 16. Required extension: `pg_trgm`. Optional: `postgis`.

## Schemas

| Schema | Purpose |
|---|---|
| `silver` | Cleaned, validated, geography-resolved staging + quarantine tables |
| `gold` | Star schema — facts, dimensions, materialised KPI views |
| `meta` | Ingestion runs, data quality log, score/weight versions, source registry |

Bronze is filesystem Parquet, not a database schema.

## Grain declarations — never mix

| Fact table | Grain |
|---|---|
| `fact_district_month` | district × month × NIC-2 |
| `fact_state_month` | state × month |
| `fact_state_annual` | state × fiscal year × NIC-2 |
| `fact_company` | one row per CIN |
| `fact_opportunity_score` | district × month × profile |

When a district-level score consumes a state-level input, that input is **inherited** by
every district in the state and must be flagged. See `is_inherited` handling in
`06-SCORING-METHODOLOGY.md`.

---

## DDL

### meta

```sql
CREATE SCHEMA IF NOT EXISTS meta;

CREATE TABLE meta.source (
    source_key        SERIAL PRIMARY KEY,
    source_code       TEXT NOT NULL UNIQUE,        -- 'S02'
    source_name       TEXT NOT NULL,
    publisher         TEXT NOT NULL,
    url               TEXT NOT NULL,
    licence           TEXT NOT NULL,               -- 'GODL-India'
    attribution_text  TEXT NOT NULL,               -- rendered in UI
    access_method     TEXT NOT NULL,               -- 'api' | 'xlsx' | 'pdf' | 'ckan'
    expected_refresh_days INT,
    data_vintage      DATE,                        -- as-of date of the DATA
    last_success_at   TIMESTAMPTZ,
    tier              CHAR(1) NOT NULL CHECK (tier IN ('A','B'))
);

CREATE TABLE meta.ingestion_run (
    load_id           BIGSERIAL PRIMARY KEY,
    source_key        INT NOT NULL REFERENCES meta.source,
    started_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at       TIMESTAMPTZ,
    status            TEXT NOT NULL,               -- running|success|failed|quarantined
    rows_fetched      BIGINT,
    rows_loaded       BIGINT,
    rows_quarantined  BIGINT,
    bronze_path       TEXT,
    observed_schema   JSONB,                       -- diffable schema history
    error_detail      TEXT
);

CREATE TABLE meta.quality_event (
    event_id     BIGSERIAL PRIMARY KEY,
    load_id      BIGINT REFERENCES meta.ingestion_run,
    gate         TEXT NOT NULL,        -- schema|business|referential|statistical
    severity     TEXT NOT NULL,        -- info|warn|error
    message      TEXT NOT NULL,
    row_sample   JSONB,
    created_at   TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE meta.weight_version (
    weight_version_id SERIAL PRIMARY KEY,
    profile_code      TEXT NOT NULL,
    method            TEXT NOT NULL,   -- 'entropy' | 'profile' | 'custom'
    weights           JSONB NOT NULL,  -- {indicator_code: weight}
    created_at        TIMESTAMPTZ DEFAULT now(),
    is_active         BOOLEAN DEFAULT false
);
```

### gold — dimensions

```sql
CREATE SCHEMA IF NOT EXISTS gold;

-- SCD-2. Districts split; Telangana was carved out of AP in 2014.
-- A type-1 geography dimension silently corrupts every historical comparison.
CREATE TABLE gold.dim_geography (
    geo_key            BIGSERIAL PRIMARY KEY,
    lgd_state_code     INT  NOT NULL,
    lgd_district_code  INT,                    -- NULL for state-grain rows
    state_name         TEXT NOT NULL,
    district_name      TEXT,
    region             TEXT,                   -- North/South/East/West/NE/Central
    area_sq_km         NUMERIC(12,2),
    centroid_lat       NUMERIC(9,6),
    centroid_lon       NUMERIC(9,6),
    grain              TEXT NOT NULL CHECK (grain IN ('state','district')),
    valid_from         DATE NOT NULL,
    valid_to           DATE,
    is_current         BOOLEAN NOT NULL DEFAULT true,
    UNIQUE (lgd_state_code, lgd_district_code, valid_from)
);
CREATE INDEX ix_geo_current ON gold.dim_geography (is_current, grain);
CREATE INDEX ix_geo_lgd ON gold.dim_geography (lgd_state_code, lgd_district_code);

-- Calendar AND Indian fiscal year. Non-negotiable in an India project.
CREATE TABLE gold.dim_date (
    date_key       INT PRIMARY KEY,        -- YYYYMM or YYYYMMDD
    full_date      DATE,
    year           INT NOT NULL,
    month          INT,
    quarter        INT,
    fiscal_year    TEXT NOT NULL,          -- 'FY2024-25'
    fiscal_quarter INT,                    -- Q1 = Apr-Jun
    grain          TEXT NOT NULL CHECK (grain IN ('day','month','year'))
);

CREATE TABLE gold.dim_industry (
    industry_key     SERIAL PRIMARY KEY,
    nic_2digit       CHAR(2) NOT NULL,
    nic_4digit       CHAR(4),
    section          CHAR(1),
    description      TEXT NOT NULL,
    is_manufacturing BOOLEAN NOT NULL DEFAULT false,
    UNIQUE (nic_2digit, nic_4digit)
);

CREATE TABLE gold.dim_company_status (
    status_key    SERIAL PRIMARY KEY,
    status_name   TEXT NOT NULL UNIQUE,   -- Active|Struck Off|Under Liquidation|Dormant|Amalgamated
    is_active     BOOLEAN NOT NULL,
    is_distress   BOOLEAN NOT NULL
);

CREATE TABLE gold.dim_profile (
    profile_key    SERIAL PRIMARY KEY,
    profile_code   TEXT NOT NULL UNIQUE,  -- manufacturing|logistics|retail|services|balanced
    profile_name   TEXT NOT NULL,
    description    TEXT,
    pillar_weights JSONB NOT NULL         -- {economic:.3, ecosystem:.25, infra:.3, human:.15}
);

CREATE TABLE gold.dim_source (
    source_key INT PRIMARY KEY REFERENCES meta.source(source_key)
);
```

### gold — facts

```sql
CREATE TABLE gold.fact_district_month (
    geo_key                      BIGINT NOT NULL REFERENCES gold.dim_geography,
    date_key                     INT    NOT NULL REFERENCES gold.dim_date,
    industry_key                 INT    REFERENCES gold.dim_industry,   -- NULL = all industries
    new_incorporations           INT,
    median_paid_up_capital_lakh  NUMERIC(14,2),
    total_paid_up_capital_lakh   NUMERIC(18,2),
    active_companies             INT,
    struck_off_companies         INT,
    msme_micro                   INT,
    msme_small                   INT,
    msme_medium                  INT,
    msme_manufacturing           INT,
    msme_services                INT,
    startups_recognised          INT,
    quality_flags                INT NOT NULL DEFAULT 0,
    load_id                      BIGINT NOT NULL REFERENCES meta.ingestion_run,
    PRIMARY KEY (geo_key, date_key, industry_key)
) PARTITION BY RANGE (date_key);
-- create yearly partitions: fact_district_month_2020 .. _2026

CREATE TABLE gold.fact_state_month (
    geo_key                 BIGINT NOT NULL REFERENCES gold.dim_geography,
    date_key                INT    NOT NULL REFERENCES gold.dim_date,
    gst_collection_cr       NUMERIC(14,2),
    gst_active_taxpayers    INT,
    energy_requirement_mu   NUMERIC(12,2),
    energy_availability_mu  NUMERIC(12,2),
    energy_deficit_pct      NUMERIC(6,3),
    peak_demand_mw          NUMERIC(12,2),
    peak_met_mw             NUMERIC(12,2),
    peak_deficit_pct        NUMERIC(6,3),
    iip_index               NUMERIC(8,2),
    quality_flags           INT NOT NULL DEFAULT 0,
    load_id                 BIGINT NOT NULL REFERENCES meta.ingestion_run,
    PRIMARY KEY (geo_key, date_key)
);

CREATE TABLE gold.fact_state_annual (
    geo_key                  BIGINT NOT NULL REFERENCES gold.dim_geography,
    date_key                 INT    NOT NULL REFERENCES gold.dim_date,
    industry_key             INT    REFERENCES gold.dim_industry,
    gsdp_current_cr          NUMERIC(16,2),
    gsdp_constant_cr         NUMERIC(16,2),
    per_capita_income        NUMERIC(14,2),
    bank_credit_cr           NUMERIC(16,2),
    bank_deposits_cr         NUMERIC(16,2),
    asi_factories            INT,
    asi_employment           INT,
    asi_fixed_capital_cr     NUMERIC(16,2),
    asi_gva_cr               NUMERIC(16,2),
    plfs_unemployment_rate   NUMERIC(6,3),
    plfs_lfpr                NUMERIC(6,3),
    plfs_wpr                 NUMERIC(6,3),
    state_capex_cr           NUMERIC(16,2),
    capex_budgeted_cr        NUMERIC(16,2),
    road_length_km           NUMERIC(12,2),
    population_projected     BIGINT,
    data_vintage_year        INT,            -- ALWAYS populated
    quality_flags            INT NOT NULL DEFAULT 0,
    load_id                  BIGINT NOT NULL REFERENCES meta.ingestion_run,
    PRIMARY KEY (geo_key, date_key, industry_key)
);

CREATE TABLE gold.fact_company (
    company_key         BIGSERIAL PRIMARY KEY,
    cin                 TEXT NOT NULL UNIQUE,
    company_name        TEXT NOT NULL,
    geo_key             BIGINT REFERENCES gold.dim_geography,
    industry_key        INT REFERENCES gold.dim_industry,
    status_key          INT REFERENCES gold.dim_company_status,
    incorporation_date  DATE,
    authorized_capital  NUMERIC(18,2),
    paid_up_capital     NUMERIC(18,2),
    company_class       TEXT,
    company_category    TEXT,
    pin_code            CHAR(6),
    geocode_confidence  NUMERIC(4,3),   -- 0..1; drives exclusion from cluster analysis
    snapshot_date       DATE NOT NULL,
    quality_flags       INT NOT NULL DEFAULT 0,
    load_id             BIGINT NOT NULL REFERENCES meta.ingestion_run
);
CREATE INDEX ix_company_geo ON gold.fact_company (geo_key);
CREATE INDEX ix_company_nic ON gold.fact_company (industry_key);
CREATE INDEX ix_company_incdate ON gold.fact_company (incorporation_date);
CREATE INDEX ix_company_status ON gold.fact_company (status_key);

CREATE TABLE gold.fact_opportunity_score (
    geo_key             BIGINT NOT NULL REFERENCES gold.dim_geography,
    date_key            INT    NOT NULL REFERENCES gold.dim_date,
    profile_key         INT    NOT NULL REFERENCES gold.dim_profile,
    opportunity_score   NUMERIC(6,3) NOT NULL CHECK (opportunity_score BETWEEN 0 AND 100),
    pillar_economic     NUMERIC(6,3),
    pillar_ecosystem    NUMERIC(6,3),
    pillar_infrastructure NUMERIC(6,3),
    pillar_human_capital  NUMERIC(6,3),
    rank_national       INT,
    rank_within_state   INT,
    rank_ci_low         INT,          -- Monte Carlo 95% interval
    rank_ci_high        INT,
    confidence_score    NUMERIC(5,4) NOT NULL,  -- data completeness, 0..1
    indicators_used     INT NOT NULL,
    indicators_total    INT NOT NULL,
    weight_version_id   INT NOT NULL REFERENCES meta.weight_version,
    computed_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (geo_key, date_key, profile_key, weight_version_id)
);

-- SHAP contributions, one row per indicator per scored district
CREATE TABLE gold.fact_score_contribution (
    geo_key           BIGINT NOT NULL,
    date_key          INT    NOT NULL,
    profile_key       INT    NOT NULL,
    weight_version_id INT    NOT NULL,
    indicator_code    TEXT   NOT NULL,
    raw_value         NUMERIC(18,4),
    normalised_value  NUMERIC(8,4),
    shap_contribution NUMERIC(8,4) NOT NULL,
    is_imputed        BOOLEAN NOT NULL DEFAULT false,
    is_inherited      BOOLEAN NOT NULL DEFAULT false,  -- state value applied to district
    source_code       TEXT NOT NULL,
    PRIMARY KEY (geo_key, date_key, profile_key, weight_version_id, indicator_code)
);
```

### silver — geography resolution

```sql
CREATE SCHEMA IF NOT EXISTS silver;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Persistent alias map. Grows over time. COMMIT THIS as a seed file.
CREATE TABLE silver.geography_alias (
    alias_id          BIGSERIAL PRIMARY KEY,
    observed_state    TEXT NOT NULL,
    observed_district TEXT,
    lgd_state_code    INT NOT NULL,
    lgd_district_code INT,
    match_method      TEXT NOT NULL,   -- exact|alias|fuzzy|manual
    confidence        NUMERIC(4,3),
    created_at        TIMESTAMPTZ DEFAULT now(),
    UNIQUE (observed_state, observed_district)
);
CREATE INDEX ix_alias_trgm_state ON silver.geography_alias
    USING gin (observed_state gin_trgm_ops);

-- Anything unresolvable lands here. NOTHING proceeds to gold unresolved.
CREATE TABLE silver.geography_quarantine (
    quarantine_id     BIGSERIAL PRIMARY KEY,
    load_id           BIGINT REFERENCES meta.ingestion_run,
    source_code       TEXT NOT NULL,
    observed_state    TEXT,
    observed_district TEXT,
    observed_pin      CHAR(6),
    raw_row           JSONB NOT NULL,
    best_guess_lgd    INT,
    best_guess_score  NUMERIC(4,3),
    resolved          BOOLEAN DEFAULT false,
    created_at        TIMESTAMPTZ DEFAULT now()
);
```

## quality_flags bitmask

```
bit 0 (1)    value imputed
bit 1 (2)    value inherited from parent geography (state → district)
bit 2 (4)    statistical outlier (flagged, not removed)
bit 3 (8)    winsorised
bit 4 (16)   geography resolved by fuzzy match
bit 5 (32)   source data stale (past expected refresh)
bit 6 (64)   partial period (incomplete month/year)
bit 7 (128)  revised by source after initial load
```

## Design decisions to defend

**1. SCD-2 on `dim_geography`.** Indian districts split regularly. Type-1 corrupts
history silently.

**2. Three grains, not one.** Forcing everything to district grain means fabricating
district data you don't have. Forcing state grain throws away district data you do have.
Declare per table.

**3. `confidence_score` on every score row.** A score from 11 of 11 indicators is not
the same object as one from 6 of 11. Publishing both as "84" is dishonest.

**4. `fact_score_contribution` as a separate table.** The explanation is the product,
so it is first-class storage, not a runtime computation.
