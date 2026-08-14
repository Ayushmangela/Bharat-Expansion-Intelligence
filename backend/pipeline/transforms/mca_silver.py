"""Bronze -> silver -> gold.fact_company for one state's MCA snapshot.

Order per docs/04-ETL-PIPELINE.md Stage 3:
1. Pandera schema validation (fails the run on violation)
2. Dedup on CIN
3. Unit normalisation (capital fields -> numeric)
4. Period normalisation (registration date -> date)
5. Geography resolution (blocking — nothing reaches gold unresolved)
6. Outlier flagging (not yet implemented for fact_company; no numeric KPI
   distribution to winsorise at this grain yet)
"""

import re
from datetime import date, datetime
from pathlib import Path

import pandas as pd
import psycopg
from app.config import settings
from psycopg.types.json import Json

from pipeline.geography.resolver import GeographyResolver
from pipeline.schemas.mca import MCACompanyRawSchema

PIN_RE = re.compile(r"(\d{6})\D*$")

QUALITY_BIT_IMPUTED = 1
QUALITY_BIT_INHERITED = 2
QUALITY_BIT_OUTLIER = 4
QUALITY_BIT_WINSORISED = 8
QUALITY_BIT_FUZZY_GEO = 16
QUALITY_BIT_STALE = 32
QUALITY_BIT_PARTIAL_PERIOD = 64
QUALITY_BIT_REVISED = 128

STATUS_DISTRESS = {"Under Liquidation", "Strike Off", "Under process of striking off", "Dissolved (Liquidated)"}
COMPANIES_ACT_EPOCH = date(1858, 1, 1)  # British Companies Act 1857 — nothing plausible predates this


def parse_capital(value: str | None) -> float | None:
    if not value or not value.strip():
        return None
    cleaned = value.replace(",", "").strip()
    try:
        return float(cleaned)
    except ValueError:
        return None


def extract_pin(address: str | None) -> str | None:
    if not address:
        return None
    m = PIN_RE.search(address.strip())
    return m.group(1) if m else None


def get_conn() -> psycopg.Connection:
    return psycopg.connect(settings.database_url.replace("+psycopg", ""))


def ensure_company_status(conn: psycopg.Connection, status_name: str) -> int:
    row = conn.execute(
        "SELECT status_key FROM gold.dim_company_status WHERE status_name = %s", (status_name,)
    ).fetchone()
    if row:
        return row[0]
    is_active = status_name == "Active"
    is_distress = status_name in STATUS_DISTRESS
    row = conn.execute(
        """
        INSERT INTO gold.dim_company_status (status_name, is_active, is_distress)
        VALUES (%s, %s, %s) RETURNING status_key
        """,
        (status_name, is_active, is_distress),
    ).fetchone()
    assert row is not None  # RETURNING always yields exactly one row on success
    return row[0]


