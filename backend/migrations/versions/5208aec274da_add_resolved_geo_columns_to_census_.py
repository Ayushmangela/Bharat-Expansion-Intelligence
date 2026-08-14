"""add resolved geo columns to census population

Revision ID: 5208aec274da
Revises: d77835febaad
Create Date: 2026-08-14 19:09:34.431065

"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '5208aec274da'
down_revision: str | Sequence[str] | None = 'd77835febaad'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Resolve census rows to LGD codes AT LOAD TIME through GeographyResolver
    # (pipeline/transforms/census_silver.py), instead of the ad-hoc
    # normalised-name dict compute_bfr.py used for the Goa/Bihar checkpoint.
    # That dict was keyed only by district name with no state scoping — a
    # real bug for the 3 genuinely-ambiguous district names found in the
    # Bihar stress test (Bilaspur, Hamirpur, Pratapgarh). See STATUS.md.
    op.execute("""
        ALTER TABLE silver.census_population_district
            ADD COLUMN lgd_state_code INT,
            ADD COLUMN lgd_district_code INT,
            ADD COLUMN resolution_method TEXT
    """)
    op.execute("""
        CREATE INDEX ix_census_pop_lgd ON silver.census_population_district
            (lgd_state_code, lgd_district_code)
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS silver.ix_census_pop_lgd")
    op.execute("""
        ALTER TABLE silver.census_population_district
            DROP COLUMN IF EXISTS lgd_state_code,
            DROP COLUMN IF EXISTS lgd_district_code,
            DROP COLUMN IF EXISTS resolution_method
    """)
