"""Tests for the six-step GeographyResolver (pipeline/geography/resolver.py).

Runs against the real database, inside an uncommitted transaction that's
always rolled back (see conftest.py's db_conn fixture) — pg_trgm's
similarity() is a real Postgres function, not reproducible in pure Python,
so the fuzzy-match step genuinely needs a live connection, and mocking it
would test the mock, not the resolver. All fixture rows use an obviously
fake state, "TESTLAND" (and "TESTUNION" for the cross-state disambiguation
test), per CLAUDE.md's own rule.
"""

import pytest
from pipeline.geography.resolver import GeographyResolver, normalise

TESTLAND = 9001
TESTUNION = 9002


@pytest.fixture
def resolver(db_conn):
    """Seeds a small, obviously-fake geography (two states, both containing
    a district literally named "Test City" — the same collision pattern
    CLAUDE.md calls out for real Aurangabad/Maharashtra vs Aurangabad/Bihar)
    then constructs a resolver against it. Nothing here is ever committed."""
    db_conn.execute(
        "INSERT INTO gold.dim_geography (lgd_state_code, state_name, grain, valid_from, is_current) VALUES "
        "(%s, 'TESTLAND', 'state', '2020-01-01', true), (%s, 'TESTUNION', 'state', '2020-01-01', true)",
        (TESTLAND, TESTUNION),
    )
    db_conn.execute(
        "INSERT INTO gold.dim_geography (lgd_state_code, lgd_district_code, state_name, district_name, grain, valid_from, is_current) VALUES "
        "(%s, 101, 'TESTLAND', 'Test City', 'district', '2020-01-01', true), "
        "(%s, 102, 'TESTLAND', 'North Test', 'district', '2020-01-01', true), "
        "(%s, 103, 'TESTLAND', 'Testvillenagarpuram', 'district', '2020-01-01', true), "
        "(%s, 201, 'TESTUNION', 'Test City', 'district', '2020-01-01', true)",
        (TESTLAND, TESTLAND, TESTLAND, TESTUNION),
    )
    db_conn.execute(
        "INSERT INTO silver.lgd_subdistrict_lookup (lgd_state_code, lgd_district_code, subdistrict_code, subdistrict_name) "
        "VALUES (%s, 101, 5001, 'Test Taluka')",
        (TESTLAND,),
    )
    db_conn.execute(
        "INSERT INTO silver.geography_alias (observed_state, observed_district, lgd_state_code, lgd_district_code, match_method, confidence) "
        "VALUES ('testland', 't. city', %s, 101, 'manual', 1.0)",
        (TESTLAND,),
    )
    db_conn.execute(
        "INSERT INTO silver.pincode_district_lookup (pincode, observed_state, observed_district) VALUES ('999001', 'TESTLAND', 'Test City')"
    )
    db_conn.execute(
        "INSERT INTO silver.lgd_pincode_lookup (pincode, lgd_state_code, lgd_district_code, local_body_code, local_body_name) "
        "VALUES ('999002', %s, 102, 1, 'Test Panchayat')",
        (TESTLAND,),
    )
    return GeographyResolver(db_conn)


class TestNormalise:
    def test_casefolds_and_strips(self):
        assert normalise("  Test City  ") == "test city"

    def test_expands_ampersand(self):
        assert normalise("Jammu & Kashmir") == "jammu and kashmir"

    def test_drops_punctuation(self):
        assert normalise("Test-City, (North)") == "test city north"

    def test_none_and_empty_are_empty_string(self):
        assert normalise(None) == ""
        assert normalise("") == ""

    def test_zero_width_chars_removed(self):
        assert normalise("Test\u200bCity") == "testcity"


class TestResolveState:
    def test_exact_match(self, resolver):
        code, method = resolver.resolve_state("TESTLAND")
        assert code == TESTLAND
        assert method == "exact"

    def test_exact_match_is_case_and_whitespace_insensitive(self, resolver):
        code, method = resolver.resolve_state("  testland  ")
        assert code == TESTLAND
        assert method == "exact"

    def test_unresolved_state_returns_none(self, resolver):
        code, method = resolver.resolve_state("Nonexistent Country")
        assert code is None
        assert method == "unresolved"


