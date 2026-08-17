# Bharat Expansion Intelligence

District-level business-location intelligence for India, built entirely on free Government of India open data — a working, tested, end-to-end system, not a prototype.

## What it answers

> "Which Indian districts should we shortlist for our next plant / warehouse / branch network — and why exactly does district X outrank district Y? And what would district Y have to change to catch up?"

561 nationally-ranked districts (778 scored in total — the rest are shown transparently as below the confidence floor for a trustworthy rank, never hidden or silently ranked anyway). A 0–100 Opportunity Score that decomposes exactly into its inputs, a real SHAP explanation layer, Monte Carlo rank-confidence intervals, and a counterfactual "what would it take to move up N ranks" engine.

## What's real, with numbers

- **3,599,249** MCA company records loaded nationally across all 36 states/UTs, **zero duplicate CINs** (idempotency verified at full scale)
- **92.39%** Udyam (MSME) district resolution nationally; Census 2011 population and literacy/worker data loaded
- A six-step, self-learning geography resolver (exact → alias → PIN → address-substring → fuzzy-match → quarantine) that disambiguates identically-named districts across states correctly — never joins on name strings, only LGD codes
- An Opportunity Score engine: winsorised, entropy-weighted (data-driven, not hand-picked), pillar-aggregated, with a **1,000-trial Monte Carlo rank-sensitivity analysis** and a confidence-gated ranking floor — a real methodology bug (thin-data districts artificially claiming rank #1) was found and fixed during development, not glossed over
- A real **LightGBM + SHAP TreeExplainer** explanation layer — and its cross-validated predictive quality (R²=0.11, genuinely weak) is reported honestly in the UI itself rather than hidden behind a confident-looking chart
- A **counterfactual engine**: binary-searches the cheapest realistic changes to reach a target rank, rejecting anything outside the observed national range as not actionable advice
- District comparison and nearest-neighbour similarity (cosine similarity on the normalised indicator vector)
- **83 backend tests + 6 frontend tests**, several of which caught real bugs during development (a SQL-injection-resistance check, a tied-indicator misreported as a lead, a CORS config gap that silently broke every POST endpoint) — not written after the fact to pad a number

## Honest scope

Only **7 of 22** documented KPIs are computable from data sources actually verified and loaded (Business Formation Rate, Formation Momentum, Capital Intensity, MSME Density, Manufacturing Share, Population Scale, Literacy Rate). GST, DPIIT, ASI, PLFS, RBI, and CEA power-supply data were evaluated in Phase 0 and are documented as not-yet-loaded — the infrastructure pillar is genuinely absent from every score, not faked with a placeholder. This is a stated, deliberate scope decision, tracked in `STATUS.md`, not an oversight.

## Stack

Python 3.14 · FastAPI · PostgreSQL 16 (`pg_trgm`) · SQLAlchemy/Alembic · Pandera · scikit-learn · LightGBM · SHAP · Next.js 16 (App Router, Server Components) · TypeScript · Tailwind · Recharts · ECharts · pytest · Vitest · Docker

All free and open source, and all data under GODL-India (see `ATTRIBUTIONS.md`).

## Quick start

```bash
cp .env.example .env
# Register free at https://www.data.gov.in -> generate an API key
# -> paste into .env as DATA_GOV_IN_API_KEY

docker compose up -d postgres redis
cd backend && pip install -e ".[dev]"
alembic upgrade head
pytest                              # 83 tests

cd ../frontend && npm install
npm test                            # 6 tests
npm run dev                         # http://localhost:3000
```

The rankings and scoring tables are populated by running the pipeline connectors and `python -m app.ml.scoring` — see `STATUS.md` for the exact commands used to build the live dataset.

## Where to look first

1. `/rankings` — the national ranking, with confidence bands and rank confidence intervals
2. Any district's scorecard (e.g. `/districts/77`) — the full score decomposition, the SHAP explanation, and the interactive "what would it take?" counterfactual panel
3. `/compare` — pick 2–5 districts for an aligned, indicator-by-indicator diff

## Documentation

`STATUS.md` is the living, honest build log — what's real, what deviated from plan and why, every bug found and how it was fixed, with real numbers throughout. `CLAUDE.md` is the project constitution (hard rules on data integrity, geography joins, secrets, and architecture).

| Doc | Contents |
|---|---|
| `STATUS.md` | **Start here** — current state, full build history, honest gaps |
| `CLAUDE.md` | Project constitution and hard rules |
| `docs/RESOURCE-REGISTRY.md` | Verified data source resource IDs |
| `docs/01-DATA-SOURCES.md` | Source registry, auth, licences, limitations |
| `docs/02-ARCHITECTURE.md` | System architecture |
| `docs/03-DATA-MODEL.md` | Star schema and DDL |
| `docs/04-ETL-PIPELINE.md` | Connectors, medallion layers, validation |
| `docs/05-KPI-DEFINITIONS.md` | Every KPI formula |
| `docs/06-SCORING-METHODOLOGY.md` | Normalisation, weighting, sensitivity, SHAP |
| `docs/07-API-SPEC.md` | FastAPI endpoints |
| `docs/08-FRONTEND-SPEC.md` | Pages and components |
| `docs/09-DATA-QUALITY.md` | Validation gates and failure modes |
| `docs/10-DEPLOYMENT.md` | Docker, CI, free hosting |
| `docs/11-ROADMAP.md` | Phased build plan |

## Data licence

All data is Government of India open data under GODL-India, which permits commercial and non-commercial reuse with attribution. See `ATTRIBUTIONS.md`.

This project is not endorsed by, and makes no claim of endorsement by, the Government of India.
