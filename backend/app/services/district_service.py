"""Business logic only, no SQL (docs/02-ARCHITECTURE.md layering rule)."""

from app.repositories import district_repository


def list_districts(state_code: int | None, q: str | None, limit: int, offset: int) -> dict:
    items, total = district_repository.list_districts(state_code, q, limit, offset)
    return {"items": items, "total": total, "limit": limit, "offset": offset}


def get_district(lgd_district_code: int) -> dict | None:
    return district_repository.get_district(lgd_district_code)


def national_overview() -> dict:
    return district_repository.national_overview()