def transform_state(state_filter: str, ingest_date: date | None = None) -> dict:
    ingest_date = ingest_date or date.today()
    partition_dir = f"{settings.bronze_path}/source=S02_MCA/ingest_date={ingest_date.isoformat()}/state={state_filter}"
    # Read ALL part files, not just part-000 — a corrected re-fetch after a
    # truncated run (see datagovin_client.py / mca.py fix) writes additional
    # parts rather than overwriting bronze (bronze is immutable, rule 12).
    part_paths = sorted(Path(partition_dir).glob("part-*.parquet"))
    if not part_paths:
        raise FileNotFoundError(f"no bronze parts found in {partition_dir}")
    df = pd.concat([pd.read_parquet(p) for p in part_paths], ignore_index=True).fillna("")
    parquet_path = ";".join(str(p) for p in part_paths)

    # Stage 3.2 BEFORE 3.1 here, deliberately: dedup on natural key (CIN)
    # first, THEN validate schema. Found live re-transforming Delhi after
    # the pagination-truncation fix — bronze legitimately contains multiple
    # overlapping parts when a fetch was resumed/retried (part-000's rows
    # are a genuine subset of part-001's complete capture), so the raw
    # concatenation has duplicate CINs by design. Pandera's `unique=True`
    # check on CIN correctly rejects that if run first; uniqueness is a
    # property of the CLEANED dataset, not of raw bronze, so dedup has to
    # come first when reading multiple parts.
    before = len(df)
    df = df.drop_duplicates(subset=["CIN"], keep="last")
    df = MCACompanyRawSchema.validate(df)
    n_deduped = before - len(df)

    conn = get_conn()

    source_row = conn.execute(
        "SELECT source_key FROM meta.source WHERE source_code = 'S02_MCA'"
    ).fetchone()
    if not source_row:
        source_row = conn.execute(
            """
            INSERT INTO meta.source (source_code, source_name, publisher, url, licence,
                attribution_text, access_method, tier)
            VALUES ('S02_MCA', 'MCA Company Master Data', 'Ministry of Corporate Affairs',
                'https://www.data.gov.in/catalog/company-master-data', 'GODL-India',
                'Ministry of Corporate Affairs, Company Master Data, GODL-India, https://www.data.gov.in/catalog/company-master-data',
                'api', 'A')
            RETURNING source_key
            """
        ).fetchone()
        conn.commit()
    assert source_row is not None
    source_key = source_row[0]

    load_row = conn.execute(
        "INSERT INTO meta.ingestion_run (source_key, status) VALUES (%s, 'running') RETURNING load_id",
        (source_key,),
    ).fetchone()
    assert load_row is not None
    load_id = load_row[0]
    conn.commit()

    resolver = GeographyResolver(conn)

    n_loaded = 0
    n_quarantined = 0
    method_counts: dict[str, int] = {}

    for _, row in df.iterrows():
        cin = row["CIN"]
        address = row["Registered_Office_Address"] or None
        pin = extract_pin(address)

        resolution = resolver.resolve(
            observed_state=row["CompanyStateCode"],
            observed_pin=pin,
            address_text=address,
        )
        method_counts[resolution.method] = method_counts.get(resolution.method, 0) + 1

        reg_date_raw = row["CompanyRegistrationdate_date"]
        try:
            reg_date = datetime.strptime(reg_date_raw, "%Y-%m-%d").date() if reg_date_raw else None
        except ValueError:
            reg_date = None

        quality_flags = 0
        if resolution.is_fuzzy:
            quality_flags |= QUALITY_BIT_FUZZY_GEO

        # Outlier, not deleted (rule 4): found via the Goa checkpoint —
        # some registration dates are obvious data-entry errors
        # ("1111-01-01", 1949 predates the Companies Act 1956). Flag rather
        # than exclude from fact_company; KPI aggregations should filter on
        # this bit rather than assume every stored date is plausible.
        if reg_date is not None and not (COMPANIES_ACT_EPOCH <= reg_date <= date.today()):
            quality_flags |= QUALITY_BIT_OUTLIER

        if resolution.lgd_district_code is None:
            n_quarantined += 1
            conn.execute(
                """
                INSERT INTO silver.geography_quarantine
                    (load_id, source_code, observed_state, observed_district, observed_pin,
                     raw_row, best_guess_lgd, best_guess_score, resolved)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, false)
                """,
                (
                    load_id,
                    "S02_MCA",
                    row["CompanyStateCode"],
                    None,
                    pin,
                    Json(row.to_dict()),
                    resolution.lgd_state_code,
                    resolution.confidence,
                ),
            )
            continue

        geo_row = conn.execute(
            """
            SELECT geo_key FROM gold.dim_geography
            WHERE lgd_state_code = %s AND lgd_district_code = %s AND is_current
            """,
            (resolution.lgd_state_code, resolution.lgd_district_code),
        ).fetchone()
        if not geo_row:
            n_quarantined += 1
            continue
        geo_key = geo_row[0]

        status_key = ensure_company_status(conn, row["CompanyStatus"])

        conn.execute(
            """
            INSERT INTO gold.fact_company
                (cin, company_name, geo_key, status_key, incorporation_date,
                 authorized_capital, paid_up_capital, company_class, company_category,
                 pin_code, geocode_confidence, snapshot_date, quality_flags, load_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (cin) DO UPDATE SET
                geo_key = EXCLUDED.geo_key,
                status_key = EXCLUDED.status_key,
                paid_up_capital = EXCLUDED.paid_up_capital,
                quality_flags = EXCLUDED.quality_flags,
                snapshot_date = EXCLUDED.snapshot_date,
                load_id = EXCLUDED.load_id
            """,
            (
                cin,
                row["CompanyName"],
                geo_key,
                status_key,
                reg_date,
                parse_capital(row["AuthorizedCapital"]),
                parse_capital(row["PaidupCapital"]),
                row["CompanyClass"] or None,
                row["CompanyCategory"] or None,
                pin,
                resolution.confidence,
                ingest_date,
                quality_flags,
                load_id,
            ),
        )
        n_loaded += 1

    conn.commit()

    conn.execute(
        """
        UPDATE meta.ingestion_run
        SET finished_at = now(), status = 'success', rows_fetched = %s,
            rows_loaded = %s, rows_quarantined = %s, bronze_path = %s
        WHERE load_id = %s
        """,
        (len(df), n_loaded, n_quarantined, parquet_path, load_id),
    )
    conn.commit()
    conn.close()

    resolution_rate = n_loaded / len(df) if len(df) else 0.0

    return {
        "state": state_filter,
        "rows_fetched": before,
        "rows_deduped_out": n_deduped,
        "rows_loaded": n_loaded,
        "rows_quarantined": n_quarantined,
        "resolution_rate": round(resolution_rate, 4),
        "method_counts": method_counts,
        "load_id": load_id,
    }


if __name__ == "__main__":
    import json
    import sys

    state = sys.argv[1] if len(sys.argv) > 1 else "goa"
    result = transform_state(state)
    print(json.dumps(result, indent=2))
