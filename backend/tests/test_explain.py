"""Unit tests for app.ml.explain's pure logic — no DB, no model training.

train_and_explain() itself (DB writes, LightGBM fit, SHAP TreeExplainer) is
verified manually against real data instead — see STATUS.md for the actual
numbers (cv_r2=0.11, honestly reported as weak) and the SHAP additivity
check (base_value + sum(shap_values) == predicted_value, confirmed for a
real district). The same reasoning as test_scoring.py applies: a mocked
model/DB wouldn't catch the kind of bug that actually surfaced here
(shap.TreeExplainer.expected_value being array-shaped, not a bare float).
"""

from app.ml.explain import _quality_label


class TestQualityLabel:
    def test_none_is_unknown(self):
        assert _quality_label(None) == "unknown"

    def test_strong_r2_labelled_moderate_to_strong(self):
        assert "moderate-to-strong" in _quality_label(0.6)
        assert "moderate-to-strong" in _quality_label(0.5)

    def test_mid_r2_labelled_weak(self):
        assert _quality_label(0.3) == "weak — SHAP contributions are suggestive only, not strong evidence"
        assert _quality_label(0.2) == "weak — SHAP contributions are suggestive only, not strong evidence"

    def test_low_r2_labelled_very_weak(self):
        # this is the real, honestly-reported result for the FMOM model
        # trained against live data this session (cv_r2 == 0.1122) — the
        # label must not silently round a weak result up to "weak" or better.
        assert "very weak" in _quality_label(0.1122)
        assert "very weak" in _quality_label(0.0)

    def test_negative_r2_labelled_very_weak(self):
        # a model that does worse than predicting the mean is a real
        # possibility with cross-validation on noisy data — must not crash
        # or misclassify as merely "weak".
        assert "very weak" in _quality_label(-0.2)
