"""add scoring schema: dim_profile, weight_version, fact_opportunity_score, fact_score_contribution

Revision ID: 475c62829513
Revises: 49775eda11bd
Create Date: 2026-08-15 11:00:04.506213

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '475c62829513'
down_revision: Union[str, Sequence[str], None] = '49775eda11bd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Phase 3 scoring schema, per docs/03-DATA-MODEL.md, docs/06-SCORING-METHODOLOGY.md.
    #
    # SCOPE DECISION, made now rather than pretending otherwise: only 7 of the
    # 22 documented KPIs are computable from data actually loaded so far
    # (BFR, FMOM, CAPI economic; MSMED, MMS ecosystem; POPS, LIT human
    # capital) — everything needing GST, DPIIT, ASI/PLFS, RBI, or CEA data
    # is not available. The infrastructure pillar has ZERO computable
    # indicators and is excluded entirely from this phase's score, not
    # faked with a placeholder — pillar_infrastructure stays NULL on every
    # row. This matches docs/11-ROADMAP.md's own explicitly sanctioned
    # reduced-scope fallback ("8 indicators instead of 22").
    #
    # fact_score_contribution.shap_contribution is populated with a linear
    # weighted contribution (weight * normalised_value), NOT real SHAP —
    # Phase 4 (LightGBM + SHAP TreeExplainer) hasn't run. A
    # `contribution_method` column distinguishes this explicitly so nobody
    # downstream mistakes a linear decomposition for SHAP.
    op.execute("""
        CREATE TABLE meta.weight_version (
            weight_version_id SERIAL PRIMARY KEY,
            profile_code      TEXT NOT NULL,
            method            TEXT NOT NULL,
            weights           JSONB NOT NULL,
            created_at        TIMESTAMPTZ DEFAULT now(),
            is_active         BOOLEAN DEFAULT false
        )
    """)

    op.execute("""
        CREATE TABLE gold.dim_profile (
            profile_key    SERIAL PRIMARY KEY,
            profile_code   TEXT NOT NULL UNIQUE,
            profile_name   TEXT NOT NULL,
            description    TEXT,
            pillar_weights JSONB NOT NULL
        )
    """)

    op.execute("""
        CREATE TABLE gold.fact_opportunity_score (
            geo_key               BIGINT NOT NULL REFERENCES gold.dim_geography,
            date_key              INT    NOT NULL REFERENCES gold.dim_date,
            profile_key           INT    NOT NULL REFERENCES gold.dim_profile,
            opportunity_score     NUMERIC(6,3) NOT NULL CHECK (opportunity_score BETWEEN 0 AND 100),
            pillar_economic       NUMERIC(6,3),
            pillar_ecosystem      NUMERIC(6,3),
            pillar_infrastructure NUMERIC(6,3),
            pillar_human_capital  NUMERIC(6,3),
            rank_national         INT,
            rank_within_state     INT,
            rank_ci_low           INT,
            rank_ci_high          INT,
            confidence_score      NUMERIC(5,4) NOT NULL,
            indicators_used       INT NOT NULL,
            indicators_total      INT NOT NULL,
            weight_version_id     INT NOT NULL REFERENCES meta.weight_version,
            computed_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
            PRIMARY KEY (geo_key, date_key, profile_key, weight_version_id)
        )
    """)

    op.execute("""
        CREATE TABLE gold.fact_score_contribution (
            geo_key            BIGINT NOT NULL,
            date_key           INT    NOT NULL,
            profile_key        INT    NOT NULL,
            weight_version_id  INT    NOT NULL,
            indicator_code     TEXT   NOT NULL,
            raw_value          NUMERIC(18,4),
            normalised_value   NUMERIC(8,4),
            shap_contribution  NUMERIC(8,4) NOT NULL,
            contribution_method TEXT NOT NULL DEFAULT 'linear_weighted',
            is_imputed         BOOLEAN NOT NULL DEFAULT false,
            is_inherited       BOOLEAN NOT NULL DEFAULT false,
            source_code        TEXT NOT NULL,
            PRIMARY KEY (geo_key, date_key, profile_key, weight_version_id, indicator_code)
        )
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS gold.fact_score_contribution")
    op.execute("DROP TABLE IF EXISTS gold.fact_opportunity_score")
    op.execute("DROP TABLE IF EXISTS gold.dim_profile")
    op.execute("DROP TABLE IF EXISTS meta.weight_version")
