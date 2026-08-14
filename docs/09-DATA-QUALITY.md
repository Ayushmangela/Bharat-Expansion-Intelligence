# 09 — Data Quality

These are not hypothetical failure modes. Each is a specific, named problem in Indian
government data.

---

## Validation gates

Every load passes through five gates in order. Any failure quarantines the batch and
writes to `meta.quality_event`.

**A failed load is always better than a silent corruption**, because corruption
propagates into every score and you may not notice for months.

### Gate 1 — Ingestion
HTTP status 200 · non-empty body · expected content-type · response size within bounds

### Gate 2 — Schema (Pandera)
Columns present · dtypes correct · nullability respected · value ranges

```python
import pandera as pa

mca_schema = pa.DataFrameSchema({
    "cin": pa.Column(str, pa.Check.str_length(21, 21), nullable=False, unique=True),
    "paid_up_capital": pa.Column(float, pa.Check.ge(0), nullable=True),
    "authorized_capital": pa.Column(float, pa.Check.ge(0), nullable=True),
    "incorporation_date": pa.Column("datetime64[ns]",
        pa.Check.le(pd.Timestamp.now()), nullable=True),
    "company_status": pa.Column(str, pa.Check.isin(VALID_STATUSES)),
})
```
Store the observed schema in `meta.ingestion_run.observed_schema` so schema drift is
diffable. **Never `SELECT *` into a fact table.**

### Gate 3 — Business rules
```
min_price <= modal_price <= max_price
paid_up_capital <= authorized_capital
0 <= any percentage <= 100
incorporation_date <= today
energy_availability <= energy_requirement
msme_micro + msme_small + msme_medium == msme_total  (where total is given)
```

### Gate 4 — Referential
Every FK resolves. Zero orphans. **Zero unresolved geographies.**

### Gate 5 — Statistical
- Row count within ±30% of the trailing average for that source
- Mean of key measures within 3σ of history
- **MCA snapshot gate: new snapshot < 95% of prior row count → quarantine, do not
  diff.** A truncated download would otherwise register as mass corporate extinction.

### Post-load assertions
```sql
-- no duplicates on natural key
SELECT COUNT(*) = COUNT(DISTINCT (geo_key, date_key, industry_key))
FROM gold.fact_district_month;

-- no orphan geographies
SELECT COUNT(*) FROM gold.fact_district_month f
LEFT JOIN gold.dim_geography g USING (geo_key) WHERE g.geo_key IS NULL;
-- must be 0

-- scores in range
SELECT COUNT(*) FROM gold.fact_opportunity_score
WHERE opportunity_score NOT BETWEEN 0 AND 100;
-- must be 0
```

---

## The failure modes, by name

### 1. State and district naming — the biggest problem

You will encounter:
`Orissa`/`Odisha` · `Pondicherry`/`Puducherry` · `Uttaranchal`/`Uttarakhand` ·
`NCT of Delhi`/`Delhi`/`Delhi (NCT)` · `Andaman & Nicobar`/`Andaman and Nicobar Islands`/
`A & N Islands` · `Dadra and Nagar Haveli and Daman and Diu` (merged 2020, appears both
ways) · plus trailing whitespace, inconsistent case, zero-width characters.

Districts are worse: they split constantly, `Gurgaon`→`Gurugram`, and names repeat
across states.

**Mitigation:** the LGD-first rule and the 6-step resolver in `04-ETL-PIPELINE.md`.
Track resolution rate as a headline metric. Target ≥95% named, ≥85% PIN-derived.

### 2. Missing values

Where: district indicators for smaller UTs · newer districts absent from older datasets ·
state DTV figures · Udyam gaps.

**Missingness is often not random** — small units under-report, so naive averaging biases
toward large ones. Classify as MCAR/MAR/MNAR. Follow the preference order in
`06-SCORING-METHODOLOGY.md` §4. Surface completeness % in the UI.

### 3. Duplicates

Where: OGD pagination returning overlapping windows on retry · companies appearing
across RoC resources · non-idempotent re-runs.

**Mitigation:** natural key + unique constraint + `ON CONFLICT DO UPDATE`. Assert
post-load.

### 4. API failures

data.gov.in intermittently times out or returns partial responses. Government sites have
maintenance windows.

**Mitigation:** backoff with jitter · circuit breaker · **serve last good snapshot marked
stale rather than showing an error** · generous timeouts (government infra is slow, not
broken) · log every failure to `meta.ingestion_run`.

### 5. Schema changes

OGD resource IDs get reissued. Field names change case between refreshes. New columns
appear.

**Mitigation:** versioned Pandera contracts. Violation fails the run loudly. Observed
schema stored per run for diffing.

### 6. Historical gaps

Udyam is cumulative not flow · GST state splits inconsistent in early years · Census is
2011 with no 2021 replacement · MCA has no built-in history.

**Mitigation:** snapshot-and-accumulate from day one. Explicit gap-detection jobs.
**Never interpolate across a gap without flagging it.**

### 7. Units

₹ crore vs ₹ lakh vs ₹ · MU vs BU vs kWh · quintal vs tonne · USD vs INR.

**Mitigation:** canonical unit per measure declared in schema, converted at silver,
original value + unit retained. **Never convert in the presentation layer.**

### 8. Reporting periods

RBI and budgets use Indian fiscal year (Apr–Mar). Census uses calendar. PLFS uses
Jul–Jun survey periods. GST is calendar-monthly.

**Mitigation:** `dim_date` carries both. Every fact declares which it uses. **Never join
across conventions without an explicit bridge.** Label every chart axis — `FY2024-25`
and `2024` are different objects.

### 9. Freshness

ASI lags 2–3 years · road statistics lag several years · Census is 2011 · Udyam is
cumulative.

**Mitigation:** `meta.source.expected_refresh_days`. Compute staleness. Sources >2×
overdue get a visible warning badge. **Never present a 2011 figure without its year.**

### 10. Outliers

Mumbai/Bengaluru/Delhi company counts orders of magnitude above median (partly real
agglomeration, partly registered-office artefacts) · tiny-population districts producing
extreme per-capita ratios.

**Mitigation:** winsorise at 1st/99th before normalising · rolling MAD for time series
(robust; standard deviation is inflated by the outliers themselves) · **flag, never
delete** · minimum-population threshold for per-capita metrics · investigate every
outlier — roughly half will be errors and half genuine findings.

---

## Rate limiting and retry

```
Retryable:      429, 500, 502, 503, 504, timeouts, connection resets
Not retryable:  400, 401, 403, 404  → fail fast, alert, do not loop

Backoff:  min(1 * 2**attempt, 60) + uniform_jitter(0, 1s), max 5 attempts
Limiter:  token bucket, 2 rps, max 4 concurrent
Breaker:  10 consecutive failures → open, skip source, alert
Checkpoint: paginated sweeps persist offset; resume, never restart 3.67M rows
```

Respect `Retry-After` when present. Set a descriptive `User-Agent`.

---

## Reported metrics (public, on `/data`)

| Metric | Target |
|---|---|
| Geography resolution rate (named) | ≥95% |
| Geography resolution rate (PIN-derived) | ≥85% |
| Districts with confidence ≥0.90 | ≥70% |
| Sources within expected refresh window | 100% |
| Quarantined rows this load | trend, investigate spikes |
| Failed loads (30d) | 0 |

Below target is not a reason to hide the number. It is a reason to display it and
investigate.
