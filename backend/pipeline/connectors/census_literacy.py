"""Census 2011 Primary Census Abstract (literacy + worker classification),
district grain. Found via a Phase 2 research agent — NOT on data.gov.in,
lives on Census of India's own NADA microdata catalog. See
docs/RESOURCE-REGISTRY.md S19 for the full discovery writeup.

Static XLSX download (not a data.gov.in API resource, no pagination/filters).
Licence: ORGI's own attribution-required reuse terms, not GODL-India —
see ATTRIBUTIONS.md.
"""

import io
import subprocess
from datetime import UTC, date, datetime

import pandas as pd

from pipeline.connectors.base import BaseConnector, RawPayload, redact_api_key

SOURCE_URL = "https://censusindia.gov.in/nada/index.php/catalog/6191/download/9268/DDW_PCA0000_2011_Indiastatedist.xlsx"


def _download_via_curl(url: str, timeout: int) -> bytes:
    """censusindia.gov.in's TLS chain fails verification against Python's
    bundled certifi store (confirmed: even a bare ssl.create_default_context()
    fails) but validates fine against macOS's system trust store, which curl
    uses. This is a working, still-verifying validation path — not a
    verification bypass — for a server whose own cert chain configuration
    Python's cert bundle doesn't fully cover."""
    result = subprocess.run(
        ["curl", "-sS", "--fail", "-m", str(timeout), url],
        capture_output=True,
        check=True,
    )
    return result.stdout


class CensusLiteracyWorkerConnector(BaseConnector):
    source_code = "S19_CENSUS2011_PCA"
    expected_refresh_days = 3650  # one-time load, Census 2011 will not be refreshed

    def natural_key(self) -> list[str]:
        return ["State", "District"]

    def fetch(self) -> RawPayload:  # type: ignore[override]  # base takes **kwargs; this source needs none
        content = _download_via_curl(SOURCE_URL, timeout=60)

        df = pd.read_excel(io.BytesIO(content))
        # District-total rows only (Level=DISTRICT, TRU=Total) — the file
        # also carries India/State rows and Rural/Urban splits we don't need
        # here; state names are pulled from the STATE-level rows below.
        state_names = (
            df[(df["Level"] == "STATE") & (df["TRU"] == "Total")]
            .set_index("State")["Name"]
            .to_dict()
        )
        district_rows = df[(df["Level"] == "DISTRICT") & (df["TRU"] == "Total")].copy()
        district_rows["state_name"] = district_rows["State"].map(state_names)

        records = district_rows.to_dict("records")
        return RawPayload(
            source_code=self.source_code,
            fetched_at=datetime.now(UTC).isoformat(),
            records=records,
            observed_schema={c: str(district_rows[c].dtype) for c in district_rows.columns},
            total_available=len(records),
            request_url=redact_api_key(SOURCE_URL),
        )


if __name__ == "__main__":
    import json

    connector = CensusLiteracyWorkerConnector()
    payload = connector.fetch()
    print(f"fetched {len(payload.records)} district rows")
    bronze_path = connector.write_bronze(payload, date.today())
    print(json.dumps({"bronze_path": bronze_path, "rows": len(payload.records)}, indent=2))
