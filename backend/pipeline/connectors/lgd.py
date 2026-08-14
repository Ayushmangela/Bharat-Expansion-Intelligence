"""LGD (Local Government Directory) connector.

Loads gold.dim_geography (SCD-2) from LGD states + districts, and
silver.lgd_pincode_lookup from LGD local-bodies-with-PIN-codes. This must run
before any other connector — everything else resolves geography against it.
"""

from datetime import UTC, date, datetime

import psycopg
from app.config import settings
from psycopg.types.json import Json

from pipeline.connectors.base import BaseConnector, RawPayload, redact_api_key
from pipeline.connectors.datagovin_client import DataGovInClient
from pipeline.connectors.resources import (
    LGD_DISTRICTS,
    LGD_LOCAL_BODIES,
    LGD_LOCAL_BODIES_PINCODES,
    LGD_STATES,
    LGD_SUB_DISTRICTS,
)


class LGDConnector(BaseConnector):
    source_code = "S07_S09_LGD"
    expected_refresh_days = 90

    def __init__(self) -> None:
        self.client = DataGovInClient()

    def natural_key(self) -> list[str]:
        return ["lgd_state_code", "lgd_district_code"]

    def fetch(self, resource_id: str, filters: dict | None = None) -> RawPayload:  # type: ignore[override]
        records, total, field_schema = self.client.fetch_all(resource_id, batch_size=1000, filters=filters)
        url = f"{settings.data_gov_in_base_url}/resource/{resource_id}?api-key={settings.data_gov_in_api_key}"
        return RawPayload(
            source_code=self.source_code,
            fetched_at=datetime.now(UTC).isoformat(),
            records=records,
            observed_schema={f["name"]: f.get("type") for f in field_schema},
            total_available=total,
            request_url=redact_api_key(url),
        )


def _get_conn() -> psycopg.Connection:
    return psycopg.connect(settings.database_url.replace("+psycopg", ""))


def _start_run(conn: psycopg.Connection, source_code: str) -> int:
    conn.execute(
        """
        INSERT INTO meta.source (source_code, source_name, publisher, url, licence,
            attribution_text, access_method, tier)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (source_code) DO NOTHING
        """,
        (
            source_code,
            "Local Government Directory",
            "Ministry of Panchayati Raj",
            "https://www.data.gov.in/catalog/local-government-directory-lgd",
            "GODL-India",
            (
                "Ministry of Panchayati Raj, Local Government Directory (LGD), GODL-India, "
                "https://www.data.gov.in/catalog/local-government-directory-lgd"
            ),
            "api",
            "A",
        ),
    )
    row = conn.execute(
        "SELECT source_key FROM meta.source WHERE source_code = %s", (source_code,)
    ).fetchone()
    assert row is not None
    source_key = row[0]
    run = conn.execute(
        """
        INSERT INTO meta.ingestion_run (source_key, status)
        VALUES (%s, 'running') RETURNING load_id
        """,
        (source_key,),
    ).fetchone()
    assert run is not None
    conn.commit()
    return run[0]


def _finish_run(conn: psycopg.Connection, load_id: int, rows_fetched: int, rows_loaded: int, bronze_path: str, schema: dict) -> None:
    conn.execute(
        """
        UPDATE meta.ingestion_run
        SET finished_at = now(), status = 'success', rows_fetched = %s,
            rows_loaded = %s, rows_quarantined = 0, bronze_path = %s, observed_schema = %s
        WHERE load_id = %s
        """,
        (rows_fetched, rows_loaded, bronze_path, Json(schema), load_id),
    )
    conn.commit()


