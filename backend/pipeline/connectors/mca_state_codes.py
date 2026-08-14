# Verified CompanyStateCode filter values for MCA_COMPANY_MASTER, one per
# gold.dim_geography state, confirmed by direct API total-count checks
# (pipeline/flows/verify_state_codes*.py) — NOT guessed. Several are old/
# pre-rename names the source still uses internally (Odisha -> "orissa",
# Puducherry -> "pondicherry"), and Jammu & Kashmir uses an ampersand.
# The Dadra And Nagar Haveli And Daman And Diu needs BOTH sub-values (the
# 2020 merger isn't reflected in this source — each half kept its own old
# CompanyStateCode).
#
# CHHATTISGARH IS DELIBERATELY EXCLUDED. Every other state/UT's total sums to
# exactly 3,674,312; the true national total is 3,674,314 — a gap of exactly
# 2, matching the ONLY Chhattisgarh-labelled value found ("chattisgarh", 2
# rows). For a 29M-population state that should have tens of thousands of
# registered companies, this means Chhattisgarh's real data is mislabeled
# under some other state's CompanyStateCode in the source itself, not merely
# hard to filter for. Not found in a 50-row Madhya Pradesh sample (the most
# likely candidate, since Chhattisgarh split from MP in 2000). See STATUS.md
# for the full investigation — flagged as a genuine source data-quality gap,
# not silently dropped.
STATE_FILTER_VALUES: dict[str, list[str]] = {
    "Andaman And Nicobar Islands": ["andaman and nicobar islands"],
    "Andhra Pradesh": ["andhra pradesh"],
    "Arunachal Pradesh": ["arunachal pradesh"],
    "Assam": ["assam"],
    "Bihar": ["bihar"],
    "Chandigarh": ["chandigarh"],
    "Delhi": ["delhi"],
    "Goa": ["goa"],
    "Gujarat": ["gujarat"],
    "Haryana": ["haryana"],
    "Himachal Pradesh": ["himachal pradesh"],
    "Jammu And Kashmir": ["jammu & kashmir"],
    "Jharkhand": ["jharkhand"],
    "Karnataka": ["karnataka"],
    "Kerala": ["kerala"],
    "Ladakh": ["ladakh"],
    "Lakshadweep": ["lakshadweep"],
    "Madhya Pradesh": ["madhya pradesh"],
    "Maharashtra": ["maharashtra"],
    "Manipur": ["manipur"],
    "Meghalaya": ["meghalaya"],
    "Mizoram": ["mizoram"],
    "Nagaland": ["nagaland"],
    "Odisha": ["orissa"],
    "Puducherry": ["pondicherry"],
    "Punjab": ["punjab"],
    "Rajasthan": ["rajasthan"],
    "Sikkim": ["sikkim"],
    "Tamil Nadu": ["tamil nadu"],
    "Telangana": ["telangana"],
    "The Dadra And Nagar Haveli And Daman And Diu": ["dadra & nagar haveli", "daman and diu"],
    "Tripura": ["tripura"],
    "Uttarakhand": ["uttarakhand"],
    "Uttar Pradesh": ["uttar pradesh"],
    "West Bengal": ["west bengal"],
}

VERIFIED_GRAND_TOTAL = 3_674_312  # excludes Chhattisgarh's 2 mislabeled rows
