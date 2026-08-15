"""Resolves silver.census_literacy_worker_district rows to LGD codes,
through GeographyResolver — same pattern as census_silver.py for the
population table. See that module's docstring for why code-based joins
between different Census-sourced tables are unsafe (confirmed: different
sources' own "census codes" are not the same numbering scheme).
"""

from datetime import date

import pandas as pd
import psycopg
from app.config import settings
from psycopg.types.json import Json

from pipeline.geography.resolver import GeographyResolver


def parse_int(value: object) -> int:
    try:
        if pd.isna(value):  # type: ignore[arg-type]
            return 0
        return int(value)  # type: ignore[call-overload]
    except (TypeError, ValueError):
        return 0


def resolve_all(ingest_date: date | None = None) -> dict:
    ingest_date = ingest_date or date.today()
    parquet_path = f"{settings.bronze_path}/source=S19_CENSUS2011_PCA/ingest_date={ingest_date.isoformat()}/part-000.parquet"
    df = pd.read_parquet(parquet_path)

    conn = psycopg.connect(settings.database_url.replace("+psycopg", ""))
    resolver = GeographyResolver(conn)

    n_resolved, n_quarantined = 0, 0
    method_counts: dict[str, int] = {}

    for _, row in df.iterrows():
        state_code = str(row["State"])
        district_code = str(row["District"])
        state_name = str(row["state_name"])
        district_name = str(row["Name"])

        resolution = resolver.resolve(observed_state=state_name, observed_district=district_name)
        method_counts[resolution.method] = method_counts.get(resolution.method, 0) + 1

        total_p = parse_int(row["TOT_P"])
        p_06 = parse_int(row["P_06"])

        conn.execute(
            """
            INSERT INTO silver.census_literacy_worker_district
                (state_census2011_code, district_census2011_code, state_name, district_name,
                 lgd_state_code, lgd_district_code, resolution_method,
                 population_total, population_0_6, population_6plus,
                 literates, illiterates, total_workers, main_workers,
                 main_cultivators, main_agri_labourers, main_household_industry, main_other_workers,
                 marginal_workers, non_workers)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (state_census2011_code, district_census2011_code) DO UPDATE SET
                lgd_state_code = EXCLUDED.lgd_state_code, lgd_district_code = EXCLUDED.lgd_district_code,
                resolution_method = EXCLUDED.resolution_method
            """,
            (
                state_code,
                district_code,
                state_name,
                district_name,
                resolution.lgd_state_code,
                resolution.lgd_district_code,
                resolution.method,
                total_p,
                p_06,
                total_p - p_06,
                parse_int(row["P_LIT"]),
                parse_int(row["P_ILL"]),
                parse_int(row["TOT_WORK_P"]),
                parse_int(row["MAINWORK_P"]),
                parse_int(row["MAIN_CL_P"]),
                parse_int(row["MAIN_AL_P"]),
                parse_int(row["MAIN_HH_P"]),
                parse_int(row["MAIN_OT_P"]),
                parse_int(row["MARGWORK_P"]),
                parse_int(row["NON_WORK_P"]),
            ),
        )

        if resolution.lgd_district_code is None:
            n_quarantined += 1
            conn.execute(
                """
                INSERT INTO silver.geography_quarantine
                    (load_id, source_code, observed_state, observed_district, raw_row, resolved)
                VALUES (NULL, 'S19_CENSUS2011_PCA', %s, %s, %s, false)
                """,
                (state_name, district_name, Json({"state_code": state_code, "district_code": district_code})),
            )
        else:
            n_resolved += 1

    conn.commit()
    conn.close()

    return {
        "rows_total": len(df),
        "rows_resolved": n_resolved,
        "rows_quarantined": n_quarantined,
        "resolution_rate": round(n_resolved / len(df), 4) if len(df) else 0.0,
        "method_counts": method_counts,
    }


if __name__ == "__main__":
    import json

    print(json.dumps(resolve_all(), indent=2))
