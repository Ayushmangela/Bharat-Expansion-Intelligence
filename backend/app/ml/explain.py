"""Phase 4 SHAP explanation engine, per docs/06-SCORING-METHODOLOGY.md §8.

Target variable: FMOM (business formation momentum — the doc's own suggested
proxy, "forward formation momentum"), predicted from the OTHER 6 indicators
(BFR, CAPI, MSMED, MMS, POPS, LIT). This is deliberately NOT opportunity_score
itself — opportunity_score is a deterministic weighted average of these same
indicators, so training a model to "predict" it back from its own inputs
would just have LightGBM re-derive a formula we already wrote down, not
surface genuine empirical structure. FMOM is a real, independent held-out
outcome. See migration cb2e5bd6a5eb's comment and STATUS.md for the full
reasoning behind keeping this in a separate table from the linear-weighted
opportunity_score decomposition.

Small-N regime (~550-780 rows depending on FMOM coverage): the model is
deliberately shallow (few leaves, high min_child_samples) and every reported
number is cross-validated, never train-set — with this few rows an
unregularised model would memorise, not learn. If cross-validated R² comes
back weak, that is reported honestly, not hidden — a SHAP explanation drawn
from a model that doesn't actually predict anything would be decoration, not
insight, and CLAUDE.md is explicit that this is not the way this project
reports results.
"""

import pandas as pd
import psycopg
import shap
from lightgbm import LGBMRegressor
from psycopg.types.json import Json
from sklearn.model_selection import KFold, cross_val_predict

from app.config import settings
from app.ml.kpis import compute_all_indicators
from app.ml.scoring import reference_month

TARGET = "FMOM"
FEATURES = ["BFR", "CAPI", "MSMED", "MMS", "POPS", "LIT"]

MODEL_PARAMS: dict[str, int | float | str] = {
    "n_estimators": 200,
    "num_leaves": 7,
    "max_depth": 3,
    "min_child_samples": 25,
    "learning_rate": 0.05,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "random_state": 20260815,
    "verbosity": -1,
}


def get_conn() -> psycopg.Connection:
    return psycopg.connect(settings.database_url.replace("+psycopg", ""))


def train_and_explain() -> dict:
    conn = get_conn()
    ref_month = reference_month(conn)
    date_key = ref_month.year * 100 + ref_month.month

    raw = compute_all_indicators()
    X_all = raw[FEATURES]
    y_all = raw[TARGET]

    # Training/CV needs the target present; LightGBM handles NaN in features
    # natively (a real split decision, not silent imputation), so training
    # rows only need to drop NaN target, not NaN features.
    train_mask = y_all.notna()
    X_train, y_train = X_all[train_mask], y_all[train_mask]
    n_train = int(train_mask.sum())

    model = LGBMRegressor(**MODEL_PARAMS)  # type: ignore[arg-type]  # heterogeneous dict vs LightGBM's precise **kwargs stub

    # Honest cross-validated R², not train-set R² — with ~550-780 rows and a
    # gradient-boosted model, train R² would be misleadingly high even if the
    # model has no real out-of-sample skill.
    cv = KFold(n_splits=5, shuffle=True, random_state=20260815)
    cv_preds = cross_val_predict(model, X_train, y_train, cv=cv)
    ss_res = float(((y_train - cv_preds) ** 2).sum())
    ss_tot = float(((y_train - y_train.mean()) ** 2).sum())
    cv_r2 = 1 - ss_res / ss_tot if ss_tot > 0 else None

    model.fit(X_train, y_train)
    explainer = shap.TreeExplainer(model)
    expected_value = explainer.expected_value
    base_value = float(expected_value[0]) if hasattr(expected_value, "__len__") else float(expected_value)

    # Predict + explain every district with at least one feature present —
    # FMOM itself doesn't need to be known to explain a district, only to
    # train the model.
    predict_mask = X_all.notna().any(axis=1)
    X_predict = X_all[predict_mask]
    predictions = model.predict(X_predict)
    shap_values = explainer.shap_values(X_predict)

    conn.execute("UPDATE meta.model_version SET is_active = false WHERE target_variable = %s", (TARGET,))
    model_row = conn.execute(
        """
        INSERT INTO meta.model_version
            (target_variable, feature_columns, cv_r2, cv_folds, n_train, base_value, model_params, is_active)
        VALUES (%s, %s, %s, %s, %s, %s, %s, true)
        RETURNING model_version_id
        """,
        (TARGET, Json(FEATURES), cv_r2, 5, n_train, base_value, Json(MODEL_PARAMS)),
    ).fetchone()
    assert model_row is not None
    model_version_id = model_row[0]

    for i, geo_key in enumerate(X_predict.index):
        for j, code in enumerate(FEATURES):
            feature_value = X_predict.iloc[i, j]
            conn.execute(
                """
                INSERT INTO gold.fact_shap_contribution
                    (geo_key, date_key, model_version_id, indicator_code, feature_value, shap_value, predicted_value)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (geo_key, date_key, model_version_id, indicator_code) DO UPDATE SET
                    feature_value = EXCLUDED.feature_value, shap_value = EXCLUDED.shap_value,
                    predicted_value = EXCLUDED.predicted_value
                """,
                (
                    int(geo_key), date_key, model_version_id, code,
                    float(feature_value) if not pd.isna(feature_value) else None,
                    round(float(shap_values[i, j]), 4),
                    round(float(predictions[i]), 4),
                ),
            )

    conn.commit()
    conn.close()

    return {
        "model_version_id": model_version_id,
        "target_variable": TARGET,
        "features": FEATURES,
        "n_train": n_train,
        "n_explained": len(X_predict),
        "cv_r2": round(cv_r2, 4) if cv_r2 is not None else None,
        "base_value": round(base_value, 4),
        "model_quality": _quality_label(cv_r2),
    }


def _quality_label(cv_r2: float | None) -> str:
    if cv_r2 is None:
        return "unknown"
    if cv_r2 >= 0.5:
        return "moderate-to-strong — SHAP contributions reflect real predictive structure"
    if cv_r2 >= 0.2:
        return "weak — SHAP contributions are suggestive only, not strong evidence"
    return "very weak or none — treat SHAP contributions as exploratory, not a reliable explanation"


if __name__ == "__main__":
    import json

    result = train_and_explain()
    print(json.dumps(result, indent=2, default=str))
