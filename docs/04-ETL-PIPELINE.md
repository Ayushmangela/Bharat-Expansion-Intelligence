# 04 — ETL Pipeline

Pattern: **ELT with a governed transform layer.** Land raw, transform in Python/Postgres.
Never transform in flight — you lose the audit trail.

## Connector base class

Every source implements this. No exceptions.

```python
# backend/pipeline/connectors/base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date

@dataclass
class RawPayload:
    source_code: str
    fetched_at: str
    records: list[dict]
    observed_schema: dict          # field -> inferred type
    total_available: int | None
    request_url: str               # api-key REDACTED before storing

class BaseConnector(ABC):
    source_code: str
    expected_refresh_days: int

    @abstractmethod
    async def fetch(self, **kwargs) -> RawPayload: ...

    @abstractmethod
    def natural_key(self) -> list[str]:
        """Columns forming the idempotency key."""

    def write_bronze(self, payload: RawPayload, ingest_date: date) -> str:
        """Parquet -> data/bronze/source={code}/ingest_date={date}/part.parquet
        Append-only. Never overwrite."""
```

## Stage 1 — Extract

- Pagination via `offset`/`limit` for OGD resources
- **The MCA sweep must be checkpointed and resumable.** ~3.67M rows across ~25 RoC
  resources will not come down in one call, and a crash at 80% must not restart at 0.
  Persist `(resource_id, last_offset)` after each page.
- Retry: `min(1 * 2**attempt, 60) + jitter(0,1s)`, max 5 attempts
  - Retryable: 429, 500, 502, 503, 504, timeouts, connection resets
  - Not retryable: 400, 401, 403, 404 → fail fast, alert, do not loop
- Circuit breaker: 10 consecutive failures on a source → open circuit, skip source this
  run, alert, serve last good data
- **Every raw response written to bronze BEFORE any parsing.**
- Redact `api-key` from any URL before logging or storing.

## Stage 2 — Bronze

```
data/bronze/source=S02_mca/ingest_date=2026-08-14/roc=mumbai/part-000.parquet
```

Immutable. Append-only. Gitignored. Never modified, never deleted.

## Stage 3 — Transform to silver

Order matters:

1. **Schema validation (Pandera)** — declare columns, dtypes, nullability, value ranges.
   A violation **fails the run**. Do not coerce silently.
2. **Deduplicate** on natural key, deterministic tie-break (latest `ingest_date` wins)
3. **Unit normalisation** — canonical unit per measure, original value + unit retained
   - Currency → ₹ lakh
   - Energy → MU
   - Percentages → 0–100 float
4. **Period normalisation** — assign `date_key`; label calendar vs fiscal explicitly
5. **Geography resolution** — see below. Blocking.
6. **Outlier flagging** — set `quality_flags` bit 2. **Never delete.**

## Geography resolution engine

This is the highest-risk component in the project. It gets its own module:
`backend/pipeline/geography/resolver.py`.

```
resolve(observed_state, observed_district=None, observed_pin=None) -> Resolution

Step 1  Normalise the string
        strip, collapse whitespace, casefold, remove zero-width chars,
        expand '&' -> 'and', drop punctuation

Step 2  Exact match against dim_geography (normalised)

Step 3  Lookup in silver.geography_alias

Step 4  PIN-code path (for MCA): parse 6-digit PIN from address text,
        join via LGD local-bodies-with-PIN-codes to district

Step 5  Fuzzy match with pg_trgm, similarity >= 0.85
        ALWAYS scoped by state -- district names are not unique nationally
        On success: write the pair into geography_alias so it is exact next time

Step 6  QUARANTINE -> silver.geography_quarantine with best guess + score
```

**Rules:**
- Nothing reaches gold unresolved
- Always disambiguate district by `(state, district)`, never district alone
- Fuzzy matches set `quality_flags` bit 4
- Track and report resolution rate every run. **Target ≥95% for named geographies,
  ≥85% for PIN-derived.** Below target = investigate before proceeding.

Known aliases to seed `data/reference/geography_alias_seed.csv`:

```
Orissa -> Odisha                     Pondicherry -> Puducherry
Uttaranchal -> Uttarakhand           NCT of Delhi -> Delhi
Delhi (NCT) -> Delhi                 A & N Islands -> Andaman and Nicobar Islands
Andaman & Nicobar -> Andaman and Nicobar Islands
Gurgaon -> Gurugram                  Bangalore -> Bengaluru
Dadra and Nagar Haveli + Daman and Diu  (merged 2020 — handle both forms)
```

Ambiguous district names requiring state scoping:
`Aurangabad` (MH, BR) · `Bilaspur` (CG, HP) · `Hamirpur` (HP, UP) ·
`Pratapgarh` (UP, RJ) · `Balrampur` (UP, CG)

## Stage 4 — Load to gold

- Upsert dimensions (SCD-2 where declared)
- Insert facts with `load_id` FK
- **Transactional per source: all rows or none.** Never partially load.
- Refresh materialised KPI views
- Run post-load assertion suite (see `09-DATA-QUALITY.md`)

## Stage 5 — Score (separate stage)

Ingestion can succeed while scoring is deferred. Scores are written with the
`weight_version_id` used, so any historical score is reproducible.

## Refresh schedule

| Source | Cadence | Strategy | On failure |
|---|---|---|---|
| LGD | Quarterly | Full refresh, SCD-2 | **Block deploy.** Critical. |
| MCA Company Master | Monthly | Checkpointed full sweep + snapshot diff | Serve last good, flag stale |
| Udyam | Monthly | Full pull + diff vs prior snapshot to derive flows | Serve last good |
| DPIIT Startups | Monthly | Full pull (small) | Serve last good |
| CEA Power | Monthly | Incremental by period | Serve last good |
| GST | Monthly | PDF fetch + parse + assert | **Quarantine on parse failure. Do not load.** |
| Open Budgets | Annual | CKAN API | Serve last good |
| eSankhyiki | Annual (IIP monthly) | Manual download + validated load | Version-pinned |
| RBI Handbook | Annual | Manual download on publication | Version-pinned |
| Census 2011 | Once | One-time load | — |

## Idempotency

Every load must be safely re-runnable.

```sql
INSERT INTO gold.fact_district_month (...)
VALUES (...)
ON CONFLICT (geo_key, date_key, industry_key)
DO UPDATE SET
    new_incorporations = EXCLUDED.new_incorporations,
    ...,
    load_id = EXCLUDED.load_id;
```

Post-load assertion: `count(*) = count(DISTINCT natural_key)`.

## Snapshot diffing (Udyam and MCA)

Udyam publishes cumulative-to-date counts. To derive a monthly flow:

```
flow(month_n) = cumulative(snapshot_n) - cumulative(snapshot_{n-1})
```

Store every snapshot. Guard against negative flows (they indicate a source restatement,
not negative registrations) — flag, don't silently clamp to zero.

**MCA snapshot integrity gate:** if a new snapshot has <95% of the prior snapshot's row
count, **quarantine and alert — do not diff.** A truncated download would otherwise
register as a mass-extinction event.

## Orchestration

Prefect flows in `backend/pipeline/flows/`. One flow per source, plus a
`daily_orchestrator` and `monthly_orchestrator`.

Alternative for zero-infra: GitHub Actions cron. Free, publicly logged, and the run
history itself becomes portfolio evidence.

**Do not use Airflow.** If asked, explain the trade-off honestly rather than complying.
