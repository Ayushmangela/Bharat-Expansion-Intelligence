"""Tests for app/repositories/scoring_repository.py.

confidence_band() is pure — tested directly, no DB.

list_rankings()'s active-weight-version filtering is tested against real
committed data (not the rollback-transaction pattern used for the
GeographyResolver tests) because the repository functions open their own
connection internally (get_conn() is called inside each function, not
dependency-injected) — a separate connection cannot see another
connection's uncommitted rows, so this specific test needs the fixture
data actually committed, with an explicit, guaranteed cleanup in a
`finally` block. Verified the cleanup actually leaves zero rows behind, the
same way the resolver tests verified their rollback did.

This is exactly the bug class that shipped and was caught mid-session (see
STATUS.md item 26): fact_opportunity_score's primary key includes
weight_version_id, so every scoring run adds a new row generation rather
than replacing the old one — without is_active filtering, a stale
generation silently leaks into the API response.
"""

import psycopg
import pytest
from app.config import settings
from app.repositories import scoring_repository
from app.repositories.scoring_repository import confidence_band
from psycopg.types.json import Json

TEST_STATE = 9101
TEST_DISTRICT = 1101
TEST_PROFILE = "test_profile_probe"
TEST_DATE_KEY = 201001  # a real, existing calendar row — dim_date is pure calendar data, not fabricated business data


class TestConfidenceBand:
    def test_high(self):
        assert confidence_band(0.95) == "High"
        assert confidence_band(0.90) == "High"

    def test_moderate(self):
        assert confidence_band(0.80) == "Moderate"
        assert confidence_band(0.75) == "Moderate"

    def test_low(self):
        assert confidence_band(0.50) == "Low"
        assert confidence_band(0.0) == "Low"

    def test_none_is_unknown(self):
        assert confidence_band(None) == "Unknown"


@pytest.fixture
def stale_and_active_weight_versions():
    """Seeds ONE district scored under TWO weight_version generations for a
    throwaway fake profile — one active, one not — to prove the repository
    only ever surfaces the active one. Committed (not rolled back) because
    scoring_repository opens its own connection; explicitly cleaned up in
    `finally` regardless of test outcome, and the cleanup itself is verified.
    """
    conn = psycopg.connect(settings.database_url.replace("+psycopg", ""))
    try:
        conn.execute(
            "INSERT INTO gold.dim_geography (lgd_state_code, state_name, grain, valid_from, is_current) "
            "VALUES (%s, 'TESTLAND', 'state', '2020-01-01', true)",
            (TEST_STATE,),
        )
        conn.execute(
            "INSERT INTO gold.dim_geography (lgd_state_code, lgd_district_code, state_name, district_name, grain, valid_from, is_current) "
            "VALUES (%s, %s, 'TESTLAND', 'Test City', 'district', '2020-01-01', true)",
            (TEST_STATE, TEST_DISTRICT),
        )
        geo_key = conn.execute(
            "SELECT geo_key FROM gold.dim_geography WHERE lgd_state_code = %s AND lgd_district_code = %s",
            (TEST_STATE, TEST_DISTRICT),
        ).fetchone()[0]

        conn.execute(
            "INSERT INTO gold.dim_profile (profile_code, profile_name, description, pillar_weights) "
            "VALUES (%s, 'Test Probe', 'throwaway fixture profile', %s)",
            (TEST_PROFILE, Json({"economic": 1.0})),
        )
        profile_key = conn.execute("SELECT profile_key FROM gold.dim_profile WHERE profile_code = %s", (TEST_PROFILE,)).fetchone()[0]

        stale_id = conn.execute(
            "INSERT INTO meta.weight_version (profile_code, method, weights, is_active) VALUES (%s, 'entropy', %s, false) RETURNING weight_version_id",
            (TEST_PROFILE, Json({"BFR": 1.0})),
        ).fetchone()[0]
        active_id = conn.execute(
            "INSERT INTO meta.weight_version (profile_code, method, weights, is_active) VALUES (%s, 'entropy', %s, true) RETURNING weight_version_id",
            (TEST_PROFILE, Json({"BFR": 1.0})),
        ).fetchone()[0]

        for weight_version_id, score in [(stale_id, 10.0), (active_id, 99.0)]:
            conn.execute(
                """
                INSERT INTO gold.fact_opportunity_score
                    (geo_key, date_key, profile_key, opportunity_score, pillar_economic,
                     confidence_score, indicators_used, indicators_total, weight_version_id)
                VALUES (%s, %s, %s, %s, %s, 1.0, 1, 1, %s)
                """,
                (geo_key, TEST_DATE_KEY, profile_key, score, score, weight_version_id),
            )
        conn.commit()

        yield {"geo_key": geo_key, "stale_id": stale_id, "active_id": active_id}
    finally:
        conn.execute(
            "DELETE FROM gold.fact_opportunity_score WHERE geo_key IN "
            "(SELECT geo_key FROM gold.dim_geography WHERE lgd_state_code = %s)",
            (TEST_STATE,),
        )
        conn.execute("DELETE FROM meta.weight_version WHERE profile_code = %s", (TEST_PROFILE,))
        conn.execute("DELETE FROM gold.dim_profile WHERE profile_code = %s", (TEST_PROFILE,))
        conn.execute("DELETE FROM gold.dim_geography WHERE lgd_state_code = %s", (TEST_STATE,))
        conn.commit()
        conn.close()