def load_states_and_districts(as_of: date | None = None) -> dict:
    """Loads gold.dim_geography with state-grain and district-grain rows.

    Returns a dict of counts for reporting.
    """
    as_of = as_of or date.today()
    connector = LGDConnector()
    conn = _get_conn()

    load_id = _start_run(conn, connector.source_code)

    states_payload = connector.fetch(LGD_STATES)
    districts_payload = connector.fetch(LGD_DISTRICTS)

    states_bronze = connector.write_bronze(states_payload, as_of, partition="states")
    districts_bronze = connector.write_bronze(districts_payload, as_of, partition="districts")

    n_state_rows = 0
    for r in states_payload.records:
        conn.execute(
            """
            INSERT INTO gold.dim_geography
                (lgd_state_code, lgd_district_code, state_name, district_name,
                 state_census2011_code, district_census2011_code, grain, valid_from, is_current)
            VALUES (%s, NULL, %s, NULL, %s, NULL, 'state', %s, true)
            ON CONFLICT (lgd_state_code, COALESCE(lgd_district_code, -1), valid_from) DO NOTHING
            """,
            (
                int(r["state_code"]),
                r["state_name_english"].strip(),
                r.get("state_census2011_code"),
                as_of,
            ),
        )
        n_state_rows += 1

    n_district_rows = 0
    n_district_skipped = 0
    for r in districts_payload.records:
        if r.get("district_code") in (None, "", "NA"):
            n_district_skipped += 1
            continue
        conn.execute(
            """
            INSERT INTO gold.dim_geography
                (lgd_state_code, lgd_district_code, state_name, district_name,
                 state_census2011_code, district_census2011_code, grain, valid_from, is_current)
            VALUES (%s, %s, %s, %s, %s, %s, 'district', %s, true)
            ON CONFLICT (lgd_state_code, COALESCE(lgd_district_code, -1), valid_from) DO NOTHING
            """,
            (
                int(r["state_code"]),
                int(r["district_code"]),
                r["state_name_english"].strip(),
                r["district_name_english"].strip(),
                r.get("state_census2011_code"),
                r.get("district_census2011_code"),
                as_of,
            ),
        )
        n_district_rows += 1

    conn.commit()

    # --- Sub-districts (talukas/tehsils), for resolver Step 4c ---
    subdistrict_payload = connector.fetch(LGD_SUB_DISTRICTS)
    subdistrict_bronze = connector.write_bronze(subdistrict_payload, as_of, partition="sub_districts")
    n_subdistrict_rows = 0
    for r in subdistrict_payload.records:
        if r.get("district_code") in (None, "", "NA") or r.get("subdistrict_code") in (None, ""):
            continue
        conn.execute(
            """
            INSERT INTO silver.lgd_subdistrict_lookup
                (lgd_state_code, lgd_district_code, subdistrict_code, subdistrict_name)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (lgd_state_code, subdistrict_code) DO NOTHING
            """,
            (
                int(r["state_code"]),
                int(r["district_code"]),
                int(r["subdistrict_code"]),
                r["subdistrict_name_english"].strip(),
            ),
        )
        n_subdistrict_rows += 1
    conn.commit()

    # --- District-entity local bodies (for resolver Step 4) ---
    # Only rows where the local body's own coverage entity IS a district
    # (i.e. "District Panchayat" type bodies). This resolves the subset of
    # PIN codes whose local body maps directly to district grain; most PINs
    # map to sub-district (block/village) local bodies and will NOT resolve
    # via this path — those fall through to Step 5 (fuzzy address match) or
    # Step 6 (quarantine). Documented limitation, not a bug.
    district_entities_payload = connector.fetch(LGD_LOCAL_BODIES, filters={"entityType": "District"})
    local_body_to_district: dict[int, int] = {}
    for r in district_entities_payload.records:
        try:
            local_body_to_district[int(r["localBodyCode"])] = int(r["entityCode"])
        except (KeyError, ValueError, TypeError):
            continue

    # --- PIN lookup (for resolver Step 4) ---
    pin_payload = connector.fetch(LGD_LOCAL_BODIES_PINCODES)
    pin_bronze = connector.write_bronze(pin_payload, as_of, partition="local_bodies_pincodes")

    n_pin_rows = 0
    n_pin_skipped = 0
    n_pin_district_resolved = 0
    for r in pin_payload.records:
        pincode = str(r.get("pincode") or "").strip()
        if len(pincode) != 6 or not pincode.isdigit():
            n_pin_skipped += 1
            continue
        local_body_code = int(r["localBodyCode"])
        district_code = local_body_to_district.get(local_body_code)
        if district_code is not None:
            n_pin_district_resolved += 1
        conn.execute(
            """
            INSERT INTO silver.lgd_pincode_lookup
                (pincode, lgd_state_code, local_body_code, local_body_name, lgd_district_code)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (pincode, local_body_code) DO NOTHING
            """,
            (
                pincode,
                int(r["stateCode"]),
                local_body_code,
                r.get("localBodyNameEnglish"),
                district_code,
            ),
        )
        n_pin_rows += 1
    conn.commit()

    _finish_run(
        conn,
        load_id,
        rows_fetched=(
            len(states_payload.records) + len(districts_payload.records)
            + len(subdistrict_payload.records) + len(pin_payload.records)
        ),
        rows_loaded=n_state_rows + n_district_rows + n_subdistrict_rows + n_pin_rows,
        bronze_path=f"{states_bronze};{districts_bronze};{subdistrict_bronze};{pin_bronze}",
        schema={
            **states_payload.observed_schema,
            **districts_payload.observed_schema,
            **subdistrict_payload.observed_schema,
            **pin_payload.observed_schema,
        },
    )

    conn.close()
    connector.client.close()

    return {
        "states_fetched": len(states_payload.records),
        "states_loaded": n_state_rows,
        "districts_fetched": len(districts_payload.records),
        "districts_loaded": n_district_rows,
        "districts_skipped_no_code": n_district_skipped,
        "pin_rows_fetched": len(pin_payload.records),
        "pin_rows_loaded": n_pin_rows,
        "pin_rows_skipped": n_pin_skipped,
        "pin_rows_district_resolved": n_pin_district_resolved,
        "subdistrict_rows_fetched": len(subdistrict_payload.records),
        "subdistrict_rows_loaded": n_subdistrict_rows,
    }


if __name__ == "__main__":
    import json

    result = load_states_and_districts()
    print(json.dumps(result, indent=2))
