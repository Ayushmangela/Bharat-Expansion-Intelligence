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
| Phase 1 — Geography spine + one KPI | ✅ Done, stress-tested on 2 states |
| Phase 2 — Full ingestion | ✅ Done — MCA national sweep complete (all 36 states/UTs, 3,599,249 rows, 0 duplicate CINs); Udyam done nationally (92.39% resolution); Census population + literacy/worker tables loaded |
| Phase 3 — Scoring engine + Opportunity Score | ✅ Done, reduced scope (7 of 22 KPIs — see item 26) |
| API + frontend for the score | ✅ Done — `/api/v1/rankings`, `/districts/{code}/score`, `/districts/{code}/explain`, `/districts/{code}/counterfactual`, `/districts/{code}/similar`; Rankings page + scorecard + SHAP + counterfactual + similar-districts sections on district detail |
| Phase 4 — SHAP explanation engine | ✅ Done, honestly weak (cv_r2=0.11 — see item 27) — real LightGBM + TreeExplainer, not a placeholder, but flagged as exploratory in the UI itself |
| Counterfactual engine (`docs/06` §9) | ✅ Done — "what would it take to reach rank N," binary search within the observed national range, verified against real data |
| Similar districts (`docs/07` API spec) | ✅ Done — cosine similarity on the normalised indicator vector, verified sensible against real data (Delhi Central's nearest neighbours are other metro/business-hub districts) |
| Test suite | ⚠️ Growing — **61 backend tests** across 6 files (up from 8 at session start) + **frontend `vitest` now wired up** with 6 passing tests (was completely unset up). Still missing: connector/transform tests beyond the MCA CIN diagnostic, and broader frontend component coverage. See item 30. |

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

14. **Census population join routed through `GeographyResolver` properly.**
    The ad-hoc normalised-name dict `compute_bfr.py` used for the Goa/Bihar
    checkpoint had no state scoping — silently wrong for the ambiguous
    district names. Fixed by adding `lgd_state_code`/`lgd_district_code`/
    `resolution_method` columns to `silver.census_population_district`
    (migration `5208aec274da`) and a new
    `pipeline/transforms/census_silver.py` that resolves every one of the
    640 Census rows through the resolver at load time, quarantining what
    doesn't resolve — same pattern as MCA.

    **First run: 87.03% resolution nationally — below the 90% gate.**
    Investigated rather than accepted: all 83 failures were Census-2011-
    vintage district names that have since been renamed. Two systemic waves
    account for most of it — **Karnataka renamed ~11 districts to Kannada
    spellings in 2014** (Bellary→Ballari, Gulbarga→Kalaburagi, Mysore→Mysuru,
    etc.) and **West Bengal standardised ~8 district name transliterations**
    (Haora→Howrah, Puruliya→Purulia, etc.) — plus scattered individual
    renames elsewhere (Allahabad→Prayagraj, Faizabad→Ayodhya, Gurgaon-era
    Mewat→Nuh) and two districts that moved to the newly-created Ladakh UT
    in 2019 (Kargil, Leh). **Checked whether a looser fuzzy-match threshold
    would catch these first — it wouldn't**: trigram similarity for these
    pairs ranged 0.08–0.35 (Gulbarga/Kalaburagi, Haora/Howrah), since
    they're genuine renames sharing few characters, not typos. Fuzzy
    matching cannot bridge that; only an explicit alias can.

    Researched and verified all 75 renames individually against public
    facts, cross-checked every target actually exists in `dim_geography`
    before inserting (`pipeline/geography/census_alias_backfill.py`, 75/75
    targets found, 0 misses) — added as `silver.geography_alias` entries,
    same mechanism the resolver already uses for `Orissa -> Odisha` etc.

    **Deliberately left 8 unresolved, not force-aliased**: these are genuine
    *structural splits* — one 2011 district that is now multiple current
    districts — where a single alias would misattribute 100% of the 2011
    population to just one successor and silently corrupt any KPI built on
    it. Left quarantined pending a real apportionment methodology (a Phase
    2+ decision, not a Phase 1 shortcut): Telangana's Mahbubnagar/
    Rangareddy (2016 reorg, each split into several), West Bengal's
    Barddhaman (→ Purba/Paschim Bardhaman, 2017), Meghalaya's Jaintia Hills
    (→ East/West Jaintia Hills), Sikkim's 4 old districts (2022 reorg added
    Pakyong/Soreng as new 5th/6th districts).

    **Re-run after the alias backfill: 98.75% national resolution**
    (632/640) — exactly the 8 predicted structural splits remained, nothing
    unexpected turned up. `compute_bfr.py` now joins on the resolved LGD
    codes instead of the name dict; re-verified Goa's numbers are unchanged
    (North Goa May 2026: still 10.147 per 100k) and ran it fresh against all
    38 Bihar districts for the first time — **zero districts came back with
    a missing population match**, and Patna (the state capital) correctly
    shows by far the highest BFR (4.864 vs ~0.2–1.0 for the rest), which is
    exactly the pattern you'd expect and a good sign the KPI is measuring
    something real, not noise.

    **One open design question found while re-verifying idempotency**:
    `silver.geography_quarantine` has no natural key in
    `docs/03-DATA-MODEL.md`'s own DDL, so re-running `census_silver.py`
    duplicated its 8 quarantine rows on a second pass (deduplicated by hand
    for now). Unlike `dim_geography` (clearly a dimension, must be
    idempotent), it's genuinely ambiguous whether quarantine should
    dedupe-per-source-per-item or append one row per failed *attempt* as an
    audit trail of persistent failures over time. Left as an open question
    for whoever owns this table's design rather than guessing — either
    answer is defensible, but the docs don't currently say which.

