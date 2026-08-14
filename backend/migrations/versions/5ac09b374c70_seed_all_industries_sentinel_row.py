"""seed all-industries sentinel row

Revision ID: 5ac09b374c70
Revises: 66bd2d4f048b
Create Date: 2026-08-14 19:24:29.670760

"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '5ac09b374c70'
down_revision: str | Sequence[str] | None = '66bd2d4f048b'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # BUG FOUND wiring up Udyam: docs/03-DATA-MODEL.md's fact_district_month
    # comments "industry_key ... NULL = all industries" right next to
    # PRIMARY KEY (geo_key, date_key, industry_key) — but Postgres forbids
    # NULL in any primary key column, full stop. That combination cannot
    # work as documented; discovered when the first Udyam district-total
    # insert (no NIC breakdown) failed with NotNullViolation. Fix: an
    # explicit "All Industries" sentinel row instead of NULL — standard
    # dimensional-modeling practice for exactly this case anyway.
    op.execute("""
        INSERT INTO gold.dim_industry (industry_key, nic_2digit, nic_4digit, section, description, is_manufacturing)
        VALUES (1, '00', NULL, NULL, 'All Industries (unspecified / not split by NIC)', false)
    """)
    op.execute("SELECT setval('gold.dim_industry_industry_key_seq', 1, true)")


def downgrade() -> None:
    op.execute("DELETE FROM gold.dim_industry WHERE industry_key = 1")
