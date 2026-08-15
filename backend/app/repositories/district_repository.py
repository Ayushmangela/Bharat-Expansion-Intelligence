"""All SQL for district-level reads lives here (rule: routers never touch
the database, services never write SQL — docs/02-ARCHITECTURE.md).

Raw ingested data (company counts, MSME breakdowns, geography resolution
stats) — the scored Opportunity Score / SHAP / counterfactual endpoints
live in scoring_repository.py instead. Uses raw psycopg, consistent with
the rest of the pipeline (backend/pipeline/ already established this
pattern) rather than introducing SQLAlchemy ORM models for a read-only
slice — that's a Phase 5 decision, not this one.
"""

import psycopg

from app.config import settings


def get_conn() -> psycopg.Connection:
    return psycopg.connect(settings.database_url.replace("+psycopg", ""))


# Whitelist of sortable columns — never interpolate the client-supplied sort key
# directly into SQL. Values are the actual ORDER BY expressions (aliases where the
# column is an aggregate, qualified names otherwise).
_SORTABLE_COLUMNS = {
    "company_count": "company_count",
    "active_company_count": "active_company_count",
    "district_name": "g.district_name",
    "state_name": "g.state_name",
}


def list_districts(
    state_code: int | None,
    q: str | None,
    limit: int,
    offset: int,
    sort: str = "company_count",
    direction: str = "desc",
) -> tuple[list[dict], int]:
    conn = get_conn()
    where = ["g.grain = 'district'", "g.is_current"]
    params: list = []
    if state_code is not None:
        where.append("g.lgd_state_code = %s")
        params.append(state_code)
    if q:
        where.append("g.district_name ILIKE %s")
        params.append(f"%{q}%")
    where_sql = " AND ".join(where)

    total = conn.execute(f"SELECT count(*) FROM gold.dim_geography g WHERE {where_sql}", params).fetchone()[0]  # type: ignore[index]

    order_col = _SORTABLE_COLUMNS.get(sort, "company_count")
    order_dir = "ASC" if direction.lower() == "asc" else "DESC"

    rows = conn.execute(
        f"""
        SELECT g.lgd_district_code, g.district_name, g.state_name, g.lgd_state_code,
               count(fc.company_key) AS company_count,
               count(fc.company_key) FILTER (WHERE s.is_active) AS active_company_count,
               fdm.msme_micro, fdm.msme_small, fdm.msme_medium, fdm.msme_manufacturing, fdm.msme_services
        FROM gold.dim_geography g
        LEFT JOIN gold.fact_company fc ON fc.geo_key = g.geo_key
        LEFT JOIN gold.dim_company_status s ON s.status_key = fc.status_key
        LEFT JOIN gold.fact_district_month fdm ON fdm.geo_key = g.geo_key
            AND fdm.date_key = (SELECT max(date_key) FROM gold.fact_district_month WHERE geo_key = g.geo_key)
        WHERE {where_sql}
        GROUP BY g.lgd_district_code, g.district_name, g.state_name, g.lgd_state_code,
                 fdm.msme_micro, fdm.msme_small, fdm.msme_medium, fdm.msme_manufacturing, fdm.msme_services
        ORDER BY {order_col} {order_dir} NULLS LAST
        LIMIT %s OFFSET %s
        """,
        [*params, limit, offset],
    ).fetchall()
    conn.close()

    items = [
        {
            "lgd_district_code": r[0],
            "district_name": r[1],
            "state_name": r[2],
            "lgd_state_code": r[3],
            "company_count": r[4],
            "active_company_count": r[5],
            "msme_micro": r[6],
            "msme_small": r[7],
            "msme_medium": r[8],
            "msme_manufacturing": r[9],
            "msme_services": r[10],
        }
        for r in rows
    ]
    return items, total


