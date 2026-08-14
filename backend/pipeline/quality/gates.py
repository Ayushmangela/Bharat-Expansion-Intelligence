"""Five validation gates, per docs/09-DATA-QUALITY.md.

Gate 1 (Ingestion) is enforced inline in DataGovInClient (status-code
handling, empty-body via `if not records: break`) rather than as a
standalone post-hoc check — there's nothing left to validate once a
response has already been parsed into records. validate_ingestion_response()
below exists for connectors that want an explicit, auditable check anyway.

Gates 2-5 run against data already loaded into silver/gold and write
failures to meta.quality_event. A failed gate does not undo the load
(bronze/gold already committed) — it flags for investigation, per
CLAUDE.md's "fails loudly, never silently corrupts" principle applied after
the fact for gates that can only be evaluated once data is loaded (referential,
statistical).
"""

from dataclasses import dataclass, field

import psycopg
from app.config import settings
from psycopg.types.json import Json


@dataclass
class GateResult:
    gate: str
    passed: bool
    message: str
    details: dict = field(default_factory=dict)


def get_conn() -> psycopg.Connection:
    return psycopg.connect(settings.database_url.replace("+psycopg", ""))


def log_quality_event(conn: psycopg.Connection, load_id: int | None, gate: str, severity: str, message: str, row_sample: dict | None = None) -> None:
    conn.execute(
        "INSERT INTO meta.quality_event (load_id, gate, severity, message, row_sample) VALUES (%s, %s, %s, %s, %s)",
        (load_id, gate, severity, message, Json(row_sample) if row_sample else None),
    )
    conn.commit()


# --- Gate 1: Ingestion -------------------------------------------------

def validate_ingestion_response(status_code: int, body: dict | None, content_type: str | None) -> GateResult:
    if status_code != 200:
        return GateResult("ingestion", False, f"non-200 status: {status_code}")
    if not body or not isinstance(body, dict):
        return GateResult("ingestion", False, "empty or non-JSON body")
    if content_type and "json" not in content_type.lower():
        return GateResult("ingestion", False, f"unexpected content-type: {content_type}")
    if "records" not in body:
        return GateResult("ingestion", False, "response missing 'records' field")
    return GateResult("ingestion", True, "ok")


# --- Gate 3: Business rules ---------------------------------------------

def gate3_business_rules(conn: psycopg.Connection, load_id: int | None = None) -> list[GateResult]:
    results = []

    # paid_up_capital <= authorized_capital (docs/09-DATA-QUALITY.md Gate 3)
    row = conn.execute(
        "SELECT count(*) FROM gold.fact_company "
        "WHERE paid_up_capital IS NOT NULL AND authorized_capital IS NOT NULL "
        "AND paid_up_capital > authorized_capital"
    ).fetchone()
    assert row is not None
    n_violations = row[0]
    if n_violations:
        sample = conn.execute(
            "SELECT cin, paid_up_capital, authorized_capital FROM gold.fact_company "
            "WHERE paid_up_capital > authorized_capital LIMIT 5"
        ).fetchall()
        result = GateResult(
            "business_rules", False,
            f"{n_violations} fact_company rows have paid_up_capital > authorized_capital",
            {"sample": [[float(v) if hasattr(v, "as_tuple") else v for v in r] for r in sample]},
        )
        log_quality_event(conn, load_id, "business_rules", "warn", result.message, result.details)
    else:
        result = GateResult("business_rules", True, "paid_up_capital <= authorized_capital: 0 violations")
    results.append(result)

    # incorporation_date <= today
    row = conn.execute(
        "SELECT count(*) FROM gold.fact_company WHERE incorporation_date > CURRENT_DATE"
    ).fetchone()
    assert row is not None
    n_future = row[0]
    if n_future:
        result = GateResult("business_rules", False, f"{n_future} fact_company rows have incorporation_date in the future")
        log_quality_event(conn, load_id, "business_rules", "error", result.message)
    else:
        result = GateResult("business_rules", True, "incorporation_date <= today: 0 violations")
    results.append(result)

    # msme_micro + msme_small + msme_medium == msme_total, where total is derivable
    # (msme_manufacturing + msme_services approximates total per udyam_silver.py)
    row = conn.execute(
        "SELECT count(*) FROM gold.fact_district_month "
        "WHERE msme_micro IS NOT NULL "
        "AND (msme_micro + msme_small + msme_medium) != (msme_manufacturing + msme_services)"
    ).fetchone()
    assert row is not None
    n_mismatch = row[0]
    if n_mismatch:
        sample = conn.execute(
            "SELECT geo_key, msme_micro, msme_small, msme_medium, msme_manufacturing, msme_services "
            "FROM gold.fact_district_month "
            "WHERE msme_micro IS NOT NULL "
            "AND (msme_micro + msme_small + msme_medium) != (msme_manufacturing + msme_services) LIMIT 5"
        ).fetchall()
        result = GateResult(
            "business_rules", False,
            f"{n_mismatch} fact_district_month rows: micro+small+medium != manufacturing+services",
            {"sample": [[float(v) if hasattr(v, "as_tuple") else v for v in r] for r in sample]},
        )
        log_quality_event(conn, load_id, "business_rules", "warn", result.message, result.details)
    else:
        result = GateResult("business_rules", True, "msme_micro+small+medium == msme_manufacturing+services: 0 violations")
    results.append(result)

    return results


