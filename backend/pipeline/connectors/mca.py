"""MCA Company Master Data connector.

Phase 1 scope: one state, not the full ~3.67M-row sweep (that's Phase 2).
Filtered by CompanyStateCode since the resource is now unified (see
docs/RESOURCE-REGISTRY.md S02) rather than split per-RoC as originally
planned — filtering by state serves "compute BFR for one state" directly.

Checkpointed: persists (resource_id, filters, last_offset) to a small json
file so a crash partway through resumes rather than restarting at 0.
"""

import json
import time
from datetime import UTC, date, datetime
from pathlib import Path

from app.config import settings

from pipeline.connectors.base import BaseConnector, RawPayload, redact_api_key
from pipeline.connectors.datagovin_client import DataGovInClient
from pipeline.connectors.resources import MCA_COMPANY_MASTER

CHECKPOINT_DIR = Path(settings.bronze_path).parent / "checkpoints"


class MCAConnector(BaseConnector):
    source_code = "S02_MCA"
    expected_refresh_days = 30

    def __init__(self) -> None:
        self.client = DataGovInClient()

    def natural_key(self) -> list[str]:
        return ["CIN"]

    def _checkpoint_path(self, state_filter: str) -> Path:
        CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
        return CHECKPOINT_DIR / f"mca_{state_filter}.json"

    def fetch_state(self, state_filter: str, batch_size: int = 1000) -> RawPayload:
        ckpt_path = self._checkpoint_path(state_filter)
        offset = 0
        records: list[dict] = []
        if ckpt_path.exists():
            ckpt = json.loads(ckpt_path.read_text())
            offset = ckpt.get("last_offset", 0)
            records = ckpt.get("records", [])

        total = None
        field_schema: list[dict] = []
        filters = {"CompanyStateCode": state_filter}

        while True:
            page = self.client.fetch_page(MCA_COMPANY_MASTER, offset=offset, limit=batch_size, filters=filters)
            if total is None:
                total = page.get("total")
                field_schema = page.get("field", [])
            page_records = page.get("records", [])
            records.extend(page_records)
            offset += batch_size
            time.sleep(1.0 / settings.http_requests_per_second)

            ckpt_path.write_text(json.dumps({"last_offset": offset, "records": records}))

            if not page_records or len(records) >= (total or 0):
                break

        ckpt_path.unlink(missing_ok=True)

        url = f"{settings.data_gov_in_base_url}/resource/{MCA_COMPANY_MASTER}?api-key={settings.data_gov_in_api_key}&filters[CompanyStateCode]={state_filter}"
        return RawPayload(
            source_code=self.source_code,
            fetched_at=datetime.now(UTC).isoformat(),
            records=records,
            observed_schema={f["name"]: f.get("type") for f in field_schema},
            total_available=total,
            request_url=redact_api_key(url),
        )

    def fetch(self, **kwargs) -> RawPayload:
        return self.fetch_state(kwargs["state_filter"])


if __name__ == "__main__":
    import sys

    state = sys.argv[1] if len(sys.argv) > 1 else "goa"
    connector = MCAConnector()
    payload = connector.fetch_state(state)
    print(f"fetched {len(payload.records)} / {payload.total_available} for state={state}")
    bronze_path = connector.write_bronze(payload, date.today(), partition=f"state={state}")
    print(f"bronze: {bronze_path}")
    connector.client.close()
