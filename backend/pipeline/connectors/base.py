from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pandas as pd
from app.config import settings


@dataclass
class RawPayload:
    source_code: str
    fetched_at: str
    records: list[dict]
    observed_schema: dict
    total_available: int | None
    request_url: str  # api-key REDACTED before storing


def redact_api_key(url: str) -> str:
    import re

    return re.sub(r"(api-key=)[^&]+", r"\1REDACTED", url)


class BaseConnector(ABC):
    source_code: str
    expected_refresh_days: int

    @abstractmethod
    def fetch(self, **kwargs) -> RawPayload: ...

    @abstractmethod
    def natural_key(self) -> list[str]:
        """Columns forming the idempotency key."""

    def write_bronze(self, payload: RawPayload, ingest_date: date, partition: str | None = None) -> str:
        """Parquet -> data/bronze/source={code}/ingest_date={date}/[partition=.../]part.parquet
        Append-only. Never overwrite."""
        parts = [settings.bronze_path, f"source={payload.source_code}", f"ingest_date={ingest_date.isoformat()}"]
        if partition:
            parts.append(partition)
        out_dir = Path(*parts)
        out_dir.mkdir(parents=True, exist_ok=True)

        existing = list(out_dir.glob("part-*.parquet"))
        part_path = out_dir / f"part-{len(existing):03d}.parquet"

        # Bronze stores raw responses verbatim (rule 12) — cast every column
        # to string so mixed types within a single field (observed here: a
        # numeric column with stray "NA" string values from Census) can't
        # break Arrow's type inference. Any typing happens in the silver
        # transform, never here.
        df = pd.DataFrame.from_records(payload.records).astype(str)
        df.to_parquet(part_path, index=False)
        return str(part_path)
