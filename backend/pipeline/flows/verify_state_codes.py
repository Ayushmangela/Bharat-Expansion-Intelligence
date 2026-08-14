"""One-off: verify the exact CompanyStateCode filter string for every state
before committing to the full national MCA sweep."""

from pipeline.connectors.datagovin_client import DataGovInClient
from pipeline.connectors.resources import MCA_COMPANY_MASTER

STATES = [
    "Andaman And Nicobar Islands", "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar",
    "Chandigarh", "Chhattisgarh", "Delhi", "Goa", "Gujarat", "Haryana", "Himachal Pradesh",
    "Jammu And Kashmir", "Jharkhand", "Karnataka", "Kerala", "Ladakh", "Lakshadweep",
    "Madhya Pradesh", "Maharashtra", "Manipur", "Meghalaya", "Mizoram", "Nagaland", "Odisha",
    "Puducherry", "Punjab", "Rajasthan", "Sikkim", "Tamil Nadu", "Telangana",
    "The Dadra And Nagar Haveli And Daman And Diu", "Tripura", "Uttarakhand", "Uttar Pradesh",
    "West Bengal",
]

client = DataGovInClient()

results = {}
for state in STATES:
    candidate = state.lower()
    page = client.fetch_page(MCA_COMPANY_MASTER, offset=0, limit=1, filters={"CompanyStateCode": candidate})
    total = page.get("total", 0)
    results[state] = {"tried": candidate, "total": total}
    print(f"{state:50s} -> '{candidate}' total={total}")

client.close()

grand_total = sum(r["total"] for r in results.values())
zero_states = [s for s, r in results.items() if r["total"] == 0]
print(f"\ngrand_total={grand_total} (expected ~3,674,314)")
print(f"zero-result states: {zero_states}")