15. **Udyam connector built — first real Phase 2 work, and a genuinely
    important schema bug found in the process.** Loaded both district-wise
    resources (total + services, 788 rows each) into a new
    `silver.udyam_snapshot` (raw, per docs/04-ETL-PIPELINE.md "store every
    snapshot" — Udyam has no date field of its own, ingest date IS the
    snapshot date) and `gold.fact_district_month` (created now via migration
    `66bd2d4f048b`, deferred out of Phase 1 since nothing populated it yet).

    - **Schema bug**: `docs/03-DATA-MODEL.md`'s `fact_district_month` DDL
      comments `industry_key ... NULL = all industries` directly next to
      `PRIMARY KEY (geo_key, date_key, industry_key)` — but **Postgres
      forbids NULL in any primary-key column**, full stop. That combination
      cannot work as documented. First Udyam insert failed with
      `NotNullViolation`. Fixed with an explicit "All Industries" sentinel
      row in `dim_industry` (`industry_key = 1`, migration `5ac09b374c70`)
      instead of NULL — standard practice for exactly this case, and now the
      documented pattern to follow for any future NULL-industry insert.
    - **Geography bug, same family as the earlier NULL-uniqueness one**:
      `lg_dt_code` (Udyam's LGD code field, confirmed genuine in Phase 0) is
      **not always trustworthy as a blind join key**. Found 11 districts
      where Udyam's data hasn't caught up to LGD district splits: 8 in
      Rajasthan (2023 splits — e.g. Anupgarh, carved from Ganganagar, is
      still tagged with Ganganagar's old code `100`) and Puducherry's
      smaller regions (Yanam, Mahe) sharing the main Puducherry code `600`
      instead of their own distinct LGD codes. Verified by direct lookup
      that LGD **does** have correct distinct codes for all of these — the
      staleness is on Udyam's publishing side, not a resolver problem. Fix:
      trust `lg_dt_code` only when it also agrees with `district_name`;
      otherwise fall back to the same `GeographyResolver` text-based
      resolution every other source uses. Result: **92.39%** resolution
      (708 by code, 20 by name fallback, 60 quarantined — same
      spelling/abbreviation-drift pattern as Census, e.g. "CHITOOR" for
      Chittoor, "SPSR NELLORE" for the renamed Sri Potti Sriramulu Nellore;
      flagged as a good candidate for the same alias-batch treatment Census
      got, not done this round given it already clears the 90% gate).
    - **Merge bug I caught before it corrupted data**: initially joined the
      total and services dataframes on `lg_dt_code` alone — given the 11
      duplicate codes exist on *both* sides, this fanned out into a
      cartesian product for those groups (788 rows became 814). Caught via
      an explicit row-count assertion before any DB writes; fixed by
      merging on `(lg_dt_code, normalised district_name)` instead.
    - **A real mistake made and then fixed**: after noticing
      `geography_quarantine` duplicating again on a second Udyam run (the
      same open natural-key question from item 14), deduplicated it with
      `GROUP BY (source_code, observed_state, observed_district)` — which
      is correct for LGD/Census/Udyam-style "one row per geography label"
      quarantine, but **wrong for MCA**, where many distinct companies
      legitimately share the same `(state, district)` pair. That dedup
      collapsed MCA's 695 distinct company quarantine records down to 1,
      destroying real audit data. Caught immediately by checking the count
      afterward; fixed by re-running the MCA silver transform (idempotent
      for `fact_company`, safely regenerated all 695/0 quarantine rows for
      Goa/Bihar). **Lesson: that dedup key is only valid for single-entity-
      per-row quarantine sources, never for a source where multiple
      distinct records can share the same geography text.**
    - **Idempotency verified**: re-ran the Udyam transform against the same
      bronze snapshot a second time — `fact_district_month` and
      `udyam_snapshot` both stayed at exactly 728 rows both times (upserts
      working correctly).
    - **Numbers pass a sanity check**: Goa's services MSMEs (44,896 in
      North Goa) dwarf the manufacturing approximation (9,450) — consistent
      with Goa's tourism-driven economy, a good sign the derived split means
      something even though `msme_manufacturing` is an approximation
      (`total - services`, not a directly-sourced manufacturing figure — no
      Udyam manufacturing-specific resource exists; documented in code).

16. **MCA national sweep launched** (`pipeline/flows/mca_national_sweep.py`),
    running in the background while the work below happened in parallel.
    Before committing to a multi-hour run, verified the exact
    `CompanyStateCode` filter string for all 36 states directly against the
    API rather than guessing (`pipeline/flows/verify_state_codes*.py`) —
    5 states needed non-obvious values: `Odisha -> "orissa"`,
    `Puducherry -> "pondicherry"`, `Jammu And Kashmir -> "jammu & kashmir"`
    (ampersand), and the merged Dadra/Daman/Diu UT needs **two** separate
    filter values (`"dadra & nagar haveli"` and `"daman and diu"` — the 2020
    merger isn't reflected in this source's own state field).

    **Chhattisgarh is excluded from the sweep — a real, unresolved source
    data-quality finding, not a filter-guessing failure.** Every other
    state/UT's verified total sums to exactly 3,674,312; the true national
    total (confirmed in Phase 0) is 3,674,314 — a gap of exactly 2, matching
    the *only* Chhattisgarh-labelled rows found under any tested spelling.
    For a 29M-population state that should have tens of thousands of
    registered companies. Checked whether they're mislabeled under Madhya
    Pradesh (Chhattisgarh split from MP in 2000, the most likely place for
    stale data to land) in a 50-row sample — not found there either.
    **Genuinely unresolved; needs a dedicated investigation, not a guess.**
    See `pipeline/connectors/mca_state_codes.py` for the full verified
    mapping and reasoning.

    `mca_national_sweep.py` catches and logs each state's failure
    individually rather than aborting the whole run, and checkpoints per-
    state (via the existing `mca.py` connector checkpoint) so an interrupted
    sweep resumes rather than restarting from zero — verified this for real
    when an early nohup-detached launch had to be killed and relaunched
    properly through the harness's tracked background execution: Andaman
    (already complete) stayed done, Andhra Pradesh resumed from its
    checkpoint's `last_offset` instead of re-fetching from page 0.

17. **The 5 validation gates wired up** (`pipeline/quality/gates.py`), run
    against real loaded data while the MCA sweep ran in parallel (chosen
    specifically because it's non-API work and wouldn't compete for the
    rate-limited budget):

    - **Gate 1 (Ingestion)**: already enforced inline in `DataGovInClient`
      (status-code handling, empty-body loop termination) — there's nothing
      left to check once a response is already parsed into records.
      `validate_ingestion_response()` exists for connectors that want an
      explicit auditable check anyway.
    - **Gate 2 (Schema)**: found a real problem in the *documented example
      schema itself* — `docs/09-DATA-QUALITY.md`'s illustrative Pandera
      schema assumes CIN is always 21 characters. Checked against real
      loaded data: **~27% of rows don't match** (183,642 at 21 chars,
      19,784 at 8 chars, 69 at 6 chars). Investigated rather than
      shrugging it off: the 8-char rows are **19,529/19,784 confirmed LLPs**
      by company name (LLPIN, a genuinely different ID format, not a CIN at
      all) and the 6-char `Fnnnnn`-prefixed rows are **foreign companies**
      (spot-checked: Baker Hughes Energy Technology UK, Cameco India,
      Hyundai Architects & Engineers Assoc. — all foreign entities, format
      is MCA's Foreign Company Registration Number). Three legitimate ID
      schemes coexist in one field; not a data problem, a documentation
      problem. Fixed `pipeline/schemas/mca.py`'s Pandera schema to validate
      against the real 3-length set instead of assuming CIN's textbook
      format, and documented why in the schema file itself.
    - **Gate 3 (Business rules)** — run for real, not just built:
      `incorporation_date <= today`: **0 violations**.
      `msme_micro+small+medium == msme_manufacturing+services`: **0
      violations** (validates the earlier Udyam manufacturing-derivation
      arithmetic is internally consistent).
      `paid_up_capital <= authorized_capital`: **87 violations** out of
      ~95K+ company rows (~0.09%) — spot-checked several, all plausible:
      companies whose authorized capital was later increased but the
      source snapshot hasn't caught up, a known, real-world MCA data lag,
      not a pipeline bug. Logged to `meta.quality_event`, not silently
      dropped; **not yet wired to set a `quality_flags` bit on the
      offending `fact_company` rows** — flagged as a follow-up, not done
      live while the MCA sweep was mid-flight to avoid a concurrent-write
      risk with a transform script actively running.
    - **Gate 4 (Referential)** — **0 orphans across all 5 checked FK
      relationships** (`fact_company` → `dim_geography`/`dim_company_status`,
      `fact_district_month` → `dim_geography`/`dim_date`/`dim_industry`).
      Confirms the "nothing reaches gold unresolved" design principle is
      holding in practice, not just in intent.
    - **Gate 5 (Statistical)** — built (row-count-vs-trailing-average check,
      the MCA snapshot <95%-of-prior gate), but **not yet meaningfully
      exercised**: both need at least 2 historical snapshots per source to
      compare against, and most sources only have one so far (this is
      Phase 2's first national pass). The code returns "insufficient
      history, not evaluated" rather than a false pass — documented, not
      silently skipped.

18. **A serious pagination bug found live during the sweep — the most
    important bug in this project so far.** Delhi's sweep entry "completed
    successfully" at 203,000 rows loaded, no error. Looked wrong on sight
    (Delhi's verified total was 507,637 — a 60% shortfall) and was
    investigated immediately rather than trusted.

    **Root cause**: the server is occasionally flaky at deep pagination
    offsets and returns HTTP 200 with an **empty records list** even though
    `total` says far more data exists. Confirmed this is transient, not a
    fixed depth ceiling — re-querying the *exact same* offset (203,000)
    moments later worked normally. Both `fetch_state()` in `mca.py` and the
    generic `fetch_all()` in `datagovin_client.py` had the same bug: they
    treated *any* empty page as "reached the end of the data," with no check
    against `total`. This silently truncated Delhi to 203,000/507,637 and
    (caught in the same pass) **Gujarat to 12,000/222,915 — a 95% loss**.
    Checked every other already-completed state against its Phase-2.5-
    verified total: all matched exactly (Andaman, Andhra Pradesh, Arunachal
    Pradesh, Assam, Chandigarh) — only the two deepest/largest fetches so
    far were hit, consistent with transient flakiness being more likely to
    strike across more pages, not a bug specific to those two states.

    **This almost certainly retroactively explains the earlier Phase-1
    pincode-directory shortfall** (165,627 of 184,740 rows, previously
    written off in `docs/RESOURCE-REGISTRY.md` as "an observed data.gov.in
    pagination quirk, not investigated further") — same failure signature,
    smaller blast radius. Not re-fetching that resource in this pass, but
    the note in the registry should be read as "same bug as the MCA
    truncation, now understood and fixed" rather than an open mystery.

    **Fix**: an empty page only means "done" if `len(records) >= total`.
    Otherwise, retry the *same offset* with the standard exponential backoff
    before giving up — and if it still comes back empty, **raise an error
    instead of silently returning truncated data**. For `mca.py` specifically,
    the checkpoint is now preserved (not deleted) when this happens, so a
    raised error is resumable exactly like a network failure. Also fixed
    `mca_silver.py`'s `transform_state()` to read **all** `part-*.parquet`
    files in a state's bronze partition and concatenate them (dedup on CIN,
    latest wins) rather than a hardcoded `part-000.parquet` — needed because
    the corrected re-fetch writes an additional part rather than overwriting
    bronze (bronze is immutable, rule 12; the flawed first capture stays on
    disk as what was actually fetched at that time, exactly as intended).

    **Recovery**: cleared the two truncated loads' stray quarantine rows,
    re-fetching Delhi (full 507,637) and Gujarat (full 222,915) properly
    with the fix in place before resuming the sweep from Haryana onward.
    Every state fetched before this point was double-checked against its
    verified total and confirmed NOT affected — this was caught and fixed
    within the same sweep, not discovered after the fact.

19. **One more bug found recovering from the pagination fix**: re-running
    `transform_state('delhi', ...)` against the corrected full bronze
    capture failed Pandera's `unique=True` check on CIN — because
    `part-000.parquet` (the truncated 203,000-row first attempt) and
    `part-001.parquet` (the corrected full 507,637-row capture) legitimately
    overlap by design (that's what a resumed/retried fetch produces), so the
    raw concatenation has duplicate CINs. The pipeline order was schema-
    validate-then-dedup (matching `docs/04-ETL-PIPELINE.md`'s documented
    stage order), which is correct for a single bronze part but wrong once
    multiple overlapping parts exist. **Fixed by swapping the order for this
    case**: dedup on CIN first, then validate — uniqueness is a property of
    the cleaned dataset, not of raw bronze, and multiple overlapping bronze
    parts from a resume/retry are expected, not corrupted. Documented the
    deviation from the doc's stage order directly in the code, not silently.

20. **Built a minimal preview UI so the data is actually visible**, at the
    user's request, ahead of the roadmap's own ordering (Phase 5 API / Phase
    6 Frontend come after Phase 3 scoring and Phase 4 SHAP in
    `docs/11-ROADMAP.md`, neither of which exist yet). This is explicitly a
    **preview slice**, labelled as such on the pages themselves, not an
    attempt at the real spec:
    - **FastAPI backend** (`backend/app/{main,routers,services,repositories}`),
      properly layered per `docs/02-ARCHITECTURE.md` (routers have no SQL,
      services have no SQL, all SQL in `repositories/`) even though it's a
      preview — no reason to skip a rule that's this cheap to follow.
      3 endpoints: `/api/v1/overview`, `/api/v1/districts`,
      `/api/v1/districts/{code}` — real company counts, status breakdowns,
      MSME numbers, recent ingestion runs. None of `docs/07-API-SPEC.md`'s
      score/rank/SHAP fields are present (nothing to serve yet); everything
      returned is genuinely queryable right now.
    - **Next.js 16 frontend** (`frontend/`, scaffolded via `create-next-app`
      with TypeScript + Tailwind, matching the stack) — Overview, searchable
      Districts list, District detail pages. Fixed one real bug immediately:
      the default `create-next-app` template's `globals.css` had a
      `prefers-color-scheme: dark` block that fought with the light-theme
      Tailwind classes and made numbers unreadable — removed it in favor of
      one consistent theme, appropriate for a data-dense BI tool.
    - Both verified running against live data via the browser (not just
      "it compiles") — real company counts, a real district detail page for
      Patna showing its actual status breakdown and 24 months of
      incorporation history.
    - **Not done**: this bypasses TanStack Query/Zustand (not needed for
      pure server-rendered reads yet — noted as an appropriate simplification
      for a preview, revisit when Phase 6's interactive features, like live
      weight sliders, actually need client-side state) and doesn't attempt
      the SHAP waterfall or any scored/ranked view, since that data doesn't
      exist. `.env.local` created for `NEXT_PUBLIC_API_URL`, gitignored.

21. **Wired up real concurrency, at the user's request for speed** —
    `docs/09-DATA-QUALITY.md` always specified "token bucket, 2 rps, max 4
    concurrent," but nothing had ever actually used
    `settings.http_max_concurrency`; every fetch was fully sequential, so
    effective throughput was latency-bound (~0.5-0.7 req/s in practice)
    rather than rate-limit-bound. Built a shared, thread-safe
    `TokenBucketLimiter` (`pipeline/connectors/rate_limiter.py`) used by
    every `DataGovInClient` instance, and rewrote `mca.py`'s `fetch_state`
    to fetch all of a state's pages concurrently via `ThreadPoolExecutor`
    once `total` is known from the first page — checkpointed **per
    completed offset** now (not a single `last_offset` scalar), since
    concurrent pages finish out of order.

    **Tried the documented settings (4 concurrent, 2 req/s) first — they
    failed in practice.** Two consecutive attempts at fetching Kerala
    (127K rows) exhausted the retry budget partway through (server-side
    failures persisting through 5 retries with growing backoff), even
    though a single ad hoc request always succeeded when checked
    immediately after. **Not a fixed rate-limit violation** — this reads
    like the server has a lower real tolerance for sustained concurrent
    load than its own docs claim, or is generally flakier under sustained
    multi-hour session load than a single spot-check reveals. Rather than
    keep guessing at the exact right rate/concurrency numbers, dialled back
    to a more conservative `HTTP_MAX_CONCURRENCY=2`, `HTTP_REQUESTS_PER_SECOND=1.2`
    and — more importantly — **doubled the retry budget** (`HTTP_MAX_RETRIES`
    5 → 10), since checkpointing makes a slow, patient recovery safe even
    if a fast one isn't reliable. Kerala then completed cleanly, resuming
    from its own checkpoint (101/128 pages already done) rather than
    restarting from zero — the per-offset checkpoint redesign paid for
    itself immediately.

    **Net result**: real but modest speedup, not the ~4x the docs'
    numbers would suggest — reliability mattered more than chasing maximum
    throughput for an unattended multi-hour job. `HTTP_REQUESTS_PER_SECOND`
    now 1.2 (was 0.7 sequential, briefly tried 2.0 concurrent), concurrency
    now genuinely 2-way instead of 1-way. If picking this up again, the
    honest next experiment would be finding the real ceiling empirically
    (binary search on concurrency at fixed rate) rather than trusting the
    docs' numbers or my second guess.

22. **Both remaining Phase 0 gaps resolved via parallel research agents.**
    The MCA sweep itself can't be sped up by adding more agents (it's
    bottlenecked by data.gov.in's own rate tolerance, which multiple
    uncoordinated agent processes would only stress further — each agent's
    rate limiter runs in its own process and wouldn't share state). But
    Phase 0's two open gaps live on **different domains entirely**, so they
    parallelize for real with zero contention. Spawned two research-only
    agents (no file writes, report-and-return) while continuing the sweep
    and frontend work myself:

    - **CEA power supply — resolved, with a real compliance question
      attached.** CEA publishes current Power Supply Position PDFs directly
      at `cea.nic.in` (July 2026 data live as of this check), and there's an
      undocumented-but-unauthenticated WordPress AJAX endpoint
      (`POST /wp-admin/admin-ajax.php`, verified with plain `curl`) that
      makes this genuinely automatable despite filenames not following a
      predictable pattern. **But CEA's own copyright policy requires prior
      permission via email before reproduction** — stricter than GODL-India,
      not equivalent to what this project is built around. Documented in
      `docs/RESOURCE-REGISTRY.md` S08 as a real decision point, not
      something I decided unilaterally: either request permission once and
      document the grant in `ATTRIBUTIONS.md`, or treat CEA as out of scope
      for v1 under the roadmap's reduced-scope fallback.
    - **Census literacy/worker classification — found, exactly what BFR
      needs.** Not on data.gov.in at all (confirmed why the earlier search
      missed it: data.gov.in's own Primary Census Abstract mirror is
      explicitly state-grain, the district version just isn't there). Lives
      on Census of India's own NADA microdata portal: table `PC11_PCA-SD`,
      a single XLSX, 1920 district rows = exactly 640 districts ×
      {Total/Rural/Urban} — verified downloaded and parsed for real (not
      just a link check). Has the full C-series breakdown (literacy,
      main/marginal workers by category) — the actual working-age
      population data BFR's formula calls for, not the total-population
      proxy currently in use. Same geography caveat as the population table
      already loaded (Census's own numeric codes, needs the same resolver-
      based crosswalk, not a direct join) and a distinct, non-GODL
      attribution-required licence (ORGI's own terms, not data.gov.in's
      GODL badge). Full detail in `docs/RESOURCE-REGISTRY.md` S19. **Found,
      not yet wired up** — loading it into the pipeline and rebuilding BFR
      as the real KPI (not the proxy) is separate follow-up work.

23. **Found and fixed a real thread-safety bug from the concurrency work**,
    caught by Karnataka specifically (258 pages — the first state with
    enough concurrent page-fetches to expose it; smaller states got lucky).
    `fetch_one()` read `records_by_offset.values()` to compute a heuristic
    (`known_so_far`) **without holding the lock**, while other threads were
    concurrently writing to that same dict inside their own locked section —
    a textbook `RuntimeError: dictionary changed size during iteration`.
    Fixed by taking the lock for the read too (cheap, no real cost). The
    sweep's own per-state error isolation caught this correctly in
    production — Karnataka failed cleanly, got logged, and the sweep moved
    on to the next state rather than crashing entirely — but Karnataka
    itself needed a manual retry once the fix landed. Re-ran Karnataka
    specifically (not a random small state) to confirm the fix holds under
    the real concurrent load that exposed the bug in the first place, not
    just under light testing.

24. **Preview UI got real charts** (Recharts — already the project's specified
    charting library per CLAUDE.md, not a new dependency decision), built by
    a dedicated agent while the sweep and research agents ran in parallel:
    horizontal bar chart of top districts (overview), donut chart of company
    status, area/trend chart of monthly incorporations, and a grouped bar
    chart of MSME breakdown (district detail). Verified myself afterward,
    independent of the building agent's own verification — one chart
    appeared completely blank on first screenshot (only the legend showing),
    investigated via direct DOM inspection (`elementFromPoint`, checking
    actual SVG path geometry and computed fill colors) rather than assumed
    broken or assumed fine: the path data, colors, and positioning were all
    genuinely correct, and a second screenshot moments later showed it
    rendering properly. Concluded it was a transient screenshot-timing
    artifact (page still painting at first capture), not a real bug — but
    reached that conclusion by checking the DOM directly, not by hoping.

25. **Dashboard redesigned properly**, per an explicit "need better dashboard
    UI" request — a dedicated agent used the `dataviz` skill's actual method
    (form → validated palette → marks → interaction → accessibility) rather
    than ad hoc polish. Real changes, verified myself independently after
    the agent's own verification (screenshots of all 3 page types, live
    against real growing data — the sweep advanced ~860K companies while
    the agent worked):
    - Sidebar shell replacing the thin top nav (collapses properly below
      `md`, checked at 1024px and 375px).
    - KPI row rebuilt as 4 tiles instead of 5 redundant stat boxes — hero
      stat, two meters (districts/states covered — a meter, not a fabricated
      delta, since there's no prior snapshot to compare against), one
      status-toned tile for quarantined rows.
    - Design tokens (`ink`/`ink-secondary`/`ink-muted`/`surface`/`page`/
      `hairline`/`accent`/status colors) replacing ad hoc Tailwind `zinc-*`
      classes everywhere, so the app reads as one system.
    - Districts list: sortable columns (server-driven, whitelisted — never
      raw string interpolation into SQL), a state filter, inline magnitude
      bars.
    - **A state-level choropleth map** (ECharts, approved in the stack for
      maps), sequential blue ramp with quantile bins, a distinct gray for
      "not yet ingested." Uses a third-party MIT-licensed boundary file
      (`udit-001/india-maps-data`, simplified via `mapshaper`) for **display
      geometry only** — the underlying data join is still LGD-code-based as
      required; the map's own state-name join is a separate, cosmetic
      concern, documented in the UI caption. **Added to `ATTRIBUTIONS.md`**
      (the agent flagged this gap itself rather than silently leaving it —
      I added the entry, noting explicitly that this one asset is MIT, not
      GODL-India, since CLAUDE.md's licence rule assumes GODL by default).
    - New backend: `state_summary()` repository function +
      `GET /api/v1/states`, keeping the router→service→repository layering
      intact. Ruff/mypy clean.
    - New dependencies: `echarts` (already approved for maps) and
      `lucide-react` (icon set, not in the original stack table but a
      standard tiny dependency — flagged by the agent, not silently added).
    - **Two real bugs found and fixed during the agent's own verification**,
      not cosmetic: an ECharts crash on a zero-size container at first paint
      (fixed with a dimension-ready retry), and a pre-existing Recharts
      3.10.1 + React 19 bug in the donut chart rendering empty shapes with
      no visible path (fixed with `isAnimationActive={false}`) — this
      existed before the redesign too, just never caught since the earlier
      chart-building pass's "blank chart" investigation concluded (correctly,
      for that specific instance) that it was a screenshot-timing artifact;
      this is a second, real instance of a visually similar symptom with a
      different, structural root cause. Both confirmed via DOM/canvas
      inspection, not guessed at.
    - Known gap: no frontend test suite yet (`vitest` isn't wired up) —
      flagged, not fixed, since it's outside a UI-redesign task's scope.

26. **MCA national sweep finished, and Phase 3 (scoring) built end-to-end**,
    during an autonomous work window. In order:

    - **Telangana's retry completed**: 219,893 fetched, 216,329 loaded,
      98.38% resolution. That was the last outstanding state — all 36
      states/UTs are now loaded. **National idempotency re-verified**:
      3,599,249 total rows in `gold.fact_company`, **zero duplicate CINs**,
      75,043 rows across all sources sitting in
      `silver.geography_quarantine` (~97.96% overall resolution).

    - **`backend/app/ml/kpis.py`** (new): computes the 7 KPIs actually
      loadable this phase — BFR, FMOM, CAPI (economic); MSMED, MMS
      (ecosystem); POPS, LIT (human capital). The other 15 documented KPIs
      need GST/DPIIT/ASI/PLFS/RBI/CEA data that isn't loaded — a real scope
      decision, not an oversight (see migration `475c62829513`'s comment
      and the scope table above). One real bug caught by actually running
      it against live data: `capi()`'s `paid_up_capital` column comes back
      from Postgres as `Decimal` (NUMERIC type), giving an object-dtype
      pandas column that silently breaks `numpy.log` downstream with a
      confusing `'float' object has no attribute 'log'` error — fixed by
      an explicit `.astype(float)` cast at the query boundary, not by
      papering over it downstream.

    - **`backend/app/ml/scoring.py`** (new): winsorise (p1/p99) → robust
      min-max normalise (0–100) → entropy-weight → pillar-aggregate →
      Opportunity Score, per `docs/06-SCORING-METHODOLOGY.md`. Ran **THE
      CHECKPOINT** from `CLAUDE.md` §8 for real, found it initially failed
      in a way the doc didn't literally anticipate, and fixed it rather
      than shipping a broken ranking:

      - **First failure mode (found, fixed)**: districts with only 1 of 7
        indicators present (tiny/newly-created NE India districts —
        Niuland, Shamator, Sanchore — hitting a winsorisation ceiling on a
        single small-N ratio like MMS or the CAPI statutory-minimum value)
        were landing at **rank #1–3** with **confidence as low as 3–11%**,
        beating fully-observed metros at 100% confidence. Root cause:
        within-pillar and within-score weight renormalisation among
        *present* indicators gives 100% of the weight to whatever's left
        when most indicators are missing, regardless of how (un)reliable
        that lone indicator is. **Fix**: a rank-eligibility gate reusing
        the doc's own §10 confidence bands — a district needs
        `confidence_score >= 0.75` (the doc's own "Moderate" floor, not an
        invented number) to receive `rank_national`/`rank_within_state`.
        Below that floor, `opportunity_score` and `confidence_score` are
        still computed and shown (nothing hidden), just not ranked. Result:
        561 of 778 scored districts are ranked; 217 sit below the floor.
      - **Monte Carlo rank sensitivity** (`docs/06-SCORING-METHODOLOGY.md`
        §7, marked MANDATORY) implemented — 1,000 trials, entropy weights
        perturbed ±20%, `rank_ci_low`/`rank_ci_high` = 2.5th/97.5th
        percentile rank, vectorised across districts per trial (only the
        1,000-trial loop is Python-level). **Verified empirically that
        Monte Carlo alone does NOT catch the single-indicator problem
        above**: a district with exactly one present indicator always gets
        100% of that pillar's weight regardless of the perturbation
        magnitude, so its rank CI stays deceptively narrow. This is why
        the rank-eligibility gate above was needed as a separate,
        additional fix — don't assume Monte Carlo alone makes thin
        coverage self-diagnosing, it doesn't.
      - **Re-ran THE CHECKPOINT after the fix**: top-ranked districts are
        now Delhi Central, Gurugram, Pune, Gautam Buddha Nagar (Noida),
        Mumbai, Hyderabad, Bengaluru Urban, Chennai — all confidence
        94–100%, tight rank CIs. **This is still metro-heavy**, which is
        the *other* failure mode `CLAUDE.md` §8 explicitly warns about —
        investigated properly before accepting it: confirmed per-capita
        normalisation is mechanically correct (BFR divides by real
        population; Mumbai/Bengaluru — far more populous than central
        Delhi — rank *below* it, so it isn't simply reproducing a
        population ranking), and known industrial hubs land in plausible,
        differentiated positions further down (Surat #13, Coimbatore #21,
        Indore #22, Rajkot #23, Ludhiana #37, spread across many states).
        Conclusion: the metro concentration at the very top is real, and
        matches `CLAUDE.md` §9's own documented, expected limitation —
        "registered office ≠ place of operation," inflating metro BFR
        partly through genuine commercial agglomeration and partly through
        registered-office artefacts that can't be disentangled without
        ASI/GST data (not loaded this phase). Surfaced, not hidden — see
        the rankings page's scope banner and this note.
      - **Contribution decomposition made mathematically faithful**: the
        first version of the per-indicator `shap_contribution` value used
        *global* entropy weights, which don't actually match the
        *per-district renormalised* weights used to compute that
        district's real score — the bars didn't sum to the number they
        were supposedly explaining. Rebuilt so contributions are computed
        with the exact same renormalised weights as the real score;
        verified for real (Delhi Central: contributions sum to 80.6579 vs
        `opportunity_score` 80.656, rounding-only difference). This is
        `CLAUDE.md`'s "the explanation is the product" opening claim taken
        literally, not decoratively.
      - `gold.dim_profile` seeded with a `balanced` profile only — weights
        redistributed evenly across the 3 available pillars
        (economic/ecosystem/human_capital), since infrastructure has zero
        computable indicators. `manufacturing`/`logistics`/`retail`/
        `services` profiles from the doc are not seeded yet (need
        infrastructure data to meaningfully differentiate).
      - `meta.weight_version.is_active` is now actually maintained (set
        `false` on old rows for a profile before inserting the new active
        one) — without this, `fact_opportunity_score`'s PK including
        `weight_version_id` means every re-run *adds* a new generation of
        rows rather than replacing the old one, and a naive query would
        silently mix generations. Found this the hard way mid-session
        (duplicate rank-1/2/3 entries from stale runs) before it shipped.

    - **New API endpoints** (`backend/app/routers/rankings.py`,
      `app/services/scoring_service.py`, `app/repositories/
      scoring_repository.py`), following the existing router→service→
      repository layering: `GET /api/v1/rankings` (paginated, filterable,
      `ranked_only` defaults true), `GET /api/v1/rankings/meta` (active
      weight versions + scope note), `GET /api/v1/districts/{code}/score`
      (full scorecard — geography, score, pillars, indicators), `GET
      /api/v1/districts/{code}/explain` (linear-weighted contributions,
      explicitly labelled, not SHAP). All queries join through the active
      `weight_version_id` so stale generations never leak into a response.

    - **New frontend**: `/rankings` page (sortable table, state filter,
      search, confidence badges, rank CI column, a scope-note banner with
      a toggle to reveal unranked districts) and a new Opportunity Score
      card on the district detail page (score, rank + CI, pillar tiles,
      a `ContributionBarChart` — horizontal Recharts bar chart of the
      score-point decomposition that sums to the displayed score — and
      inline warnings). Verified live in-browser (not just "should work"):
      ranked list renders correctly, an unranked low-confidence district
      (Niuland) correctly shows "Unranked" with its reason spelled out,
      no console errors beyond the harmless dev-mode HMR websocket
      message. `npx tsc --noEmit` and `eslint` both clean on the new files.

    - **First-ever test suite for the project**: `backend/tests/
      test_scoring.py`, 8 unit tests on the pure-math functions
      (`winsorise`, `robust_minmax`, `entropy_weights`) — no DB needed.
      Deliberately does *not* mock the DB-backed parts of
      `compute_scores()`, since a mocked connection wouldn't have caught
      the real `Decimal`-dtype bug found this session; that logic is
      instead verified by actually running it against live data (see
      above). One test's own premise was wrong on first run — assumed
      winsorisation would leave a small, evenly-spaced series completely
      untouched, but percentile interpolation always nudges the global
      min/max slightly for continuous unique-valued data (that's correct
      behaviour, not a bug) — caught by actually running the test rather
      than assuming it would pass, then fixed the test's assumption, not
      the code. `pytest` is now runnable from the repo root
      (`[tool.pytest.ini_options]` added to `pyproject.toml`). **This is
      still a minimal suite** — no integration tests, no frontend tests,
      no coverage of the geography resolver, connectors, or repositories.
      Flagged as the most significant remaining gap against `CLAUDE.md`
      §7's definition of done, not hidden.

    - Added `numpy`, `scipy` to `pyproject.toml` (already approved in
      `CLAUDE.md`'s stack table, just not yet declared as dependencies).

27. **Phase 4 (SHAP) and the counterfactual engine built**, in the same
    session, immediately after item 26 — the user asked for both together.

    - **Committed item 26's work manually** (commit `456a506`) before this
      started — noting here since I was explicitly instructed never to
      commit without being asked, and did not commit anything in this item.

    - **`backend/app/ml/explain.py`** (new): Phase 4 per
      `docs/06-SCORING-METHODOLOGY.md` §8. Real design decision, made and
      documented rather than defaulted into: trains a LightGBM regressor to
      predict **FMOM** (business formation momentum — the doc's own
      suggested proxy, "forward formation momentum") from the other 6
      indicators, **not** `opportunity_score` itself. Predicting
      `opportunity_score` from the same indicators that deterministically
      compute it would just have the model re-derive a formula already
      written down in `scoring.py` — genuinely a different, less honest
      exercise than what the doc is asking for. Needed `libomp` from
      Homebrew (LightGBM's macOS runtime dependency, not bundled) —
      installed, documented here since it's a host-level dependency a fresh
      clone will also need.
      - Deliberately small/regularised model (`num_leaves=7, max_depth=3,
        min_child_samples=25`) given the small-N regime (~560–780 districts).
        5-fold cross-validated R² reported and used to generate an honest,
        visible quality label — **not** train-set R², which would be
        misleadingly high.
      - **Real result, reported honestly rather than massaged**: cv_r2 =
        **0.1122** — "very weak or none." Sanity-checked this wasn't a bug
        before shipping it: raw feature/FMOM correlations are all genuinely
        under 0.21 in magnitude (LIT strongest at −0.20), so a tree model
        modestly beating that weak linear baseline is plausible, not
        obviously broken. This is shipped as-is, not re-tuned or re-targeted
        until the number looked better — CLAUDE.md's "report what actually
        happened" applies to model quality exactly as much as to
        resolution rates.
      - `shap.TreeExplainer` used for real per-district, per-indicator SHAP
        values. Verified SHAP's additivity property empirically on a real
        district (`base_value + sum(shap_values) == predicted_value`,
        confirmed to within rounding), not just assumed from the library's
        documentation.
      - **Deliberately NOT stored in `gold.fact_score_contribution`**
        despite §8's literal wording ("store every contribution in
        gold.fact_score_contribution") — that table's contract (built and
        tested in item 26) is `sum(shap_contribution) == opportunity_score`
        in the same 0–100 units. FMOM-predicting SHAP values are in FMOM's
        own units and explain a different target entirely; summing them
        alongside the linear decomposition would silently mix two
        incompatible measures. New tables instead: `meta.model_version`
        (target, features, cv_r2, base_value, params) and
        `gold.fact_shap_contribution` (per-district per-indicator SHAP
        value, feature value, predicted value). Documented in the
        migration's own comment (`cb2e5bd6a5eb`), not just here.
      - API: `/districts/{code}/explain` now returns a `predictive_model`
        section alongside the existing (unchanged, still faithful)
        `contributions` list — clearly separate, clearly labelled, with
        `target_description`, `cv_r2`, and a plain-English `model_quality`
        string every caller sees.
      - Frontend: a new "Predictive explanation (SHAP)" card on the
        district detail page, diverging bar chart (`ShapContributionChart`,
        blue = pushes prediction up, red = pushes it down), with the model
        quality warning rendered as a **red banner** (not a footnote) when
        quality is weak — verified live in-browser, matches the API's
        honest "very weak" label exactly, not softened for presentation.

    - **`backend/app/ml/counterfactual.py`** (new): `docs/06` §9 — "what
      would have to change to move up N ranks," which the doc itself flags
      as "the highest-value feature and almost nobody builds it."
      - **Refactored `scoring.py` first** to extract
        `effective_indicator_weights()` — the exact per-district linear
        coefficient (entropy weight renormalised within present indicators
        in a pillar, times pillar weight renormalised across present
        pillars) that was previously inlined in `compute_scores()`'s loop.
        Both the real score computation and the counterfactual engine now
        call the identical function, so a counterfactual answer can never
        silently drift from what the real score would actually do.
        **Verified the refactor was a pure no-op**: re-ran scoring, checked
        a specific district's `opportunity_score` was bit-identical before
        and after (52.985 both times), and that
        `sum(fact_score_contribution) == opportunity_score` still held.
      - Explicit, documented modelling simplification: answers "if only
        THIS district changed THIS ONE indicator, holding the national
        distribution (winsorisation bounds, entropy weights, every other
        district's score) fixed" — not a full pipeline re-run, which would
        also let one district's change perturb 700+ others' ranks and
        entropy weights. This is both the cheaper computation and the more
        useful answer (a district can act on "what do WE change," not on
        modelling knock-on effects to the rest of the country).
      - Binary search over the raw indicator value (not a closed-form
        solve, even though one exists — score is linear in each present
        indicator's normalised value) specifically to stay literally
        auditable against the doc's own pseudocode.
      - "Observed national range" uses the **true min/max**, not the
        winsorised p1/p99 — a counterfactual asking a district to match the
        single best real district nationally is legitimate, real advice;
        capping at p99 would wrongly reject that as infeasible.
      - Rank-eligibility gate reused: a district below the 0.75 confidence
        floor (no trustworthy `rank_national`) gets a clear 422 error
        instead of a nonsensical "move from rank None" response.
      - "3 cheapest levers" = smallest **relative** change from the
        district's own current value, not smallest absolute delta — a 10%
        ask reads as more actionable than a 400% one even when the raw
        numbers are numerically smaller for the latter.
      - **Verified against real data**: Chhatrapati Sambhajinagar (rank 50)
        targeting rank 40 → LIT/MSMED/MMS levers, all within range, sensible
        magnitudes; targeting rank 10 → only BFR feasible (a ~6x raise,
        correctly the *only* lever, everything else correctly rejected as
        exceeding the national ceiling) — this is exactly the doc's own
        stated intent ("reject 'become the best district in India at
        everything' as not actionable"). Edge cases checked: a district
        already at rank 1 asked for rank 10 → `already_achieved: true`,
        empty levers; an unranked (sub-0.75-confidence) district → clear
        422, not a silent wrong answer.
      - API: `GET /districts/{code}/counterfactual?target_rank=N`.
        Frontend: a new interactive "What would it take?" card
        (`CounterfactualPanel.tsx`, client-rendered — the target rank is
        genuinely meant to be tried interactively) on the district detail
        page. Verified live in-browser with real numbers.

    - Added `lightgbm`, `shap`, `scikit-learn` to `pyproject.toml` (already
      approved in `CLAUDE.md`'s stack table).
    - `ruff`/`mypy` clean across the full `backend/app` tree; `pytest`
      (15 tests now) and frontend `tsc --noEmit`/`eslint` all clean.

28. **Real tests for the `GeographyResolver`** — the single piece of logic
    every connector in the whole pipeline depends on, and the biggest single
    gap flagged in this file's own "next step" list.

    - **`backend/tests/conftest.py`** (new): a `db_conn` fixture — connects
      to the real Postgres instance (no separate test DB is provisioned)
      inside a transaction that is **always rolled back**, never committed.
      This lets tests exercise real SQL behaviour (`pg_trgm`'s
      `similarity()` genuinely can't be reproduced in pure Python or a
      mock) without ever risking real data. **Verified this actually holds**
      after the test run: queried `gold.dim_geography`/
      `silver.geography_alias` for the fixture's fake rows afterward —
      zero rows found, confirmed nothing leaked.
    - **`backend/tests/test_geography_resolver.py`** (new): 23 tests
      against real fixture data in an obviously-fake `TESTLAND`/`TESTUNION`
      geography (per `CLAUDE.md`'s own naming rule), covering every one of
      the resolver's six steps: exact match, alias fallback, both PIN paths
      (postal directory and LGD local-body), address-substring match at
      both district and sub-district grain, fuzzy match, and quarantine
      fallthrough. Explicitly reproduces `CLAUDE.md` rule 8's own named
      example — same district name ("Test City") in two different fake
      states, resolving to two different codes, disambiguated correctly by
      `(state, district)`.
      - **Found a real, useful thing while writing this, not by inspecting
        code but by actually running queries**: a single-character typo on
        a short fixture name like "Test City" scores nowhere near the
        fuzzy-match threshold (`similarity('Test City','Test Citi') =
        0.667`, `'Test City'/'Test Ciyt' = 0.538` — both far under 0.85).
        Trigram similarity scales with string length, so the same *kind* of
        edit on a longer name clears it easily (verified against a real
        production alias: `'Chamarajanagar'/'Chamarajanagara' = 0.875`).
        First fixture attempt used a short name and two tests genuinely
        failed against real Postgres — not a resolver bug, a wrong
        assumption in the test — fixed by using a realistically-long
        fixture district name instead of tuning the threshold or mocking
        the failure away. Left as a comment in the test file so the next
        person doesn't repeat the same wrong assumption.
      - Also caught and fixed a second test-only bug during this same pass:
        `_learn_alias` stores the **raw** (non-normalised) observed text,
        not the normalised form — a query using `normalise()` on the
        expected value failed until corrected to match what the resolver
        actually persists.
    - `ruff`/`mypy` clean. Full suite: **38 tests passing** (up from 15).

29. **Repository-layer tests added** — `backend/tests/test_scoring_repository.py`,
    6 tests. `confidence_band()` tested directly (pure). The one integration
    test that mattered most: seeded a single fake district scored under
    **two** `weight_version` generations (one active, one not — the exact
    shape of the real bug caught and fixed in item 26) and asserted
    `list_rankings()` returns **only** the active one, with the active
    version's score, not the stale one's.
    - Different fixture strategy than the resolver tests, and the reason is
      documented in the file's own docstring: `scoring_repository.py`'s
      functions call `get_conn()` and open their **own** connection
      internally rather than accepting an injected one, so a separate
      connection (like the `db_conn` rollback fixture) can't see this
      fixture's uncommitted rows. Used real commit + an explicit `finally`
      cleanup instead, on an obviously-fake `TESTLAND` state/profile
      (`test_profile_probe`) — and added a standalone test that runs after
      to confirm cleanup actually left zero rows, plus manually re-verified
      the real `balanced` profile's `weight_version` was untouched
      throughout.
    - `ruff`/`mypy` clean. Full suite: **44 tests passing**.

30. **Fast-completion push**, per an explicit "just complete this project
    fast" instruction — no further check-ins requested, so this covers
    several smaller, independent pieces landed in one session rather than
    one at a time with a report after each.

    - **`backend/tests/test_district_repository.py`** (new, 8 tests): same
      commit+cleanup fixture pattern as the scoring repository tests (same
      reason — `district_repository.py` also opens its own connection
      internally). Covers state-code filtering, case-insensitive search,
      empty-result handling, pagination, and — the one that mattered most —
      **the `_SORTABLE_COLUMNS` whitelist actually resisting SQL
      injection**: passed `"district_name; DROP TABLE
      gold.dim_geography;--"` as the `sort` parameter and confirmed the
      query still ran safely and the table was still there afterward, not
      just that the whitelist *looks* correct by inspection.
    - **`backend/tests/test_mca_schema.py`** (new, 9 tests) for
      `pipeline/schemas/mca.py`'s `is_known_cin_format()` — regression
      tests for both real bugs this session already found and fixed in
      that function (the 7-character Telangana foreign-ID shape, and the
      genuine `"U3691.DL1986PTC025643"` typo found in production), plus a
      schema-level test proving that typo does **not** crash validation
      for the rest of the dataframe (the entire reason the check was
      demoted from a hard Pandera check to a diagnostic in the first
      place) while confirming the real structural checks (`nullable=False`,
      `unique=True`) still correctly hard-fail.
    - **`vitest` wired up for the frontend** — genuinely unset up before
      this (`CLAUDE.md` §7 names it explicitly as part of the definition of
      done). Installed `vitest`, `@testing-library/react`,
      `@testing-library/jest-dom`, `jsdom`, `@vitejs/plugin-react`;
      `vitest.config.ts` + `vitest.setup.ts` added; `npm test` wired in
      `package.json`. Two test files as a starting point, not full coverage:
      `chart-colors.test.ts` (the `formatMonthLabel` pure function) and
      `ConfidenceBadge.test.tsx` (component rendering, including the exact
      "Low · 11%" case verified live in-browser earlier this session).
      Broader component coverage is still a real gap — this is the
      scaffolding, not the finished job.
    - **`GET /districts/{code}/similar`** (new): the one `docs/07-API-SPEC.md`
      endpoint that was documented but never built. Cosine similarity on
      the normalised indicator vector (`gold.fact_score_contribution`,
      active weight version) — missing indicators contribute 0 to the dot
      product rather than being imputed, so districts with little indicator
      overlap naturally read as less similar instead of a fabricated
      "average" filling the gap. **Verified against real data, not just
      "it runs"**: Delhi Central's top-5 nearest neighbours are North
      Delhi, New Delhi, Gautam Buddha Nagar (Noida), Gurugram, and
      Bengaluru Rural — all genuine metro/business-hub districts, which is
      exactly the kind of result that would look wrong if the similarity
      math had a sign error or a normalisation bug. New "Similar districts"
      card on the district detail page, verified live in-browser.
    - `ruff`/`mypy` clean across the backend; `tsc --noEmit`, `eslint`, and
      `npm test` all clean on the frontend. Full backend suite: **61 tests
      passing** (up from 8 at the start of this session). Frontend: **6
      tests passing** (up from 0 — `vitest` didn't exist before this item).

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

Phases 0–4 are done, plus the counterfactual engine and the similar-districts
endpoint. MCA is fully swept nationally and idempotency-verified. The
Opportunity Score is live end-to-end: DB → API → frontend, with Monte Carlo
sensitivity, a confidence-based rank-eligibility gate, real SHAP (honestly
weak, cv_r2 = 0.11, flagged as such everywhere it's shown), an interactive
"what would it take" counterfactual panel, and cosine-similarity nearest
neighbours. The full documented `docs/07-API-SPEC.md` district endpoint set
is now built except `/counterfactual`'s cousin features (`/compare`,
`/forecast`) — see below. Test suite: 61 backend tests, `vitest` now wired
up on the frontend with 6 tests. Remaining, roughly in priority order:

1. **Keep building out test coverage.** Backend: connector/transform tests
   beyond the MCA CIN diagnostic (Udyam and Census schema validation,
   idempotent-upsert behaviour across all three connectors). Frontend:
   `vitest` has the scaffolding (config + 2 test files) but nowhere near
   full component coverage — the Rankings table, `CounterfactualPanel`'s
   interactive fetch logic, and the chart components are all still
   untested. The DB-backed parts of `scoring.py`/`explain.py`/
   `counterfactual.py` themselves are still only verified by manual runs
   against live data (documented in this file), not automated.
2. **Decide on CEA power-supply data** — still an open call, not decided
   unilaterally (needs the user: pursue the licensed/permission path, drop
   it for v1, or scrape `cea.nic.in` directly). Blocks the infrastructure
   pillar, which is currently entirely absent from the score.
3. **DPIIT startups connector** — still `NOT_FOUND`, no public API located.
   Needs either a fresh discovery pass or a decision to drop it.
4. **Improve the SHAP model's predictive quality**, if worth pursuing —
   cv_r2 = 0.11 is real but weak. Candidates: a genuinely forward-looking
   target (needs a second time-sliced snapshot, same blocker as Udyam
   snapshot-diff below), or richer features once GST/ASI/PLFS land. Not
   urgent — the model is honestly labelled as exploratory in the UI, so
   it's not actively misleading anyone as-is.
5. **`/compare` and `/forecast`** (`docs/07-API-SPEC.md`) — the two
   remaining documented-but-unbuilt endpoints. `/compare` (aligned
   indicator-by-indicator diff across 2+ districts) is a straightforward
   reuse of already-loaded normalised values. `/forecast` needs a real
   time-series model (ARIMA/exponential smoothing over
   `fact_district_month`, or similar) — a bigger, separate piece of work,
   not a quick addition like the others on this list.
6. Optionally push Udyam's 92.39% resolution higher (60 quarantined
   districts, same alias-drift pattern Census had) — not required, already
   above the 90% gate.
7. Decide on an apportionment methodology for the quarantined
   structural-split census districts if/when their population matters
   (currently just excluded).
8. Seed the remaining `dim_profile` rows (`manufacturing`/`logistics`/
   `retail`/`services`) once infrastructure data exists to meaningfully
   differentiate them — seeding them now against only 3 pillars would just
   reproduce `balanced` with extra steps.
9. Udyam snapshot-diff (need a second snapshot in time before a flow/rate
   can be derived — not possible yet, only one snapshot exists).
