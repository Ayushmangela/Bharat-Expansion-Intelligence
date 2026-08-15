"""Tests for app/repositories/district_repository.py.

Same commit+cleanup fixture strategy as test_scoring_repository.py, for the
same reason: these functions call get_conn() and open their own connection
internally, so the db_conn rollback fixture (a separate connection) can't
see this fixture's rows. An obviously-fake TESTLAND state/district, cleaned
up in `finally` and verified afterward.
"""

import psycopg
import pytest
from app.config import settings
from app.repositories import district_repository

TEST_STATE = 9201
TEST_DISTRICT = 1201


@pytest.fixture
def testland_district():
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
        conn.commit()
        yield {"state": TEST_STATE, "district": TEST_DISTRICT}
    finally:
        conn.execute("DELETE FROM gold.dim_geography WHERE lgd_state_code = %s", (TEST_STATE,))
        conn.commit()
        conn.close()


class TestListDistricts:
    def test_filters_by_state_code(self, testland_district):
        items, total = district_repository.list_districts(TEST_STATE, None, 50, 0)
        assert total == 1
        assert items[0]["district_name"] == "Test City"

    def test_search_by_name_is_case_insensitive(self, testland_district):
        items, total = district_repository.list_districts(None, "test city", 50, 0)
        assert total >= 1
        assert any(i["lgd_district_code"] == TEST_DISTRICT for i in items)

    def test_search_with_no_matches_returns_empty_not_error(self, testland_district):
        items, total = district_repository.list_districts(None, "no such district exists anywhere xyz", 50, 0)
        assert total == 0
        assert items == []

    def test_unknown_sort_key_falls_back_to_default_not_sql_injection(self, testland_district):
        # _SORTABLE_COLUMNS is a whitelist — an unrecognised or malicious
        # sort key must silently fall back to the default column, never be
        # interpolated into the ORDER BY clause directly.
        _items, total = district_repository.list_districts(
            TEST_STATE, None, 50, 0, sort="district_name; DROP TABLE gold.dim_geography;--", direction="desc"
        )
        assert total == 1  # query still ran safely; nothing was dropped
        # the table clearly still exists and is queryable if we got a result at all

    def test_pagination_limit_and_offset(self, testland_district):
        items, total = district_repository.list_districts(TEST_STATE, None, 1, 0)
        assert len(items) == 1
        assert total == 1
        items_page2, _ = district_repository.list_districts(TEST_STATE, None, 1, 1)
        assert items_page2 == []


class TestGetDistrict:
    def test_returns_none_for_nonexistent_district(self):
        assert district_repository.get_district(999999999) is None

    def test_returns_geography_for_real_fixture_district(self, testland_district):
        result = district_repository.get_district(TEST_DISTRICT)
        assert result is not None
        assert result["geography"]["district_name"] == "Test City"
        assert result["geography"]["state_name"] == "TESTLAND"
        # no companies/msme loaded for this fake district — must be empty, not crash
        assert result["company_status_breakdown"] == []
        assert result["monthly_incorporations"] == []


class TestStateSummary:
    def test_includes_states_with_zero_companies(self, testland_district):
        # the whole point of this function per its own docstring: a state
        # with a district row but zero fact_company rows must still appear,
        # distinguishable from "not yet ingested" rather than silently
        # dropped by an inner join.
        summary = district_repository.state_summary()
        testland_row = next((s for s in summary if s["lgd_state_code"] == TEST_STATE), None)
        assert testland_row is not None
        assert testland_row["company_count"] == 0
        assert testland_row["total_districts"] == 1
