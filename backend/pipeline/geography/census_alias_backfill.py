"""One-off backfill: aliases for Census-2011-vintage district names that have
since been renamed (spelling standardisation, official renames, or moved to
a newly-created state), verified against current gold.dim_geography before
insertion.

Deliberately EXCLUDES genuine structural splits (one 2011 district that is
now multiple current districts) — a single alias there would misrepresent
population by attributing 100% of it to just one successor district. Those
stay quarantined pending an apportionment methodology (Phase 2+ concern):
Telangana's Mahbubnagar/Rangareddy (2016 reorg split each into several),
West Bengal's Barddhaman (split into Purba/Paschim Bardhaman, 2017),
Meghalaya's Jaintia Hills (split into East/West Jaintia Hills),
Sikkim's East/South/West Districts (2022 reorg added Pakyong/Soreng).

Run once after pipeline/connectors/lgd.py has loaded gold.dim_geography.
"""

import psycopg
from app.config import settings

# (observed_state, observed_district) -> (target_state, target_district)
# Every target verified present in gold.dim_geography before this file was written.
RENAMES: dict[tuple[str, str], tuple[str, str]] = {
    ("ANDAMAN & NICOBAR ISLANDS", "South Andaman"): ("Andaman And Nicobar Islands", "South Andamans"),
    ("ANDHRA PRADESH", "Anantapur"): ("Andhra Pradesh", "Ananthapuramu"),
    ("ANDHRA PRADESH", "Y.S.R.(Cuddapah)"): ("Andhra Pradesh", "Y.S.R."),
    ("ASSAM", "Kamrup Metropolitan"): ("Assam", "Kamrup Metro"),
    ("ASSAM", "Morigaon"): ("Assam", "Marigaon"),
    ("BIHAR", "Purba Champaran"): ("Bihar", "Purbi Champaran"),
    ("CHHATTISGARH", "Koriya"): ("Chhattisgarh", "Korea"),
    ("GUJARAT", "Ahmadabad"): ("Gujarat", "Ahmedabad"),
    ("GUJARAT", "Dohad"): ("Gujarat", "Dahod"),
    ("GUJARAT", "The Dangs"): ("Gujarat", "Dangs"),
    ("HARYANA", "Mewat"): ("Haryana", "Nuh"),
    ("HIMACHAL PRADESH", "Lahul & Spiti"): ("Himachal Pradesh", "Lahaul And Spiti"),
    ("JAMMU & KASHMIR", "Badgam"): ("Jammu And Kashmir", "Budgam"),
    ("JAMMU & KASHMIR", "Bandipore"): ("Jammu And Kashmir", "Bandipora"),
    ("JAMMU & KASHMIR", "Baramula"): ("Jammu And Kashmir", "Baramulla"),
    ("JAMMU & KASHMIR", "Punch"): ("Jammu And Kashmir", "Poonch"),
    ("JAMMU & KASHMIR", "Shupiyan"): ("Jammu And Kashmir", "Shopian"),
    # Moved to the newly-created Ladakh UT (2019 J&K reorganisation) — a
    # genuine state-boundary change, not just a rename.
    ("JAMMU & KASHMIR", "Kargil"): ("Ladakh", "Kargil"),
    ("JAMMU & KASHMIR", "Leh(Ladakh)"): ("Ladakh", "Leh Ladakh"),
    ("JHARKHAND", "Kodarma"): ("Jharkhand", "Koderma"),
    ("JHARKHAND", "Pashchimi Singhbhum"): ("Jharkhand", "West Singhbhum"),
    ("JHARKHAND", "Purbi Singhbhum"): ("Jharkhand", "East Singhbum"),
    ("JHARKHAND", "Sahibganj"): ("Jharkhand", "Sahebganj"),
    ("KARNATAKA", "Bagalkot"): ("Karnataka", "Bagalkote"),
    ("KARNATAKA", "Bangalore Rural"): ("Karnataka", "Bengaluru Rural"),
    ("KARNATAKA", "Belgaum"): ("Karnataka", "Belagavi"),
    ("KARNATAKA", "Bellary"): ("Karnataka", "Ballari"),
    ("KARNATAKA", "Bijapur"): ("Karnataka", "Vijayapura"),
    ("KARNATAKA", "Chikmagalur"): ("Karnataka", "Chikkamagaluru"),
    ("KARNATAKA", "Davanagere"): ("Karnataka", "Davangere"),
    ("KARNATAKA", "Gulbarga"): ("Karnataka", "Kalaburagi"),
    ("KARNATAKA", "Mysore"): ("Karnataka", "Mysuru"),
    ("KARNATAKA", "Shimoga"): ("Karnataka", "Shivamogga"),
    ("KARNATAKA", "Tumkur"): ("Karnataka", "Tumakuru"),
    ("LAKSHADWEEP", "Lakshadweep"): ("Lakshadweep", "Lakshadweep District"),
    ("MADHYA PRADESH", "Hoshangabad"): ("Madhya Pradesh", "Narmadapuram"),
    ("MAHARASHTRA", "Ahmadnagar"): ("Maharashtra", "Ahmednagar"),
    ("MAHARASHTRA", "Aurangabad"): ("Maharashtra", "Chhatrapati Sambhajinagar"),
    ("MAHARASHTRA", "Bid"): ("Maharashtra", "Beed"),
    ("MAHARASHTRA", "Buldana"): ("Maharashtra", "Buldhana"),
    ("MAHARASHTRA", "Gondiya"): ("Maharashtra", "Gondia"),
    ("MAHARASHTRA", "Osmanabad"): ("Maharashtra", "Dharashiv"),
    ("MAHARASHTRA", "Raigarh"): ("Maharashtra", "Raigad"),
    ("MEGHALAYA", "Ribhoi"): ("Meghalaya", "Ri Bhoi"),
    ("MIZORAM", "Saiha"): ("Mizoram", "Siaha"),
    ("ODISHA", "Baudh"): ("Odisha", "Boudh"),
    ("ODISHA", "Debagarh"): ("Odisha", "Deogarh"),
    ("ODISHA", "Nabarangapur"): ("Odisha", "Nabarangpur"),
    ("ODISHA", "Subarnapur"): ("Odisha", "Sonepur"),
    ("PUNJAB", "Firozpur"): ("Punjab", "Ferozepur"),
    ("PUNJAB", "Muktsar"): ("Punjab", "Sri Muktsar Sahib"),
    ("PUNJAB", "Sahibzada Ajit Singh Nagar"): ("Punjab", "S.A.S Nagar"),
    ("RAJASTHAN", "Chittaurgarh"): ("Rajasthan", "Chittorgarh"),
    ("RAJASTHAN", "Dhaulpur"): ("Rajasthan", "Dholpur"),
    ("RAJASTHAN", "Jalor"): ("Rajasthan", "Jalore"),
    ("RAJASTHAN", "Jhunjhunun"): ("Rajasthan", "Jhunjhunu"),
    ("UTTARAKHAND", "Garhwal"): ("Uttarakhand", "Pauri Garhwal"),
    ("UTTARAKHAND", "Hardwar"): ("Uttarakhand", "Haridwar"),
    ("UTTARAKHAND", "Rudraprayag"): ("Uttarakhand", "Rudra Prayag"),
    ("UTTARAKHAND", "Udham Singh Nagar"): ("Uttarakhand", "Udam Singh Nagar"),
    ("UTTARAKHAND", "Uttarkashi"): ("Uttarakhand", "Uttar Kashi"),
    ("UTTAR PRADESH", "Allahabad"): ("Uttar Pradesh", "Prayagraj"),
    ("UTTAR PRADESH", "Faizabad"): ("Uttar Pradesh", "Ayodhya"),
    ("UTTAR PRADESH", "Jyotiba Phule Nagar"): ("Uttar Pradesh", "Amroha"),
    ("UTTAR PRADESH", "Kanshiram Nagar"): ("Uttar Pradesh", "Kasganj"),
    ("UTTAR PRADESH", "Mahamaya Nagar"): ("Uttar Pradesh", "Hathras"),
    ("UTTAR PRADESH", "Sant Ravidas Nagar (Bhadohi)"): ("Uttar Pradesh", "Bhadohi"),
    ("WEST BENGAL", "Darjiling"): ("West Bengal", "Darjeeling"),
    ("WEST BENGAL", "Haora"): ("West Bengal", "Howrah"),
    ("WEST BENGAL", "Hugli"): ("West Bengal", "Hooghly"),
    ("WEST BENGAL", "Koch Bihar"): ("West Bengal", "Cooch Behar"),
    ("WEST BENGAL", "Maldah"): ("West Bengal", "Malda"),
    ("WEST BENGAL", "North Twenty Four Parganas"): ("West Bengal", "North 24 Parganas"),
    ("WEST BENGAL", "Puruliya"): ("West Bengal", "Purulia"),
    ("WEST BENGAL", "South Twenty Four Parganas"): ("West Bengal", "South 24 Parganas"),
}


def backfill() -> dict:
    conn = psycopg.connect(settings.database_url.replace("+psycopg", ""))

    n_inserted, n_target_missing = 0, []
    for (obs_state, obs_district), (target_state, target_district) in RENAMES.items():
        target = conn.execute(
            "SELECT lgd_state_code, lgd_district_code FROM gold.dim_geography "
            "WHERE state_name = %s AND district_name = %s AND grain = 'district' AND is_current",
            (target_state, target_district),
        ).fetchone()
        if not target:
            n_target_missing.append((obs_state, obs_district, target_state, target_district))
            continue
        lgd_state_code, lgd_district_code = target
        conn.execute(
            """
            INSERT INTO silver.geography_alias
                (observed_state, observed_district, lgd_state_code, lgd_district_code, match_method, confidence)
            VALUES (%s, %s, %s, %s, 'manual', 1.0)
            ON CONFLICT (observed_state, COALESCE(observed_district, '')) DO NOTHING
            """,
            (obs_state, obs_district, lgd_state_code, lgd_district_code),
        )
        n_inserted += 1
    conn.commit()
    conn.close()

    return {"inserted": n_inserted, "target_missing": n_target_missing}


if __name__ == "__main__":
    import json

    print(json.dumps(backfill(), indent=2))
