from pipeline.connectors.datagovin_client import DataGovInClient
from pipeline.connectors.resources import MCA_COMPANY_MASTER

CANDIDATES = ["ROC Chhattisgarh", "ROC Raipur", "ROC-Chhattisgarh", "Chhattisgarh"]

client = DataGovInClient()
for c in CANDIDATES:
    page = client.fetch_page(MCA_COMPANY_MASTER, offset=0, limit=2, filters={"CompanyROCcode": c})
    print(f"CompanyROCcode='{c}' -> total={page.get('total', 0)} sample={page.get('records', [])[:1]}")
client.close()
