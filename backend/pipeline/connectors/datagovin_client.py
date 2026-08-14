import time

import httpx
from app.config import settings


class DataGovInClient:
    """Thin, polite client for api.data.gov.in resources.

    Retry policy per docs/04-ETL-PIPELINE.md: retryable on 429/5xx/timeouts,
    exponential backoff capped at 60s, max settings.http_max_retries attempts.
    Not retryable: 4xx other than 429 -> fail fast.
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
        """
        offset = 0
        all_records: list[dict] = []
        total = None
        field_schema: list[dict] = []

        while True:
            page = self._get_page(resource_id, offset=offset, limit=batch_size, filters=filters)
            if total is None:
                total = page.get("total")
                field_schema = page.get("field", [])
            records = page.get("records", [])
            all_records.extend(records)
            time.sleep(1.0 / settings.http_requests_per_second)
            if not records or len(all_records) >= (total or 0):
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
            time.sleep(1.0 / settings.http_requests_per_second)
        raise RuntimeError(f"Exceeded retries fetching {resource_id}") from last_exc

    def close(self) -> None:
        self._client.close()
