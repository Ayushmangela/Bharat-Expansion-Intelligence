"""fix idempotency: NULL-safe unique constraints

Revision ID: d77835febaad
Revises: 5cff293a9721
Create Date: 2026-08-14 18:53:47.702114

"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'd77835febaad'
down_revision: str | Sequence[str] | None = '5cff293a9721'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # BUG FOUND during Phase-1 idempotency verification: Postgres UNIQUE
    # constraints treat NULL as distinct from NULL, so re-running the LGD
    # loader (state rows carry lgd_district_code = NULL) silently inserted
    # duplicate state rows on every run — violating CLAUDE.md rule 15.
    # District rows were never affected (lgd_district_code is NOT NULL there).
    # Same pattern independently hit silver.geography_alias for state-only
    # aliases (observed_district = NULL, e.g. Orissa -> Odisha).

    # --- dedupe existing damage first ---
    op.execute("""
        DELETE FROM gold.dim_geography
        WHERE geo_key NOT IN (
            SELECT min(geo_key) FROM gold.dim_geography
            GROUP BY lgd_state_code, lgd_district_code, valid_from
        )
    """)
    op.execute("""
        DELETE FROM silver.geography_alias
        WHERE alias_id NOT IN (
            SELECT min(alias_id) FROM silver.geography_alias
            GROUP BY observed_state, observed_district
        )
    """)

    # --- replace NULL-unsafe UNIQUE constraints with COALESCE-based unique indexes ---
    op.execute("ALTER TABLE gold.dim_geography DROP CONSTRAINT dim_geography_lgd_state_code_lgd_district_code_valid_from_key")
    op.execute("""
        CREATE UNIQUE INDEX ux_dim_geography_natural_key
        ON gold.dim_geography (lgd_state_code, COALESCE(lgd_district_code, -1), valid_from)
    """)

    op.execute("ALTER TABLE silver.geography_alias DROP CONSTRAINT geography_alias_observed_state_observed_district_key")
    op.execute("""
        CREATE UNIQUE INDEX ux_geography_alias_natural_key
        ON silver.geography_alias (observed_state, COALESCE(observed_district, ''))
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS silver.ux_geography_alias_natural_key")
    op.execute(
        "ALTER TABLE silver.geography_alias ADD CONSTRAINT geography_alias_observed_state_observed_district_key "
        "UNIQUE (observed_state, observed_district)"
    )
    op.execute("DROP INDEX IF EXISTS gold.ux_dim_geography_natural_key")
    op.execute(
        "ALTER TABLE gold.dim_geography ADD CONSTRAINT dim_geography_lgd_state_code_lgd_district_code_valid_from_key "
        "UNIQUE (lgd_state_code, lgd_district_code, valid_from)"
    )
