# Resource Registry — PHASE 0

**This blocks everything. Do not write connectors until this file is filled in.**

## Why this exists

data.gov.in identifies datasets by UUID resource IDs. Those IDs are not guessable, are
not stable forever, and are not fully documented on catalog pages. **Hardcoding an
invented UUID sends the pipeline to a dead endpoint that returns an empty 200 rather
than an error**, which is the worst possible failure mode — it looks like "no data"
rather than "wrong URL".

So: discover them, verify them, record them here, then hardcode the verified values.

## API shape (verified)

```
GET https://api.data.gov.in/resource/{resource_id}
    ?api-key={KEY}
    &format=json
    &limit={n}
    &offset={m}
    &filters[field_name]=value
    &fields=col1,col2
    &sort[field_name]=asc
```

Response contains `records`, `field` (schema), `count`, `total`.

## Discovery procedure

```bash
pip install datagovindia
```

```python
from datagovindia import DataGovIndia
dgi = DataGovIndia(API_KEY)
dgi.search(title="Company Master Data", max_results=20, print_results=True)
```

Use the wrapper for **discovery only**. Once you have the ID, call the REST API
directly in production code. Never leave catalogue search in the hot path.

## Verification checklist per resource

For each candidate ID, before recording it:

1. `GET` it with `limit=5` and confirm HTTP 200 with non-empty `records`
2. Record the exact field names returned (they drift from what catalog pages describe)
3. Record `total` (row count) — this is your baseline for the row-count sanity gate
4. Confirm the geography fields present (state name? district name? LGD code?)
5. Confirm the date/period field and its format
6. Save one raw response to `data/reference/samples/{source}.json` — committed, so
   schema drift is diffable later

## Registry — FILL THIS IN

Status values: `PENDING` · `VERIFIED` · `NOT_FOUND` · `BROKEN`

### S02 — MCA Company Master Data
- Catalog: https://www.data.gov.in/catalog/company-master-data
- **Deviation from expectation:** the catalog no longer publishes ~25 separate RoC
  resources. It is now **one unified resource**, filterable by the `CompanyROCcode`
  field (e.g. `"ROC Haryana"`, a free-text label, not a code).
- Status: `VERIFIED`
- Resource ID: `4dbe5667-7b6b-41d7-82af-211562424d9a`
- Actual fields observed: `CIN`, `CompanyName`, `CompanyROCcode`, `CompanyCategory`,
  `CompanySubCategory`, `CompanyClass`, `AuthorizedCapital`, `PaidupCapital`,
  `CompanyRegistrationdate_date`, `Registered_Office_Address`, `Listingstatus`,
  `CompanyStatus`, `CompanyStateCode`, `CompanyIndian/Foreign Company`, `nic_code`,
  `CompanyIndustrialClassification`
  - No `Registrar_of_Companies` or `PrincipalBusinessActivity` fields as originally
    expected — those became `CompanyROCcode` and `CompanyIndustrialClassification`.
  - `CompanyStateCode` is a lowercase state **name** (e.g. `"haryana"`), not an LGD
    code — must resolve through `geography_alias`.
  - No district or PIN field. District must be extracted from `Registered_Office_Address`
    (free text) via PIN regex, confirming the PIN→district resolution step in
    `04-ETL-PIPELINE.md` is required, not optional.
  - Many fields (`CompanyCategory`, `AuthorizedCapital`, etc.) are empty strings on a
    meaningful fraction of sample rows — expect to quarantine/flag, not drop.
- Total rows: **3,674,314** — matches the ~3.67M expectation exactly.
- Sample: `data/reference/samples/mca_company_master.json`

### S03 — Udyam MSME (district-wise)
- Catalog: https://www.data.gov.in/catalog/udyam-registration-msme-registration
- Status: `VERIFIED`
- Resource IDs:
  - Total: `f8cd85a1-f9b8-4ff1-b195-9f75c10eb338` (788 rows)
  - Services: `c3dfe7e6-0cfd-4ddb-8f79-9cb3695d9866` (788 rows)
- **Confirmed: `lg_dt_code` field is present and is a genuine LGD district code.**
  This is the geography anchor as hoped — join directly to `dim_geography` on this
  field, no alias resolution needed for Udyam.
- Actual fields observed: `state_name`, `state_id`, `district_name`, `lg_dt_code`,
  `medium`, `micro`, `small`, `total`
- Sample: `data/reference/samples/udyam_district_total.json`,
  `data/reference/samples/udyam_district_services.json`

