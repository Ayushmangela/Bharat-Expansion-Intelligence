import time

import httpx
from app.config import settings

from pipeline.connectors.rate_limiter import TokenBucketLimiter

# Process-wide shared limiter — matches docs/09-DATA-QUALITY.md's "token
# bucket, 2 rps, max 4 concurrent" exactly. Shared across ALL DataGovInClient
# instances (and therefore all threads using them) so the rate cap is
# actually global, not per-instance.
_shared_limiter = TokenBucketLimiter(
    rate_per_second=settings.http_requests_per_second,
    max_concurrent=settings.http_max_concurrency,
)


class DataGovInClient:
    """Thin, polite client for api.data.gov.in resources.

    Retry policy per docs/04-ETL-PIPELINE.md: retryable on 429/5xx/timeouts,
    exponential backoff capped at 60s, max settings.http_max_retries attempts.
    Not retryable: 4xx other than 429 -> fail fast.

    Thread-safe: httpx.Client is documented safe for concurrent use across
    threads, and the shared TokenBucketLimiter above serialises the actual
    rate/concurrency ceiling. Callers may share one DataGovInClient instance
    across a ThreadPoolExecutor.
    """

    def __init__(self) -> None:
        self._client = httpx.Client(
            base_url=settings.data_gov_in_base_url,
            timeout=settings.http_timeout_seconds,
            headers={"User-Agent": settings.user_agent},
        )

    def fetch_all(self, resource_id: str, batch_size: int = 1000, filters: dict | None = None) -> tuple[list[dict], int, list[dict]]:
        """Fetch every record from a resource, paginating via offset/limit.

        Returns (records, total_available, observed_field_schema).

        BUG FOUND live during the Phase 2 MCA sweep: the server is
        occasionally flaky at deep pagination offsets and returns HTTP 200
        with an EMPTY records list even when `total` says far more data
        exists (confirmed transient — re-querying the exact same offset
        moments later succeeded normally; not a fixed depth ceiling). The
        original version here treated any empty page as "reached the end,"
        which silently truncated results (Delhi: 203,000 of 507,637 rows —
        a 60% loss — before this was caught). This almost certainly also
        explains the earlier, smaller pincode-directory shortfall
        (165,627 of 184,740) that was previously written off as an
        unexplained "quirk" — same bug, smaller blast radius. Fix: an empty
        page only means "done" if it's consistent with `total`; otherwise
        retry the SAME offset with backoff, and raise rather than silently
        truncate if it never recovers.
        """
        offset = 0
        all_records: list[dict] = []
        total = None
        field_schema: list[dict] = []
        max_empty_retries = settings.http_max_retries

        while True:
            page = self._get_page(resource_id, offset=offset, limit=batch_size, filters=filters)
            if total is None:
                total = page.get("total") or 0
                field_schema = page.get("field", [])
            records = page.get("records", [])

            if not records and len(all_records) < total:
                for attempt in range(max_empty_retries):
                    sleep_s = min(1 * (2**attempt), 60)
                    time.sleep(sleep_s)
                    retry_page = self._get_page(resource_id, offset=offset, limit=batch_size, filters=filters)
                    records = retry_page.get("records", [])
                    if records:
                        break
                if not records:
                    raise RuntimeError(
                        f"{resource_id}: empty page at offset={offset} persisted after "
                        f"{max_empty_retries} retries, but total={total} implies "
                        f"{total - len(all_records)} more records — refusing to silently truncate"
                    )

            all_records.extend(records)
            if not records or len(all_records) >= total:
                break
            offset += batch_size

        return all_records, total or len(all_records), field_schema

    def fetch_page(self, resource_id: str, offset: int, limit: int, filters: dict | None = None) -> dict:
        return self._get_page(resource_id, offset=offset, limit=limit, filters=filters)

    def _get_page(self, resource_id: str, offset: int, limit: int, filters: dict | None = None) -> dict:
        params: dict[str, str | int] = {
            "api-key": settings.data_gov_in_api_key,
            "format": "json",
            "limit": limit,
            "offset": offset,
        }
        if filters:
            for k, v in filters.items():
                params[f"filters[{k}]"] = v

        last_exc: Exception | None = None
        for attempt in range(settings.http_max_retries):
            try:
                with _shared_limiter:
                    resp = self._client.get(f"/resource/{resource_id}", params=params)
                if resp.status_code == 429 or resp.status_code >= 500:
                    raise httpx.HTTPStatusError("retryable", request=resp.request, response=resp)
                resp.raise_for_status()
                return resp.json()
            except httpx.HTTPStatusError as e:
                if e.response is not None and 400 <= e.response.status_code < 500 and e.response.status_code != 429:
                    raise  # not retryable
                last_exc = e
            except (httpx.TimeoutException, httpx.TransportError) as e:
                last_exc = e
            sleep_s = min(1 * (2**attempt), 60)
            time.sleep(sleep_s)
        raise RuntimeError(f"Exceeded retries fetching {resource_id}") from last_exc

    def close(self) -> None:
        self._client.close()