def get_district(lgd_district_code: int) -> dict | None:
    conn = get_conn()
    geo = conn.execute(
        """
        SELECT geo_key, lgd_district_code, district_name, state_name, lgd_state_code, area_sq_km
        FROM gold.dim_geography WHERE lgd_district_code = %s AND grain = 'district' AND is_current
        """,
        (lgd_district_code,),
    ).fetchone()
    if not geo:
        conn.close()
        return None
    geo_key = geo[0]

    status_breakdown = conn.execute(
        """
        SELECT s.status_name, count(*) FROM gold.fact_company fc
        JOIN gold.dim_company_status s ON s.status_key = fc.status_key
        WHERE fc.geo_key = %s GROUP BY s.status_name ORDER BY count(*) DESC
        """,
        (geo_key,),
    ).fetchall()

    msme = conn.execute(
        "SELECT msme_micro, msme_small, msme_medium, msme_manufacturing, msme_services FROM gold.fact_district_month "
        "WHERE geo_key = %s ORDER BY date_key DESC LIMIT 1",
        (geo_key,),
    ).fetchone()

    monthly_incorporations = conn.execute(
        """
        SELECT date_trunc('month', incorporation_date)::date AS month, count(*)
        FROM gold.fact_company WHERE geo_key = %s AND incorporation_date IS NOT NULL AND (quality_flags & 4) = 0
        GROUP BY 1 ORDER BY 1 DESC LIMIT 24
        """,
        (geo_key,),
    ).fetchall()

    conn.close()

    return {
        "geography": {
            "lgd_district_code": geo[1],
            "district_name": geo[2],
            "state_name": geo[3],
            "lgd_state_code": geo[4],
            "area_sq_km": float(geo[5]) if geo[5] else None,
        },
        "company_status_breakdown": [{"status": s, "count": c} for s, c in status_breakdown],
        "msme": (
            {"micro": msme[0], "small": msme[1], "medium": msme[2], "manufacturing": msme[3], "services": msme[4]}
            if msme
            else None
        ),
        "monthly_incorporations": [{"month": m.isoformat(), "count": c} for m, c in monthly_incorporations],
    }


def state_summary() -> list[dict]:
    """Company counts by state, for every state/UT in the LGD geography table —
    including states with zero ingested companies yet, so callers (e.g. the
    state choropleth) can distinguish 'zero' from 'not yet ingested'."""
    conn = get_conn()
    rows = conn.execute(
        """
        SELECT g.state_name, g.lgd_state_code,
               count(DISTINCT g.lgd_district_code) AS total_districts,
               count(DISTINCT fc.geo_key) AS districts_with_data,
               count(fc.company_key) AS company_count
        FROM gold.dim_geography g
        LEFT JOIN gold.fact_company fc ON fc.geo_key = g.geo_key
        WHERE g.grain = 'district' AND g.is_current
        GROUP BY g.state_name, g.lgd_state_code
        ORDER BY company_count DESC NULLS LAST
        """
    ).fetchall()
    conn.close()
    return [
        {
            "state_name": r[0],
            "lgd_state_code": r[1],
            "total_districts": r[2],
            "districts_with_data": r[3],
            "company_count": r[4],
        }
        for r in rows
    ]


def national_overview() -> dict:
    conn = get_conn()
    row = conn.execute(
        """
        SELECT
            (SELECT count(*) FROM gold.fact_company) AS total_companies,
            (SELECT count(DISTINCT g.lgd_state_code) FROM gold.fact_company fc JOIN gold.dim_geography g ON g.geo_key=fc.geo_key) AS states_covered,
            (SELECT count(*) FROM gold.dim_geography WHERE grain='district') AS total_districts,
            (SELECT count(DISTINCT geo_key) FROM gold.fact_company) AS districts_with_data,
            (SELECT count(*) FROM silver.geography_quarantine) AS quarantined_rows
        """
    ).fetchone()
    top_districts = conn.execute(
        """
        SELECT g.district_name, g.state_name, count(*) AS n
        FROM gold.fact_company fc JOIN gold.dim_geography g ON g.geo_key = fc.geo_key
        GROUP BY g.district_name, g.state_name ORDER BY n DESC LIMIT 10
        """
    ).fetchall()
    recent_runs = conn.execute(
        """
        SELECT s.source_code, r.status, r.rows_fetched, r.rows_loaded, r.rows_quarantined, r.started_at
        FROM meta.ingestion_run r JOIN meta.source s ON s.source_key = r.source_key
        ORDER BY r.started_at DESC LIMIT 15
        """
    ).fetchall()
    conn.close()

    assert row is not None
    return {
        "total_companies": row[0],
        "states_covered": row[1],
        "total_districts": row[2],
        "districts_with_data": row[3],
        "quarantined_rows": row[4],
        "top_districts_by_company_count": [{"district_name": d, "state_name": s, "company_count": n} for d, s, n in top_districts],
        "recent_ingestion_runs": [
            {"source": s, "status": st, "rows_fetched": rf, "rows_loaded": rl, "rows_quarantined": rq, "started_at": sa.isoformat()}
            for s, st, rf, rl, rq, sa in recent_runs
        ],
    }
