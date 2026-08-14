# 11 — Roadmap

Sequential. One phase at a time. Do not start a phase before its predecessor's definition
of done is met.

---

## Phase 0 — Resource discovery (BLOCKING)

Nothing else can start. See `docs/RESOURCE-REGISTRY.md`.

- [ ] Register on data.gov.in, generate API key
- [ ] `.env` created, `.gitignore` updated **before first commit**
- [ ] Discover and verify resource IDs for MCA (all RoCs), Udyam, DPIIT, LGD, CEA, Census
- [ ] Record actual field names (they drift from catalog descriptions)
- [ ] Record baseline row counts
- [ ] Commit one sample response per source to `data/reference/samples/`
- [ ] Generate `backend/pipeline/connectors/resources.py`
- [ ] **Written report of anything that differed from expectations**

**Done when:** every source is `VERIFIED` or `NOT_FOUND` with a recorded fallback.

---

## Phase 1 — Geography spine + one KPI end to end

The highest-risk work. Do it first, while you have the most patience for it.

- [ ] Postgres up, Alembic initialised, `meta`/`silver`/`gold` schemas created
- [ ] LGD connector → `dim_geography` (SCD-2), all states + districts
- [ ] `geography_alias` seeded from `data/reference/geography_alias_seed.csv`
- [ ] Six-step resolver implemented and unit-tested
- [ ] `dim_date` populated (calendar + Indian fiscal year)
- [ ] MCA connector — **one RoC only**, checkpointed, landing in bronze
- [ ] Pandera schema for MCA; silver transform; PIN→district resolution
- [ ] **Business Formation Rate computed for one state, end to end**

**Done when:** you have a BFR number you would stake your reputation on, and a measured
geography resolution rate.

Do not move on if resolution is below 90%. Fix the resolver.

---

## Phase 2 — Full ingestion

- [ ] MCA sweep across all RoCs (~3.67M rows), checkpointed and resumable
- [ ] Udyam connector + snapshot-diff logic
- [ ] DPIIT connector
- [ ] CEA Power connector
- [ ] Census 2011 load (tagged `vintage = 2011`)
- [ ] RBI Handbook manual load from committed XLSX
- [ ] eSankhyiki ASI + PLFS load
- [ ] Open Budgets CKAN connector
- [ ] GST PDF parser (with quarantine-on-failure)
- [ ] All five validation gates wired
- [ ] `meta.ingestion_run` populated on every load
- [ ] Idempotency verified — run twice, assert no duplicates

**Done when:** `fact_district_month`, `fact_state_month`, `fact_state_annual` are
populated and post-load assertions pass.

---

## Phase 3 — KPIs and first score

- [ ] All 22 KPIs implemented per `05-KPI-DEFINITIONS.md`
- [ ] **Direction unit tests** — one wrong sign inverts everything
- [ ] Winsorisation + robust min-max normalisation
- [ ] Pillar aggregation
- [ ] Entropy weighting
- [ ] Profile weighting from `dim_profile`
- [ ] First Opportunity Score for all districts
- [ ] `confidence_score` computed
- [ ] **THE CHECKPOINT: inspect the top 10**

**Done when:** the top 10 is not just the 10 largest metros, and you can explain every
entry in it.

If it is just metros, stop and fix normalisation. See `06-SCORING-METHODOLOGY.md` §3.

---

## Phase 4 — Explanation engine

This is where the project becomes the product.

- [ ] LightGBM model trained on the indicator vector
- [ ] SHAP TreeExplainer, contributions stored in `fact_score_contribution`
- [ ] Monte Carlo sensitivity → `rank_ci_low` / `rank_ci_high`
- [ ] Counterfactual lever computation
- [ ] Nearest-comparable districts (cosine similarity)
- [ ] Spearman correlation matrix + VIF report — drop redundant indicators
- [ ] `weight_version` persistence; verify historical score reproducibility

**Done when:** you can explain any district's score as a decomposition, and reproduce
last month's score exactly.

---

## Phase 5 — API

- [ ] FastAPI scaffold with router/service/repository layering enforced
- [ ] All endpoints in `07-API-SPEC.md`
- [ ] Redis caching with `weight_version` + `load_version` in keys
- [ ] `/meta/sources` and `/meta/quality` (public)
- [ ] OpenAPI schema clean
- [ ] Integration tests

---

## Phase 6 — Frontend

- [ ] Next.js + TS + Tailwind scaffold (App Router)
- [ ] Typed client generated from OpenAPI
- [ ] **ShapWaterfall component first** — it is the hero
- [ ] District Scorecard page
- [ ] Ranking Explorer with live weight sliders
- [ ] National Overview with choropleth
- [ ] Head-to-Head compare
- [ ] **Data & Sources page (public)**
- [ ] Confidence badges, rank intervals, vintage tags, inherited badges everywhere
- [ ] Accessibility pass — no colour-only encoding

---

## Phase 7 — Forecasting and clustering

- [ ] SARIMA on district formation with fiscal seasonality
- [ ] **MASE vs seasonal-naive reported on every forecast**
- [ ] STL decomposition
- [ ] PELT changepoint detection
- [ ] HDBSCAN + K-means district archetypes
- [ ] Moran's I spatial autocorrelation
- [ ] Trends page

---

## Phase 8 — Optional AI layer

Build last. The app must already work without it.

- [ ] Ollama integration, config-gated behind `LLM_ENABLED`
- [ ] Narrative generation from SHAP output — **computed numbers only, never raw data**
- [ ] Every figure in a narrative traceable to a KPI
- [ ] NL query: parameter extraction → allowlist validation → parameterised SQL
- [ ] **Never LLM-generated raw SQL**
- [ ] Graceful degradation verified: set `LLM_ENABLED=false`, confirm everything still works

---

## Phase 9 — Deploy

- [ ] Docker Compose working locally
- [ ] Neon/Supabase provisioned, migrations applied
- [ ] API on Render/Railway/Fly
- [ ] Frontend on Vercel/Netlify
- [ ] GitHub Actions monthly pipeline with secrets configured
- [ ] `ATTRIBUTIONS.md` complete, in-product attribution rendering
- [ ] README with live demo link and a screenshot of the SHAP waterfall

---

## Explicitly out of scope for v1

Do not build these without a conversation:

- VAHAN vehicle registrations (Tier B, no official API, not load-bearing)
- Industrial cluster discovery via HDBSCAN on geocoded companies — **excellent
  follow-on**, shares ~70% of this infrastructure, but it is a separate phase
- District-level bank credit (source unverified at district granularity)
- Any Tier C source from `01-DATA-SOURCES.md`
- User accounts and saved views
- Airflow

---

## Reduced scope fallback

If time runs short, the project still works end to end at reduced coverage:

- 5 states instead of 36
- 8 indicators instead of 22
- 1 profile instead of 5
- No forecasting, no LLM

**The architecture does not require all 750 districts to be a complete system.** A
working narrow version beats a broken wide one, and the reduction is a legitimate
engineering decision rather than a failure — say so if asked.
