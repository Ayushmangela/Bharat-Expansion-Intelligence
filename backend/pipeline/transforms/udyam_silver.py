"""Bronze -> silver.udyam_snapshot + gold.fact_district_month for Udyam MSME.

Geography: `lg_dt_code` is a genuine LGD district code (confirmed Phase 0),
but is NOT always trustworthy as-is — Udyam's own data lags LGD district
splits. Found in Rajasthan (2023 splits: Anupgarh/Ganganagar, Dudu/Jaipur,
Jaipur Gramin/Jaipur, Sanchore/Jalore, Jodhpur Gramin/Jodhpur,
Gangapurcity/Sawai Madhopur, Neem Ka Thana/Sikar, Kekri/Ajmer,
Shahpura/Bhilwara — 8 pairs) and Puducherry (Yanam/Mahe both tagged with
Puducherry's own code instead of their own). Strategy: trust lg_dt_code only
when it maps to a dim_geography row whose district_name also matches (case-
insensitive); otherwise fall back to resolving state+district TEXT through
GeographyResolver, same as every other source. Quarantine what neither path
resolves.

msme_manufacturing is DERIVED as total - services (no Udyam manufacturing-
specific resource was found in Phase 0 discovery — see
docs/RESOURCE-REGISTRY.md S03). This is "everything that isn't services",
not manufacturing specifically — labelled as an approximation, not hidden.
"""

from datetime import date

import pandas as pd
import psycopg
from app.config import settings
from psycopg.types.json import Json

from pipeline.geography.resolver import GeographyResolver, normalise

QUALITY_BIT_FUZZY_GEO = 16
ALL_INDUSTRIES_KEY = 1  # gold.dim_industry sentinel row — see migration 5ac09b374c70


def parse_int(value: str | None) -> int:
    try:
        return int(str(value).strip() or 0)
    except (TypeError, ValueError):
        return 0