# --- Gate 4: Referential -------------------------------------------------

def gate4_referential(conn: psycopg.Connection, load_id: int | None = None) -> list[GateResult]:
    results = []

    checks = [
        ("fact_company.geo_key -> dim_geography", """
            SELECT count(*) FROM gold.fact_company f
            LEFT JOIN gold.dim_geography g ON g.geo_key = f.geo_key
            WHERE g.geo_key IS NULL
        """),
        ("fact_company.status_key -> dim_company_status", """
            SELECT count(*) FROM gold.fact_company f
            LEFT JOIN gold.dim_company_status s ON s.status_key = f.status_key
            WHERE f.status_key IS NOT NULL AND s.status_key IS NULL
        """),
        ("fact_district_month.geo_key -> dim_geography", """
            SELECT count(*) FROM gold.fact_district_month f
            LEFT JOIN gold.dim_geography g ON g.geo_key = f.geo_key
            WHERE g.geo_key IS NULL
        """),
        ("fact_district_month.date_key -> dim_date", """
            SELECT count(*) FROM gold.fact_district_month f
            LEFT JOIN gold.dim_date d ON d.date_key = f.date_key
            WHERE d.date_key IS NULL
        """),
        ("fact_district_month.industry_key -> dim_industry", """
            SELECT count(*) FROM gold.fact_district_month f
            LEFT JOIN gold.dim_industry i ON i.industry_key = f.industry_key
            WHERE i.industry_key IS NULL
        """),
        # "Zero unresolved geographies" — nothing in gold should reference a
        # geo_key that doesn't exist; already covered above. This checks the
        # complementary direction: nothing sitting unresolved in quarantine
        # that SHOULD have made it to gold by now is out of scope for an
        # automated gate (quarantine is expected to hold genuine failures).
    ]

    for name, sql in checks:
        row = conn.execute(sql).fetchone()
        assert row is not None
        n_orphans = row[0]
        if n_orphans:
            result = GateResult("referential", False, f"{name}: {n_orphans} orphans")
            log_quality_event(conn, load_id, "referential", "error", result.message)
        else:
            result = GateResult("referential", True, f"{name}: 0 orphans")
        results.append(result)

    return results


# --- Gate 5: Statistical -------------------------------------------------

def gate5_statistical(conn: psycopg.Connection, source_code: str, current_rows_loaded: int, load_id: int | None = None) -> GateResult:
    """Row count within +/-30% of the trailing average for this source.

    Needs at least 2 prior successful loads to have a trailing average —
    with only one snapshot per source so far (this is Phase 2's first
    national sweep), this gate is PRIMED but not yet meaningfully exercised
    for most sources. Documented, not hidden: see STATUS.md.
    """
    row = conn.execute(
        """
        SELECT avg(rows_loaded), count(*) FROM meta.ingestion_run r
        JOIN meta.source s ON s.source_key = r.source_key
        WHERE s.source_code = %s AND r.status = 'success' AND r.rows_loaded IS NOT NULL
        """,
        (source_code,),
    ).fetchone()
    assert row is not None
    trailing_avg, n_prior_runs = row

    if trailing_avg is None or n_prior_runs < 2:
        return GateResult(
            "statistical", True,
            f"insufficient history for {source_code} ({n_prior_runs or 0} prior run(s)) — gate not evaluated, not failed",
        )

    lower, upper = trailing_avg * 0.7, trailing_avg * 1.3
    if not (lower <= current_rows_loaded <= upper):
        result = GateResult(
            "statistical", False,
            f"{source_code}: {current_rows_loaded} rows loaded vs trailing avg {trailing_avg:.0f} "
            f"(expected {lower:.0f}-{upper:.0f})",
        )
        log_quality_event(conn, load_id, "statistical", "warn", result.message)
        return result

    return GateResult("statistical", True, f"{source_code}: {current_rows_loaded} within +/-30% of trailing avg {trailing_avg:.0f}")


def mca_snapshot_gate(conn: psycopg.Connection, new_row_count: int, prior_row_count: int | None) -> GateResult:
    """MCA-specific: new snapshot < 95% of prior row count -> quarantine, don't diff.
    A truncated download would otherwise register as mass corporate extinction.
    """
    if prior_row_count is None:
        return GateResult("statistical", True, "no prior MCA snapshot to compare — gate not evaluated")
    if new_row_count < prior_row_count * 0.95:
        return GateResult(
            "statistical", False,
            f"MCA snapshot has {new_row_count} rows, <95% of prior {prior_row_count} — quarantine, do not diff",
        )
    return GateResult("statistical", True, f"MCA snapshot {new_row_count} rows >= 95% of prior {prior_row_count}")


# --- Runner ---------------------------------------------------------------

def run_business_and_referential_gates() -> dict:
    """Runs gates 3 and 4 against current gold state (source-agnostic, run
    after any load or on demand)."""
    conn = get_conn()
    results = gate3_business_rules(conn) + gate4_referential(conn)
    conn.close()

    n_passed = sum(1 for r in results if r.passed)
    return {
        "total": len(results),
        "passed": n_passed,
        "failed": len(results) - n_passed,
        "results": [{"gate": r.gate, "passed": r.passed, "message": r.message} for r in results],
    }


if __name__ == "__main__":
    import json

    print(json.dumps(run_business_and_referential_gates(), indent=2))
