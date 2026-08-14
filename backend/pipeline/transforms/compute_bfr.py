"""Business Formation Rate for one state, district x month grain.

BFR = new_incorporations_in_period / working_age_population * 100_000
(docs/05-KPI-DEFINITIONS.md)

Known deviation, documented not hidden: "working age population" (15-59) is
not available — Census 2011 literacy/worker-classification tables were not
found in Phase 0 discovery (see docs/RESOURCE-REGISTRY.md S19, PENDING).
This uses TOTAL population 2011 as the denominator instead, which is what's
actually available right now. The KPI number below is therefore a proxy,
not the KPI as formally defined, and is labelled as such in the output.
"""

import json

import psycopg
from app.config import settings


def compute(state_lgd_code: int) -> list[dict]:
    conn = psycopg.connect(settings.database_url.replace("+psycopg", ""))

    # Census population is joined via lgd_state_code/lgd_district_code,
    # resolved once at load time by pipeline/transforms/census_silver.py
    # through the same GeographyResolver MCA uses (98.75% national
    # resolution; the 8 unresolved are genuine post-2011 district splits
    # with no single correct target — see STATUS.md). This replaced an
    # earlier ad-hoc normalised-name dict join that had no state scoping
    # and was silently wrong for any ambiguous district name.
    rows = conn.execute(
        """
        SELECT
            g.district_name,
            g.lgd_district_code,
            date_trunc('month', fc.incorporation_date)::date AS month,
            count(*) AS new_incorporations,
            c.population_total_2011
        FROM gold.fact_company fc
        JOIN gold.dim_geography g ON g.geo_key = fc.geo_key
        LEFT JOIN silver.census_population_district c
            ON c.lgd_state_code = g.lgd_state_code AND c.lgd_district_code = g.lgd_district_code
        WHERE g.lgd_state_code = %s
          AND fc.incorporation_date IS NOT NULL
          AND (fc.quality_flags & 4) = 0  -- exclude QUALITY_BIT_OUTLIER (flagged, not deleted, per rule 4)
        GROUP BY g.district_name, g.lgd_district_code, date_trunc('month', fc.incorporation_date), c.population_total_2011
        ORDER BY g.district_name, month
        """,
        (state_lgd_code,),
    ).fetchall()

    results = []
    for district_name, district_code, month, new_incorp, population in rows:
        bfr = None
        if population and population > 0:
            bfr = round(new_incorp / population * 100_000, 3)
        results.append(
            {
                "district": district_name,
                "lgd_district_code": district_code,
                "month": month.isoformat(),
                "new_incorporations": new_incorp,
                "population_total_2011": population,
                "bfr_proxy_per_100k_total_pop": bfr,
            }
        )

    conn.close()
    return results


if __name__ == "__main__":
    import sys

    state_code = int(sys.argv[1]) if len(sys.argv) > 1 else 30  # Goa's LGD state_code
    out = compute(state_code)
    print(json.dumps(out, indent=2, default=str))
