"""add model_version and fact_shap_contribution for Phase 4 SHAP engine

Revision ID: cb2e5bd6a5eb
Revises: 475c62829513
Create Date: 2026-08-15 11:46:55.257709

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'cb2e5bd6a5eb'
down_revision: Union[str, Sequence[str], None] = '475c62829513'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Phase 4 — SHAP explanation engine, per docs/06-SCORING-METHODOLOGY.md §8.
    #
    # DEVIATION FROM A LITERAL READING OF §8, documented here and in
    # STATUS.md: the doc says "store every contribution in
    # gold.fact_score_contribution" (the same table linear_weighted
    # contributions already live in). We deliberately did NOT do that.
    #
    # gold.fact_score_contribution's contract (built and tested earlier this
    # phase) is that sum(shap_contribution) for a district == that
    # district's opportunity_score exactly, in the same 0-100 units, for the
    # SAME target the score already represents. The SHAP model here predicts
    # something genuinely different: FMOM (business formation momentum) from
    # the other 6 indicators, held out as a real regression target — not the
    # opportunity_score itself, because opportunity_score is a deterministic
    # function of those same indicators, so "predicting" it back from its own
    # inputs would just have LightGBM re-derive the known weighted-average
    # formula, teaching us nothing a linear decomposition didn't already
    # show. FMOM is a genuine held-out outcome in FMOM's own units (a ratio,
    # not 0-100), so its SHAP contributions cannot honestly be summed
    # alongside opportunity_score's linear contributions without silently
    # mixing units. A separate table keeps that boundary explicit instead of
    # letting a future query silently sum across two incompatible measures.
    op.execute("""
        CREATE TABLE meta.model_version (
            model_version_id SERIAL PRIMARY KEY,
            target_variable   TEXT NOT NULL,
            feature_columns   JSONB NOT NULL,
            cv_r2             NUMERIC(6,4),
            cv_folds          INT,
            n_train           INT NOT NULL,
            base_value        NUMERIC(10,4) NOT NULL,
            model_params      JSONB NOT NULL,
            trained_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
            is_active         BOOLEAN DEFAULT false
        )
    """)

    op.execute("""
        CREATE TABLE gold.fact_shap_contribution (
            geo_key           BIGINT NOT NULL REFERENCES gold.dim_geography,
            date_key          INT    NOT NULL REFERENCES gold.dim_date,
            model_version_id  INT    NOT NULL REFERENCES meta.model_version,
            indicator_code    TEXT   NOT NULL,
            feature_value     NUMERIC(18,4),
            shap_value        NUMERIC(10,4) NOT NULL,
            predicted_value   NUMERIC(10,4) NOT NULL,
            computed_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
            PRIMARY KEY (geo_key, date_key, model_version_id, indicator_code)
        )
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS gold.fact_shap_contribution")
    op.execute("DROP TABLE IF EXISTS meta.model_version")