class TestActiveWeightVersionFiltering:
    def test_list_rankings_only_returns_the_active_generation(self, stale_and_active_weight_versions):
        items, total, meta = scoring_repository.list_rankings(
            TEST_PROFILE, None, None, None, False, 50, 0, "opportunity_score", "desc"
        )
        assert total == 1  # not 2 — the stale generation must not appear at all
        assert len(items) == 1
        assert items[0]["opportunity_score"] == 99.0  # the active generation's value, not the stale 10.0
        assert meta["weight_version_id"] == stale_and_active_weight_versions["active_id"]


TEST_STATE_2 = 9102
TEST_DISTRICT_A = 1102
TEST_DISTRICT_B = 1103
TEST_PROFILE_2 = "test_profile_compare"


@pytest.fixture
def two_scored_districts():
    """Two fake districts under one active weight_version, with one
    indicator (CAPI) deliberately tied at the same normalised value on
    both — this is what test_compare_ties_are_not_misreported_as_a_lead
    below exercises."""
    conn = psycopg.connect(settings.database_url.replace("+psycopg", ""))
    try:
        conn.execute(
            "INSERT INTO gold.dim_geography (lgd_state_code, state_name, grain, valid_from, is_current) VALUES (%s, 'TESTLAND', 'state', '2020-01-01', true)",
            (TEST_STATE_2,),
        )
        conn.execute(
            "INSERT INTO gold.dim_geography (lgd_state_code, lgd_district_code, state_name, district_name, grain, valid_from, is_current) VALUES "
            "(%s, %s, 'TESTLAND', 'Test City A', 'district', '2020-01-01', true), "
            "(%s, %s, 'TESTLAND', 'Test City B', 'district', '2020-01-01', true)",
            (TEST_STATE_2, TEST_DISTRICT_A, TEST_STATE_2, TEST_DISTRICT_B),
        )
        geo_a, geo_b = (
            conn.execute(
                "SELECT geo_key FROM gold.dim_geography WHERE lgd_state_code=%s AND lgd_district_code=%s", (TEST_STATE_2, d)
            ).fetchone()[0]
            for d in (TEST_DISTRICT_A, TEST_DISTRICT_B)
        )
        conn.execute(
            "INSERT INTO gold.dim_profile (profile_code, profile_name, description, pillar_weights) VALUES (%s, 'Compare Probe', 'throwaway', %s)",
            (TEST_PROFILE_2, Json({"economic": 1.0})),
        )
        profile_key = conn.execute("SELECT profile_key FROM gold.dim_profile WHERE profile_code=%s", (TEST_PROFILE_2,)).fetchone()[0]
        weight_version_id = conn.execute(
            "INSERT INTO meta.weight_version (profile_code, method, weights, is_active) VALUES (%s, 'entropy', %s, true) RETURNING weight_version_id",
            (TEST_PROFILE_2, Json({"BFR": 0.5, "CAPI": 0.5})),
        ).fetchone()[0]
        for geo_key, bfr_score in [(geo_a, 80.0), (geo_b, 20.0)]:
            conn.execute(
                "INSERT INTO gold.fact_opportunity_score (geo_key, date_key, profile_key, opportunity_score, confidence_score, indicators_used, indicators_total, weight_version_id) "
                "VALUES (%s, %s, %s, %s, 1.0, 2, 2, %s)",
                (geo_key, TEST_DATE_KEY, profile_key, (bfr_score + 100.0) / 2, weight_version_id),
            )
            conn.execute(
                "INSERT INTO gold.fact_score_contribution (geo_key, date_key, profile_key, weight_version_id, indicator_code, raw_value, normalised_value, shap_contribution, contribution_method, source_code) "
                "VALUES (%s, %s, %s, %s, 'BFR', %s, %s, 1, 'linear_weighted', 'S02')",
                (geo_key, TEST_DATE_KEY, profile_key, weight_version_id, bfr_score, bfr_score),
            )
            # CAPI: identical normalised value for both districts — a genuine tie
            conn.execute(
                "INSERT INTO gold.fact_score_contribution (geo_key, date_key, profile_key, weight_version_id, indicator_code, raw_value, normalised_value, shap_contribution, contribution_method, source_code) "
                "VALUES (%s, %s, %s, %s, 'CAPI', 1.0, 100.0, 1, 'linear_weighted', 'S02')",
                (geo_key, TEST_DATE_KEY, profile_key, weight_version_id),
            )
        conn.commit()
        yield {"district_a": TEST_DISTRICT_A, "district_b": TEST_DISTRICT_B}
    finally:
        conn.execute(
            "DELETE FROM gold.fact_score_contribution WHERE geo_key IN (SELECT geo_key FROM gold.dim_geography WHERE lgd_state_code=%s)",
            (TEST_STATE_2,),
        )
        conn.execute(
            "DELETE FROM gold.fact_opportunity_score WHERE geo_key IN (SELECT geo_key FROM gold.dim_geography WHERE lgd_state_code=%s)",
            (TEST_STATE_2,),
        )
        conn.execute("DELETE FROM meta.weight_version WHERE profile_code = %s", (TEST_PROFILE_2,))
        conn.execute("DELETE FROM gold.dim_profile WHERE profile_code = %s", (TEST_PROFILE_2,))
        conn.execute("DELETE FROM gold.dim_geography WHERE lgd_state_code = %s", (TEST_STATE_2,))
        conn.commit()
        conn.close()


