"""add fact_district_month and udyam snapshot table

Revision ID: 66bd2d4f048b
Revises: 5208aec274da
Create Date: 2026-08-14 19:20:16.188457

"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '66bd2d4f048b'
down_revision: str | Sequence[str] | None = '5208aec274da'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # gold.fact_district_month, exactly as specified in docs/03-DATA-MODEL.md
    # (deferred out of the Phase 1 migration since nothing populated it yet —
    # Udyam is the first source that needs it). Partitioned by date_key
    # (YYYYMM) per the doc's comment; only the current year's partition is
    # created here, more added as needed.
    op.execute("""
        CREATE TABLE gold.fact_district_month (
            geo_key                      BIGINT NOT NULL REFERENCES gold.dim_geography,
            date_key                     INT    NOT NULL REFERENCES gold.dim_date,
            industry_key                 INT    REFERENCES gold.dim_industry,
            new_incorporations           INT,
            median_paid_up_capital_lakh  NUMERIC(14,2),
            total_paid_up_capital_lakh   NUMERIC(18,2),
            active_companies             INT,
            struck_off_companies         INT,
            msme_micro                   INT,
            msme_small                   INT,
            msme_medium                  INT,
            msme_manufacturing           INT,
            msme_services                INT,
            startups_recognised          INT,
            quality_flags                INT NOT NULL DEFAULT 0,
            load_id                      BIGINT NOT NULL REFERENCES meta.ingestion_run,
            PRIMARY KEY (geo_key, date_key, industry_key)
        ) PARTITION BY RANGE (date_key)
    """)
    op.execute("""
        CREATE TABLE gold.fact_district_month_2026 PARTITION OF gold.fact_district_month
            FOR VALUES FROM (202601) TO (202701)
    """)

    # Udyam publishes CUMULATIVE-TO-DATE counts with no date field of its own
    # (docs/09-DATA-QUALITY.md / CLAUDE.md known limitation). This table
    # stores every raw snapshot as pulled, per docs/04-ETL-PIPELINE.md
    # "store every snapshot" — required for future flow-diffing even though
    # the current KPIs (MSMED, MMS in 05-KPI-DEFINITIONS.md) consume the
    # cumulative stock values directly, not a derived monthly flow.
    op.execute("""
        CREATE TABLE silver.udyam_snapshot (
            snapshot_id       BIGSERIAL PRIMARY KEY,
            lgd_state_code    INT NOT NULL,
            lgd_district_code INT NOT NULL,
            snapshot_date     DATE NOT NULL,
            micro             INT NOT NULL,
            small             INT NOT NULL,
            medium            INT NOT NULL,
            total             INT NOT NULL,
            services_micro    INT,
            services_small    INT,
            services_medium   INT,
            services_total    INT,
            load_id           BIGINT NOT NULL REFERENCES meta.ingestion_run,
            UNIQUE (lgd_state_code, lgd_district_code, snapshot_date)
        )
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS silver.udyam_snapshot")
    op.execute("DROP TABLE IF EXISTS gold.fact_district_month")
