"""Thin HTTP layer only — no SQL, no business logic (docs/02-ARCHITECTURE.md).

PREVIEW SLICE: real raw data (company counts, MSME breakdowns), not the
scored/SHAP endpoints in docs/07-API-SPEC.md — Phase 3/4 haven't run yet.
"""

from fastapi import APIRouter, HTTPException, Query

from app.services import district_service

router = APIRouter(prefix="/api/v1", tags=["districts"])


@router.get("/overview")
def overview() -> dict:
    return district_service.national_overview()


@router.get("/districts")
def list_districts(
    state_code: int | None = Query(default=None),
    q: str | None = Query(default=None),
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
) -> dict:
    return district_service.list_districts(state_code, q, limit, offset)


@router.get("/districts/{lgd_district_code}")
def get_district(lgd_district_code: int) -> dict:
    result = district_service.get_district(lgd_district_code)
    if result is None:
        raise HTTPException(status_code=404, detail=f"district {lgd_district_code} not found")
    return result
