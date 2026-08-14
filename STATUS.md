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
| Phase 2 — Full ingestion | 🚧 In progress — Udyam connector done (92.39% resolution); MCA still only Goa+Bihar, not the full ~3.67M-row sweep |

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

Phase 1 is solid (checkpoint met, stress-tested on two states, Census join
routed through the resolver). Phase 2 has started: Udyam is done nationally
(92.39% resolution, real numbers in `gold.fact_district_month`). Remaining:

1. **MCA full sweep across all ~36 states/UTs** (~3.67M rows) — the biggest
   remaining piece. The connector already supports this per-state
   (`pipeline/connectors/mca.py`, checkpointed/resumable); just needs to loop
   every state instead of Goa/Bihar. Will take a while given the politeness
   rate limit (0.7 req/s) — budget for it, don't rush it.
2. Optionally push Udyam's 92.39% higher with an alias batch for the 60
   quarantined districts (same spelling/abbreviation-drift pattern Census
   had) — not required, already above the 90% gate.
3. Decide whether to spend a follow-up discovery session on the two Phase 0 gaps
   (Census literacy/worker-classification — needed to turn BFR from a
   total-population proxy into the KPI as formally defined; CEA power supply).
4. Decide on an apportionment methodology for the 8 quarantined structural-split
   census districts if/when their population matters (currently just excluded).
5. Remaining Phase 2 items once MCA's full sweep lands: Udyam snapshot-diff
   (need a second snapshot before a flow can be derived — not possible yet,
   only one snapshot exists), all five validation gates wired, idempotency
   re-verified at full national scale.
