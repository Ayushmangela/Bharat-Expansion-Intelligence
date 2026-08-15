"""Counterfactual engine, per docs/06-SCORING-METHODOLOGY.md §9 — "what
would have to change to move up N ranks." Flagged in the doc as the
highest-value, least-commonly-built feature: turns a score into a policy
to-do list ("raise MSME density from X to Y") instead of a bare number.

Modelling simplification, stated explicitly rather than left implicit: this
answers "if ONLY this district changed this ONE indicator, holding the
national distribution (winsorisation bounds, entropy weights, every other
district's score) fixed, what would it take." Re-deriving the whole national
pipeline (which would let one district's change shift entropy weights or
other districts' ranks too) is a different, much more expensive question the
doc doesn't ask for — "rank(score with indicator_i + delta) <= target_rank"
reads as exactly this single-district, partial-equilibrium framing, and it's
also the only version of the question a district actually facing this report
can act on ("what do WE change"), not requiring the reader to reason about
knock-on effects to 700+ other districts' rankings.

Binary search (not the closed-form solution that also exists here, since
opportunity_score is linear in each present indicator's normalised value)
because it's what the doc's pseudocode specifies, and it stays correct even
if a future indicator's direction or normalisation stops being simply
monotonic.
"""

from dataclasses import dataclass

import pandas as pd
import psycopg

from app.config import settings
from app.ml.kpis import INDICATOR_META, compute_all_indicators
from app.ml.scoring import PILLAR_WEIGHTS_BALANCED, effective_indicator_weights

MAX_BINARY_SEARCH_ITERATIONS = 40
CONVERGENCE_TOLERANCE = 1e-6


def get_conn() -> psycopg.Connection:
    return psycopg.connect(settings.database_url.replace("+psycopg", ""))


@dataclass
class Lever:
    indicator_code: str
    current_value: float
    required_value: float
    required_delta: float
    feasible: bool
    description: str


def _national_bounds(raw: pd.DataFrame) -> dict[str, tuple[float, float]]:
    """Observed national range per indicator — the doc's explicit
    feasibility constraint ("subject to delta keeping indicator within
    observed national range"). Uses the true min/max actually seen, not the
    winsorised p1/p99 — a counterfactual asking a district to merely match
    the best OTHER real district is legitimate advice; winsorised bounds
    would reject that as infeasible even though a real district achieves it.
    """
    bounds = {}
    for code in raw.columns:
        series = raw[code].dropna()
        if not series.empty:
            bounds[code] = (float(series.min()), float(series.max()))
    return bounds


