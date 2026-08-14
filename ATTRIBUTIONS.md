# Data Attributions

All datasets used in this project are published by the Government of India under the
**Government Open Data License – India (GODL)**, gazetted February 2017 under the
National Data Sharing and Accessibility Policy (NDSAP).

GODL grants a worldwide, royalty-free, non-exclusive licence to use, adapt, publish,
translate, add value to, and create derivative works and services from the data, for
lawful commercial and non-commercial purposes, subject to attribution.

Licence: https://www.data.gov.in/Godl

**This project is not endorsed by, and makes no claim of endorsement by, the
Government of India.**

---

## Required attribution format

Each source below follows the GODL requirement to acknowledge provider, source,
licence, and URL. These strings are also stored in `gold.dim_source` and rendered
in the in-product source panel.

---

**Company Master Data**
Ministry of Corporate Affairs, Government of India. Accessed via the Open Government
Data (OGD) Platform India, https://www.data.gov.in/catalog/company-master-data
Licensed under GODL-India. Data vintage: {see dim_source.data_vintage}

**Udyam Registration (MSME Registration)**
Ministry of Micro, Small and Medium Enterprises, Government of India. Accessed via
https://www.data.gov.in/catalog/udyam-registration-msme-registration
Licensed under GODL-India.

**Startups Recognised by DPIIT**
Department for Promotion of Industry and Internal Trade, Government of India. Accessed
via https://www.data.gov.in/catalog/startup-recognized-dpiit
Licensed under GODL-India.

**Local Government Directory (LGD)**
Ministry of Panchayati Raj and Office of the Registrar General of India, Government of
India. Accessed via https://lgdirectory.gov.in and
https://www.data.gov.in/catalog/local-government-directory-lgd
Licensed under GODL-India.

**Power Supply Position**
Central Electricity Authority, Ministry of Power, Government of India. Accessed via
https://www.data.gov.in/catalog/power-supply-position
Licensed under GODL-India.

**Annual Survey of Industries, Periodic Labour Force Survey, Index of Industrial
Production, National Accounts Statistics**
Ministry of Statistics and Programme Implementation, Government of India. Accessed via
the eSankhyiki portal, https://esankhyiki.mospi.gov.in
Official statistics released under NDSAP.

**Handbook of Statistics on Indian States**
Reserve Bank of India. Accessed via the Database on Indian Economy,
https://data.rbi.org.in/DBIE/ and https://rbi.org.in/Scripts/Statistics.aspx
Used for research with courtesy attribution to the Database on Indian Economy, RBI.

**GST Statistics**
Goods and Services Tax Network / Ministry of Finance, Government of India. Accessed via
https://www.gst.gov.in/download/gststatistics and Press Information Bureau releases.

**State Budget Data**
Open Budgets India (Centre for Budget and Governance Accountability + CivicDataLab),
https://openbudgetsindia.org — and PRS Legislative Research,
https://prsindia.org/budgets/states (licensed CC BY 4.0).

**Census of India 2011**
Office of the Registrar General & Census Commissioner, Ministry of Home Affairs,
Government of India. Accessed via https://www.data.gov.in
Licensed under GODL-India. **Data vintage: 2011.**

---

## Map geometry (not GODL — a distinct licence, noted explicitly)

**India state boundaries (choropleth display only)**
`udit-001/india-maps-data` (GitHub), https://github.com/udit-001/india-maps-data —
**MIT licence**, not GODL-India. This is a third-party boundary/geometry dataset used
only to draw the state-level choropleth map on the frontend (`frontend/public/data/india-states.geojson`,
simplified locally via `mapshaper`); it carries no government statistical data of its
own and is not joined into `gold` — the underlying company/district data it's drawn
over is still resolved via LGD codes as required. Reflects the post-2019 state list
(Telangana, Ladakh, merged Dadra & Nagar Haveli/Daman & Diu present).

---

## Software licences

See `pyproject.toml` and `frontend/package.json`. All dependencies are permissively
licensed (MIT / BSD / Apache 2.0). Metabase (AGPL) and Superset (Apache 2.0), if used,
run as separate services and are not linked into this codebase.
