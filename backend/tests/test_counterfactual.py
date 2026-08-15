"""Unit tests for the pure math in app.ml.counterfactual — no DB needed.

compute_counterfactual() itself (DB reads, real binary search against live
weights) is verified manually against real data instead — see STATUS.md for
actual runs (e.g. Chhatrapati Sambhajinagar rank 50 -> target 40: LIT/MSMED/MMS
levers, all within the observed national range; rank 50 -> target 10: only
BFR feasible, everything else correctly rejected as outside the national
range). Same reasoning as test_scoring.py: a mocked DB wouldn't catch the
kind of bug that actually matters here (off-by-one in the target-score
threshold, wrong search direction).
"""

import pandas as pd
from app.ml.counterfactual import _national_bounds


class TestNationalBounds:
    def test_returns_true_min_max_not_winsorised(self):
        # Deliberately NOT p1/p99 — see the module docstring: a counterfactual
        # should be allowed to ask a district to match the single best real
        # district nationally, not be capped at the 99th percentile.
        df = pd.DataFrame({"BFR": [1.0, 5.0, 5000.0, float("nan"), 3.0]})
        bounds = _national_bounds(df)
        assert bounds["BFR"] == (1.0, 5000.0)

    def test_drops_indicator_with_no_data(self):
        df = pd.DataFrame({"BFR": [1.0, 2.0], "GHOST": [float("nan"), float("nan")]})
        bounds = _national_bounds(df)
        assert "GHOST" not in bounds
        assert "BFR" in bounds
