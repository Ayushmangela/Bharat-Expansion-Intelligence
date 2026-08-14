# Bharat Expansion Intelligence

District-level business location intelligence for India, built entirely on free Government of India open data.

## What it answers

> "Which Indian districts should we shortlist for our next plant / warehouse / branch network — and why exactly does district X outrank district Y?"

750+ districts. 10 verified free government sources. An explainable 0–100 Opportunity Score with SHAP decomposition, Monte Carlo rank confidence intervals, and a counterfactual "what would have to change" analysis.

## Why it exists

Every input that should drive an Indian expansion decision — business formation, MSME ecosystem, industrial base, labour availability, power reliability, fiscal capacity — exists in free public data. None of it is joined together. It sits across seven portals in four formats at three geographic grains with no common key.

This project does the integration.

## Status

Pre-Phase 0. See `docs/11-ROADMAP.md`.

## Quick start

```bash
cp .env.example .env
# Register at https://www.data.gov.in, generate an API key,
# paste it into .env as DATA_GOV_IN_API_KEY

docker compose up -d postgres redis
cd backend && pip install -e ".[dev]"
alembic upgrade head

# Phase 0: discover and record resource IDs — blocks everything else
python -m pipeline.discovery.find_resources
```

## Documentation

Start with `CLAUDE.md`, then `docs/11-ROADMAP.md`.

| Doc | Contents |
|---|---|
| `CLAUDE.md` | Project constitution and hard rules |
| `docs/RESOURCE-REGISTRY.md` | Phase 0 — verified resource IDs |
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

## Stack

Python 3.11 · FastAPI · PostgreSQL 16 · Prefect · LightGBM · SHAP · Next.js · TypeScript · Tailwind · ECharts · Docker

All free and open source.
