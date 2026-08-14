from pipeline.connectors.datagovin_client import DataGovInClient
from pipeline.connectors.resources import MCA_COMPANY_MASTER

CANDIDATES = {
    "Chhattisgarh": ["chattisgarh", "chhattisgarh ", "chhattishgarh"],
    "Jammu And Kashmir": ["jammu & kashmir", "jammu and kashmir ", "j&k", "jammu-and-kashmir"],
    "Odisha": ["orissa", "odisha "],
    "Puducherry": ["pondicherry", "puducherry "],
    "The Dadra And Nagar Haveli And Daman And Diu": [
        "dadra and nagar haveli",
        "daman and diu",
        "dadra & nagar haveli and daman & diu",
        "dnh and dd",
    ],
}

client = DataGovInClient()
for state, cands in CANDIDATES.items():
    print(f"--- {state} ---")
    for c in cands:
        page = client.fetch_page(MCA_COMPANY_MASTER, offset=0, limit=1, filters={"CompanyStateCode": c})
        print(f"  '{c}' -> total={page.get('total', 0)}")
client.close()
