"""phase 1 schema: meta, geography, fact_company

Phase-1 scoped subset of docs/03-DATA-MODEL.md. Deliberately excludes
dim_profile, dim_source, fact_district_month, fact_state_month,
fact_state_annual, fact_opportunity_score, fact_score_contribution, and
meta.weight_version — those are Phase 2/3 concerns and building them now
would be scoring/ingestion infrastructure with nothing yet to populate it.
See STATUS.md for the phase boundary this migration draws.

Revision ID: c2a69df9db6d
Revises:
Create Date: 2026-08-14 18:22:57.249816

"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'c2a69df9db6d'
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS meta")
    op.execute("CREATE SCHEMA IF NOT EXISTS silver")
    op.execute("CREATE SCHEMA IF NOT EXISTS gold")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    op.execute("""
        CREATE TABLE meta.source (
            source_key        SERIAL PRIMARY KEY,
            source_code       TEXT NOT NULL UNIQUE,
            source_name       TEXT NOT NULL,
            publisher         TEXT NOT NULL,
            url               TEXT NOT NULL,
            licence           TEXT NOT NULL,
            attribution_text  TEXT NOT NULL,
            access_method     TEXT NOT NULL,
            expected_refresh_days INT,
            data_vintage      DATE,
            last_success_at   TIMESTAMPTZ,
            tier              CHAR(1) NOT NULL CHECK (tier IN ('A','B'))
        )
    """)

    op.execute("""
        CREATE TABLE meta.ingestion_run (
            load_id           BIGSERIAL PRIMARY KEY,
            source_key        INT NOT NULL REFERENCES meta.source,
            started_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
            finished_at       TIMESTAMPTZ,
            status             TEXT NOT NULL,
            rows_fetched      BIGINT,
            rows_loaded       BIGINT,
            rows_quarantined  BIGINT,
            bronze_path       TEXT,
            observed_schema   JSONB,
            error_detail      TEXT
        )
    """)

    op.execute("""
        CREATE TABLE meta.quality_event (
            event_id     BIGSERIAL PRIMARY KEY,
            load_id      BIGINT REFERENCES meta.ingestion_run,
            gate         TEXT NOT NULL,
            severity     TEXT NOT NULL,
            message      TEXT NOT NULL,
            row_sample   JSONB,
            created_at   TIMESTAMPTZ DEFAULT now()
        )
    """)

    op.execute("""
        CREATE TABLE gold.dim_geography (
            geo_key            BIGSERIAL PRIMARY KEY,
            lgd_state_code     INT  NOT NULL,
            lgd_district_code  INT,
            state_name         TEXT NOT NULL,
            district_name      TEXT,
            state_census2011_code    TEXT,
            district_census2011_code TEXT,
            region             TEXT,
            area_sq_km         NUMERIC(12,2),
            centroid_lat       NUMERIC(9,6),
            centroid_lon       NUMERIC(9,6),
            grain              TEXT NOT NULL CHECK (grain IN ('state','district')),
            valid_from         DATE NOT NULL,
            valid_to           DATE,
            is_current         BOOLEAN NOT NULL DEFAULT true,
            UNIQUE (lgd_state_code, lgd_district_code, valid_from)
        )
    """)
    op.execute("CREATE INDEX ix_geo_current ON gold.dim_geography (is_current, grain)")
    op.execute("CREATE INDEX ix_geo_lgd ON gold.dim_geography (lgd_state_code, lgd_district_code)")
    op.execute("CREATE INDEX ix_geo_census ON gold.dim_geography (state_census2011_code, district_census2011_code)")

    op.execute("""
        CREATE TABLE gold.dim_date (
            date_key       INT PRIMARY KEY,
            full_date      DATE,
            year           INT NOT NULL,
            month          INT,
            quarter        INT,
            fiscal_year    TEXT NOT NULL,
            fiscal_quarter INT,
            grain          TEXT NOT NULL CHECK (grain IN ('day','month','year'))
        )
    """)

    op.execute("""
        CREATE TABLE gold.dim_industry (
            industry_key     SERIAL PRIMARY KEY,
            nic_2digit       CHAR(2) NOT NULL,
            nic_4digit       CHAR(4),
            section          CHAR(1),
            description      TEXT NOT NULL,
            is_manufacturing BOOLEAN NOT NULL DEFAULT false,
            UNIQUE (nic_2digit, nic_4digit)
        )
    """)

    op.execute("""
        CREATE TABLE gold.dim_company_status (
            status_key    SERIAL PRIMARY KEY,
            status_name   TEXT NOT NULL UNIQUE,
            is_active     BOOLEAN NOT NULL,
            is_distress   BOOLEAN NOT NULL
        )
    """)

    op.execute("""
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
            geocode_confidence  NUMERIC(4,3),
            snapshot_date       DATE NOT NULL,
            quality_flags       INT NOT NULL DEFAULT 0,
            load_id             BIGINT NOT NULL REFERENCES meta.ingestion_run
        )
    """)
    op.execute("CREATE INDEX ix_company_geo ON gold.fact_company (geo_key)")
    op.execute("CREATE INDEX ix_company_nic ON gold.fact_company (industry_key)")
    op.execute("CREATE INDEX ix_company_incdate ON gold.fact_company (incorporation_date)")
    op.execute("CREATE INDEX ix_company_status ON gold.fact_company (status_key)")

    op.execute("""
        CREATE TABLE silver.geography_alias (
            alias_id          BIGSERIAL PRIMARY KEY,
            observed_state    TEXT NOT NULL,
            observed_district TEXT,
            lgd_state_code    INT NOT NULL,
            lgd_district_code INT,
            match_method      TEXT NOT NULL,
            confidence        NUMERIC(4,3),
            created_at        TIMESTAMPTZ DEFAULT now(),
            UNIQUE (observed_state, observed_district)
        )
    """)
    op.execute("""
        CREATE INDEX ix_alias_trgm_state ON silver.geography_alias
            USING gin (observed_state gin_trgm_ops)
    """)

    op.execute("""
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
        )
    """)

    # Phase-1 addition, not in the original DDL: LGD local-body PIN codes,
    # needed by resolver Step 4 (PIN -> district). Small reference table,
    # not part of the star schema proper.
    op.execute("""
        CREATE TABLE silver.lgd_pincode_lookup (
            pincode            CHAR(6) NOT NULL,
            lgd_state_code     INT NOT NULL,
            lgd_district_code  INT,
            local_body_code    INT,
            local_body_name    TEXT,
            PRIMARY KEY (pincode, local_body_code)
        )
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS silver.lgd_pincode_lookup")
    op.execute("DROP TABLE IF EXISTS silver.geography_quarantine")
    op.execute("DROP TABLE IF EXISTS silver.geography_alias")
    op.execute("DROP TABLE IF EXISTS gold.fact_company")
    op.execute("DROP TABLE IF EXISTS gold.dim_company_status")
    op.execute("DROP TABLE IF EXISTS gold.dim_industry")
    op.execute("DROP TABLE IF EXISTS gold.dim_date")
    op.execute("DROP TABLE IF EXISTS gold.dim_geography")
    op.execute("DROP TABLE IF EXISTS meta.quality_event")
    op.execute("DROP TABLE IF EXISTS meta.ingestion_run")
    op.execute("DROP TABLE IF EXISTS meta.source")
