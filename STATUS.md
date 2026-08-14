# STATUS — read this before doing anything else

This file is a handoff note for whoever (human or AI) picks up this project next. It
tells you what state the repo is actually in, as opposed to what the docs originally
planned. `CLAUDE.md` is still the constitution — read it first. This file just tells
you where things stand against `docs/11-ROADMAP.md` right now.

**Keep this file up to date.** Whenever a phase completes, a source status changes, or
a design decision deviates from the docs, update this file in the same session. Stale
status here is worse than no status file at all.

---

## Where things stand

| Phase | Status |
|---|---|
| Phase 0 — Resource discovery | ✅ Done, with 2 known gaps (see below) |
| Phase 1 — Geography spine + one KPI | ✅ Core checkpoint met — see below for what's real vs. simplified |
| Phase 2+ | Not started |

---

## What actually happened, in order

1. **Repo restructuring.** The project originally landed as a `BEI/` subfolder full of
   flat docs. Moved to match the layout `CLAUDE.md` §4 actually specifies: numbered
   docs under `docs/`, `CLAUDE.md`/`README.md`/`ATTRIBUTIONS.md`/`.env.example` at
   root.

2. **Frontend stack changed to Next.js.** The original docs specified React 18 + Vite.
   The user explicitly asked for Next.js instead. Updated `CLAUDE.md`, `README.md`,
   `docs/02-ARCHITECTURE.md`, `docs/08-FRONTEND-SPEC.md`, `docs/10-DEPLOYMENT.md`,
   `docs/11-ROADMAP.md` accordingly. **If you see "React + Vite" anywhere else in the
   docs, it's stale — treat Next.js as authoritative.**

3. **Secrets scaffolding.** `.gitignore` created (covers `.env`, `data/bronze/`,
   `node_modules/`, Python caches, `.venv/`). `.env` created locally from
   `.env.example` and is **not** tracked. The user registered a real
   `DATA_GOV_IN_API_KEY` on data.gov.in and it is verified working (confirmed via a
   live curl against a known resource, HTTP 200, non-empty records, not the
   rate-limited sample key).

   **How the user found the API key**, since it wasn't obvious: log into
   `data.gov.in` itself (not the Meri Pehchaan SSO dashboard, which looks similar but
   has no API key option). Then open any dataset page → **API tab** → **"Generate API
   Key"** button. The key is account-wide, generated from any dataset's page.

4. **Repository file tree scaffolded** per `CLAUDE.md` §4: `backend/app/*`,
   `backend/pipeline/*`, `backend/migrations/`, `backend/tests/`, `frontend/app/`,
   `frontend/src/*`, `data/bronze/`, `data/reference/samples/`. Root `pyproject.toml`
   and `docker-compose.yml` exist as stubs — **not yet filled in as of the end of
   Phase 0** (Phase 1 fills these in).

