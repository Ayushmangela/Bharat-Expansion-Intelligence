"""KPI computation, per docs/05-KPI-DEFINITIONS.md.

SCOPE: only the 7 KPIs computable from data actually loaded so far. Every
other documented KPI needs a source that isn't loaded (GST, DPIIT, ASI/PLFS,
RBI, CEA) — see docs/RESOURCE-REGISTRY.md for status per source. This is a
real scope decision, not an oversight; see migration 475c62829513's comment
and STATUS.md for the full reasoning.

Reference period: trailing 12 months ending at the latest COMPLETE month in
loaded MCA data (the most recent calendar month is treated as partial/still
accumulating and excluded — confirmed by inspection: the latest month's
count is consistently far lower than prior months, consistent with a
snapshot taken mid-month rather than a real seasonal drop).

Each function returns a DataFrame indexed by geo_key with one raw value
column — never pre-normalised. Winsorisation/normalisation happens once,
centrally, in scoring.py, so every indicator goes through the identical
pipeline.
"""

import math
from datetime import date

import pandas as pd
import psycopg

from app.config import settings

QUALITY_BIT_OUTLIER = 4


def get_conn() -> psycopg.Connection:
    return psycopg.connect(settings.database_url.replace("+psycopg", ""))


def reference_month(conn: psycopg.Connection) -> date:
    """Latest complete month in fact_company — the month before the max
    observed month, since the max month is generally still-accumulating."""
    row = conn.execute(
        "SELECT max(date_trunc('month', incorporation_date))::date FROM gold.fact_company "
        "WHERE (quality_flags & %s) = 0",
        (QUALITY_BIT_OUTLIER,),
    ).fetchone()
    assert row is not None and row[0] is not None
    latest_month = row[0]
    # step back one month
    if latest_month.month == 1:
        return date(latest_month.year - 1, 12, 1)
    return date(latest_month.year, latest_month.month - 1, 1)


def bfr(conn: psycopg.Connection, period_end: date) -> pd.DataFrame:
    """new_incorporations (trailing 12m) / population_6plus * 100_000.

    Deviation from doc, documented not hidden: the formula's grain is
    "district x month" but a single month is too noisy for a stable score
    snapshot — trailing-12m sum is used instead, consistent with how FMOM
    already needs a 12m window. population_6plus is a proxy for
    working_age_population — see compute_bfr.py / STATUS.md for why no
    cleaner denominator exists in the loaded Census tables.
    """
    period_start = date(period_end.year - 1, period_end.month, 1)
    rows = conn.execute(
        """
        SELECT fc.geo_key, count(*) AS new_incorp, lw.population_6plus, pop.population_total_2011
        FROM gold.fact_company fc
        JOIN gold.dim_geography g ON g.geo_key = fc.geo_key
        LEFT JOIN silver.census_literacy_worker_district lw
            ON lw.lgd_state_code = g.lgd_state_code AND lw.lgd_district_code = g.lgd_district_code
        LEFT JOIN silver.census_population_district pop
            ON pop.lgd_state_code = g.lgd_state_code AND pop.lgd_district_code = g.lgd_district_code
        WHERE fc.incorporation_date >= %s AND fc.incorporation_date < %s
          AND (fc.quality_flags & %s) = 0
        GROUP BY fc.geo_key, lw.population_6plus, pop.population_total_2011
        """,
        (period_start, period_end, QUALITY_BIT_OUTLIER),
    ).fetchall()
    out = []
    for geo_key, new_incorp, pop_6plus, pop_total in rows:
        denom = pop_6plus or pop_total
        if denom:
            out.append({"geo_key": geo_key, "BFR": new_incorp / denom * 100_000})
    return pd.DataFrame(out).set_index("geo_key") if out else pd.DataFrame(columns=["BFR"])


def fmom(conn: psycopg.Connection, period_end: date) -> pd.DataFrame:
    """(trailing_12m / prior_12m) - 1. NULL if prior-12m count is 0 (can't
    compute a meaningful ratio against zero — division by zero, not a real
    momentum value)."""
    cur_start = date(period_end.year - 1, period_end.month, 1)
    prior_start = date(period_end.year - 2, period_end.month, 1)
    rows = conn.execute(
        """
        SELECT geo_key,
               count(*) FILTER (WHERE incorporation_date >= %s) AS trailing,
               count(*) FILTER (WHERE incorporation_date < %s) AS prior
        FROM gold.fact_company
        WHERE incorporation_date >= %s AND incorporation_date < %s
          AND (quality_flags & %s) = 0
        GROUP BY geo_key
        """,
        (cur_start, cur_start, prior_start, period_end, QUALITY_BIT_OUTLIER),
    ).fetchall()
    out = [{"geo_key": g, "FMOM": (t / p - 1)} for g, t, p in rows if p > 0]
    return pd.DataFrame(out).set_index("geo_key") if out else pd.DataFrame(columns=["FMOM"])


def capi(conn: psycopg.Connection, period_end: date) -> pd.DataFrame:
    """median(paid_up_capital_lakh) of companies incorporated in the trailing
    12m. Source paid_up_capital is stored in rupees (not lakh) in
    fact_company — divide by 100,000 here, once, rather than propagate a
    unit ambiguity downstream (docs/04-ETL-PIPELINE.md: canonical unit
    declared once, never converted in the presentation layer)."""
    period_start = date(period_end.year - 1, period_end.month, 1)
    rows = conn.execute(
        """
        SELECT geo_key, paid_up_capital FROM gold.fact_company
        WHERE incorporation_date >= %s AND incorporation_date < %s
          AND (quality_flags & %s) = 0
          AND paid_up_capital IS NOT NULL AND paid_up_capital >= 0
        """,
        (period_start, period_end, QUALITY_BIT_OUTLIER),
    ).fetchall()
    df = pd.DataFrame(rows, columns=["geo_key", "paid_up_capital"])
    if df.empty:
        return pd.DataFrame(columns=["CAPI"])
    df["paid_up_capital_lakh"] = df["paid_up_capital"] / 100_000
    out = df.groupby("geo_key")["paid_up_capital_lakh"].median().rename("CAPI").to_frame()
    return out


