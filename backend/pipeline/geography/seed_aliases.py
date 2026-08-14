"""Loads data/reference/geography_alias_seed.csv into silver.geography_alias."""

import csv
from pathlib import Path

import psycopg
from app.config import settings

from pipeline.geography.resolver import normalise

SEED_PATH = Path(settings.reference_path) / "geography_alias_seed.csv"


def seed() -> dict:
    conn = psycopg.connect(settings.database_url.replace("+psycopg", ""))

    states = {
        normalise(name): code
        for code, name in conn.execute(
            "SELECT lgd_state_code, state_name FROM gold.dim_geography WHERE grain = 'state' AND is_current"
        ).fetchall()
    }
    districts = {
        (code, normalise(name)): dcode
        for code, dcode, name in conn.execute(
            "SELECT lgd_state_code, lgd_district_code, district_name FROM gold.dim_geography "
            "WHERE grain = 'district' AND is_current"
        ).fetchall()
    }

    inserted, skipped = 0, []
    with open(SEED_PATH, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            lgd_state_code = states.get(normalise(row["lgd_state_name"]))
            if lgd_state_code is None:
                skipped.append((row, "lgd_state_name not found"))
                continue

            lgd_district_code = None
            if row.get("lgd_district_name"):
                lgd_district_code = districts.get((lgd_state_code, normalise(row["lgd_district_name"])))
                if lgd_district_code is None:
                    skipped.append((row, "lgd_district_name not found"))
                    continue

            conn.execute(
                """
                INSERT INTO silver.geography_alias
                    (observed_state, observed_district, lgd_state_code, lgd_district_code, match_method, confidence)
                VALUES (%s, %s, %s, %s, 'manual', 1.0)
                ON CONFLICT (observed_state, COALESCE(observed_district, '')) DO NOTHING
                """,
                (
                    row["observed_state"] or "",
                    row["observed_district"] or None,
                    lgd_state_code,
                    lgd_district_code,
                ),
            )
            inserted += 1
    conn.commit()
    conn.close()
    return {"inserted": inserted, "skipped": skipped}


if __name__ == "__main__":
    result = seed()
    print(f"inserted={result['inserted']}")
    for row, reason in result["skipped"]:
        print(f"SKIPPED: {row} -- {reason}")
