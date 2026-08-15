"""Opportunity Score computation, per docs/06-SCORING-METHODOLOGY.md.

Pipeline, in order (the doc is explicit that order matters):
1. Winsorise each indicator at p1/p99 BEFORE normalising (rule: without this,
   Mumbai/Bengaluru/Delhi-scale outliers squash everything else into the
   bottom of the range — this is THE checkpoint the doc warns about).
2. Direction-align (invert lower-is-better indicators — none of the 7
   computed here are lower-is-better, but the mechanism is kept generic).
3. Robust min-max normalise to [0, 100] on winsorised values.
4. Entropy-weight (data-driven, no manually-picked weights).
5. Pillar aggregation (weighted average within pillar).
6. Profile weighting across pillars -> final Opportunity Score.
7. Confidence score = sum(weight_i present) / sum(weight_i total).
8. Linear per-indicator contribution stored (NOT SHAP — Phase 4 territory,
   see migration 475c62829513's comment).

INFRASTRUCTURE PILLAR: excluded entirely, not faked — zero computable
indicators this phase (docs/RESOURCE-REGISTRY.md: CEA broken/licence-gated,
RBI/road data not loaded). pillar_infrastructure is NULL on every row.
Pillar weights are redistributed across the 3 available pillars.
"""

import numpy as np
import pandas as pd
import psycopg
from psycopg.types.json import Json

from app.config import settings
from app.ml.kpis import INDICATOR_META, compute_all_indicators, reference_month

QUALITY_BIT_IMPUTED = 1
QUALITY_BIT_WINSORISED = 8

MC_TRIALS = 1000
MC_PERTURBATION = 0.20
MC_SEED = 20260815  # fixed seed: reruns on unchanged data must reproduce the same CI, not a new random draw each time

# docs/06-SCORING-METHODOLOGY.md §10's own "Moderate" floor, reused as the
# rank-eligibility gate — see the comment at its use site in compute_scores().
RANK_MIN_CONFIDENCE = 0.75

# Redistributed from the doc's 4-pillar table (economic/ecosystem/infrastructure/
# human_capital) proportionally, since infrastructure has zero computable
# indicators this phase. "balanced" is the only profile computed for now —
# manufacturing/logistics/retail/services all lean on infrastructure or
# ecosystem indicators not yet available in enough depth to differentiate.
PILLAR_WEIGHTS_BALANCED = {"economic": 1 / 3, "ecosystem": 1 / 3, "human_capital": 1 / 3}


def get_conn() -> psycopg.Connection:
    return psycopg.connect(settings.database_url.replace("+psycopg", ""))


def winsorise(series: pd.Series) -> tuple[pd.Series, pd.Series]:
    """Returns (winsorised_values, was_winsorised_bool_mask)."""
    p1, p99 = series.quantile(0.01), series.quantile(0.99)
    clipped = series.clip(lower=p1, upper=p99)
    was_clipped = (series < p1) | (series > p99)
    return clipped, was_clipped


def robust_minmax(series: pd.Series) -> pd.Series:
    p1, p99 = series.quantile(0.01), series.quantile(0.99)
    if p99 == p1:
        return pd.Series(50.0, index=series.index)  # no spread — every district equal, not undefined
    normalised = 100 * (series - p1) / (p99 - p1)
    return normalised.clip(0, 100)


def entropy_weights(normalised_df: pd.DataFrame) -> dict[str, float]:
    """docs/06-SCORING-METHODOLOGY.md §6a. Indicators that discriminate more
    between districts get more weight — removes "you just made the weights
    up" as an objection. p_ij=0 contributes 0 to the entropy sum (standard
    convention, avoids log(0))."""
    n = len(normalised_df)
    k = 1 / np.log(n) if n > 1 else 0
    weights = {}
    divergences = {}
    for col in normalised_df.columns:
        x = normalised_df[col].dropna()
        if x.sum() == 0 or len(x) < 2:
            divergences[col] = 0.0
            continue
        p = x / x.sum()
        p_nonzero = p[p > 0]
        e = -k * (p_nonzero * np.log(p_nonzero)).sum()
        divergences[col] = 1 - e
    total_divergence = sum(divergences.values())
    for col, d in divergences.items():
        weights[col] = d / total_divergence if total_divergence > 0 else 1 / len(divergences)
    return weights


