# AUTO-GENERATED from docs/RESOURCE-REGISTRY.md — verified 2026-08-14
# Do not edit by hand. Re-run discovery (see docs/RESOURCE-REGISTRY.md) if a resource
# breaks, and regenerate this file from the updated registry.

DATA_GOV_IN_BASE_URL = "https://api.data.gov.in"

# --- S02: MCA Company Master Data ---
# Unified single resource (NOT split per-RoC as originally expected).
# Filter by CompanyROCcode field if a per-RoC subset is needed.
MCA_COMPANY_MASTER = "4dbe5667-7b6b-41d7-82af-211562424d9a"

# --- S03: Udyam MSME, district-wise ---
# lg_dt_code field is a genuine LGD district code — join directly, no alias needed.
UDYAM_DISTRICT_TOTAL = "f8cd85a1-f9b8-4ff1-b195-9f75c10eb338"
UDYAM_DISTRICT_SERVICES = "c3dfe7e6-0cfd-4ddb-8f79-9cb3695d9866"

# --- S04: DPIIT Recognised Startups ---
# NOT_FOUND: no api.data.gov.in resource exists. Data is a "Sourced Webservice"
# pointing at startupindia.gov.in with no documented public API found so far.
DPIIT_STARTUPS: str | None = None

# --- All India Pincode Directory (Dept of Posts) ---
# Added mid-Phase-1 after the resolver checkpoint showed LGD's local-body PIN
# join only resolves ~60% of PIN codes to a district directly (most PINs map
# to sub-district local bodies, not District Panchayats). This resource has
# a clean pincode -> district field intended for exactly this purpose.
ALL_INDIA_PINCODE_DIRECTORY = "5c2f62fe-5afa-4119-a499-fec9d604d5bd"

# --- S07/S09: Local Government Directory (LGD) — load first, everything joins to it ---
LGD_STATES = "a71e60f0-a21d-43de-a6c5-fa5d21600cdb"
LGD_DISTRICTS = "37231365-78ba-44d5-ac22-3deec40b9197"
LGD_SUB_DISTRICTS = "6be51a29-876a-403a-a6da-42fde795e751"
LGD_LOCAL_BODIES = "1a6c26ed-d67c-40ea-aa20-d38d35f341a5"
LGD_LOCAL_BODIES_PINCODES = "71818d1a-c114-46cb-aa9b-56ed70d4bc4a"

# --- S08: CEA Power Supply Position ---
# BROKEN: no stable resource. A new resource is published per month with the month
# baked into column names; nothing newer than 2023 found on data.gov.in as of this
# discovery run. Kept only as a schema reference — do not build a connector against
# a single hardcoded ID here. See docs/RESOURCE-REGISTRY.md S08 for the CEA fallback.
CEA_POWER_SUPPLY_SAMPLE_ONLY = "59b6cf39-6093-4da7-b9c9-6fe68ecff587"  # Oct 2014, reference only

# --- S19: Census 2011 ---
# State/District Code fields on this resource are Census's own codes, not LGD —
# resolve through geography_alias, never join directly.
CENSUS_2011_POPULATION = "c9fee525-1c00-4ac2-969c-17bf42d2cc0a"
# Literacy and worker-classification (district-wise, all-India) not yet found —
# PENDING further discovery. See docs/RESOURCE-REGISTRY.md S19.
CENSUS_2011_LITERACY: str | None = None
CENSUS_2011_WORKER_CLASSIFICATION: str | None = None