### S04 — DPIIT Recognised Startups
- Catalog: https://www.data.gov.in/catalog/startup-recognized-dpiit
- Status: `NOT_FOUND`
- **This dataset has no `api.data.gov.in` resource.** Its API tab reads: "This feature
  is unavailable as the data is directly hosted on the source server." It is a
  "Sourced Webservice" pointing at `https://www.startupindia.gov.in`, not an
  api.data.gov.in resource.
- Fallback: `https://www.startupindia.gov.in/content/sih/en/search.html` — no
  documented public API found there either. This needs a scrape-and-be-polite
  approach per rule 2.5, or should be re-scoped as `PENDING` for a follow-up
  discovery session focused specifically on startupindia.gov.in's own endpoints.

### S07/S09 — Local Government Directory
- Catalog: https://www.data.gov.in/catalog/local-government-directory-lgd
- Status: `VERIFIED` (all 5 resources)
- **Load this FIRST. Everything joins to it.** Confirmed as designed.

| Resource | Resource ID | Rows | Notes |
|---|---|---|---|
| States | `a71e60f0-a21d-43de-a6c5-fa5d21600cdb` | 36 | Fields: `state_code`, `state_name_english`, `state_name_local`, `state_census2011_code`, `state_or_ut`, `last_updated`. Carries **both** the LGD code and the Census 2011 code — this is the crosswalk. |
| Districts | `37231365-78ba-44d5-ac22-3deec40b9197` | 785 | Fields: `state_code`, `district_code`, `district_name_english`, `district_census2011_code`, etc. **785 rows, not ~750** — LGD is a living directory (post-bifurcation districts included); Census 2011 had ~640. Confirms `dim_geography` must be SCD-2, per the architecture doc. |
| Sub-Districts | `6be51a29-876a-403a-a6da-42fde795e751` | 7,151 | Some `district_census2011_code` values are literally `"NA"` (e.g. newer districts like "Jaipur (Gramin)") — expect nulls in the crosswalk, not a bug. |
| Local Bodies | `1a6c26ed-d67c-40ea-aa20-d38d35f341a5` | 353,197 | **Schema drift within the resource itself**: the `field` schema block lists `coverage_entityCode`/`coverage_entityName`/etc., but actual records return flattened keys `entityCode`/`entityName`/etc. (no `coverage_` prefix). Also one field name is literally `'"stateCode"'` — a stray embedded double-quote in the field name string. Parse defensively; do not trust the `field` block's naming exactly. |
| Local Bodies + PIN | `71818d1a-c114-46cb-aa9b-56ed70d4bc4a` | 7,411 | Clean: `stateCode`, `stateNameEnglish`, `localBodyCode`, `localBodyNameEnglish`, `localBodyTypeName`, `pincode`. This is the PIN→local-body→district path for MCA address resolution. |

- Samples: `data/reference/samples/lgd_states.json`, `lgd_districts.json`,
  `lgd_sub_districts.json`, `lgd_local_bodies.json`, `lgd_local_bodies_pincodes.json`

### S08 — CEA Power Supply Position
- Catalog: https://www.data.gov.in/catalog/power-supply-position
- Status: `BROKEN`
- **Not usable as designed.** CEA publishes a **separate resource per month**
  (e.g. "Power Supply Position - October 2014"), not one continuously-updated
  state×month resource. The month is baked directly into column names
  (`october_2014_requirement__mu_`), so even the schema changes shape every month.
  Many months are "Request API" only (no live resource at all — download-only).
  Catalog search found nothing newer than 2023; no 2024–2026 editions exist on
  data.gov.in, suggesting the feed may be stale or discontinued on this portal.
- Verified example (for schema reference only, not a stable production resource):
  `59b6cf39-6093-4da7-b9c9-6fe68ecff587` ("Power Supply Position - October 2014"),
  43 rows, sample saved to `data/reference/samples/cea_power_supply_oct2014.json`.
