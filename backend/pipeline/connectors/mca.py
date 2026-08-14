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
        """BUG FOUND live during the Phase 2 sweep: the server is occasionally
        flaky at deep pagination offsets and returns HTTP 200 with an EMPTY
        records list even though `total` says far more data exists (confirmed
        transient — the exact same offset succeeded moments later). The
        original loop here treated any empty page as "done," which silently
        truncated Delhi to 203,000 of 507,637 rows (60% loss) before this was
        caught. Fixed: an empty page only means "done" if consistent with
        `total`; otherwise retry the same offset with backoff, and raise
        rather than silently truncate if it never recovers — the checkpoint
        stays in place (not deleted) so a raised error is resumable, same as
        any other failure.
        """
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
                total = page.get("total") or 0
                field_schema = page.get("field", [])
            page_records = page.get("records", [])

            if not page_records and len(records) < total:
                for attempt in range(settings.http_max_retries):
                    sleep_s = min(1 * (2**attempt), 60)
                    time.sleep(sleep_s)
                    retry_page = self.client.fetch_page(MCA_COMPANY_MASTER, offset=offset, limit=batch_size, filters=filters)
                    page_records = retry_page.get("records", [])
                    if page_records:
                        break
                if not page_records:
                    raise RuntimeError(
                        f"MCA state={state_filter}: empty page at offset={offset} persisted after "
                        f"{settings.http_max_retries} retries, but total={total} implies "
                        f"{total - len(records)} more records — refusing to silently truncate. "
                        f"Checkpoint preserved at {ckpt_path}, safe to re-run."
                    )

            records.extend(page_records)
            offset += batch_size
            time.sleep(1.0 / settings.http_requests_per_second)

            ckpt_path.write_text(json.dumps({"last_offset": offset, "records": records}))

            if not page_records or len(records) >= total:
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
