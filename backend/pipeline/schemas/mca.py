"""Pandera schema for raw MCA Company Master rows, as actually observed
(see docs/RESOURCE-REGISTRY.md S02) — not the originally-expected field set.

Almost every field arrives as string, including numeric ones (AuthorizedCapital,
PaidupCapital), and many are empty string rather than null. Schema validates
shape and required presence; type coercion happens in the transform step.

The "CIN" field is NOT uniformly a 21-character CIN despite the name — three
legitimate identifier formats coexist in it (confirmed by direct data check,
see STATUS.md Gate 2 finding): 21-char standard CIN (domestic companies),
8-char "XXX-NNNN" LLPIN (LLPs — 19,529/19,784 rows with this length have
"LLP" in the company name), and "Fnnnnn"-style Foreign Company Registration
Number (foreign entities — e.g. Baker Hughes, Cameco India). A schema that
assumed a fixed 21-char length (as docs/09-DATA-QUALITY.md's illustrative
example does) would reject ~27% of real rows.

BUG FOUND live during the Phase 2 national sweep, twice, from the same root
cause: an earlier version of this check validated the foreign-company format
as an EXACT 6-character length, generalised from a small sample where every
example happened to be "F" + 5 digits. Telangana's data broke that
assumption with "F123456" (F + 6 digits = 7 characters) — a previously-
unseen but equally legitimate variant, not a data error. Fixed with a regex
instead of a sampled length. But the regex ALSO turned out too strict: a
1-in-200,000 sample check against already-loaded data found a genuine typo
("U3691.DL1986PTC025643" — a literal "." where a digit belongs) that no
reasonable format regex should accept, yet real MCA data contains it. A
Pandera column check fails validation for the ENTIRE dataframe on a single
non-matching row — meaning any one malformed identifier, of which a dataset
this size will always have some, would keep crashing whole-state transforms
no matter how carefully the regex is tuned.

**Conclusion: format-matching CIN is not something worth hard-failing a
load over.** The real invariant that matters is structural (non-null,
unique) — kept below as actual Pandera checks. Format plausibility is
demoted to a non-blocking diagnostic count, logged but never a reason to
reject a row or crash a state.
"""

import re

import pandera.pandas as pa
from pandera.typing import Series

_DOMESTIC_CIN = re.compile(r"^[UL]\d{5}[A-Z]{2}\d{4}[A-Z]{3}\d{6}$")
_LLPIN = re.compile(r"^[A-Z]{3}-\d{4}$")
_FOREIGN_COMPANY_ID = re.compile(r"^F\d{4,8}$")


def is_known_cin_format(cin: str) -> bool:
    """Non-blocking diagnostic only — see module docstring for why this is
    not a Pandera check. Callers may use this to count/log anomalies."""
    return bool(_DOMESTIC_CIN.match(cin) or _LLPIN.match(cin) or _FOREIGN_COMPANY_ID.match(cin))


class MCACompanyRawSchema(pa.DataFrameModel):
    CIN: Series[str] = pa.Field(nullable=False, unique=True)
    CompanyName: Series[str] = pa.Field(nullable=False)
    CompanyROCcode: Series[str] = pa.Field(nullable=True)
    CompanyCategory: Series[str] = pa.Field(nullable=True)
    CompanySubCategory: Series[str] = pa.Field(nullable=True)
    CompanyClass: Series[str] = pa.Field(nullable=True)
    AuthorizedCapital: Series[str] = pa.Field(nullable=True)
    PaidupCapital: Series[str] = pa.Field(nullable=True)
    CompanyRegistrationdate_date: Series[str] = pa.Field(nullable=True)
    Registered_Office_Address: Series[str] = pa.Field(nullable=True)
    CompanyStatus: Series[str] = pa.Field(nullable=False)
    CompanyStateCode: Series[str] = pa.Field(nullable=False)
    nic_code: Series[str] = pa.Field(nullable=True)
    CompanyIndustrialClassification: Series[str] = pa.Field(nullable=True)

    class Config:
        strict = False  # source carries extra columns we don't consume yet (Listingstatus, Indian/Foreign)
        coerce = True
