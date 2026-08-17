"""Tests for the small pure parsing helpers scattered across the MCA/Udyam/
Census transforms — the part of each transform that's actually unit-testable
without a full bronze-to-gold pipeline run (the row-by-row DB-writing loops
around them are, like scoring.py/explain.py/counterfactual.py, verified by
manual runs against live data instead — see STATUS.md). These parse the
messiest part of the whole pipeline: real government source data as loose,
inconsistently-formatted strings, so their edge-case behaviour (empty
string, None, comma-formatted numbers, garbage) matters more than most.
"""

from pipeline.transforms import census_literacy_silver, udyam_silver
from pipeline.transforms.mca_silver import extract_pin, parse_capital


class TestMcaParseCapital:
    def test_plain_number(self):
        assert parse_capital("100000") == 100000.0

    def test_comma_formatted(self):
        assert parse_capital("1,00,000") == 100000.0

    def test_none_is_none(self):
        assert parse_capital(None) is None

    def test_empty_string_is_none(self):
        assert parse_capital("") is None
        assert parse_capital("   ") is None

    def test_garbage_is_none_not_a_crash(self):
        assert parse_capital("N/A") is None


class TestMcaExtractPin:
    def test_pin_at_end_of_address(self):
        assert extract_pin("123 MG Road, Bangalore, Karnataka 560001") == "560001"

    def test_pin_with_trailing_punctuation(self):
        assert extract_pin("123 MG Road, Bangalore - 560001.") == "560001"

    def test_no_pin_present_is_none(self):
        assert extract_pin("123 MG Road, Bangalore") is None

    def test_none_address_is_none(self):
        assert extract_pin(None) is None

    def test_does_not_match_a_5_digit_number(self):
        # PIN_RE requires exactly 6 digits — a 5-digit trailing number
        # (e.g. a truncated or malformed field) must not be mistaken for one.
        assert extract_pin("Building 12345") is None


class TestUdyamParseInt:
    def test_plain_string_number(self):
        assert udyam_silver.parse_int("42") == 42

    def test_none_defaults_to_zero(self):
        assert udyam_silver.parse_int(None) == 0

    def test_empty_string_defaults_to_zero(self):
        assert udyam_silver.parse_int("") == 0
        assert udyam_silver.parse_int("   ") == 0

    def test_garbage_defaults_to_zero_not_a_crash(self):
        assert udyam_silver.parse_int("not a number") == 0


class TestCensusLiteracyParseInt:
    def test_plain_int(self):
        assert census_literacy_silver.parse_int(42) == 42

    def test_float_truncates(self):
        assert census_literacy_silver.parse_int(42.9) == 42

    def test_nan_defaults_to_zero(self):
        # this is the one meaningfully different behaviour from
        # udyam_silver's parse_int: this version is built to receive
        # pandas/numpy NA types directly (a float column read from an
        # Excel/parquet source), not pre-stringified values.
        assert census_literacy_silver.parse_int(float("nan")) == 0

    def test_none_defaults_to_zero(self):
        assert census_literacy_silver.parse_int(None) == 0

    def test_garbage_string_defaults_to_zero(self):
        assert census_literacy_silver.parse_int("not a number") == 0
