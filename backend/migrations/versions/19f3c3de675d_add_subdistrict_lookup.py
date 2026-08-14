"""add subdistrict lookup

Revision ID: 19f3c3de675d
Revises: c2a69df9db6d
Create Date: 2026-08-14 18:31:04.182286

"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '19f3c3de675d'
down_revision: str | Sequence[str] | None = 'c2a69df9db6d'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Resolver Step 4c: sub-district (taluka/tehsil) name found in address text
    # maps to a parent district. Added after the Phase 1 checkpoint on Goa MCA
    # data showed real addresses reference talukas ("Salcete", "Bardez",
    # "Mormugao") far more often than district names themselves. See STATUS.md.
    op.execute("""
        CREATE TABLE silver.lgd_subdistrict_lookup (
            lgd_state_code     INT NOT NULL,
            lgd_district_code  INT NOT NULL,
            subdistrict_code   INT NOT NULL,
            subdistrict_name   TEXT NOT NULL,
            PRIMARY KEY (lgd_state_code, subdistrict_code)
        )
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS silver.lgd_subdistrict_lookup")
