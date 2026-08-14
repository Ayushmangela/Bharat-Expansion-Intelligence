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
| Phase 1 — Geography spine + one KPI | 🚧 In progress |
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

Per `docs/11-ROADMAP.md` Phase 1: Postgres up via `docker-compose.yml`, Alembic
initialised, `meta`/`silver`/`gold` schemas created, LGD connector loading
`dim_geography` as SCD-2, `geography_alias` seeded, six-step resolver implemented and
tested, `dim_date` populated, MCA connector for one RoC/subset landing in bronze,
Pandera schema + silver transform + PIN→district resolution, and a Business Formation
Rate computed for one state end to end — done when resolution rate is measured and
≥90% (roadmap's explicit gate; do not proceed past Phase 1 below that without fixing
the resolver first).
