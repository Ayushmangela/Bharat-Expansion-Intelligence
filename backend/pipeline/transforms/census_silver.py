"""Resolves silver.census_population_district rows to LGD codes.

Runs each row's (state, district) text through GeographyResolver — the same
resolver MCA uses — rather than the ad-hoc normalised-name dict compute_bfr.py
used for the Goa/Bihar checkpoint. That dict was keyed only by district name
with no state scoping, silently wrong for any of the 3 genuinely-ambiguous
district names found in Phase 1 (Bilaspur, Hamirpur, Pratapgarh). See
STATUS.md item 13/14.

Unresolved rows are quarantined, same as MCA — nothing reaches a resolved
state silently wrong.
"""

import psycopg
from app.config import settings
from psycopg.types.json import Json

from pipeline.geography.resolver import GeographyResolver


def resolve_all() -> dict:
    conn = psycopg.connect(settings.database_url.replace("+psycopg", ""))
    resolver = GeographyResolver(conn)

    rows = conn.execute(
        "SELECT state_census2011_code, district_census2011_code, state_name, district_name "
        "FROM silver.census_population_district"
    ).fetchall()

    n_resolved = 0
    n_quarantined = 0
    method_counts: dict[str, int] = {}

    for state_c2011, district_c2011, state_name, district_name in rows:
        resolution = resolver.resolve(observed_state=state_name, observed_district=district_name)
        method_counts[resolution.method] = method_counts.get(resolution.method, 0) + 1

        if resolution.lgd_district_code is None:
            n_quarantined += 1
            conn.execute(
                """
                INSERT INTO silver.geography_quarantine
                    (load_id, source_code, observed_state, observed_district, raw_row, best_guess_lgd, resolved)
                VALUES (NULL, 'S19_CENSUS2011', %s, %s, %s, %s, false)
                """,
                (
                    state_name,
                    district_name,
                    Json({"state_census2011_code": state_c2011, "district_census2011_code": district_c2011}),
                    resolution.lgd_state_code,
                ),
            )
            continue

        conn.execute(
            """
            UPDATE silver.census_population_district
            SET lgd_state_code = %s, lgd_district_code = %s, resolution_method = %s
            WHERE state_census2011_code = %s AND district_census2011_code = %s
            """,
            (resolution.lgd_state_code, resolution.lgd_district_code, resolution.method, state_c2011, district_c2011),
        )
        n_resolved += 1

    conn.commit()
    conn.close()

    return {
        "rows_total": len(rows),
        "rows_resolved": n_resolved,
        "rows_quarantined": n_quarantined,
        "resolution_rate": round(n_resolved / len(rows), 4) if rows else 0.0,
        "method_counts": method_counts,
    }


if __name__ == "__main__":
    import json

    print(json.dumps(resolve_all(), indent=2))
