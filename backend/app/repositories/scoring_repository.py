"""All SQL for Opportunity Score reads lives here (routers never touch the
database, services never write SQL — docs/02-ARCHITECTURE.md).

Every query joins through the *active* weight_version for the requested
profile (meta.weight_version.is_active) — fact_opportunity_score's primary
key includes weight_version_id, so a stale/inactive generation would
otherwise silently double-count or return last run's numbers alongside
this run's. See app/ml/scoring.py's compute_scores() for how is_active is
maintained.
"""

import numpy as np
import psycopg

from app.config import settings

CONFIDENCE_BANDS = [(0.90, "High"), (0.75, "Moderate")]


def confidence_band(score: float | None) -> str:
    if score is None:
        return "Unknown"
    for floor, label in CONFIDENCE_BANDS:
        if score >= floor:
            return label
    return "Low"


def get_conn() -> psycopg.Connection:
    return psycopg.connect(settings.database_url.replace("+psycopg", ""))


def _active_weight_version(conn: psycopg.Connection, profile_code: str) -> tuple[int, int] | None:
    row = conn.execute(
        """
        SELECT wv.weight_version_id, p.profile_key
        FROM meta.weight_version wv
        JOIN gold.dim_profile p ON p.profile_code = wv.profile_code
        WHERE wv.profile_code = %s AND wv.is_active
        """,
        (profile_code,),
    ).fetchone()
    return (row[0], row[1]) if row else None


_SORTABLE_COLUMNS = {
    "opportunity_score": "s.opportunity_score",
    "rank_national": "s.rank_national",
    "confidence_score": "s.confidence_score",
    "district_name": "g.district_name",
    "state_name": "g.state_name",
}