def monte_carlo_rank_sensitivity(
    normalised: pd.DataFrame,
    indicator_codes: list[str],
    weights: dict[str, float],
    pillar_weights: dict[str, float],
    scored_geo_keys: list[int],
    n_trials: int = MC_TRIALS,
) -> pd.DataFrame:
    """docs/06-SCORING-METHODOLOGY.md §7 — MANDATORY. Perturb entropy weights
    +/-20% per trial, recompute every district's rank, report the 2.5th/97.5th
    percentile rank across trials.

    This is what turns "Niuland: rank 1" (built from a single noisy indicator,
    confidence 0.11) into "Niuland: rank 1 (95% CI: 1-640)" — a wide interval
    that is itself the finding: a score resting on one indicator is not a
    stable ranking, and the doc is explicit that publishing the interval,
    not suppressing the district, is the correct way to surface that.

    Vectorised across districts per trial (only the 1000-trial loop is
    Python-level) — a per-district Python loop x 1000 trials would be too
    slow for no benefit, since every district in a trial shares the same
    perturbed weight draw.
    """
    from scipy.stats import rankdata

    df = normalised.loc[scored_geo_keys, indicator_codes]
    values = df.to_numpy(dtype=float)  # (D, K)
    present = ~np.isnan(values)
    values_filled = np.where(present, values, 0.0)
    base_w = np.array([weights[c] for c in indicator_codes])
    pillar_of = np.array([INDICATOR_META[c][0] for c in indicator_codes])

    pillars = list(pillar_weights.keys())
    pillar_idx = {p: np.where(pillar_of == p)[0] for p in pillars}
    # pillar presence is a data fact, not a per-trial random draw — fixed once
    pillar_present = {p: present[:, pillar_idx[p]].any(axis=1) for p in pillars if len(pillar_idx[p])}

    rng = np.random.default_rng(MC_SEED)
    n_districts = values.shape[0]
    rank_matrix = np.empty((n_trials, n_districts))

    for t in range(n_trials):
        pw = base_w * (1 + rng.uniform(-MC_PERTURBATION, MC_PERTURBATION, size=base_w.shape[0]))

        pillar_scores = np.full((n_districts, len(pillars)), np.nan)
        for pi, p in enumerate(pillars):
            idx = pillar_idx[p]
            if len(idx) == 0:
                continue
            w_matrix = present[:, idx] * pw[idx][None, :]
            w_sum = w_matrix.sum(axis=1)
            weighted_val = (values_filled[:, idx] * w_matrix).sum(axis=1)
            with np.errstate(invalid="ignore", divide="ignore"):
                pillar_scores[:, pi] = np.where(w_sum > 0, weighted_val / np.where(w_sum > 0, w_sum, 1), np.nan)

        pw_pillar = np.array([pillar_weights[p] for p in pillars])
        pillar_present_matrix = np.array([pillar_present[p] for p in pillars]).T  # (D, P)
        w_matrix = pillar_present_matrix * pw_pillar[None, :]
        w_sum = w_matrix.sum(axis=1)
        weighted_val = np.nan_to_num(pillar_scores) * w_matrix
        final_score = weighted_val.sum(axis=1) / np.where(w_sum > 0, w_sum, 1)

        rank_matrix[t, :] = rankdata(-final_score, method="min")

    ci_low = np.percentile(rank_matrix, 2.5, axis=0)
    ci_high = np.percentile(rank_matrix, 97.5, axis=0)
    return pd.DataFrame(
        {"geo_key": scored_geo_keys, "rank_ci_low": ci_low.astype(int), "rank_ci_high": ci_high.astype(int)}
    ).set_index("geo_key")


