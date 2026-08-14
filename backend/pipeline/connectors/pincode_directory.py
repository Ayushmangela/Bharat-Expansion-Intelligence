"""All India Pincode Directory (Dept of Posts) connector.

Loads silver.pincode_district_lookup — a direct pincode -> (state, district)
text crosswalk, used by the geography resolver's Step 4 as a stronger
alternative to the LGD local-body PIN join (which only resolves PINs whose
local body is itself a District Panchayat entity, ~60% coverage).
"""

from datetime import UTC, date

import psycopg
from app.config import settings

from pipeline.connectors.base import BaseConnector, RawPayload, redact_api_key
from pipeline.connectors.datagovin_client import DataGovInClient
from pipeline.connectors.resources import ALL_INDIA_PINCODE_DIRECTORY


class PincodeDirectoryConnector(BaseConnector):
    source_code = "S_PINCODE_DIR"
    expected_refresh_days = 180

    def __init__(self) -> None:
        self.client = DataGovInClient()

    def natural_key(self) -> list[str]:
        return ["pincode"]

    def fetch(self) -> RawPayload:  # type: ignore[override]  # base takes **kwargs; this source needs none
        records, total, field_schema = self.client.fetch_all(ALL_INDIA_PINCODE_DIRECTORY, batch_size=1000)
        from datetime import datetime

        url = f"{settings.data_gov_in_base_url}/resource/{ALL_INDIA_PINCODE_DIRECTORY}?api-key={settings.data_gov_in_api_key}"
        return RawPayload(
            source_code=self.source_code,
            fetched_at=datetime.now(UTC).isoformat(),
            records=records,
            observed_schema={f["name"]: f.get("type") for f in field_schema},
            total_available=total,
            request_url=redact_api_key(url),
        )


def load() -> dict:
    connector = PincodeDirectoryConnector()
    conn = psycopg.connect(settings.database_url.replace("+psycopg", ""))

    payload = connector.fetch()
    bronze_path = connector.write_bronze(payload, date.today())

    n_loaded = 0
    n_skipped = 0
    for r in payload.records:
        pincode = str(r.get("pincode") or "").strip().split(".")[0]
        district = (r.get("district") or "").strip()
        state = (r.get("statename") or "").strip()
        if len(pincode) != 6 or not pincode.isdigit() or not district or not state:
            n_skipped += 1
            continue
        conn.execute(
            """
            INSERT INTO silver.pincode_district_lookup (pincode, observed_state, observed_district)
            VALUES (%s, %s, %s)
            ON CONFLICT (pincode) DO NOTHING
            """,
            (pincode, state, district),
        )
        n_loaded += 1
    conn.commit()
    conn.close()
    connector.client.close()

    return {
        "rows_fetched": len(payload.records),
        "rows_loaded_unique_pincodes": n_loaded,
        "rows_skipped": n_skipped,
        "bronze_path": bronze_path,
    }


if __name__ == "__main__":
    import json

    print(json.dumps(load(), indent=2))
