# 01 — Data Sources

Ten sources. All free. All verified live on 14 Aug 2026. All GODL-India or equivalent.

**Tier A** = verified free, active, machine-readable API.
**Tier B** = verified free and active, but no official API — file download or document parse.

No Tier C (unverified) source is used in this project. If you are tempted to add one,
raise it first.

---

## S01 — data.gov.in OGD Platform (transport layer)

| | |
|---|---|
| URL | https://www.data.gov.in |
| API | `https://api.data.gov.in/resource/{resource_id}` |
| Auth | Free API key, query param `api-key` |
| Registration | Free account required |
| Rate limit | **Not publicly documented.** Be conservative: 2 rps, max 4 concurrent. |
| Params | `format`, `limit`, `offset`, `filters[field]`, `fields`, `sort[field]` |
| Licence | GODL-India |
| Tier | **A** |

Carries S02, S03, S04, S08, S09, S19 below.

**Do not use the public sample key** — it caps at 10 records and will silently truncate
your loads.

---

## S02 — MCA Company Master Data — CORE SIGNAL

| | |
|---|---|
| Publisher | Ministry of Corporate Affairs |
| Catalog | https://www.data.gov.in/catalog/company-master-data |
| Access | S01 API, published **RoC-wise** (multiple resources) |
| Scale | ~3.67 million companies |
| Tier | **A** |

**Fields used:** `CIN`, `CompanyName`, `CompanyStatus`, `CompanyClass`,
`CompanyCategory`, `AuthorizedCapital`, `PaidupCapital`, `CompanyRegistrationdate_date`,
`Registered_Office_Address` (contains PIN), `Registrar_of_Companies`,
`PrincipalBusinessActivity` (NIC), `CompanyStateCode`.

**Why it matters:** `registration_date` + `state` + `NIC` + `paid_up_capital` gives you a
monthly time series of business formation by geography and industry, with capital
intensity. That is a real economic indicator, not a toy metric.

**Limitations — surface these:**
- Periodic **snapshot**, not a live feed. Valid for structural/historical analysis;
  invalid for live due diligence on a named company.
- **Registered office ≠ operating location.** Metro counts are inflated by companies
  that register in Mumbai/Delhi and operate elsewhere. Cross-check against ASI factory
  counts and flag divergence.
- Address parsing to PIN will fail on some records. Track resolution rate; target ≥85%.

---

## S03 — Udyam MSME Registration — GEOGRAPHY ANCHOR

| | |
|---|---|
| Publisher | Ministry of MSME |
| Catalog | https://www.data.gov.in/catalog/udyam-registration-msme-registration |
| Access | S01 API |
| Refresh | Confirmed updated 17 Mar 2026 |
| Tier | **A** |

**Fields:** state, district, **LGD district code**, enterprise counts split
Micro/Small/Medium and Manufacturing/Services.

**Why it matters twice over:** it is both an MSME density metric *and* the cleanest
district-level dataset that ships LGD codes natively. Use it to validate your geography
resolution.

**Limitation:** counts are **cumulative to date**, not flows. Monthly registration rate
must be derived by snapshotting and diffing. Build that as an SCD pattern — it
manufactures a time series nobody else has.

---

## S04 — DPIIT Recognised Startups

| | |
|---|---|
| Publisher | DPIIT / Startup India |
| Catalog | https://www.data.gov.in/catalog/startup-recognized-dpiit |
| Grain | year × state × industry, 2016→present |
| Refresh | Monthly release calendar |
| Size | ~8,550 rows |
| Tier | **A** |

**Limitation:** these are **counts, not funding amounts**. Never describe this as
measuring capital formation.

---

## S06 — MoSPI eSankhyiki (ASI, PLFS, IIP, NAS)

| | |
|---|---|
| Publisher | Ministry of Statistics and Programme Implementation |
| URL | https://esankhyiki.mospi.gov.in |
| Access | Portal download; Macro Indicators module supports API sharing — verify |
| Auth | None |
| Tier | **A** |

**ASI (Annual Survey of Industries)** is the crown jewel: factory count, fixed capital,
employment, wages, GVA by state × NIC. Closest thing India has to a manufacturing census.

**PLFS** gives state-level unemployment rate, LFPR, WPR.

**Limitation:** ASI lags 2–3 years. PLFS is annual. Do not promise real-time labour
analytics. Label every value with its survey year.

---

## S07 — RBI Handbook of Statistics on Indian States

