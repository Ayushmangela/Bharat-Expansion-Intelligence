# CLAUDE.md — Bharat Expansion Intelligence

You are building a district-level business location intelligence platform for India, using only free Government of India open data.

Read this file first. It is the constitution. Everything in `docs/` elaborates on it but never overrides it.

---

## 1. What this project is

A BI platform that ranks all 750+ Indian districts for business expansion suitability, and — more importantly — **explains why** each district ranks where it does, in named, sourced, quantified terms.

**The score is not the product. The explanation is the product.** A number without a decomposition is astrology. Every score must decompose into individually inspectable, source-traceable contributions.

If you are ever choosing between "add another indicator" and "make the existing explanation clearer," choose the explanation.

---

## 2. Hard rules — never violate these

### 2.1 Data integrity

1. **Never fabricate data.** No synthetic rows, no `np.random`, no placeholder numbers that look real, no "sample data for demo purposes" that could be mistaken for real. If a source is unavailable, the pipeline fails loudly and the UI shows a gap. Test fixtures live in `tests/fixtures/` and must be obviously fake (e.g. state `"TESTLAND"`).
2. **Never invent an API endpoint or resource ID.** If you do not have a verified resource ID, stop and run the discovery task in `docs/RESOURCE-REGISTRY.md`. Do not guess UUIDs.
3. **Never impute silently.** Imputation is allowed only with an explicit flag column recording that the value was imputed and how.
4. **Never delete outliers.** Flag them in `quality_flags`. Deleting inconvenient data produces a model that lies.
5. **Never present a number without its vintage.** Census 2011 data is labelled 2011. ASI data is labelled with its survey year.

### 2.2 Geography — the LGD-first rule

6. **LGD codes are the only join key for geography.** Never join on state name or district name strings.
7. **Nothing enters the `gold` schema with an unresolved geography.** Unresolvable records go to `silver.geography_quarantine` for review.
8. Always disambiguate district by `(state_code, district_code)`. District names are not unique across states — `Aurangabad` exists in both Maharashtra and Bihar.

### 2.3 Secrets

9. **`.env` is in `.gitignore` before the first commit, not after.** Ship `.env.example` with placeholders.
10. **Never commit an API key**, not even in a comment, notebook output, test file, or commit message. If one is ever committed, regenerate it immediately — git history is permanent and scrapers find committed keys within hours.
11. No secrets in logs. Redact `api-key` from any logged URL.

### 2.4 Architecture discipline

12. **Bronze is immutable.** Raw responses are written verbatim, partitioned by source and ingest date, and never modified or deleted. This is your audit trail — when a number looks wrong in six months, bronze proves whether the source changed or your code did.
13. **All SQL lives in `repositories/`.** Routers never touch the database. Services never write SQL.
14. **Every fact table declares its grain and never mixes grains.** See `docs/03-DATA-MODEL.md`.
15. **Every load is idempotent.** Re-running yesterday's job must not double-count. Enforce with natural keys and upserts.
16. **Every load is versioned.** Every fact row carries a `load_id` foreign key to `meta.ingestion_run`.

### 2.5 Scraping and politeness

17. **Do not scrape when an official API exists.** Use the data.gov.in API for anything available there.
18. Where no API exists (GST PDFs), be polite: conservative rate limits, descriptive User-Agent, backoff on failure. Government servers are not adversaries.
19. **Never build vehicle-registration lookup by number plate.** It returns personal data, which is outside the GODL licence. Aggregate dashboard data only.

### 2.6 Licence compliance

20. All data is GODL-India licensed and requires attribution: provider, source, licence, URL. `ATTRIBUTIONS.md` and the in-product source panel are features, not chores.
21. Never imply Government of India endorsement.

---

## 3. Tech stack — do not substitute without asking

| Layer | Choice |
|---|---|
| Language | Python 3.11+ |
| API | FastAPI + Uvicorn |
| DB | PostgreSQL 16 (`pg_trgm` required) |
| ORM/migrations | SQLAlchemy 2 + Alembic |
| Dataframes | pandas; Polars for the MCA sweep only |
| Validation | Pandera (data), Pydantic (API contracts) |
| ML | scikit-learn, LightGBM, SHAP, HDBSCAN |
| Stats | NumPy, SciPy, statsmodels, ruptures |
| Cache | Redis |
| HTTP | httpx (async) |
| Orchestration | Prefect (or GitHub Actions cron) — **not Airflow** |
| Frontend | Next.js 14+ (App Router) + TypeScript + Tailwind |
| Charts | Recharts (standard), Apache ECharts (map, large scatter) |
| State | TanStack Query (server), Zustand (UI) |
| Containers | Docker Compose |

**No Airflow.** Eleven scheduled jobs do not need a scheduler cluster. If asked to add it, push back and explain the trade-off.

