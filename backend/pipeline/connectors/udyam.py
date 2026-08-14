"""Udyam MSME (district-wise) connector.

Two resources: total and services-only district enterprise counts. Both
carry a genuine LGD district code (`lg_dt_code`) — confirmed in Phase 0
discovery, no geography_alias resolution needed, direct join to
gold.dim_geography.

Udyam is cumulative-to-date with no date field of its own (CLAUDE.md known
limitation). The ingest date IS the snapshot date.
"""

from datetime import UTC, date, datetime

from app.config import settings

from pipeline.connectors.base import BaseConnector, RawPayload, redact_api_key
from pipeline.connectors.datagovin_client import DataGovInClient
from pipeline.connectors.resources import UDYAM_DISTRICT_SERVICES, UDYAM_DISTRICT_TOTAL


class UdyamConnector(BaseConnector):
    source_code = "S03_UDYAM"
    expected_refresh_days = 30

    def __init__(self) -> None:
        self.client = DataGovInClient()

    def natural_key(self) -> list[str]:
        return ["lg_dt_code"]

    def fetch(self, resource_id: str) -> RawPayload:  # type: ignore[override]
        records, total, field_schema = self.client.fetch_all(resource_id, batch_size=1000)
        url = f"{settings.data_gov_in_base_url}/resource/{resource_id}?api-key={settings.data_gov_in_api_key}"
        return RawPayload(
            source_code=self.source_code,
            fetched_at=datetime.now(UTC).isoformat(),
            records=records,
            observed_schema={f["name"]: f.get("type") for f in field_schema},
            total_available=total,
            request_url=redact_api_key(url),
        )

    def fetch_both(self) -> tuple[RawPayload, RawPayload]:
        return self.fetch(UDYAM_DISTRICT_TOTAL), self.fetch(UDYAM_DISTRICT_SERVICES)


if __name__ == "__main__":
    import json

    connector = UdyamConnector()
    total_payload, services_payload = connector.fetch_both()
    print(f"total: {len(total_payload.records)} rows, services: {len(services_payload.records)} rows")
    t_path = connector.write_bronze(total_payload, date.today(), partition="total")
    s_path = connector.write_bronze(services_payload, date.today(), partition="services")
    print(json.dumps({"total_bronze": t_path, "services_bronze": s_path}, indent=2))
    connector.client.close()