| | |
|---|---|
| Publisher | Reserve Bank of India |
| URL | https://rbi.org.in/Scripts/Statistics.aspx · https://data.rbi.org.in/DBIE/ |
| Access | **XLSX download — Tier B for automation.** Download once, commit, version. |
| Coverage | Series from 1951 to 2024, 9th edition (2023-24) released Dec 2024 |
| Tier | **A** (data) / **B** (access) |

Single publication giving GSDP/GSVA (current and constant), per-capita income,
agriculture, industry, infrastructure, banking, and fiscal indicators — all state-wise,
consistently defined.

**Do not scrape DBIE live.** Download the workbook, commit it to
`data/reference/rbi/handbook_states_{edition}.xlsx`, and load from there. Pin the edition.

---

## S08 — CEA Power Supply Position

| | |
|---|---|
| Publisher | Central Electricity Authority, Ministry of Power |
| Catalog | https://www.data.gov.in/catalog/power-supply-position |
| Grain | state × month |
| Tier | **A** |

**Fields:** energy requirement vs availability (MU), peak demand vs peak met (MW),
energy deficit %, peak deficit %.

**Why it matters:** energy deficit is the most under-rated free industrial-siting
variable. Installed capacity tells you what exists; deficit tells you whether a factory
will actually get power.

Optional enrichment (Tier B, not required): daily Grid-India PSP reports at
https://report.grid-india.in/psp_report.php and National Power Portal daily reports at
https://npp.gov.in/publishedReports.

---

## S09 — Local Government Directory — THE JOIN KEY

| | |
|---|---|
| Publisher | Ministry of Panchayati Raj + Registrar General of India |
| URL | https://lgdirectory.gov.in |
| Catalog | https://www.data.gov.in/catalog/local-government-directory-lgd |
| Tier | **A** |

State / district / sub-district / block / village / local body codes, plus **PIN code
mapping**.

**This is the most important source in the project and it contains zero business
metrics.** LGD codes were mandated by the Cabinet Secretariat in Nov 2016 as the
standard location code across all e-governance applications, precisely so datasets could
be joined. Building geography on LGD instead of name strings is the decision that
separates a working India BI project from a broken one.

Archived versioned dumps: https://ramseraph.github.io/opendata/lgd/

**Load this before any fact data.**

---

## S13 — GST Statistics

| | |
|---|---|
| Publisher | GSTN / Ministry of Finance |
| URL | https://www.gst.gov.in/download/gststatistics |
| Monthly PDFs | `tutorial.gst.gov.in/downloads/news/` and PIB releases |
| Access | **PDF table extraction** |
| Tier | **B** |

State-wise gross GST collection (monthly) = best free monthly proxy for state economic
activity. State-wise active taxpayer count = best free proxy for formal business base.

**Limitations:** PDF layout drifts. State-wise splits are inconsistent in early years.
Build the parser defensively with strict assertions; **quarantine on parse failure, never
load a partial parse.**

---

## S16 — Open Budgets India + PRS

| | |
|---|---|
| URL | https://openbudgetsindia.org · https://prsindia.org/budgets/states |
| Access | **CKAN Action API** (OBI runs on CKAN) — genuine Tier A path |
| Auth | None |
| Licence | PRS content is CC BY 4.0 |
| Tier | **A** |

State capital expenditure — budgeted, revised, actual. This is what predicts future
infrastructure, and `actual ÷ budgeted` is a credible execution-capacity metric.

---

## S19 — Census of India 2011

| | |
|---|---|
| Publisher | Registrar General & Census Commissioner |
| Access | S01 API + censusindia.gov.in |
| Tier | **A** |

Population, households, sex ratio, literacy, urban/rural, worker classification — to
village level.

**Handle the vintage honestly.** The 2021 Census was not conducted on schedule. Use
Census 2011 for **structure and ratios** (which decay slowly), use official projections
for **population levels**, and label every Census-derived metric with `vintage = 2011`
in the UI. Silently presenting 2011 figures as current is the failure mode; disclosing
and handling it is the mark of competence.

---

## Excluded — do not add without discussion

| Source | Why excluded |
|---|---|
| `vahan.parivahan.gov.in/api/v1/vehicle/{reg_no}` | Unverified, and returns **personal data** — outside GODL scope. Never build this. |
| VAHAN aggregate dashboard | Real and free, but **no official API**. Optional Tier B enrichment only; not load-bearing. |
| RBI Basic Statistical Returns at district level | Unverified at district granularity. State level only via S07. |
| eNAM, NPCI, DGCA, port traffic, PPAC, IMD, PMGSY | Unverified as of 14 Aug 2026 |

Two verified structural facts that constrain design:
- DGCI&S does not disseminate transaction-level trade data.
- India does not freely publish state-wise exports at HS-code level.