- **Fallback investigated (Phase 2, via dedicated research agent) — technically
  viable, but a real licensing question, not yet resolved.** CEA publishes
  current Power Supply Position reports directly (July 2026 data confirmed live
  as of this check) at `https://cea.nic.in/monthly-reports-archive/?lang=en`, as
  a PDF per month (Energy + Peak, separately), text-based and cleanly
  extractable (not scanned). Verified example:
  `https://cea.nic.in/wp-content/uploads/power_supply/2026/07/Energy_July26_Provisional.pdf`.
  Grain matches what's needed: state/UT × Energy Requirement/Supplied/Not-Supplied
  (MU), both report-month and April-to-date cumulative.
  - **Automatable, but not via predictable filenames** — the filename scheme
    changed between 2024 and 2026 (`PSPEnergyJune2024-1.pdf` vs
    `Energy_July26_Provisional.pdf`), so naive URL construction breaks. The
    archive page's "Show Archive Reports" button fires an **unauthenticated
    WordPress AJAX endpoint** (verified with plain `curl`, no session/nonce
    needed): `POST https://cea.nic.in/wp-admin/admin-ajax.php` with
    `action=archive_report&year=YYYY&month=MonthName&category=power_supply`,
    returning an HTML fragment with the actual PDF link(s) to parse out. A
    scheduled job can do this reliably: POST → parse href → download PDF →
    extract table (pdfplumber/camelot).
  - **Licensing gap — needs a decision before building a connector.** CEA's
    own Copyright Policy
    (`https://cea.nic.in/wp-content/uploads/web_policies/2021/11/Copyright_CEA.pdf`)
    requires **prior permission via email to CEA before reproduction**, plus
    attribution and no-alteration — stricter than GODL-India and not
    equivalent to the open-reuse terms this project is built around
    (CLAUDE.md §2.6). The site footer separately claims "All Rights
    Reserved." Options if pursued: request permission once and document the
    grant in `ATTRIBUTIONS.md`, or treat CEA as out of scope for v1 under the
    roadmap's reduced-scope fallback. **Not decided — needs the user's call,
    not an assumption.**

### S19 — Census 2011
- Status: `PARTIAL`
- **Population found, literacy/worker-classification not found in this session.**
- Population (rural/urban by sex): `VERIFIED` —
  Resource ID: `c9fee525-1c00-4ac2-969c-17bf42d2cc0a`, 707 rows (640 usable
  district rows after excluding state/national aggregate rows — matches the
  known Census 2011 district count).
  **The `field` schema block advertises pretty names (`State Code`,
  `District Code`, `Districts`) but actual records use snake_case keys
  (`state_code`, `district_code`, `districts`, `population___total___2011`,
  ...). Trust record keys, not the `field` block** — this cost a full debug
  cycle in Phase 1 (0 rows loaded on first attempt) before being caught.
  **Confirmed by direct testing: this resource's own "district code" is NOT
  the same numbering as LGD's `district_census2011_code`.** Example:
  Alappuzha is LGD district_census2011_code `598`, but this resource's own
  code for Alappuzha is `11`. Two sources both calling a column "census 2011
  code" does not mean the values are comparable — resolve by **normalised
  district name, scoped by state**, through `GeographyResolver`, not by code
  join. (Phase 1 used a direct name-dict join for the Goa checkpoint, ad hoc,
  not yet routed through the resolver properly — see `STATUS.md` item 10.)
  Sample: `data/reference/samples/census_2011_population.json`.
- Literacy rate + worker classification (district-wise, all-India): `VERIFIED`
  — **found in Phase 2 via a dedicated research agent, not on data.gov.in at
  all.** Confirmed why the earlier data.gov.in search missed it: data.gov.in's
  own "Primary Census Abstract 2011 - India and States" is explicitly
  state-grain per its own metadata; the district-grain version simply isn't
  mirrored there. It lives on the Census of India's own microdata catalog
  (ORGI's NADA portal, a separate site from data.gov.in):
  - Table: **"PCA SD: Primary Census Abstract data, India & States/UTs — State
    and district level — 2011"**, reference `PC11_PCA-SD`.
  - Catalog page: `https://censusindia.gov.in/nada/index.php/catalog/6191`
  - Direct download (verified HTTP 200):
    `https://censusindia.gov.in/nada/index.php/catalog/6191/download/9268/DDW_PCA0000_2011_Indiastatedist.xlsx`
  - Format: single XLSX (~1.34 MB), one sheet, 2029 rows × 94 columns — 3
    India-total rows, 105 state/UT rows, and **1920 district rows = exactly
    640 districts × {Total/Rural/Urban}**, matching the official Census 2011
    district count exactly (same count as the population resource already
    loaded).
  - Columns confirmed present: `P_LIT`/`M_LIT`/`F_LIT`, `P_ILL`/`M_ILL`/`F_ILL`
    (literacy); `TOT_WORK_P/M/F`, `MAINWORK_P/M/F` split by `MAIN_CL`
    (cultivators)/`MAIN_AL` (agricultural labourers)/`MAIN_HH` (household
    industry)/`MAIN_OT` (other workers), the same breakdown again for
    `MARGWORK` (marginal workers, further split by duration), plus
    `NON_WORK_P/M/F`. This is the full C-series worker classification — the
    working-age population breakdown BFR's formula actually calls for,
    replacing the current total-population proxy.
  - **Same geography caveat as the population resource already loaded**:
    `State`/`District` columns are Census 2011's own numeric codes (2-digit
    state, 3-digit district), not LGD codes — needs the same
    `GeographyResolver`-based crosswalk already built for the population
    table (`pipeline/transforms/census_silver.py`), not a direct code join.
  - Stability: persistent NADA/IHSN catalog entry (catalog id 6191, resource
    id 9268) — citable, not something needing periodic rediscovery.
  - **Licensing — not GODL, a distinct term.** ORGI's Terms & Conditions
    (`https://censusindia.gov.in/census.website/node/288`) permit reproduction
    free of charge if accurate, not misleading, and attributed — but this
    isn't the GODL-India badge data.gov.in resources carry. Cite it as ORGI's
    own attribution-required reuse policy in `ATTRIBUTIONS.md`, not as GODL.
  - Not yet loaded into the pipeline — this is a Phase 2 discovery result,
    wiring up the actual connector/transform is separate follow-up work.
