"""add census population reference table

Revision ID: 5cff293a9721
Revises: 11d74a2e7874
Create Date: 2026-08-14 18:40:30.498900

"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '5cff293a9721'
down_revision: str | Sequence[str] | None = '11d74a2e7874'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Reference crosswalk, not a gold fact table. Keyed on CENSUS's own state/
    # district codes (not LGD) since that's what the source publishes; joins
    # to gold.dim_geography via its state_census2011_code/district_census2011_code
    # columns. See pipeline/connectors/census.py docstring for why this isn't
    # in the star schema proper yet.
    op.execute("""
        CREATE TABLE silver.census_population_district (
            state_census2011_code    TEXT NOT NULL,
            district_census2011_code TEXT NOT NULL,
            state_name               TEXT NOT NULL,
            district_name            TEXT NOT NULL,
            population_total_2011    BIGINT NOT NULL,
            population_rural_2011    BIGINT NOT NULL,
            population_urban_2011    BIGINT NOT NULL,
            PRIMARY KEY (state_census2011_code, district_census2011_code)
        )
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS silver.census_population_district")
