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

from pipeline.geography.resolver import normalise


def compute(state_lgd_code: int) -> list[dict]:
    conn = psycopg.connect(settings.database_url.replace("+psycopg", ""))

    # NOTE: dim_geography.district_census2011_code (from LGD) and
    # silver.census_population_district's own codes are NOT the same
    # numbering scheme — confirmed by cross-checking Alappuzha (LGD: '598',
    # this resource: '11') and Goa's districts. Two different sources both
    # calling their column "census 2011 code" does not mean the values are
    # comparable. Joining on normalised district NAME (scoped by state)
    # instead — see STATUS.md for the full finding.
    rows = conn.execute(
        """
        SELECT
            g.district_name,
            g.lgd_district_code,
            date_trunc('month', fc.incorporation_date)::date AS month,
            count(*) AS new_incorporations
        FROM gold.fact_company fc
        JOIN gold.dim_geography g ON g.geo_key = fc.geo_key
        WHERE g.lgd_state_code = %s
          AND fc.incorporation_date IS NOT NULL
          AND (fc.quality_flags & 4) = 0  -- exclude QUALITY_BIT_OUTLIER (flagged, not deleted, per rule 4)
        GROUP BY g.district_name, g.lgd_district_code, date_trunc('month', fc.incorporation_date)
        ORDER BY g.district_name, month
        """,
        (state_lgd_code,),
    ).fetchall()

    population_by_name = {
        normalise(district_name): population_total
        for (district_name, population_total) in conn.execute(
            "SELECT district_name, population_total_2011 FROM silver.census_population_district"
        ).fetchall()
    }

    results = []
    for district_name, district_code, month, new_incorp in rows:
        population = population_by_name.get(normalise(district_name))
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
