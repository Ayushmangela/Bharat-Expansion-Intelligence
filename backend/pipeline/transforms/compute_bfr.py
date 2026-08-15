"""Business Formation Rate for one state, district x month grain.

BFR = new_incorporations_in_period / working_age_population * 100_000
(docs/05-KPI-DEFINITIONS.md)

Known deviation, documented not hidden: Census 2011's district-grain PCA
table (silver.census_literacy_worker_district, loaded in Phase 2 — see
docs/RESOURCE-REGISTRY.md S19) has no clean 15-59 age bucket, only a 0-6
split. population_6plus (total minus under-6) is used as a real improvement
over the earlier total-population proxy, but it is still NOT the same as
"working-age (15-59)" — it includes the elderly, and the field name/output
key say "6plus", never "working_age", so this cannot be silently mistaken
for the KPI's literal definition. Falls back to total population 2011
(silver.census_population_district) for any district not yet resolved in
the newer literacy/worker table.
"""

import json

import psycopg
from app.config import settings


def compute(state_lgd_code: int) -> list[dict]:
    conn = psycopg.connect(settings.database_url.replace("+psycopg", ""))

    # Both census tables are joined via lgd_state_code/lgd_district_code,
    # resolved once at load time through GeographyResolver (same pattern for
    # both — see census_silver.py and census_literacy_silver.py). This
    # replaced an earlier ad-hoc normalised-name dict join that had no state
    # scoping and was silently wrong for any ambiguous district name.
    rows = conn.execute(
        """
        SELECT
            g.district_name,
            g.lgd_district_code,
            date_trunc('month', fc.incorporation_date)::date AS month,
            count(*) AS new_incorporations,
            lw.population_6plus,
            pop.population_total_2011
        FROM gold.fact_company fc
        JOIN gold.dim_geography g ON g.geo_key = fc.geo_key
        LEFT JOIN silver.census_literacy_worker_district lw
            ON lw.lgd_state_code = g.lgd_state_code AND lw.lgd_district_code = g.lgd_district_code
        LEFT JOIN silver.census_population_district pop
            ON pop.lgd_state_code = g.lgd_state_code AND pop.lgd_district_code = g.lgd_district_code
        WHERE g.lgd_state_code = %s
          AND fc.incorporation_date IS NOT NULL
          AND (fc.quality_flags & 4) = 0  -- exclude QUALITY_BIT_OUTLIER (flagged, not deleted, per rule 4)
        GROUP BY g.district_name, g.lgd_district_code, date_trunc('month', fc.incorporation_date),
                 lw.population_6plus, pop.population_total_2011
        ORDER BY g.district_name, month
        """,
        (state_lgd_code,),
    ).fetchall()

    results = []
    for district_name, district_code, month, new_incorp, pop_6plus, pop_total in rows:
        denominator = pop_6plus if pop_6plus else pop_total
        denominator_source = "population_6plus" if pop_6plus else ("population_total_2011" if pop_total else None)
        bfr = round(new_incorp / denominator * 100_000, 3) if denominator else None
        results.append(
            {
                "district": district_name,
                "lgd_district_code": district_code,
                "month": month.isoformat(),
                "new_incorporations": new_incorp,
                "denominator_source": denominator_source,
                "denominator_value": denominator,
                "bfr_proxy_per_100k": bfr,
            }
        )

    conn.close()
    return results


if __name__ == "__main__":
    import sys

    state_code = int(sys.argv[1]) if len(sys.argv) > 1 else 30  # Goa's LGD state_code
    out = compute(state_code)
    print(json.dumps(out, indent=2, default=str))