5. **Phase 0 resource discovery completed.** Full detail in
   `docs/RESOURCE-REGISTRY.md` — that is the source of truth, this is just a summary:

   | Source | Status | Resource ID(s) |
   |---|---|---|
   | LGD (states/districts/sub-districts/local bodies/pincodes) | ✅ VERIFIED, all 5 | see `backend/pipeline/connectors/resources.py` |
   | Udyam (total + services) | ✅ VERIFIED, both | carries genuine LGD `lg_dt_code` — direct join, no alias needed |
   | MCA Company Master | ✅ VERIFIED, but **not as documented** | now ONE unified resource (was expected to be ~25 per-RoC resources); 3,674,314 rows, matches expectation |
   | Census 2011 population | ✅ VERIFIED | 707 rows; its own state/district codes are **not LGD codes** — must resolve via `geography_alias` |
   | Census 2011 literacy / worker classification | ⚠️ PENDING | no all-India district-wise resource found; only state-level and single-state results turned up. Needs a follow-up discovery session, possibly against RGI's own tables instead of data.gov.in's catalog |
   | DPIIT startups | ❌ NOT_FOUND | no `api.data.gov.in` resource exists at all; it's an external webservice at startupindia.gov.in with no documented public API found |
   | CEA Power Supply | ❌ BROKEN | publishes a new resource per month with the month baked into column names; nothing newer than 2023 found on the portal. Fallback: scrape cea.nic.in directly, or drop for v1 (roadmap's reduced-scope fallback explicitly allows this) |

   10 sample responses saved to `data/reference/samples/`.

   **Decision made with the user:** proceed to Phase 1 using LGD + Udyam + MCA +
   Census population. CEA, DPIIT, and Census literacy/worker-classification are
   deferred, not silently dropped — they need a real follow-up discovery pass, not a
   guess.

6. **Phase 1 built end-to-end for one state (Goa).** Full detail is in the code
   itself (`backend/pipeline/`) — this is the summary of what's real and what
   deviated from `docs/03-DATA-MODEL.md` / `docs/04-ETL-PIPELINE.md`:

   - **Postgres 16 running locally via Docker** on host port **5433**, not 5432 —
     an unrelated container (`cirp_postgres`, another project) already held 5432.
     `docker-compose.yml` and `.env` both reflect 5433.
   - **Alembic set up**, 4 migrations applied. Schema is a **Phase-1-scoped
     subset** of the documented DDL: `meta.source`, `meta.ingestion_run`,
     `meta.quality_event`, `gold.dim_geography`, `gold.dim_date`,
     `gold.dim_industry`, `gold.dim_company_status`, `gold.fact_company`,
     `silver.geography_alias`, `silver.geography_quarantine`. Deliberately
     excluded: `dim_profile`, `dim_source`, `fact_district_month`,
     `fact_state_month`, `fact_state_annual`, `fact_opportunity_score`,
     `fact_score_contribution`, `meta.weight_version` — Phase 2/3 concerns,
     nothing to populate them yet.
   - **`gold.dim_geography` got two extra columns** not in the original DDL:
     `state_census2011_code`, `district_census2011_code` (from LGD). This was
     meant to be the crosswalk key to Census data, but **turned out not to
     work** — see the census code-mismatch finding below. The columns are
     harmless and stay populated from LGD, but don't assume they crosswalk to
     every census-labeled field in other sources.
   - **Three new tables not in the original DDL**, all in `silver`, all
     reference/crosswalk tables rather than star-schema objects:
     `lgd_pincode_lookup`, `lgd_subdistrict_lookup`, `pincode_district_lookup`,
     plus `census_population_district` (added via a later migration). These
     exist because the documented resolver design (LGD PIN join alone) turned
     out to be insufficient — see the resolution-rate story below.
   - **LGD loaded**: 36 states, 785 districts (not ~750 — LGD is a living
     directory, districts get added), 7,151 sub-districts, 7,411 local-body PIN
     rows, all SCD-2 `valid_from`-dated and idempotent (re-running the loader
     produces identical counts, verified).
   - **`dim_date` populated**: 216 months, 2010–2027, calendar + Indian fiscal
     year (Apr–Mar).
   - **Geography resolver**: implemented all six steps from
     `docs/04-ETL-PIPELINE.md`, plus two steps the docs didn't anticipate
     (below). Learns fuzzy matches into `geography_alias` automatically
     (Step 5's stated behavior).
   - **MCA loaded for Goa** (not "one RoC" as the roadmap says — MCA is no
     longer split by RoC, see Phase 0 notes — filtered by `CompanyStateCode`
     instead, which serves "one state end to end" more directly): 15,684
     companies fetched and landed in bronze, checkpointed/resumable.
   - **Census 2011 population loaded**: 640 districts (matches the known
     Census 2011 district count).
   - **Business Formation Rate computed for Goa, both districts, every month
     with data** — real, non-null, directionally sane numbers (e.g. North Goa
     May 2026: 83 new incorporations / 818,008 pop = 10.15 per 100k; South Goa
     same month: 34 / 640,537 = 5.31 per 100k — North Goa is the more
     commercial/urbanized district, consistent with the higher rate).
     **This is a proxy, not the KPI as formally defined**: the formula calls
     for *working-age* population, but Census 2011 literacy/worker-
     classification tables were never found in Phase 0 (still `PENDING`).
     Total population 2011 is used instead. Labelled as a proxy in the output,
     not silently substituted.
   - **Final geography resolution rate: 95.57%** (14,989 / 15,684 resolved),
     above the roadmap's explicit ≥90% gate and above the ≥95% named / ≥85%
     PIN-derived targets from `docs/04-ETL-PIPELINE.md`. This did NOT happen
     on the first pass — see below.

7. **The resolution-rate story, since it's the most important thing that
   happened in Phase 1.** First pass, using only what the docs specified
   (state exact/alias match, district exact/alias match, LGD PIN join,
   pg_trgm fuzzy): **69.35%**. Investigated the failures directly (real MCA
   addresses in `silver.geography_quarantine`) rather than lowering the bar:

   - Most failures were real addresses like "PANAJI,Goa,India-403001" or
     "VASCO-DA-GAMA,Goa" — **city/taluka names, not district names**, and
     Goa's LGD districts are named "North Goa"/"South Goa", which never
     appear verbatim in an address. Added **Step 4c**: match a known
     *sub-district* (taluka) name in the address text, then map up to its
     parent district via LGD's own sub-district table. → **76.03%**.
   - Remaining failures were mostly city names like "Panaji" and
     "Vasco-da-Gama" that are neither district nor taluka names — but they
     had valid PIN codes. The documented LGD-PIN-join path only resolves
     PINs whose local body is *itself* a District Panchayat entity (~60% of
     PINs). Discovered and loaded a much better source: the **Dept of Posts'
     "All India Pincode Directory"** (`5c2f62fe-5afa-4119-a499-fec9d604d5bd`,
     not in the original registry — added it), which has a direct
     `pincode → district` text field. → **95.57%**.

   This is the concrete version of what `docs/11-ROADMAP.md` warned about
   ("do it first while you have the most patience") — the documented design
   was a reasonable starting point but needed two real iterations against
   real data before it worked. Both fixes are now permanent parts of the
   resolver, not one-off patches for Goa.

8. **Two real bugs found and fixed along the way, not just design gaps:**
   - **No politeness delay on successful API pages.** `DataGovInClient` only
     slept between *retries*, never between successful sequential pages. This
     is why a routine LGD + Goa-MCA load tripped data.gov.in's rate limiter
     mid-session (confirmed via curl: 429 "Rate limit exceeded" on every
     resource, recovered after ~20s — a burst limit, not a daily quota, but
     still a real politeness violation of CLAUDE.md rule 18). Fixed in both
     `datagovin_client.py` and `mca.py`'s manual pagination loop.
     `HTTP_REQUESTS_PER_SECOND` in `.env` was also lowered from 2 to 0.7
     afterward, since 2 req/s still weren't enough headroom.
   - **Bronze parquet write crashed on mixed-type columns.** Census's
     `population___total___2011` field mixes numeric values and the literal
     string `"NA"` in the same column; `pd.DataFrame.from_records(...).to_parquet()`
     let pyarrow infer types and it choked. Fixed by casting every column to
     string before writing bronze (`base.py`) — bronze is supposed to be raw
     verbatim storage anyway, typing belongs in the silver transform, not here.

9. **A second confirmed instance of the "schema block lies about record
   keys" pattern first seen in LGD local bodies (Phase 0).** The Census
   population resource's `field` metadata advertises pretty names like
   `"State Code"`, but actual records use snake_case keys (`state_code`).
   Cost an entire debugging cycle (0 rows loaded on first attempt) before
   being caught. **Lesson for future connectors: always print one raw record
   and read keys off it directly — never trust the `field` block's naming.**

10. **Census code crosswalk assumption was wrong — found and fixed.** The
    original plan (baked into the `dim_geography` migration) was to crosswalk
    Census population data via `state_census2011_code`/`district_census2011_code`
    columns carried on both LGD and the Census resource. **These turned out to
    be two different numbering schemes that happen to share a column name.**
    Confirmed directly: LGD's `district_census2011_code` for Alappuzha is
    `598`; the population resource's own code for Alappuzha is `11`. Fixed
    `compute_bfr.py` to join on **normalised district name, scoped by state**,
    instead — which worked cleanly for Goa. This is not yet proven to
    generalize to ambiguous-name districts nationally (Aurangabad, Bilaspur,
    etc.) — that's exactly what the resolver's alias/fuzzy machinery exists
    for, but it hasn't been run against the full Census population table yet,
    only used ad hoc in `compute_bfr.py`. **Flagging as a Phase 2 TODO**:
    route the Census population join through `GeographyResolver` properly
    instead of the direct name-dict lookup used for the Goa checkpoint.

11. **Idempotency bug found and fixed — this one is important.** After the
    Phase 1 checkpoint looked done, ran the roadmap's own required check
    ("run twice, assert no duplicates" — `docs/11-ROADMAP.md` Phase 2 DoD,
    pulled forward as a sanity check). It failed: `gold.dim_geography`
    grew by 36 rows (an exact state-count multiple) on every re-run.
    **Root cause: Postgres treats NULL as distinct from NULL in UNIQUE
    constraints.** State-grain rows carry `lgd_district_code = NULL`, so
    `ON CONFLICT (lgd_state_code, lgd_district_code, valid_from)` never
    matched them against each other — every re-run silently inserted 36 more
    "duplicate" states. District rows were never affected (their
    `lgd_district_code` is always non-null). The exact same pattern had
    already independently corrupted `silver.geography_alias` (7 duplicated
    state-only aliases, e.g. `Orissa -> Odisha` with `observed_district = NULL`).
    **Fixed**: migration `d77835febaad` deduplicates existing damage, drops
    both NULL-unsafe UNIQUE constraints, and replaces them with
    `COALESCE(..., sentinel)`-based unique indexes; `lgd.py`, `seed_aliases.py`,
    and the resolver's `_learn_alias` all updated to target the new indexes.
    **Verified idempotent by running both loaders twice in a row and
    confirming identical row counts both times** (36 states / 785 districts /
    11 aliases, unchanged). This is exactly the kind of thing rule 15 exists
    to catch, and it would have silently corrupted every downstream count
    (district counts, resolution rates, everything) on the very first
    scheduled monthly re-run in production.

12. **One more outlier found via the same route**: `compute_bfr.py`'s first
    real output showed a company with `incorporation_date = 1111-01-01` — an
    obvious data-entry error skewing monthly bucketing. Per rule 4 (never
    delete outliers, flag them), added an epoch-plausibility check
    (`1858-01-01` to today — the British Companies Act 1857 predates
    anything genuinely registrable) to `mca_silver.py`, setting
    `quality_flags` bit 2 (`QUALITY_BIT_OUTLIER`) rather than dropping the
    row. `compute_bfr.py` excludes outlier-flagged rows from the KPI
    aggregation while the row stays in `fact_company` for audit. Only 1 row
    out of 14,989 hit this. **Known remaining gap, not chased further given
    low materiality**: a handful of 1949–1963 incorporation dates for Goa
    are still technically implausible (Goa was Portuguese territory until
    1961 and didn't join India until then), but a state-specific liberation-
    date check felt like over-fitting to one state rather than a general
    rule — flagging for whoever tackles the full national sweep.

13. **Resolver stress-tested on a second, harder state (Bihar) — passed.**
    Goa (2 districts, clean addresses, 95.57%) was too easy a first test to
    trust nationally. Fetched Bihar (80,418 companies — includes a district
    named "Aurangabad", the classic ambiguous-name case from
    `docs/04-ETL-PIPELINE.md`) and ran it through the same pipeline:
    - **100% resolution rate** (80,418 / 80,418, zero quarantined).
    - **Idempotency re-confirmed** on real MCA data, not just LGD reference
      data: re-ran the Bihar silver transform a second time,
      `gold.fact_company` total stayed at exactly 95,407 rows both times
      (Goa's 14,989 + Bihar's 80,418), quarantine count unchanged at 695.
    - **The "Aurangabad" ambiguity check turned up a real, useful finding**:
      it's not actually ambiguous anymore. Maharashtra's Aurangabad was
      renamed **Chhatrapati Sambhajinagar** in 2023 (confirmed present under
      that name in current LGD data); only Bihar's Aurangabad still carries
      the name. Same story for `Balrampur` — Chhattisgarh's is now
      **Balrampur-Ramanujganj**, so only UP's Balrampur remains. **2 of the 5
      ambiguous-district-name examples in `docs/04-ETL-PIPELINE.md` were
      stale**; updated that doc to reflect it. The 3 that remain genuinely
      ambiguous, verified against live data: `Bilaspur` (CG, HP), `Hamirpur`
      (HP, UP), `Pratapgarh` (UP, RJ).
    - 1,087 Bihar companies correctly resolved to Bihar's Aurangabad
      district specifically (spot-checked directly), confirming the
      resolver's state-scoping design works as intended even where the
      underlying ambiguity exists in `dim_geography`.
    - Combined resolution rate across both states tested: **95,407 / 96,102
      = 99.28%** (Goa's harder addresses pull the blended rate down from
      Bihar's 100%; both are individually above the 90% gate).

    **Conclusion: the resolver is in good shape for Phase 2's full sweep.**
    Two states, different sizes and address styles, both comfortably above
    target, idempotency holds under real fact data.

---

## Environment notes for whoever runs this next

- A Python virtualenv exists at `.venv/` (gitignored). It has `datagovindia`, `httpx`,
  `pandas` installed from the Phase 0 discovery work. It does **not** yet have the
  full project dependency set — that lands with Phase 1's `pyproject.toml`.
- The `datagovindia` package's `sync_metadata()` method downloads the **entire**
  400k+ resource catalog to build a local searchable index. That is overkill for
  finding a handful of resource IDs and was abandoned in favor of just searching
  data.gov.in's own web UI and reading resource IDs off each dataset's API tab
  directly. If you need to discover a genuinely new source, prefer that approach —
  it's much faster.
- Docker is available (`docker --version` confirmed working) — `docker-compose.yml`
  is drafted in `docs/10-DEPLOYMENT.md` but not yet copied to the real root file as
  a working config.
- `python3` on this machine is 3.14 (CLAUDE.md asks for 3.11+; nothing so far depends
  on a specific 3.11–3.14 feature, but flag it if a dependency ever refuses to build
  on 3.14).

---

## Next step, concretely

Phase 1's checkpoint is met and stress-tested (Goa + Bihar, both above the 90%
gate, idempotency confirmed on real fact data). Remaining before/alongside Phase 2:

1. **Route the Census population join through `GeographyResolver`** instead of the
   direct normalised-name dict used in `compute_bfr.py` (see item 10 above) — the
   ad hoc version worked for Goa/Bihar but hasn't been proven against the 3
   remaining genuinely-ambiguous district names (Bilaspur, Hamirpur, Pratapgarh).
2. Decide whether to spend a follow-up discovery session on the two Phase 0 gaps
   (Census literacy/worker-classification, CEA) before or after Phase 2.
3. Phase 2 proper: MCA sweep across ALL states (~3.67M rows, checkpointed/resumable
   — the connector already supports this per-state, just needs to loop all states),
   Udyam connector + snapshot-diff, all five validation gates wired,
   `meta.ingestion_run` populated on every load (already true), idempotency
   re-verified at full scale.
