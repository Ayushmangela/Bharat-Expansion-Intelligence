# 02 — Architecture

## System diagram

```
┌──────────────────────── SOURCES (10, all free) ────────────────────────┐
│  REST/JSON   MCA · Udyam · DPIIT · CEA Power · LGD · Census (data.gov.in)│
│  CKAN API    Open Budgets India                                          │
│  XLSX        RBI Handbook of Statistics on Indian States                 │
│  Portal      MoSPI eSankhyiki (ASI, PLFS, IIP, NAS)                      │
│  PDF         GST statistics                                              │
└───────────────────────────────┬────────────────────────────────────────┘
                                │
                  ┌─────────────▼─────────────┐
                  │  CONNECTORS               │  one class per source
                  │  · BaseConnector ABC      │  common interface
                  │  · retry + backoff+jitter │
                  │  · rate limiter (token    │
                  │    bucket, 2 rps)         │
                  │  · circuit breaker        │
                  │  · run manifest emitted   │
                  └─────────────┬─────────────┘
                                │
                  ┌─────────────▼─────────────┐
                  │  BRONZE  (immutable)      │  Parquet
                  │  data/bronze/             │  source={s}/ingest_date={d}/
                  │  raw, verbatim, append-   │  NEVER modified or deleted
                  │  only, gitignored         │  = the audit trail
                  └─────────────┬─────────────┘
                                │
                  ┌─────────────▼─────────────┐
                  │  SILVER  (validated)      │
                  │  · Pandera schema gate    │  ← fails run on violation
                  │  · unit normalisation     │
                  │  · GEOGRAPHY RESOLUTION   │  ← LGD codes or quarantine
                  │  · period normalisation   │
                  │  · outliers FLAGGED       │  ← never deleted
                  │  · dedupe on natural key  │
                  └─────────────┬─────────────┘
                                │
                  ┌─────────────▼─────────────┐
                  │  GOLD  (PostgreSQL)       │
                  │  star schema              │
                  │  5 facts · 6 dimensions   │
                  │  SCD-2 on geography+company│
                  │  materialised KPI views   │
                  │  every row: load_id +     │
                  │  quality_flags            │
                  └─────────────┬─────────────┘
                                │
                  ┌─────────────▼─────────────┐
                  │  SCORING ENGINE (separate)│
                  │  · normalise + winsorise  │
                  │  · entropy + profile wts  │
                  │  · Monte Carlo sensitivity│
                  │  · SHAP decomposition     │
                  │  · versioned weight vector│  ← historical scores reproducible
                  └─────────────┬─────────────┘
                                │
          ┌─────────────────────┼─────────────────────┐
          ▼                     ▼                     ▼
  ┌───────────────┐   ┌──────────────────┐   ┌─────────────────┐
  │ FastAPI       │   │ Redis cache      │   │ Metabase (opt.) │
  │ routers →     │   │ keyed on weight  │   │ ad-hoc on gold  │
  │ services →    │◄──┤ version + load id│   └─────────────────┘
  │ repositories  │   └──────────────────┘
  └───────┬───────┘
          ▼
  ┌───────────────┐   ┌──────────────────┐
  │ Next.js       │   │ Ollama (optional)│  narrative layer
  │ TypeScript    │◄──┤ degrades to raw  │  MUST degrade gracefully
  └───────────────┘   │ decomposition    │
                      └──────────────────┘
```

## Why medallion (bronze/silver/gold)

Because your sources **will** change schema without warning, and when a number looks
wrong six months from now you need to prove whether the source changed or your code did.
Immutable bronze gives you that proof. This is the single most defensible architectural
decision in the project and you should be able to articulate it.

## Layering rules — enforced

```
routers/       HTTP only. Pydantic in, Pydantic out. No logic. No SQL.
services/      Business logic. Orchestrates repositories. NO SQL.
repositories/  ALL SQL. Returns domain objects, not ORM rows.
models/        SQLAlchemy ORM + Pydantic schemas (kept separate).
ml/            Scoring, SHAP, forecasting. Pure functions where possible.
core/          Logging, cache, config, exceptions.
```

A router that imports SQLAlchemy is a bug. A service that writes `SELECT` is a bug.

## Pipeline layering

```
connectors/    Fetch only. Returns RawPayload. Knows nothing about the schema.
schemas/       Pandera contracts, versioned, one per source.
transforms/    bronze→silver→gold. Pure, testable.
geography/     LGD resolution engine. Used by every transform.
flows/         Prefect orchestration. Thin — just wiring.
```

## Concurrency and politeness

- `httpx.AsyncClient` with a bounded semaphore (`HTTP_MAX_CONCURRENCY=4`)
- Token-bucket rate limiter at `HTTP_REQUESTS_PER_SECOND=2`
- Descriptive `User-Agent` identifying the project
- Schedule heavy sweeps during Indian off-peak hours

data.gov.in publishes no numeric rate limit, which means assume nothing and be
conservative. Getting blocked costs days.

## Caching strategy

| Layer | Contents | TTL | Invalidated by |
|---|---|---|---|
| Bronze (disk) | Raw responses, verbatim | Permanent | Never |
| Redis: query | Expensive aggregations | 24h | Successful gold load |
| Redis: score | Scores + SHAP values | Until recompute | Weight-version change |
| Frontend (TanStack) | API responses | 5 min SWR | User action |

**Cache keys must include both `load_version` and `weight_version`.** Omitting either
produces stale scores that look correct — a genuinely painful bug to diagnose.

## Graceful degradation

The LLM narrative layer is **strictly optional**. If Ollama is unavailable, the
dashboard renders the raw SHAP decomposition table and everything still works. Build it
this way from the start: it is both good engineering and proof that the numbers stand
on their own.

## What is deliberately NOT in this architecture

- **No Airflow.** Eleven scheduled jobs. Prefect or GitHub Actions cron is correct.
- **No Kafka / streaming.** Nothing here is real-time. Monthly and daily batch.
- **No microservices.** One API service. Splitting this would be cargo-culting.
- **No deep learning.** See CLAUDE.md §3.
- **No auth** (initially). Public read-only tool. Add JWT only if saved views ship.