**No deep learning.** ~750 districts × ~60 months would overfit, and it would destroy explainability, which is the entire product premise. Gradient boosting + SHAP is the correct tool for tabular data at this scale.

---

## 4. Repository layout

```
bharat-expansion-intelligence/
├── CLAUDE.md                    ← you are here
├── README.md
├── ATTRIBUTIONS.md
├── .env.example
├── docker-compose.yml
├── pyproject.toml
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py            settings via pydantic-settings
│   │   ├── routers/             thin HTTP layer only
│   │   ├── services/            business logic, no SQL
│   │   ├── repositories/        ALL SQL lives here
│   │   ├── models/              SQLAlchemy ORM + Pydantic schemas
│   │   ├── ml/                  scoring, SHAP, forecasting
│   │   └── core/                logging, cache, exceptions
│   ├── pipeline/
│   │   ├── connectors/          one per source, common base class
│   │   ├── schemas/             Pandera contracts, versioned
│   │   ├── transforms/          bronze→silver→gold
│   │   ├── geography/           LGD resolution engine
│   │   └── flows/               Prefect flows
│   ├── migrations/              Alembic
│   └── tests/
├── frontend/
│   ├── app/                     Next.js App Router routes
│   └── src/
│       ├── components/
│       ├── api/                 typed client
│       └── lib/
├── data/
│   ├── bronze/                  gitignored, immutable
│   └── reference/               committed: alias tables, LGD snapshots
└── docs/
```

---

## 5. Documentation index

Read the relevant doc before implementing that layer. Do not improvise designs that are already specified.

| Doc | Read before |
|---|---|
| `docs/RESOURCE-REGISTRY.md` | **Any data work. This is Phase 0 and it blocks everything.** |
| `docs/01-DATA-SOURCES.md` | Writing any connector |
| `docs/02-ARCHITECTURE.md` | Any structural decision |
| `docs/03-DATA-MODEL.md` | Any migration or schema change |
| `docs/04-ETL-PIPELINE.md` | Any connector or transform |
| `docs/05-KPI-DEFINITIONS.md` | Any metric computation |
| `docs/06-SCORING-METHODOLOGY.md` | The scoring engine |
| `docs/07-API-SPEC.md` | Any endpoint |
| `docs/08-FRONTEND-SPEC.md` | Any UI work |
| `docs/09-DATA-QUALITY.md` | Any validation logic |
| `docs/10-DEPLOYMENT.md` | Docker, CI, hosting |
| `docs/11-ROADMAP.md` | Deciding what to build next |

---

## 6. How to work with me (the human)

- **One deliverable at a time.** Do not build three phases at once. Finish, verify, report, then ask what's next.
- **Do not pad estimates.** If something takes an hour, say an hour.
- **Be critically honest.** If a design in these docs is wrong, say so and explain why. Do not implement something you believe is broken just because it is written down. These docs are a starting position, not scripture.
- **Report what actually happened**, including failures, resolution rates below target, and rows quarantined. Do not report success when a step partially failed.
- **Ask before scope changes.** Adding a source, changing the stack, or altering the star schema needs a conversation first.

---

## 7. Definition of done for any task

A task is done when:

1. It runs end to end without manual intervention
2. Tests pass (`pytest` backend, `vitest` frontend)
   - Note: with Next.js, `vitest` covers components/hooks; use `playwright` for route-level/e2e checks if added later.
3. `ruff` and `mypy` are clean
4. New data paths have a Pandera schema
5. New facts have a `load_id` and `quality_flags`
6. Any new source is added to `ATTRIBUTIONS.md` and `dim_source`
7. The reported outcome includes actual numbers (rows loaded, resolution rate, failures)

---

## 8. The single most important early checkpoint

At the end of Phase 1, you will produce a first district ranking.

**Look at the top 10. If it is just the 10 largest metros, the normalisation is broken.** Mumbai, Bengaluru and Delhi have company counts orders of magnitude above the median — partly real agglomeration, partly registered-office artefacts (companies register in metros while operating elsewhere).

Do not proceed to build features on top of a broken ranking. Fix winsorisation and per-capita normalisation first. See `docs/06-SCORING-METHODOLOGY.md` §3.

---

## 9. Known data limitations to surface, never hide

- MCA company master is a **periodic snapshot**, not a live feed. Valid for historical/structural analysis; invalid for live due diligence on a named company.
- Registered office ≠ place of operation. Metro company counts are inflated. Flag districts where company count vastly exceeds ASI factory count.
- Census is **2011**. The 2021 Census was not conducted on schedule. Use for structure and ratios; use projections for population levels.
- ASI lags 2–3 years. PLFS is annual.
- Udyam is **cumulative-to-date**, not a flow. Monthly registration rates must be derived by snapshot diffing.
- State-level indicators inherited by districts must be visibly flagged as inherited.
- GST state-wise splits are inconsistent in early years.

Every one of these belongs in the public data-quality page, not buried in a README.