- **Tag everything from this source with vintage = 2011.**

### S_PINCODE_DIR — All India Pincode Directory (added in Phase 1, not Phase 0)
- Catalog: https://www.data.gov.in/catalog/all-india-pincode-directory
- Status: `VERIFIED`
- Resource ID: `5c2f62fe-5afa-4119-a499-fec9d604d5bd`
- Publisher: Department of Posts
- **Why this was added after Phase 0 closed:** the documented resolver design
  (LGD local-body PIN join) only resolved ~60% of PIN codes to a district —
  most PINs map to sub-district local bodies, not District Panchayat
  entities. This resource has a direct `pincode → district` TEXT field
  (district names in caps, e.g. `"NORTH GOA"`) intended for exactly this
  purpose, and pushed MCA geography resolution from 76% to 95.57% on the
  Phase 1 Goa checkpoint. See `STATUS.md` for the full story.
- Fields: `circlename`, `regionname`, `divisionname`, `officename`, `pincode`,
  `officetype`, `delivery`, `district`, `statename`, `latitude`, `longitude`
- Total rows: reported `184,740`; **only 165,627 actually came back** on the
  original fetch (~19,000-row gap). **Now understood, not a mystery**: this
  was the same transient deep-pagination bug found and fixed during the
  Phase 2 MCA sweep (`STATUS.md` item 18) — the server occasionally returns
  an empty page mid-pagination even though `total` says more data exists,
  and the original client code treated that as "done." Fixed in
  `datagovin_client.py`'s `fetch_all()`. Not re-fetched in this pass since
  the resolver already works well with the partial set (19,586 unique
  pincodes, a plausible national count) — re-running this connector would
  now get the true complete set if/when it matters.

### Non-API sources (no resource ID; record access method instead)

| Source | Method | Status | Notes |
|---|---|---|---|
| MoSPI eSankhyiki (ASI, PLFS, IIP, NAS) | Portal download | `PENDING` | https://esankhyiki.mospi.gov.in — check whether the Macro Indicators API is usable; if so record the endpoint |
| RBI Handbook of Statistics on Indian States | Manual XLSX download | `PENDING` | https://rbi.org.in/Scripts/Statistics.aspx — commit the workbook to `data/reference/` with its edition year |
| GST statistics | PDF parse | `PENDING` | https://www.gst.gov.in/download/gststatistics |
| Open Budgets India | CKAN Action API | `PENDING` | https://openbudgetsindia.org — standard CKAN `package_search` |

## Output artefact

When complete, generate `backend/pipeline/connectors/resources.py`:

```python
# AUTO-GENERATED from docs/RESOURCE-REGISTRY.md — verified {date}
# Do not edit by hand. Re-run discovery if a resource breaks.

MCA_COMPANY_MASTER: dict[str, str] = {
    "RoC-Mumbai": "…",
    # …
}
UDYAM_DISTRICT_TOTAL = "…"
DPIIT_STARTUPS = "…"
LGD_STATES = "…"
LGD_DISTRICTS = "…"
LGD_PINCODES = "…"
CEA_POWER_SUPPLY = "…"
```

## Definition of done for Phase 0

- [ ] Every row above is `VERIFIED` or explicitly `NOT_FOUND` with a fallback recorded
- [ ] `resources.py` generated
- [ ] One sample response per source committed to `data/reference/samples/`
- [ ] Baseline row counts recorded (feeds the row-count sanity gate in `09-DATA-QUALITY.md`)
- [ ] A short written report of anything that differed from what this file expected
