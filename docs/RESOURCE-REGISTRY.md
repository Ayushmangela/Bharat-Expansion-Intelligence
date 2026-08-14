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
- Note: published **RoC-wise**, so expect MULTIPLE resource IDs (one per Registrar of
  Companies), not one. Record all of them.
- Status: `PENDING`
- Resource IDs: _(fill in — expect ~25 RoC resources)_
- Expected fields: `CIN`, `CompanyName`, `CompanyStatus`, `CompanyClass`,
  `CompanyCategory`, `CompanySubCategory`, `AuthorizedCapital`, `PaidupCapital`,
  `CompanyRegistrationdate_date`, `Registered_Office_Address`, `Registrar_of_Companies`,
  `PrincipalBusinessActivity`, `CompanyStateCode`
- Actual fields observed: _(fill in)_
- Total rows: _(fill in — should aggregate to ~3.67M)_

### S03 — Udyam MSME (district-wise)
- Catalog: https://www.data.gov.in/catalog/udyam-registration-msme-registration
- Known resource slugs:
  - `district-wise-total-msme-registered-enterprises-under-udyam-registration-till-last-date`
  - `district-wise-services-msme-registered-enterprises-under-udyam-registration-till-last-date`
- Status: `PENDING`
- Resource IDs: _(fill in)_
- **Critical: confirm the LGD district code field is present.** This dataset is
  documented as carrying LGD codes and that makes it your geography anchor.
- Actual fields observed: _(fill in)_

### S04 — DPIIT Recognised Startups
- Catalog: https://www.data.gov.in/catalog/startup-recognized-dpiit
- Slug: `industry-state-and-year-wise-startups-recognized-dpiit-till-last-week`
- Status: `PENDING`
- Resource ID: _(fill in)_
- Expected grain: year × state × industry. Expected size ~8,550 rows.

### S07/S09 — Local Government Directory
- Catalog: https://www.data.gov.in/catalog/local-government-directory-lgd
- Slugs: `local-government-directory-lgd-states`,
  `local-government-directory-lgd-districts`,
  `local-government-directory-lgd-sub-districts`,
  `local-government-directory-lgd-local-bodies`,
  `local-government-directory-lgd-local-bodies-pin-codes`
- Status: `PENDING`
- Resource IDs: _(fill in)_
- **Load this FIRST. Everything joins to it.**
- Fallback if the API is incomplete: direct CSV export from https://lgdirectory.gov.in,
  or the archived dumps at https://ramseraph.github.io/opendata/lgd/

### S08 — CEA Power Supply Position
- Catalog: https://www.data.gov.in/catalog/power-supply-position
- Status: `PENDING`
- Resource ID: _(fill in)_
- Expected grain: state × month. Fields: energy requirement/availability (MU),
  peak demand/met (MW), deficits (%).

### S19 — Census 2011
- Status: `PENDING`
- Resource IDs: _(fill in — need district-level population, literacy, worker
  classification)_
- **Tag everything from this source with vintage = 2011.**

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
