"""Populates gold.dim_date at month grain, calendar + Indian fiscal year.

Indian fiscal year: Apr-Mar. FY2024-25 runs Apr 2024 - Mar 2025.
fiscal_quarter: Q1=Apr-Jun, Q2=Jul-Sep, Q3=Oct-Dec, Q4=Jan-Mar.
"""

from datetime import date

import psycopg
from app.config import settings

START_YEAR = 2010
END_YEAR = 2027


def fiscal_year_label(year: int, month: int) -> str:
    if month >= 4:
        return f"FY{year}-{str(year + 1)[-2:]}"
    return f"FY{year - 1}-{str(year)[-2:]}"


def fiscal_quarter(month: int) -> int:
    return {4: 1, 5: 1, 6: 1, 7: 2, 8: 2, 9: 2, 10: 3, 11: 3, 12: 3, 1: 4, 2: 4, 3: 4}[month]


def populate() -> int:
    conn = psycopg.connect(settings.database_url.replace("+psycopg", ""))
    n = 0
    for year in range(START_YEAR, END_YEAR + 1):
        for month in range(1, 13):
            date_key = year * 100 + month
            quarter = (month - 1) // 3 + 1
            conn.execute(
                """
                INSERT INTO gold.dim_date
                    (date_key, full_date, year, month, quarter, fiscal_year, fiscal_quarter, grain)
                VALUES (%s, %s, %s, %s, %s, %s, %s, 'month')
                ON CONFLICT (date_key) DO NOTHING
                """,
                (
                    date_key,
                    date(year, month, 1),
                    year,
                    month,
                    quarter,
                    fiscal_year_label(year, month),
                    fiscal_quarter(month),
                ),
            )
            n += 1
    conn.commit()
    conn.close()
    return n


if __name__ == "__main__":
    print(f"dim_date rows upserted: {populate()}")