def msmed(conn: psycopg.Connection) -> pd.DataFrame:
    """(micro+small+medium) / population_6plus * 1_000. Udyam's own snapshot
    date is the reference here (cumulative-to-date, no separate period)."""
    rows = conn.execute(
        """
        SELECT fdm.geo_key, fdm.msme_micro, fdm.msme_small, fdm.msme_medium, lw.population_6plus, pop.population_total_2011
        FROM gold.fact_district_month fdm
        LEFT JOIN gold.dim_geography g ON g.geo_key = fdm.geo_key
        LEFT JOIN silver.census_literacy_worker_district lw
            ON lw.lgd_state_code = g.lgd_state_code AND lw.lgd_district_code = g.lgd_district_code
        LEFT JOIN silver.census_population_district pop
            ON pop.lgd_state_code = g.lgd_state_code AND pop.lgd_district_code = g.lgd_district_code
        """
    ).fetchall()
    out = []
    for geo_key, micro, small, medium, pop_6plus, pop_total in rows:
        denom = pop_6plus or pop_total
        if denom and micro is not None:
            out.append({"geo_key": geo_key, "MSMED": (micro + small + medium) / denom * 1_000})
    return pd.DataFrame(out).set_index("geo_key") if out else pd.DataFrame(columns=["MSMED"])


def mms(conn: psycopg.Connection) -> pd.DataFrame:
    """msme_manufacturing / (msme_manufacturing + msme_services)."""
    rows = conn.execute(
        "SELECT geo_key, msme_manufacturing, msme_services FROM gold.fact_district_month "
        "WHERE msme_manufacturing IS NOT NULL"
    ).fetchall()
    out = [
        {"geo_key": g, "MMS": man / (man + svc)}
        for g, man, svc in rows
        if (man + svc) > 0
    ]
    return pd.DataFrame(out).set_index("geo_key") if out else pd.DataFrame(columns=["MMS"])


def pops(conn: psycopg.Connection) -> pd.DataFrame:
    """log10(population). Log-transformed per doc — raw population spans 4
    orders of magnitude and would otherwise dominate normalisation."""
    rows = conn.execute(
        "SELECT lgd_state_code, lgd_district_code, population_total_2011 FROM silver.census_population_district "
        "WHERE lgd_district_code IS NOT NULL AND population_total_2011 > 0"
    ).fetchall()
    geo_rows = conn.execute(
        "SELECT lgd_state_code, lgd_district_code, geo_key FROM gold.dim_geography WHERE grain='district' AND is_current"
    ).fetchall()
    geo_map = {(s, d): g for s, d, g in geo_rows}
    out = []
    for state_code, district_code, population in rows:
        geo_key = geo_map.get((state_code, district_code))
        if geo_key:
            out.append({"geo_key": geo_key, "POPS": math.log10(population)})
    return pd.DataFrame(out).set_index("geo_key") if out else pd.DataFrame(columns=["POPS"])


def lit(conn: psycopg.Connection) -> pd.DataFrame:
    """literate_population / population_6plus * 100.

    Doc's official formula uses population_7_plus; loaded Census table only
    has a 0-6 breakdown, not 0-7 — population_6plus used instead, a small
    (~1 age-year) known discrepancy from the literal definition, documented
    here and in the resource registry rather than silently substituted.
    """
    rows = conn.execute(
        """
        SELECT g.geo_key, lw.literates, lw.population_6plus
        FROM silver.census_literacy_worker_district lw
        JOIN gold.dim_geography g ON g.lgd_state_code = lw.lgd_state_code AND g.lgd_district_code = lw.lgd_district_code
        WHERE lw.lgd_district_code IS NOT NULL AND lw.population_6plus > 0
        """
    ).fetchall()
    out = [{"geo_key": g, "LIT": lit_count / pop6 * 100} for g, lit_count, pop6 in rows]
    return pd.DataFrame(out).set_index("geo_key") if out else pd.DataFrame(columns=["LIT"])


# indicator_code -> (pillar, direction: 1 for higher-better, -1 for lower-better)
INDICATOR_META = {
    "BFR": ("economic", 1),
    "FMOM": ("economic", 1),
    "CAPI": ("economic", 1),
    "MSMED": ("ecosystem", 1),
    "MMS": ("ecosystem", 1),
    "POPS": ("human_capital", 1),
    "LIT": ("human_capital", 1),
}


def compute_all_indicators() -> pd.DataFrame:
    """Returns a district (geo_key) x indicator wide DataFrame, raw values,
    outer-joined — missing cells are genuinely missing (NaN), never
    imputed here. Imputation policy lives in scoring.py."""
    conn = get_conn()
    ref_month = reference_month(conn)
    period_end = date(ref_month.year, ref_month.month + 1, 1) if ref_month.month < 12 else date(ref_month.year + 1, 1, 1)

    frames = [
        bfr(conn, period_end),
        fmom(conn, period_end),
        capi(conn, period_end),
        msmed(conn),
        mms(conn),
        pops(conn),
        lit(conn),
    ]
    conn.close()

    wide = frames[0]
    for f in frames[1:]:
        wide = wide.join(f, how="outer")
    return wide