def list_rankings(
    profile_code: str,
    state_code: int | None,
    q: str | None,
    min_score: float | None,
    ranked_only: bool,
    limit: int,
    offset: int,
    sort: str,
    direction: str,
) -> tuple[list[dict], int, dict]:
    conn = get_conn()
    versions = _active_weight_version(conn, profile_code)
    if versions is None:
        conn.close()
        return [], 0, {"profile_code": profile_code, "computed": False}
    weight_version_id, profile_key = versions

    where = ["s.weight_version_id = %s", "s.profile_key = %s"]
    params: list = [weight_version_id, profile_key]
    if state_code is not None:
        where.append("g.lgd_state_code = %s")
        params.append(state_code)
    if q:
        where.append("g.district_name ILIKE %s")
        params.append(f"%{q}%")
    if min_score is not None:
        where.append("s.opportunity_score >= %s")
        params.append(min_score)
    if ranked_only:
        where.append("s.rank_national IS NOT NULL")
    where_sql = " AND ".join(where)

    total = conn.execute(
        f"SELECT count(*) FROM gold.fact_opportunity_score s JOIN gold.dim_geography g ON g.geo_key = s.geo_key WHERE {where_sql}",
        params,
    ).fetchone()[0]  # type: ignore[index]

    order_col = _SORTABLE_COLUMNS.get(sort, "s.opportunity_score")
    order_dir = "ASC" if direction.lower() == "asc" else "DESC"

    rows = conn.execute(
        f"""
        SELECT g.lgd_district_code, g.district_name, g.state_name, g.lgd_state_code,
               s.opportunity_score, s.rank_national, s.rank_within_state,
               s.rank_ci_low, s.rank_ci_high, s.confidence_score,
               s.indicators_used, s.indicators_total
        FROM gold.fact_opportunity_score s
        JOIN gold.dim_geography g ON g.geo_key = s.geo_key
        WHERE {where_sql}
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
            "opportunity_score": float(r[4]),
            "rank_national": r[5],
            "rank_within_state": r[6],
            "rank_ci_low": r[7],
            "rank_ci_high": r[8],
            "confidence_score": float(r[9]),
            "confidence_band": confidence_band(float(r[9])),
            "indicators_used": r[10],
            "indicators_total": r[11],
        }
        for r in rows
    ]
    meta = {"profile_code": profile_code, "weight_version_id": weight_version_id, "computed": True}
    return items, total, meta


INDICATOR_NAMES = {
    "BFR": "Business Formation Rate",
    "FMOM": "Formation Momentum",
    "CAPI": "Capital Intensity",
    "MSMED": "MSME Density",
    "MMS": "Manufacturing Share",
    "POPS": "Population Scale",
    "LIT": "Literacy Rate",
}
INDICATOR_UNITS = {
    "BFR": "per 100k population (6+)",
    "FMOM": "YoY ratio",
    "CAPI": "₹ lakh (median)",
    "MSMED": "per 1,000 population (6+)",
    "MMS": "share of MSMEs",
    "POPS": "log10(population, 2011)",
    "LIT": "% of population (6+)",
}


def get_scorecard(lgd_district_code: int, profile_code: str) -> dict | None:
    conn = get_conn()
    geo = conn.execute(
        """
        SELECT geo_key, lgd_district_code, district_name, state_name, lgd_state_code,
               area_sq_km, centroid_lat, centroid_lon
        FROM gold.dim_geography WHERE lgd_district_code = %s AND grain = 'district' AND is_current
        """,
        (lgd_district_code,),
    ).fetchone()
    if not geo:
        conn.close()
        return None
    geo_key = geo[0]

    versions = _active_weight_version(conn, profile_code)
    if versions is None:
        conn.close()
        return {
            "geography": _geo_dict(geo),
            "score": None,
            "warnings": [f"no scoring run found for profile '{profile_code}'"],
        }
    weight_version_id, profile_key = versions

    score_row = conn.execute(
        """
        SELECT opportunity_score, rank_national, rank_within_state, rank_ci_low, rank_ci_high,
               confidence_score, indicators_used, indicators_total, computed_at,
               pillar_economic, pillar_ecosystem, pillar_infrastructure, pillar_human_capital
        FROM gold.fact_opportunity_score
        WHERE geo_key = %s AND weight_version_id = %s AND profile_key = %s
        """,
        (geo_key, weight_version_id, profile_key),
    ).fetchone()

    contributions = conn.execute(
        """
        SELECT indicator_code, raw_value, normalised_value, shap_contribution, contribution_method,
               is_imputed, is_inherited, source_code
        FROM gold.fact_score_contribution
        WHERE geo_key = %s AND weight_version_id = %s AND profile_key = %s
        ORDER BY abs(shap_contribution) DESC
        """,
        (geo_key, weight_version_id, profile_key),
    ).fetchall()
    conn.close()

    if score_row is None:
        return {
            "geography": _geo_dict(geo),
            "score": None,
            "warnings": [f"district not scored under profile '{profile_code}' (insufficient source data)"],
        }

    warnings = []
    if score_row[6] < score_row[7]:
        warnings.append(f"{score_row[7] - score_row[6]} of {score_row[7]} indicators unavailable for this district")
    if score_row[1] is None:
        warnings.append(
            f"confidence {float(score_row[5]):.0%} is below the ranking floor (75%) — opportunity_score is "
            "shown but this district is not nationally ranked; too few indicators are present to trust a rank"
        )

    return {
        "geography": _geo_dict(geo),
        "score": {
            "opportunity_score": float(score_row[0]),
            "profile": profile_code,
            "rank_national": score_row[1],
            "rank_within_state": score_row[2],
            "rank_ci_low": score_row[3],
            "rank_ci_high": score_row[4],
            "confidence_score": float(score_row[5]),
            "confidence_band": confidence_band(float(score_row[5])),
            "indicators_used": score_row[6],
            "indicators_total": score_row[7],
            "weight_version_id": weight_version_id,
            "computed_at": score_row[8].isoformat(),
        },
        "pillars": {
            "economic": float(score_row[9]) if score_row[9] is not None else None,
            "ecosystem": float(score_row[10]) if score_row[10] is not None else None,
            "infrastructure": float(score_row[11]) if score_row[11] is not None else None,
            "human_capital": float(score_row[12]) if score_row[12] is not None else None,
        },
        "indicators": [
            {
                "code": code,
                "name": INDICATOR_NAMES.get(code, code),
                "raw_value": float(raw) if raw is not None else None,
                "unit": INDICATOR_UNITS.get(code, ""),
                "normalised_value": float(norm) if norm is not None else None,
                "contribution": float(contrib),
                "contribution_method": method,
                "is_imputed": imputed,
                "is_inherited": inherited,
                "source_code": source,
            }
            for code, raw, norm, contrib, method, imputed, inherited, source in contributions
        ],
        "warnings": warnings + ["Opportunity Score covers 7 of 22 documented indicators (see /api/v1/scoring/meta) — infrastructure pillar not yet computable"],
    }


def _geo_dict(geo: tuple) -> dict:
    return {
        "lgd_district_code": geo[1],
        "district_name": geo[2],
        "state_name": geo[3],
        "lgd_state_code": geo[4],
        "area_sq_km": float(geo[5]) if geo[5] else None,
        "centroid": {"lat": float(geo[6]), "lon": float(geo[7])} if geo[6] is not None else None,
    }


def get_predictive_shap(geo_key: int) -> dict | None:
    """Phase 4 SHAP, kept deliberately separate from the linear opportunity-
    score decomposition above — see migration cb2e5bd6a5eb's comment.
    Predicts FMOM (business formation momentum), not opportunity_score, so
    its units and its sum are NOT comparable to `contributions` above; that
    is why this is a distinct section in the API response, not merged into
    the same list."""
    conn = get_conn()
    model_row = conn.execute(
        "SELECT model_version_id, target_variable, cv_r2, base_value, n_train, trained_at "
        "FROM meta.model_version WHERE is_active ORDER BY trained_at DESC LIMIT 1"
    ).fetchone()
    if model_row is None:
        conn.close()
        return None
    model_version_id, target_variable, cv_r2, base_value, n_train, trained_at = model_row

    rows = conn.execute(
        """
        SELECT indicator_code, feature_value, shap_value, predicted_value
        FROM gold.fact_shap_contribution
        WHERE geo_key = %s AND model_version_id = %s
        ORDER BY abs(shap_value) DESC
        """,
        (geo_key, model_version_id),
    ).fetchall()
    conn.close()
    if not rows:
        return None

    cv_r2_f = float(cv_r2) if cv_r2 is not None else None
    return {
        "model_version_id": model_version_id,
        "target_variable": target_variable,
        "target_description": "Business Formation Momentum (YoY change in new-incorporation rate) — a genuine held-out outcome, not opportunity_score itself",
        "cv_r2": cv_r2_f,
        "model_quality": _shap_quality_label(cv_r2_f),
        "n_train_districts": n_train,
        "trained_at": trained_at.isoformat(),
        "base_value": float(base_value),
        "predicted_value": float(rows[0][3]),
        "contributions": [
            {
                "indicator_code": code,
                "indicator_name": INDICATOR_NAMES.get(code, code),
                "feature_value": float(fv) if fv is not None else None,
                "shap_value": float(sv),
            }
            for code, fv, sv, _pv in rows
        ],
    }


def _shap_quality_label(cv_r2: float | None) -> str:
    if cv_r2 is None:
        return "unknown"
    if cv_r2 >= 0.5:
        return "moderate-to-strong — reflects real predictive structure"
    if cv_r2 >= 0.2:
        return "weak — suggestive only, not strong evidence"
    return "very weak or none — treat as exploratory, not a reliable explanation"


def get_explain(lgd_district_code: int, profile_code: str) -> dict | None:
    """Linear-weighted decomposition of opportunity_score (faithful — sums
    exactly to the score), plus a separate predictive_model section holding
    genuine SHAP values from the Phase 4 model (see get_predictive_shap)."""
    scorecard = get_scorecard(lgd_district_code, profile_code)
    if scorecard is None or scorecard.get("score") is None:
        return scorecard
    conn = get_conn()
    geo_row = conn.execute(
        "SELECT geo_key FROM gold.dim_geography WHERE lgd_district_code = %s AND grain='district' AND is_current",
        (lgd_district_code,),
    ).fetchone()
    conn.close()
    geo_key = geo_row[0] if geo_row else None
    return {
        "lgd_district_code": lgd_district_code,
        "profile": profile_code,
        "final_score": scorecard["score"]["opportunity_score"],
        "contributions": [
            {
                "indicator_code": i["code"],
                "indicator_name": i["name"],
                "contribution": i["contribution"],
                "contribution_method": i["contribution_method"],
                "raw_value": i["raw_value"],
                "is_imputed": i["is_imputed"],
                "is_inherited": i["is_inherited"],
                "source_code": i["source_code"],
            }
            for i in scorecard["indicators"]
        ],
        "predictive_model": get_predictive_shap(geo_key) if geo_key else None,
        "narrative": None,
        "narrative_available": False,
        "warnings": scorecard["warnings"],
    }


def get_similar_districts(lgd_district_code: int, profile_code: str, limit: int) -> dict | None:
    """Cosine similarity on the normalised indicator vector, per
    docs/07-API-SPEC.md. Missing indicators are treated as 0 contribution to
    the dot product (not imputed to the mean or dropped) — a fair, simple
    convention: two districts sharing few present indicators naturally pull
    toward lower similarity rather than a fabricated "average" value filling
    the gap."""
    conn = get_conn()
    versions = _active_weight_version(conn, profile_code)
    if versions is None:
        conn.close()
        return None
    weight_version_id, _profile_key = versions

    geo_row = conn.execute(
        "SELECT geo_key FROM gold.dim_geography WHERE lgd_district_code = %s AND grain='district' AND is_current",
        (lgd_district_code,),
    ).fetchone()
    if geo_row is None:
        conn.close()
        return None
    target_geo_key = geo_row[0]

    rows = conn.execute(
        """
        SELECT c.geo_key, g.lgd_district_code, g.district_name, g.state_name, c.indicator_code, c.normalised_value
        FROM gold.fact_score_contribution c
        JOIN gold.dim_geography g ON g.geo_key = c.geo_key
        WHERE c.weight_version_id = %s
        """,
        (weight_version_id,),
    ).fetchall()
    conn.close()
    if not rows:
        return None

    indicator_codes = sorted({r[4] for r in rows})
    idx = {code: i for i, code in enumerate(indicator_codes)}
    vectors: dict[int, np.ndarray] = {}
    meta: dict[int, tuple[int, str, str]] = {}
    for geo_key, lgd_code, dist_name, state_name, code, norm in rows:
        vec = vectors.setdefault(geo_key, np.zeros(len(indicator_codes)))
        vec[idx[code]] = float(norm) if norm is not None else 0.0
        meta[geo_key] = (lgd_code, dist_name, state_name)

    if target_geo_key not in vectors:
        return {"lgd_district_code": lgd_district_code, "items": []}

    target_vec = vectors[target_geo_key]
    target_norm = np.linalg.norm(target_vec)
    scored = []
    for geo_key, vec in vectors.items():
        if geo_key == target_geo_key:
            continue
        denom = target_norm * np.linalg.norm(vec)
        similarity = float(np.dot(target_vec, vec) / denom) if denom > 0 else 0.0
        scored.append((similarity, geo_key))
    scored.sort(key=lambda x: x[0], reverse=True)

    return {
        "lgd_district_code": lgd_district_code,
        "items": [
            {
                "lgd_district_code": meta[geo_key][0],
                "district_name": meta[geo_key][1],
                "state_name": meta[geo_key][2],
                "similarity": round(similarity, 4),
            }
            for similarity, geo_key in scored[:limit]
        ],
    }


def weight_meta() -> dict:
    conn = get_conn()
    rows = conn.execute(
        "SELECT profile_code, weight_version_id, method, weights, created_at FROM meta.weight_version WHERE is_active ORDER BY profile_code"
    ).fetchall()
    conn.close()
    return {
        "active_versions": [
            {"profile_code": p, "weight_version_id": w, "method": m, "weights": wts, "created_at": c.isoformat()}
            for p, w, m, wts, c in rows
        ],
        "scope_note": (
            "Only 7 of the 22 documented KPIs are computable from data loaded so far "
            "(BFR, FMOM, CAPI, MSMED, MMS, POPS, LIT). The infrastructure pillar has zero "
            "computable indicators this phase and is excluded, not faked."
        ),
    }


def compare_districts(lgd_district_codes: list[int], profile_code: str) -> dict | None:
    """docs/07-API-SPEC.md POST /api/v1/compare — aligned indicator-by-
    indicator diff plus a trade-off summary. The "summary" is derived
    directly from the data (which district leads on which indicator, and
    on the overall score) — never generated prose, so it can't say
    anything the numbers alongside it don't already show."""
    conn = get_conn()
    versions = _active_weight_version(conn, profile_code)
    if versions is None:
        conn.close()
        return None
    weight_version_id, _profile_key = versions

    geo_rows = conn.execute(
        "SELECT geo_key, lgd_district_code, district_name, state_name FROM gold.dim_geography "
        "WHERE lgd_district_code = ANY(%s) AND grain='district' AND is_current",
        (lgd_district_codes,),
    ).fetchall()
    if len(geo_rows) < 2:
        conn.close()
        return {"error": "at least 2 valid districts are required to compare"}
    geo_key_to_code = {r[0]: r[1] for r in geo_rows}
    district_meta = {r[1]: {"lgd_district_code": r[1], "district_name": r[2], "state_name": r[3]} for r in geo_rows}
    geo_keys = list(geo_key_to_code.keys())

    scores = conn.execute(
        "SELECT geo_key, opportunity_score, rank_national FROM gold.fact_opportunity_score "
        "WHERE geo_key = ANY(%s) AND weight_version_id = %s",
        (geo_keys, weight_version_id),
    ).fetchall()
    score_by_code = {geo_key_to_code[g]: {"opportunity_score": float(s), "rank_national": r} for g, s, r in scores}

    contrib_rows = conn.execute(
        "SELECT geo_key, indicator_code, raw_value, normalised_value FROM gold.fact_score_contribution "
        "WHERE geo_key = ANY(%s) AND weight_version_id = %s",
        (geo_keys, weight_version_id),
    ).fetchall()
    conn.close()

    by_indicator: dict[str, dict[int, tuple[float | None, float | None]]] = {}
    for geo_key, code, raw, norm in contrib_rows:
        by_indicator.setdefault(code, {})[geo_key_to_code[geo_key]] = (
            float(raw) if raw is not None else None,
            float(norm) if norm is not None else None,
        )

    indicators = []
    for code in sorted(by_indicator.keys()):
        values = by_indicator[code]
        present = {c: v[1] for c, v in values.items() if v[1] is not None}
        # None means either no data or a genuine tie — max() alone would
        # silently pick one side of a tie (e.g. two districts both hitting
        # the CAPI statutory-minimum ceiling) and misreport it as a real
        # lead, which a "trade-off summary" must not do.
        leader = None
        if present:
            top_value = max(present.values())
            tied_at_top = [c for c, v in present.items() if v == top_value]
            leader = tied_at_top[0] if len(tied_at_top) == 1 else None
        indicators.append(
            {
                "indicator_code": code,
                "name": INDICATOR_NAMES.get(code, code),
                "values": {str(c): {"raw_value": v[0], "normalised_value": v[1]} for c, v in values.items()},
                "leader": leader,
            }
        )

    score_leader = max(score_by_code, key=lambda c: score_by_code[c]["opportunity_score"]) if score_by_code else None
    lead_counts = {code: sum(1 for i in indicators if i["leader"] == code) for code in district_meta}

    return {
        "districts": [
            {**district_meta[c], **score_by_code.get(c, {"opportunity_score": None, "rank_national": None})}
            for c in lgd_district_codes
            if c in district_meta
        ],
        "indicators": indicators,
        "trade_off_summary": {
            "overall_score_leader": score_leader,
            "indicators_led_count": lead_counts,
        },
    }
