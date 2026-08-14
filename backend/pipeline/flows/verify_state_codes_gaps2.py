from pipeline.connectors.datagovin_client import DataGovInClient
from pipeline.connectors.resources import MCA_COMPANY_MASTER

CANDIDATES = {
    "Chhattisgarh": ["chhatisgarh", "chattishgarh", "c.g.", "cg", "chhattisgarh(cg)", "chhattishgarh (cg)"],
    "DNHDD": [
        "dadra and nagar haveli and daman and diu",
        "dadra and nagar haveli and daman & diu",
        "dadra & nagar haveli",
        "dadra and nagar haveli & daman and diu",
        "the dadra and nagar haveli and daman and diu",
    ],
}

client = DataGovInClient()
for state, cands in CANDIDATES.items():
    print(f"--- {state} ---")
    for c in cands:
        page = client.fetch_page(MCA_COMPANY_MASTER, offset=0, limit=1, filters={"CompanyStateCode": c})
        print(f"  '{c}' -> total={page.get('total', 0)}")
client.close()