def effective_indicator_weights(
    present_indicators: list[str], weights: dict[str, float], pillar_weights: dict[str, float]
) -> dict[str, float]:
    """The per-district linear coefficient such that
    opportunity_score == sum(effective_weight[c] * normalised_value[c] for c
    in present_indicators) exactly — i.e. entropy weight renormalised within
    the indicator's pillar (among what's present), times that pillar's
    weight renormalised across present pillars. Factored out of
    compute_scores()'s per-district loop so counterfactual.py can reuse the
    exact same coefficients rather than re-deriving (and risking drift from)
    the real scoring math.
    """
    pillars_present = {INDICATOR_META[c][0] for c in present_indicators}
    present_pillar_weight = sum(pillar_weights[p] for p in pillars_present)

    effective: dict[str, float] = {}
    for pillar_name in pillars_present:
        pillar_indicators = [c for c in present_indicators if INDICATOR_META[c][0] == pillar_name]
        indicator_weight_sum = sum(weights[c] for c in pillar_indicators)
        pw_effective = pillar_weights[pillar_name] / present_pillar_weight
        for c in pillar_indicators:
            effective[c] = (weights[c] / indicator_weight_sum) * pw_effective
    return effective


def compute_scores(profile_code: str = "balanced") -> dict:
    conn = get_conn()
    ref_month = reference_month(conn)
    date_key = ref_month.year * 100 + ref_month.month

    raw = compute_all_indicators()
    indicator_codes = list(INDICATOR_META.keys())

    # --- winsorise + normalise, per indicator, across all districts with a value ---
    normalised = pd.DataFrame(index=raw.index)
    winsorised_flags = pd.DataFrame(False, index=raw.index, columns=indicator_codes)
    for code in indicator_codes:
        series = raw[code].dropna()
        if series.empty:
            normalised[code] = np.nan
            continue
        clipped, was_clipped = winsorise(series)
        _pillar, direction = INDICATOR_META[code]
        aligned = clipped if direction == 1 else -clipped
        norm = robust_minmax(aligned)
        normalised[code] = norm.reindex(raw.index)
        winsorised_flags.loc[series.index, code] = was_clipped

    # --- entropy weights, computed on districts with complete data (standard
    # practice — entropy weighting needs a rectangular matrix) ---
    complete_rows = normalised.dropna()
    weights = entropy_weights(complete_rows) if not complete_rows.empty else dict.fromkeys(indicator_codes, 1 / len(indicator_codes))

    # Deactivate prior versions for this profile first — fact_opportunity_score's
    # PK includes weight_version_id, so every run inserts a fresh row set rather
    # than overwriting; is_active is what lets readers (API/queries) find the
    # current snapshot instead of averaging across scoring-run generations.
    conn.execute("UPDATE meta.weight_version SET is_active = false WHERE profile_code = %s", (profile_code,))
    weight_row = conn.execute(
        "INSERT INTO meta.weight_version (profile_code, method, weights, is_active) VALUES (%s, %s, %s, true) RETURNING weight_version_id",
        (profile_code, "entropy", Json(weights)),
    ).fetchone()
    assert weight_row is not None
    weight_version_id = weight_row[0]

    profile_row = conn.execute("SELECT profile_key FROM gold.dim_profile WHERE profile_code = %s", (profile_code,)).fetchone()
    assert profile_row is not None, f"profile {profile_code} not seeded — run seed_profiles() first"
    profile_key = profile_row[0]

    pillar_weights = PILLAR_WEIGHTS_BALANCED

    n_scored = 0
    score_rows = []
    # geo_key -> {indicator_code: contribution in score-points}, using the SAME
    # per-district renormalised weights that actually produced opportunity_score
    # below — sum(contributions) == opportunity_score exactly for every district.
    # This is what makes /districts/{code}/explain faithful rather than
    # decorative: CLAUDE.md's "the explanation is the product" means the bars
    # must reconstruct the number, not just gesture at rough importance.
    contributions_by_geo: dict[int, dict[str, float]] = {}
    for geo_key in normalised.index:
        row = normalised.loc[geo_key]
        present = row.dropna()
        if present.empty:
            continue

        # pillar scores: weighted average of present indicators in that pillar
        # (renormalising indicator weights within the pillar to sum to 1 among
        # what's actually present — docs §5 "weighted average within pillar")
        present_indicators = list(present.index)
        pillar_scores: dict[str, float] = {}
        for pillar_name in ("economic", "ecosystem", "human_capital"):
            pillar_indicators = [c for c in present_indicators if INDICATOR_META[c][0] == pillar_name]
            if not pillar_indicators:
                continue
            w = np.array([weights[c] for c in pillar_indicators])
            w = w / w.sum()
            vals = np.array([present[c] for c in pillar_indicators])
            pillar_scores[pillar_name] = float((w * vals).sum())

        if not pillar_scores:
            continue

        eff_weights = effective_indicator_weights(present_indicators, weights, pillar_weights)
        opportunity_score = sum(eff_weights[c] * present[c] for c in present_indicators)
        contributions_by_geo[geo_key] = {c: eff_weights[c] * present[c] for c in present_indicators}

        confidence = sum(weights[c] for c in present.index) / sum(weights.values())

        score_rows.append(
            {
                "geo_key": geo_key,
                "opportunity_score": round(opportunity_score, 3),
                "pillar_economic": round(pillar_scores["economic"], 3) if "economic" in pillar_scores else None,
                "pillar_ecosystem": round(pillar_scores["ecosystem"], 3) if "ecosystem" in pillar_scores else None,
                "pillar_human_capital": round(pillar_scores["human_capital"], 3) if "human_capital" in pillar_scores else None,
                "confidence_score": round(confidence, 4),
                "indicators_used": len(present),
                "indicators_total": len(indicator_codes),
            }
        )
        n_scored += 1

    scores_df = pd.DataFrame(score_rows).sort_values("opportunity_score", ascending=False).reset_index(drop=True)

    # Rank-eligibility gate: a district must clear the doc's own §10 "Moderate"
    # confidence floor (>=0.75) to receive a national/state rank. Without this,
    # a district with a single present indicator gets 100% of that indicator's
    # weight renormalised onto it (see monte_carlo_rank_sensitivity docstring)
    # and can out-rank a fully-observed metro on one noisy small-N ratio —
    # confirmed happening for real (Niuland/Sanchore/Shamator at rank 1-3,
    # confidence 0.03-0.11, MMS/CAPI-driven) before this gate was added.
    # opportunity_score and confidence_score are still computed and stored for
    # every district — nothing is hidden — only the *rank* is withheld below
    # the floor, since the doc itself says a Low-confidence number should be
    # "interpreted with caution," not presented as a credible #1.
    eligible = scores_df["confidence_score"] >= RANK_MIN_CONFIDENCE
    scores_df["rank_national"] = pd.NA
    scores_df.loc[eligible, "rank_national"] = (
        scores_df.loc[eligible, "opportunity_score"].rank(ascending=False, method="min").astype(int)
    )

    geo_to_state: dict[int, int] = dict(
        conn.execute("SELECT geo_key, lgd_state_code FROM gold.dim_geography WHERE grain='district' AND is_current").fetchall()
    )
    scores_df["state_code"] = scores_df["geo_key"].map(geo_to_state)
    scores_df["rank_within_state"] = pd.NA
    scores_df.loc[eligible, "rank_within_state"] = (
        scores_df.loc[eligible].groupby("state_code")["opportunity_score"].rank(ascending=False, method="min").astype(int)
    )

    mc = monte_carlo_rank_sensitivity(
        normalised, indicator_codes, weights, pillar_weights, scores_df.loc[eligible, "geo_key"].tolist()
    )
    scores_df = scores_df.set_index("geo_key").join(mc).reset_index()

    for _, r in scores_df.iterrows():
        conn.execute(
            """
            INSERT INTO gold.fact_opportunity_score
                (geo_key, date_key, profile_key, opportunity_score, pillar_economic, pillar_ecosystem,
                 pillar_infrastructure, pillar_human_capital, rank_national, rank_within_state,
                 rank_ci_low, rank_ci_high, confidence_score, indicators_used, indicators_total, weight_version_id)
            VALUES (%s, %s, %s, %s, %s, %s, NULL, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (geo_key, date_key, profile_key, weight_version_id) DO UPDATE SET
                opportunity_score = EXCLUDED.opportunity_score,
                pillar_economic = EXCLUDED.pillar_economic,
                pillar_ecosystem = EXCLUDED.pillar_ecosystem,
                pillar_human_capital = EXCLUDED.pillar_human_capital,
                rank_national = EXCLUDED.rank_national,
                rank_within_state = EXCLUDED.rank_within_state,
                rank_ci_low = EXCLUDED.rank_ci_low,
                rank_ci_high = EXCLUDED.rank_ci_high,
                confidence_score = EXCLUDED.confidence_score
            """,
            (
                int(r["geo_key"]), date_key, profile_key, r["opportunity_score"],
                r["pillar_economic"], r["pillar_ecosystem"], r["pillar_human_capital"],
                int(r["rank_national"]) if pd.notna(r["rank_national"]) else None,
                int(r["rank_within_state"]) if pd.notna(r["rank_within_state"]) else None,
                int(r["rank_ci_low"]) if pd.notna(r["rank_ci_low"]) else None,
                int(r["rank_ci_high"]) if pd.notna(r["rank_ci_high"]) else None,
                r["confidence_score"], int(r["indicators_used"]), int(r["indicators_total"]), weight_version_id,
            ),
        )

        geo_key = int(r["geo_key"])
        for code in indicator_codes:
            if pd.isna(normalised.loc[geo_key, code]):
                continue
            contribution = contributions_by_geo[geo_key][code]
            flags = QUALITY_BIT_WINSORISED if winsorised_flags.loc[geo_key, code] else 0
            conn.execute(
                """
                INSERT INTO gold.fact_score_contribution
                    (geo_key, date_key, profile_key, weight_version_id, indicator_code,
                     raw_value, normalised_value, shap_contribution, contribution_method,
                     is_imputed, is_inherited, source_code)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'linear_weighted', %s, false, %s)
                ON CONFLICT (geo_key, date_key, profile_key, weight_version_id, indicator_code) DO UPDATE SET
                    raw_value = EXCLUDED.raw_value, normalised_value = EXCLUDED.normalised_value,
                    shap_contribution = EXCLUDED.shap_contribution
                """,
                (
                    geo_key, date_key, profile_key, weight_version_id, code,
                    float(raw.loc[geo_key, code]) if not pd.isna(raw.loc[geo_key, code]) else None,
                    float(normalised.loc[geo_key, code]),
                    round(contribution, 4),
                    bool(flags & QUALITY_BIT_IMPUTED),
                    "S02" if code in ("BFR", "FMOM", "CAPI") else ("S03" if code in ("MSMED", "MMS") else "S19"),
                ),
            )

    conn.commit()
    conn.close()

    ranked = scores_df[scores_df["rank_national"].notna()].sort_values("rank_national")
    top10 = ranked.head(10)[
        ["geo_key", "opportunity_score", "rank_national", "rank_ci_low", "rank_ci_high", "confidence_score"]
    ].to_dict("records")

    return {
        "date_key": date_key,
        "reference_month": ref_month.isoformat(),
        "weight_version_id": weight_version_id,
        "entropy_weights": weights,
        "districts_scored": n_scored,
        "districts_ranked": int(eligible.sum()),
        "districts_below_rank_confidence_floor": int((~eligible).sum()),
        "top_10_geo_keys": top10,
    }


def seed_profiles() -> None:
    conn = get_conn()
    conn.execute(
        """
        INSERT INTO gold.dim_profile (profile_code, profile_name, description, pillar_weights)
        VALUES ('balanced', 'Balanced',
                'Equal weighting across the 3 pillars with computable indicators this phase (infrastructure excluded — see STATUS.md)',
                %s)
        ON CONFLICT (profile_code) DO NOTHING
        """,
        (Json(PILLAR_WEIGHTS_BALANCED),),
    )
    conn.commit()
    conn.close()


if __name__ == "__main__":
    import json

    seed_profiles()
    result = compute_scores("balanced")
    print(json.dumps(result, indent=2, default=str))
