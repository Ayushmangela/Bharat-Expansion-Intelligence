"""Census 2011 population connector.

Loads silver.census_population_district as a reference crosswalk table
(NOT part of the gold star schema — see STATUS.md for why: docs/03-DATA-MODEL.md's
DDL has no population column on any Phase-1 table, and adding one is a star-schema
change that needs a conversation per CLAUDE.md rule "Ask before scope changes").
State/District Code on this source are Census's OWN codes, not LGD — resolved
via dim_geography.state_census2011_code / district_census2011_code, never a
direct join. See docs/RESOURCE-REGISTRY.md S19.
"""

from datetime import UTC, date, datetime

import psycopg
from app.config import settings

from pipeline.connectors.base import BaseConnector, RawPayload, redact_api_key
from pipeline.connectors.datagovin_client import DataGovInClient
from pipeline.connectors.resources import CENSUS_2011_POPULATION


class CensusConnector(BaseConnector):
    source_code = "S19_CENSUS2011"
    expected_refresh_days = 3650  # one-time load; Census 2011 will not be refreshed

    def __init__(self) -> None:
        self.client = DataGovInClient()

    def natural_key(self) -> list[str]:
        return ["state_code", "district_code"]

    def fetch(self) -> RawPayload:  # type: ignore[override]  # base takes **kwargs; this source needs none
        records, total, field_schema = self.client.fetch_all(CENSUS_2011_POPULATION, batch_size=1000)
        url = f"{settings.data_gov_in_base_url}/resource/{CENSUS_2011_POPULATION}?api-key={settings.data_gov_in_api_key}"
        return RawPayload(
            source_code=self.source_code,
            fetched_at=datetime.now(UTC).isoformat(),
            records=records,
            observed_schema={f["name"]: f.get("type") for f in field_schema},
            total_available=total,
            request_url=redact_api_key(url),
        )


def load() -> dict:
    connector = CensusConnector()
    conn = psycopg.connect(settings.database_url.replace("+psycopg", ""))

    payload = connector.fetch()
    bronze_path = connector.write_bronze(payload, date.today())

    n_loaded, n_skipped = 0, 0
    for r in payload.records:
        # NOTE: the `field` schema block advertises pretty names ("State Code"),
        # but actual records use snake_case field ids (state_code). Same
        # schema-vs-record mismatch pattern seen in LGD local bodies
        # (docs/RESOURCE-REGISTRY.md S07/S09) — trust record keys, not `field`.
        state_c2011 = str(r.get("state_code") or "").strip()
        district_c2011 = str(r.get("district_code") or "").strip()
        state_name = str(r.get("state") or "").strip()
        district_name = str(r.get("districts") or "").strip()
        if state_c2011 in ("", "INDIA") or district_c2011 in ("", "NA", "STATE", "INDIA"):
            n_skipped += 1
            continue
        try:
            total_pop = int(float(r.get("population___total___2011") or 0))
        except (TypeError, ValueError):
            n_skipped += 1
            continue

        conn.execute(
            """
            INSERT INTO silver.census_population_district
                (state_census2011_code, district_census2011_code, state_name, district_name,
                 population_total_2011, population_rural_2011, population_urban_2011)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (state_census2011_code, district_census2011_code) DO NOTHING
            """,
            (
                state_c2011,
                district_c2011,
                state_name,
                district_name,
                total_pop,
                int(float(r.get("population___rural___2011") or 0)),
                int(float(r.get("population___urban___2011") or 0)),
            ),
        )
        n_loaded += 1
    conn.commit()
    conn.close()
    connector.client.close()

    return {
        "rows_fetched": len(payload.records),
        "rows_loaded": n_loaded,
        "rows_skipped": n_skipped,
        "bronze_path": bronze_path,
    }


if __name__ == "__main__":
    import json

    print(json.dumps(load(), indent=2))