class TestResolveDistrict:
    def test_exact_district_match(self, resolver):
        r = resolver.resolve("TESTLAND", "Test City")
        assert (r.lgd_state_code, r.lgd_district_code) == (TESTLAND, 101)
        assert r.method == "exact"
        assert r.confidence == 1.0

    def test_same_district_name_disambiguated_by_state(self, resolver):
        # CLAUDE.md rule 8, directly: "Aurangabad exists in both Maharashtra
        # and Bihar" — same district name, different state, must resolve to
        # different codes. This is the constitution's own named example,
        # reproduced here with fake data.
        testland_result = resolver.resolve("TESTLAND", "Test City")
        testunion_result = resolver.resolve("TESTUNION", "Test City")
        assert testland_result.lgd_district_code == 101
        assert testunion_result.lgd_district_code == 201
        assert testland_result.lgd_district_code != testunion_result.lgd_district_code

    def test_state_only_when_no_district_given(self, resolver):
        r = resolver.resolve("TESTLAND")
        assert r.lgd_state_code == TESTLAND
        assert r.lgd_district_code is None

    def test_unresolved_state_short_circuits(self, resolver):
        r = resolver.resolve("Nonexistent Country", "Test City")
        assert r.lgd_state_code is None
        assert r.method == "unresolved"


class TestAliasResolution:
    def test_known_alias_resolves_despite_no_exact_match(self, resolver):
        # "T. City" doesn't exactly match "Test City" but a seeded alias row does.
        r = resolver.resolve("testland", "t. city")
        assert (r.lgd_state_code, r.lgd_district_code) == (TESTLAND, 101)
        assert r.method == "alias"


class TestPinResolution:
    def test_postal_directory_pin(self, resolver):
        r = resolver.resolve(observed_state=None, observed_pin="999001")
        assert (r.lgd_state_code, r.lgd_district_code) == (TESTLAND, 101)
        assert r.method == "pin_postal"

    def test_lgd_pincode_fallback_when_not_in_postal_directory(self, resolver):
        r = resolver.resolve(observed_state=None, observed_pin="999002")
        assert (r.lgd_state_code, r.lgd_district_code) == (TESTLAND, 102)
        assert r.method == "pin_lgd"

    def test_malformed_pin_is_ignored_not_crashed_on(self, resolver):
        # not 6 digits — should just fall through to unresolved, not raise
        r = resolver.resolve(observed_state=None, observed_district=None, observed_pin="12")
        assert r.method == "unresolved"


class TestAddressTextResolution:
    def test_district_name_contained_in_address(self, resolver):
        r = resolver.resolve("TESTLAND", None, address_text="office near North Test district hq")
        assert r.lgd_district_code == 102
        assert r.method == "address_contains"

    def test_subdistrict_name_contained_in_address(self, resolver):
        r = resolver.resolve("TESTLAND", None, address_text="located near Test Taluka industrial area")
        assert r.lgd_district_code == 101
        assert r.method == "subdistrict_contains"


class TestFuzzyResolution:
    # pg_trgm similarity scales with string length — a single-character typo
    # on a short name like "Test City" scores well under 0.85 (verified
    # empirically: 0.667 for "Test City"/"Test Citi"), while the same kind
    # of edit on a longer, more realistic district-name length clears it
    # comfortably. This mirrors real production aliases (e.g.
    # "Chamarajanagar" -> "Chamarajanagara" scored 0.875 in the live data)
    # more faithfully than a short fixture name would.
    TYPO = "Testvillenagarpuramu"  # correct name + one trailing character

    def test_close_typo_resolves_via_fuzzy_match(self, resolver):
        r = resolver.resolve("TESTLAND", self.TYPO)
        assert r.lgd_district_code == 103
        assert r.method == "fuzzy"
        assert r.is_fuzzy is True
        assert r.confidence >= 0.85

    def test_fuzzy_match_is_learned_as_an_alias(self, resolver, db_conn):
        # _learn_alias stores the RAW observed_state/observed_district as
        # passed to resolve() (not the normalised form) — the raw text is
        # the useful audit trail of what a source actually sent.
        resolver.resolve("TESTLAND", self.TYPO)
        row = db_conn.execute(
            "SELECT lgd_district_code FROM silver.geography_alias WHERE observed_state = %s AND observed_district = %s",
            ("TESTLAND", self.TYPO),
        ).fetchone()
        assert row is not None
        assert row[0] == 103

    def test_learned_alias_is_immediately_usable_within_the_same_resolver(self, resolver):
        # a second identical lookup should now hit the (in-memory) alias
        # index directly rather than re-running the trigram query.
        resolver.resolve("TESTLAND", self.TYPO)
        r2 = resolver.resolve("TESTLAND", self.TYPO)
        assert r2.lgd_district_code == 103
        assert r2.method == "alias"

    def test_wildly_different_string_does_not_false_positive(self, resolver):
        r = resolver.resolve("TESTLAND", "Completely Unrelated Nonsense Place")
        assert r.lgd_district_code is None
        assert r.method == "unresolved"


class TestQuarantineFallthrough:
    def test_unresolvable_district_returns_state_only_unresolved(self, resolver):
        r = resolver.resolve("TESTLAND", "Completely Unrelated Nonsense Place")
        assert r.lgd_state_code == TESTLAND
        assert r.lgd_district_code is None
        assert r.method == "unresolved"
        assert r.confidence == 0.0
