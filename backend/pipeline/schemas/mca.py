"""Pandera schema for raw MCA Company Master rows, as actually observed
(see docs/RESOURCE-REGISTRY.md S02) — not the originally-expected field set.

Almost every field arrives as string, including numeric ones (AuthorizedCapital,
PaidupCapital), and many are empty string rather than null. Schema validates
shape and required presence; type coercion happens in the transform step.
"""

import pandera.pandas as pa
from pandera.typing import Series


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
