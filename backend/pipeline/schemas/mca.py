"""Pandera schema for raw MCA Company Master rows, as actually observed
(see docs/RESOURCE-REGISTRY.md S02) — not the originally-expected field set.

Almost every field arrives as string, including numeric ones (AuthorizedCapital,
PaidupCapital), and many are empty string rather than null. Schema validates
shape and required presence; type coercion happens in the transform step.

The "CIN" field is NOT uniformly a 21-character CIN despite the name — three
legitimate identifier formats coexist in it (confirmed by direct data check,
see STATUS.md Gate 2 finding): 21-char standard CIN (domestic companies),
8-char "XXX-NNNN" LLPIN (LLPs — 19,529/19,784 rows with this length have
"LLP" in the company name), and 6-char "Fnnnnn" Foreign Company Registration
Number (foreign entities — e.g. Baker Hughes, Cameco India). A schema that
assumed a fixed 21-char length (as docs/09-DATA-QUALITY.md's illustrative
example does) would reject ~27% of real rows.
"""

import pandera.pandas as pa
from pandera.typing import Series

VALID_CIN_LENGTHS = {21, 8, 6}


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

    @pa.check("CIN")
    def cin_is_a_known_id_format(cls, cin: Series[str]) -> Series[bool]:
        return cin.str.len().isin(VALID_CIN_LENGTHS)
