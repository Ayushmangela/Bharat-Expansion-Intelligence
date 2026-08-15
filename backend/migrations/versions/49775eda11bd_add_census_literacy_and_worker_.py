"""add census literacy and worker classification table

Revision ID: 49775eda11bd
Revises: 5ac09b374c70
Create Date: 2026-08-15 10:50:00.905898

"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '49775eda11bd'
down_revision: str | Sequence[str] | None = '5ac09b374c70'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Census 2011 Primary Census Abstract (PCA), district grain — literacy +
    # worker classification, found via the Phase 2 research agent (not on
    # data.gov.in; see docs/RESOURCE-REGISTRY.md S19). Resolved to LGD codes
    # at load time through GeographyResolver, same pattern as
    # census_population_district — this table's own "State"/"District"
    # columns are Census's own numeric codes, not LGD, and (as already
    # confirmed for the population table) not even the SAME numbering as
    # LGD's own census2011_code fields, so never join on the codes directly.
    #
    # NOTE ON "WORKING-AGE POPULATION": this table has no clean 15-59 age
    # bucket at district grain — only a 0-6 breakdown (P_06). population_6plus
    # (TOT_P - P_06) is stored as a real, honestly-labeled improvement over
    # the total-population proxy BFR used before this, but it is NOT the same
    # as "working-age (15-59)" and must not be presented as such.
    op.execute("""
        CREATE TABLE silver.census_literacy_worker_district (
            state_census2011_code    TEXT NOT NULL,
            district_census2011_code TEXT NOT NULL,
            state_name               TEXT NOT NULL,
            district_name            TEXT NOT NULL,
            lgd_state_code           INT,
            lgd_district_code        INT,
            resolution_method        TEXT,
            population_total         BIGINT NOT NULL,
            population_0_6           BIGINT NOT NULL,
            population_6plus         BIGINT NOT NULL,
            literates                BIGINT NOT NULL,
            illiterates              BIGINT NOT NULL,
            total_workers            BIGINT NOT NULL,
            main_workers             BIGINT NOT NULL,
            main_cultivators         BIGINT NOT NULL,
            main_agri_labourers      BIGINT NOT NULL,
            main_household_industry  BIGINT NOT NULL,
            main_other_workers       BIGINT NOT NULL,
            marginal_workers         BIGINT NOT NULL,
            non_workers               BIGINT NOT NULL,
            PRIMARY KEY (state_census2011_code, district_census2011_code)
        )
    """)
    op.execute("""
        CREATE INDEX ix_census_lit_worker_lgd ON silver.census_literacy_worker_district
            (lgd_state_code, lgd_district_code)
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS silver.census_literacy_worker_district")
