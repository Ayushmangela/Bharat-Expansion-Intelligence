"""Tests for pipeline/schemas/mca.py.

is_known_cin_format() is pure — the interesting cases here are exactly the
ones that broke a real load this session (see the module's own docstring):
a length-generalised regex that missed a legitimate 7-character foreign ID,
and a stricter regex that then rejected a genuine 1-in-200,000 data typo.
Both are reproduced here as regression tests, plus a schema-level test
proving that typo does NOT crash validation for the whole dataframe (the
entire reason the check was demoted from a hard Pandera @pa.check to a
non-blocking diagnostic in the first place).
"""

import pandas as pd
import pandera.errors
import pytest
from pipeline.schemas.mca import MCACompanyRawSchema, is_known_cin_format


class TestIsKnownCinFormat:
    def test_domestic_cin_21_chars(self):
        assert is_known_cin_format("U74999MH2015PTC269013") is True

    def test_llpin_8_chars(self):
        assert is_known_cin_format("ABC-1234") is True

    def test_foreign_company_id_5_digits(self):
        # the original, first-observed shape
        assert is_known_cin_format("F12345") is True

    def test_foreign_company_id_6_digits(self):
        # the shape that broke the first version of this check —
        # Telangana's real data had "F123456" (F + 6 digits, not 5)
        assert is_known_cin_format("F123456") is True

    def test_the_actual_typo_found_in_production_is_rejected_by_the_diagnostic(self):
        # "U3691.DL1986PTC025643" — a real row from the loaded dataset, a
        # literal "." where a digit belongs. The diagnostic correctly flags
        # it as not-a-known-format (it genuinely isn't one) — the point of
        # demoting this to non-blocking is that flagging it must not also
        # crash the load; see TestSchemaDoesNotHardFailOnFormat below.
        assert is_known_cin_format("U3691.DL1986PTC025643") is False

    def test_garbage_is_rejected(self):
        assert is_known_cin_format("") is False
        assert is_known_cin_format("NOT-A-REAL-CIN") is False


class TestSchemaDoesNotHardFailOnFormat:
    def _valid_row(self, **overrides) -> dict:
        row = {
            "CIN": "U74999MH2015PTC269013",
            "CompanyName": "TEST COMPANY PRIVATE LIMITED",
            "CompanyROCcode": "ROC-MUMBAI",
            "CompanyCategory": "Company limited by Shares",
            "CompanySubCategory": "Non-govt company",
            "CompanyClass": "Private",
            "AuthorizedCapital": "100000",
            "PaidupCapital": "100000",
            "CompanyRegistrationdate_date": "2015-01-01",
            "Registered_Office_Address": "TEST ADDRESS",
            "CompanyStatus": "Active",
            "CompanyStateCode": "MH",
            "nic_code": "01111",
            "CompanyIndustrialClassification": "AGRICULTURE",
        }
        row.update(overrides)
        return row

    def test_a_malformed_but_present_cin_does_not_fail_validation(self):
        # this is the exact regression this schema exists to prevent: a
        # single row with a typo'd CIN must not crash validation for every
        # other row in the same dataframe/state.
        df = pd.DataFrame([self._valid_row(CIN="U3691.DL1986PTC025643")])
        validated = MCACompanyRawSchema.validate(df)
        assert len(validated) == 1

    def test_null_cin_still_fails_validation(self):
        # nullable=False is a real, structural Pandera check — this must
        # still hard-fail, unlike format.
        df = pd.DataFrame([self._valid_row(CIN=None)])
        with pytest.raises(pandera.errors.SchemaError):
            MCACompanyRawSchema.validate(df)

    def test_duplicate_cin_still_fails_validation(self):
        # unique=True is also a real, structural check.
        df = pd.DataFrame([self._valid_row(), self._valid_row()])
        with pytest.raises(pandera.errors.SchemaError):
            MCACompanyRawSchema.validate(df)
