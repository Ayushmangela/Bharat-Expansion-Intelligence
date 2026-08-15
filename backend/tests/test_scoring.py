"""Unit tests for the pure-math parts of app.ml.scoring — no DB needed.

These are the mathematically subtle pieces from the Phase 3 scoring build:
winsorisation, robust min-max normalisation, and entropy weighting. The DB-
backed parts of compute_scores() are exercised manually against real data
(see STATUS.md) rather than mocked here — a mocked psycopg connection
wouldn't catch the kind of bug that actually surfaced during development
(e.g. Decimal-typed columns breaking numpy math), so integration-style
verification against the real database is more honest than a unit test that
mocks the DB away.
"""

import numpy as np
import pandas as pd
import pytest
from app.ml.scoring import entropy_weights, robust_minmax, winsorise


class TestWinsorise:
    def test_clips_outliers_to_p1_p99(self):
        series = pd.Series([1.0] * 98 + [1000.0, -1000.0])
        clipped, was_clipped = winsorise(series)
        assert clipped.max() < 1000.0
        assert clipped.min() > -1000.0
        assert was_clipped.sum() == 2

    def test_middle_of_distribution_unchanged(self):
        # For any continuous, strictly-increasing series without ties at the
        # extremes, p1/p99 interpolation always sits *inside* the true
        # min/max — so the global min and max always get nudged by
        # definition, even with zero "real" outliers. That's correct
        # winsorisation behaviour, not a bug (this replaced an earlier,
        # wrong version of this test that expected literally nothing to
        # move). What must hold is that only the tails move — the bulk of
        # the distribution (middle 98%) is untouched.
        series = pd.Series(range(1, 101), dtype=float)
        clipped, was_clipped = winsorise(series)
        middle = series.iloc[5:95]
        pd.testing.assert_series_equal(clipped.iloc[5:95], middle)
        assert not was_clipped.iloc[5:95].any()
        assert was_clipped.sum() <= 4  # only near the very tails


class TestRobustMinmax:
    def test_scales_to_0_100(self):
        series = pd.Series([10.0] * 100 + list(range(100)))
        normalised = robust_minmax(series)
        assert normalised.min() >= 0
        assert normalised.max() <= 100

    def test_degenerate_distribution_returns_midpoint_not_error(self):
        # p1 == p99 (every value identical) must not divide by zero — every
        # district gets 50 (no information to discriminate on), not NaN/inf.
        series = pd.Series([5.0] * 20)
        normalised = robust_minmax(series)
        assert (normalised == 50.0).all()

    def test_direction_can_be_inverted_by_caller(self):
        # scoring.py negates the series before calling this for lower-is-better
        # indicators — verify a negated series flips the ranking.
        series = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
        normal = robust_minmax(series)
        inverted = robust_minmax(-series)
        assert normal.iloc[0] < normal.iloc[-1]
        assert inverted.iloc[0] > inverted.iloc[-1]


class TestEntropyWeights:
    def test_weights_sum_to_one(self):
        df = pd.DataFrame({"A": np.random.uniform(0, 100, 50), "B": np.random.uniform(0, 100, 50)})
        weights = entropy_weights(df)
        assert weights["A"] + weights["B"] == pytest.approx(1.0)

    def test_constant_column_gets_zero_weight(self):
        # a column identical across every district carries no discriminating
        # information — entropy weighting must recognise that, not split
        # weight evenly with a genuinely informative column.
        df = pd.DataFrame({"CONST": [50.0] * 30, "VARIES": np.linspace(0, 100, 30)})
        weights = entropy_weights(df)
        assert weights["CONST"] == pytest.approx(0.0, abs=1e-9)
        assert weights["VARIES"] == pytest.approx(1.0, abs=1e-9)

    def test_more_dispersed_column_gets_more_weight(self):
        # a column where every district has a wildly different value carries
        # more discriminating power than one where most districts cluster —
        # this is the documented "removes the you-just-made-it-up objection".
        rng = np.random.default_rng(0)
        df = pd.DataFrame(
            {
                "DISPERSED": rng.uniform(0, 100, 200),
                "CLUSTERED": np.concatenate([np.full(190, 50.0), rng.uniform(0, 100, 10)]),
            }
        )
        weights = entropy_weights(df)
        assert weights["DISPERSED"] > weights["CLUSTERED"]