def compute_counterfactual(lgd_district_code: int, target_rank: int, profile_code: str = "balanced") -> dict | None:
    conn = get_conn()
    geo_row = conn.execute(
        "SELECT geo_key FROM gold.dim_geography WHERE lgd_district_code = %s AND grain='district' AND is_current",
        (lgd_district_code,),
    ).fetchone()
    if geo_row is None:
        conn.close()
        return None
    geo_key = geo_row[0]

    weight_row = conn.execute(
        "SELECT weight_version_id, weights FROM meta.weight_version WHERE profile_code = %s AND is_active",
        (profile_code,),
    ).fetchone()
    if weight_row is None:
        conn.close()
        return None
    weight_version_id, weights = weight_row

    own_score_row = conn.execute(
        "SELECT opportunity_score, rank_national FROM gold.fact_opportunity_score "
        "WHERE geo_key = %s AND weight_version_id = %s",
        (geo_key, weight_version_id),
    ).fetchone()
    if own_score_row is None:
        conn.close()
        return {"error": "district has no computed score under this profile"}
    current_score, current_rank = float(own_score_row[0]), own_score_row[1]

    if current_rank is None:
        conn.close()
        return {
            "error": (
                "district is below the ranking confidence floor — a counterfactual 'move to rank N' "
                "isn't meaningful without a trustworthy current rank to move from"
            )
        }
    if current_rank <= target_rank:
        conn.close()
        return {
            "lgd_district_code": lgd_district_code,
            "current_rank": current_rank,
            "target_rank": target_rank,
            "already_achieved": True,
            "levers": [],
            "infeasible": [],
        }

    # Other districts' scores, held fixed — the "partial equilibrium" assumption above.
    other_scores = [
        float(r[0])
        for r in conn.execute(
            "SELECT opportunity_score FROM gold.fact_opportunity_score "
            "WHERE weight_version_id = %s AND rank_national IS NOT NULL AND geo_key != %s "
            "ORDER BY opportunity_score DESC",
            (weight_version_id, geo_key),
        ).fetchall()
    ]
    if target_rank < 1 or target_rank > len(other_scores) + 1:
        conn.close()
        return {"error": f"target_rank must be between 1 and {len(other_scores) + 1}"}
    # need to exceed the (target_rank)-th other district's score to land at rank <= target_rank
    target_score = other_scores[target_rank - 1] + 0.001

    raw = compute_all_indicators()
    if geo_key not in raw.index:
        conn.close()
        return {"error": "district has no computable indicators"}
    own_raw = raw.loc[geo_key]
    present_indicators = list(own_raw.dropna().index)
    eff_weights = effective_indicator_weights(present_indicators, weights, PILLAR_WEIGHTS_BALANCED)
    bounds = _national_bounds(raw)

    # Winsorisation bounds actually used by the live score (frozen, matching
    # scoring.py's own p1/p99 per indicator) — needed to map a candidate raw
    # value to the same normalised value the real score would have used.
    p1p99 = {code: (raw[code].quantile(0.01), raw[code].quantile(0.99)) for code in raw.columns}

    def normalise(code: str, value: float) -> float:
        p1, p99 = p1p99[code]
        if p99 == p1:
            return 50.0
        clipped = min(max(value, p1), p99)
        return max(0.0, min(100.0, 100 * (clipped - p1) / (p99 - p1)))

    levers: list[Lever] = []
    infeasible: list[str] = []

    for code in present_indicators:
        current_value = float(own_raw[code])
        current_normalised = normalise(code, current_value)
        w = eff_weights[code]
        score_without_this_indicator = current_score - w * current_normalised

        if code not in bounds:
            continue
        national_min, national_max = bounds[code]
        # only search the direction that helps (all 7 current indicators are
        # higher-is-better; INDICATOR_META's direction flag is honoured here
        # so a future lower-is-better indicator searches downward instead)
        direction = INDICATOR_META[code][1]
        search_hi = national_max if direction == 1 else current_value
        search_lo = current_value if direction == 1 else national_min

        def score_at(value: float, _w: float = w, _base: float = score_without_this_indicator, _code: str = code) -> float:
            return _base + _w * normalise(_code, value)

        if score_at(search_hi if direction == 1 else search_lo) < target_score:
            infeasible.append(code)
            continue

        lo, hi = (current_value, search_hi) if direction == 1 else (search_lo, current_value)
        for _ in range(MAX_BINARY_SEARCH_ITERATIONS):
            mid = (lo + hi) / 2
            if score_at(mid) >= target_score:
                hi = mid
            else:
                lo = mid
            if abs(hi - lo) < CONVERGENCE_TOLERANCE * max(abs(national_max - national_min), 1.0):
                break
        required_value = hi if direction == 1 else lo

        levers.append(
            Lever(
                indicator_code=code,
                current_value=round(current_value, 4),
                required_value=round(required_value, 4),
                required_delta=round(required_value - current_value, 4),
                feasible=True,
                description=(
                    f"raise {code} from {current_value:.2f} to {required_value:.2f}"
                    if direction == 1
                    else f"lower {code} from {current_value:.2f} to {required_value:.2f}"
                ),
            )
        )

    conn.close()

    # "cheapest" = smallest relative change from the district's own current
    # value — a 10% improvement is a more actionable ask than a 400% one,
    # even if the absolute delta is numerically smaller for the latter.
    def relative_cost(lever: Lever) -> float:
        if lever.current_value == 0:
            return abs(lever.required_delta)
        return abs(lever.required_delta / lever.current_value)

    levers.sort(key=relative_cost)

    return {
        "lgd_district_code": lgd_district_code,
        "current_rank": current_rank,
        "target_rank": target_rank,
        "current_score": round(current_score, 3),
        "target_score": round(target_score, 3),
        "already_achieved": False,
        "levers": [lever.__dict__ for lever in levers[:3]],
        "infeasible": infeasible,
    }