class TestCompareDistricts:
    def test_clear_leader_is_reported(self, two_scored_districts):
        result = scoring_repository.compare_districts([TEST_DISTRICT_A, TEST_DISTRICT_B], TEST_PROFILE_2)
        bfr = next(i for i in result["indicators"] if i["indicator_code"] == "BFR")
        assert bfr["leader"] == TEST_DISTRICT_A  # 80.0 > 20.0, unambiguous
        assert result["trade_off_summary"]["overall_score_leader"] == TEST_DISTRICT_A

    def test_ties_are_not_misreported_as_a_lead(self, two_scored_districts):
        # both districts have normalised_value=100.0 on CAPI — max() alone
        # would arbitrarily pick one side of the tie; leader must be None.
        result = scoring_repository.compare_districts([TEST_DISTRICT_A, TEST_DISTRICT_B], TEST_PROFILE_2)
        capi = next(i for i in result["indicators"] if i["indicator_code"] == "CAPI")
        assert capi["leader"] is None

    def test_fewer_than_two_valid_districts_returns_error(self, two_scored_districts):
        result = scoring_repository.compare_districts([TEST_DISTRICT_A, 999999999], TEST_PROFILE_2)
        assert result is not None
        assert "error" in result


def test_fixture_cleanup_actually_ran(db_conn):
    # Runs after the tests above, whose fixture teardowns have already
    # fired by the time this starts (pytest runs tests in file-definition
    # order by default, and this project has no randomisation plugin
    # enabled) — confirms no TESTLAND row from this file survives, the
    # same verification style used for the resolver tests.
    for state in (TEST_STATE, TEST_STATE_2):
        count = db_conn.execute("SELECT count(*) FROM gold.dim_geography WHERE lgd_state_code = %s", (state,)).fetchone()[0]
        assert count == 0
    for profile in (TEST_PROFILE, TEST_PROFILE_2):
        count = db_conn.execute("SELECT count(*) FROM meta.weight_version WHERE profile_code = %s", (profile,)).fetchone()[0]
        assert count == 0