def transform(ingest_date: date | None = None) -> dict:
    ingest_date = ingest_date or date.today()
    total_path = f"{settings.bronze_path}/source=S03_UDYAM/ingest_date={ingest_date.isoformat()}/total/part-000.parquet"
    services_path = f"{settings.bronze_path}/source=S03_UDYAM/ingest_date={ingest_date.isoformat()}/services/part-000.parquet"

    total_df = pd.read_parquet(total_path)
    services_df = pd.read_parquet(services_path)

    # Merge on (lg_dt_code, district_name), not lg_dt_code alone — lg_dt_code
    # has 11 duplicate values on each side (Rajasthan's 2023 district splits,
    # Puducherry's sub-regions all sharing the parent's stale code; see
    # module docstring), and a merge on lg_dt_code alone fans out into a
    # cartesian product wherever both sides have the same duplicate code
    # (788 rows became 814 on the first attempt — caught before trusting it).
    total_df["_merge_key"] = total_df["district_name"].str.strip().str.casefold()
    services_df["_merge_key"] = services_df["district_name"].str.strip().str.casefold()
    merged = total_df.merge(
        services_df[["lg_dt_code", "_merge_key", "micro", "small", "medium", "total"]],
        on=["lg_dt_code", "_merge_key"],
        how="left",
        suffixes=("", "_services"),
    )
    assert len(merged) == len(total_df), f"merge fanned out: {len(total_df)} -> {len(merged)}"

    conn = psycopg.connect(settings.database_url.replace("+psycopg", ""))
    resolver = GeographyResolver(conn)

    source_row = conn.execute("SELECT source_key FROM meta.source WHERE source_code = 'S03_UDYAM'").fetchone()
    if not source_row:
        source_row = conn.execute(
            """
            INSERT INTO meta.source (source_code, source_name, publisher, url, licence,
                attribution_text, access_method, tier)
            VALUES ('S03_UDYAM', 'Udyam MSME Registration (district-wise)',
                'Ministry of Micro, Small and Medium Enterprises',
                'https://www.data.gov.in/catalog/udyam-registration-msme-registration', 'GODL-India',
                'Ministry of MSME, Udyam Registration, GODL-India, https://www.data.gov.in/catalog/udyam-registration-msme-registration',
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

    date_key = ingest_date.year * 100 + ingest_date.month

    n_resolved_by_code = 0
    n_resolved_by_name = 0
    n_quarantined = 0

    for _, row in merged.iterrows():
        lg_dt_code = parse_int(row["lg_dt_code"])
        district_name_raw = str(row["district_name"])
        state_name_raw = str(row["state_name"])

        code_row = conn.execute(
            "SELECT geo_key, lgd_state_code, lgd_district_code, district_name FROM gold.dim_geography "
            "WHERE lgd_district_code = %s AND grain = 'district' AND is_current",
            (lg_dt_code,),
        ).fetchone()

        geo_key = None
        lgd_state_code = None
        lgd_district_code = None
        quality_flags = 0

        if code_row and normalise(code_row[3]) == normalise(district_name_raw):
            geo_key, lgd_state_code, lgd_district_code, _ = code_row
            n_resolved_by_code += 1
        else:
            resolution = resolver.resolve(observed_state=state_name_raw, observed_district=district_name_raw)
            if resolution.lgd_district_code is not None:
                geo_row = conn.execute(
                    "SELECT geo_key FROM gold.dim_geography WHERE lgd_state_code=%s AND lgd_district_code=%s AND is_current",
                    (resolution.lgd_state_code, resolution.lgd_district_code),
                ).fetchone()
                if geo_row:
                    geo_key = geo_row[0]
                    lgd_state_code = resolution.lgd_state_code
                    lgd_district_code = resolution.lgd_district_code
                    quality_flags |= QUALITY_BIT_FUZZY_GEO
                    n_resolved_by_name += 1

        if geo_key is None:
            n_quarantined += 1
            conn.execute(
                """
                INSERT INTO silver.geography_quarantine
                    (load_id, source_code, observed_state, observed_district, raw_row, resolved)
                VALUES (%s, 'S03_UDYAM', %s, %s, %s, false)
                """,
                (load_id, state_name_raw, district_name_raw, Json(row.to_dict())),
            )
            continue

        micro, small, medium, total = parse_int(row["micro"]), parse_int(row["small"]), parse_int(row["medium"]), parse_int(row["total"])
        s_micro = parse_int(row.get("micro_services"))
        s_small = parse_int(row.get("small_services"))
        s_medium = parse_int(row.get("medium_services"))
        s_total = parse_int(row.get("total_services"))

        conn.execute(
            """
            INSERT INTO silver.udyam_snapshot
                (lgd_state_code, lgd_district_code, snapshot_date, micro, small, medium, total,
                 services_micro, services_small, services_medium, services_total, load_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (lgd_state_code, lgd_district_code, snapshot_date) DO UPDATE SET
                micro = EXCLUDED.micro, small = EXCLUDED.small, medium = EXCLUDED.medium, total = EXCLUDED.total,
                services_micro = EXCLUDED.services_micro, services_small = EXCLUDED.services_small,
                services_medium = EXCLUDED.services_medium, services_total = EXCLUDED.services_total,
                load_id = EXCLUDED.load_id
            """,
            (lgd_state_code, lgd_district_code, ingest_date, micro, small, medium, total, s_micro, s_small, s_medium, s_total, load_id),
        )

        conn.execute(
            """
            INSERT INTO gold.fact_district_month
                (geo_key, date_key, industry_key, msme_micro, msme_small, msme_medium,
                 msme_manufacturing, msme_services, quality_flags, load_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (geo_key, date_key, industry_key) DO UPDATE SET
                msme_micro = EXCLUDED.msme_micro, msme_small = EXCLUDED.msme_small, msme_medium = EXCLUDED.msme_medium,
                msme_manufacturing = EXCLUDED.msme_manufacturing, msme_services = EXCLUDED.msme_services,
                quality_flags = EXCLUDED.quality_flags, load_id = EXCLUDED.load_id
            """,
            (geo_key, date_key, ALL_INDUSTRIES_KEY, micro, small, medium, total - s_total, s_total, quality_flags, load_id),
        )

    conn.execute(
        """
        UPDATE meta.ingestion_run
        SET finished_at = now(), status = 'success', rows_fetched = %s,
            rows_loaded = %s, rows_quarantined = %s
        WHERE load_id = %s
        """,
        (len(merged), n_resolved_by_code + n_resolved_by_name, n_quarantined, load_id),
    )
    conn.commit()
    conn.close()

    total_rows = len(merged)
    return {
        "rows_total": total_rows,
        "resolved_by_code": n_resolved_by_code,
        "resolved_by_name_fallback": n_resolved_by_name,
        "quarantined": n_quarantined,
        "resolution_rate": round((n_resolved_by_code + n_resolved_by_name) / total_rows, 4) if total_rows else 0.0,
        "load_id": load_id,
    }


if __name__ == "__main__":
    import json

    print(json.dumps(transform(), indent=2))
