"""add pincode district lookup

Revision ID: 11d74a2e7874
Revises: 19f3c3de675d
Create Date: 2026-08-14 18:34:38.753116

"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '11d74a2e7874'
down_revision: str | Sequence[str] | None = '19f3c3de675d'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Direct pincode -> (statename, district) text lookup from the Dept of
    # Posts pincode directory. observed_district/observed_state are RAW text
    # as published (e.g. "NORTH GOA") — still resolved through the same
    # normalise()/alias/fuzzy path as any other observed geography string,
    # never joined to gold directly.
    op.execute("""
        CREATE TABLE silver.pincode_district_lookup (
            pincode           CHAR(6) PRIMARY KEY,
            observed_state    TEXT NOT NULL,
            observed_district TEXT NOT NULL
        )
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS silver.pincode_district_lookup")
