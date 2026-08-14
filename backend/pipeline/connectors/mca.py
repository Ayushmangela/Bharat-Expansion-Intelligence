"""MCA Company Master Data connector.

Filtered by CompanyStateCode since the resource is now unified (see
docs/RESOURCE-REGISTRY.md S02) rather than split per-RoC as originally
planned.

Concurrent: once `total` is known from the first page, remaining pages are
fetched in parallel (ThreadPoolExecutor, up to settings.http_max_concurrency
workers) against the shared rate limiter in datagovin_client.py — matching
docs/09-DATA-QUALITY.md's "token bucket, 2 rps, max 4 concurrent" design,
which existed on paper but was never actually wired up (everything ran fully
sequential before this). This is a real speedup for large states: Delhi
(~508 pages) went from latency-bound sequential fetching to rate-limit-bound
concurrent fetching.

Checkpointed by completed offset (not a single last_offset scalar, since
concurrent pages complete out of order) so a crash partway through resumes
only the missing pages rather than restarting the whole state.
"""

import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime
from pathlib import Path

from app.config import settings

from pipeline.connectors.base import BaseConnector, RawPayload, redact_api_key
from pipeline.connectors.datagovin_client import DataGovInClient
from pipeline.connectors.resources import MCA_COMPANY_MASTER

CHECKPOINT_DIR = Path(settings.bronze_path).parent / "checkpoints"
CHECKPOINT_WRITE_EVERY = 25  # pages between checkpoint writes; full I/O every page is costly at scale


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

    def _fetch_page_with_anomaly_retry(self, state_filter: str, offset: int, batch_size: int, filters: dict, total: int, known_so_far: int) -> list[dict]:
        """BUG FOUND live during the Phase 2 sweep: the server is occasionally
        flaky at deep pagination offsets and returns HTTP 200 with an EMPTY
        records list even though `total` says far more data exists (confirmed
        transient — the exact same offset succeeded moments later). Treating
        any empty page as "done" silently truncated Delhi to 203,000 of
        507,637 rows (60% loss) before this was caught. Fix: retry the same
        offset with backoff, and raise rather than silently return an empty
        result if it never recovers.
        """
        page = self.client.fetch_page(MCA_COMPANY_MASTER, offset=offset, limit=batch_size, filters=filters)
        page_records = page.get("records", [])
        if page_records or known_so_far >= total:
            return page_records

        for attempt in range(settings.http_max_retries):
            sleep_s = min(1 * (2**attempt), 60)
            time.sleep(sleep_s)
            retry_page = self.client.fetch_page(MCA_COMPANY_MASTER, offset=offset, limit=batch_size, filters=filters)
            page_records = retry_page.get("records", [])
            if page_records:
                return page_records

        raise RuntimeError(
            f"MCA state={state_filter}: empty page at offset={offset} persisted after "
            f"{settings.http_max_retries} retries, but total={total} implies more records exist — "
            f"refusing to silently truncate."
        )

    def fetch_state(self, state_filter: str, batch_size: int = 1000) -> RawPayload:
        ckpt_path = self._checkpoint_path(state_filter)
        filters = {"CompanyStateCode": state_filter}

        records_by_offset: dict[int, list[dict]] = {}
        if ckpt_path.exists():
            ckpt = json.loads(ckpt_path.read_text())
            records_by_offset = {int(k): v for k, v in ckpt.get("records_by_offset", {}).items()}

        first_page = self.client.fetch_page(MCA_COMPANY_MASTER, offset=0, limit=batch_size, filters=filters)
        total = first_page.get("total") or 0
        field_schema = first_page.get("field", [])
        if 0 not in records_by_offset:
            records_by_offset[0] = first_page.get("records", [])

        all_offsets = list(range(0, total, batch_size))
        remaining_offsets = [o for o in all_offsets if o not in records_by_offset]

        lock = threading.Lock()
        completed_since_checkpoint = 0

        def fetch_one(offset: int) -> None:
            nonlocal completed_since_checkpoint
            # BUG FOUND live on Karnataka (258 pages — enough concurrent
            # traffic to hit it): reading records_by_offset.values() here
            # without the lock raced against other threads' `with lock:`
            # writes below, causing "RuntimeError: dictionary changed size
            # during iteration". Smaller states didn't have enough
            # concurrent pages to expose it. Fixed by taking the lock for
            # the read too.
            with lock:
                known_so_far = sum(len(v) for v in records_by_offset.values())
            page_records = self._fetch_page_with_anomaly_retry(state_filter, offset, batch_size, filters, total, known_so_far)
            with lock:
                records_by_offset[offset] = page_records
                completed_since_checkpoint += 1
                if completed_since_checkpoint >= CHECKPOINT_WRITE_EVERY:
                    completed_since_checkpoint = 0
                    ckpt_path.write_text(json.dumps({"records_by_offset": {str(k): v for k, v in records_by_offset.items()}}))

        if remaining_offsets:
            with ThreadPoolExecutor(max_workers=settings.http_max_concurrency) as pool:
                list(pool.map(fetch_one, remaining_offsets))

        ckpt_path.unlink(missing_ok=True)

        records = [r for offset in sorted(records_by_offset) for r in records_by_offset[offset]]

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
