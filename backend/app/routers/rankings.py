"""Thin HTTP layer only — no SQL, no business logic (docs/02-ARCHITECTURE.md).

Opportunity Score endpoints, per docs/07-API-SPEC.md. Scope reduced to the 7
KPIs actually computable this phase (see app/ml/kpis.py, STATUS.md) —
`indicators_used`/`indicators_total` on every response makes that visible to
the caller rather than presenting a full 22-indicator score.
"""

from fastapi import APIRouter, HTTPException, Query

from app.services import scoring_service

router = APIRouter(prefix="/api/v1", tags=["scoring"])


@router.get("/rankings")
def list_rankings(
    profile: str | None = Query(default=None),
    state_code: int | None = Query(default=None),
    q: str | None = Query(default=None),
    min_score: float | None = Query(default=None),
    ranked_only: bool = Query(default=True, description="exclude districts below the 0.75 confidence rank floor"),
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
    sort: str = Query(default="opportunity_score"),
    direction: str = Query(default="desc", pattern="^(asc|desc)$"),
) -> dict:
    return scoring_service.list_rankings(profile, state_code, q, min_score, ranked_only, limit, offset, sort, direction)


@router.get("/rankings/meta")
def rankings_meta() -> dict:
    return scoring_service.weight_meta()


@router.get("/districts/{lgd_district_code}/score")
def district_score(lgd_district_code: int, profile: str | None = Query(default=None)) -> dict:
    result = scoring_service.get_scorecard(lgd_district_code, profile)
    if result is None:
        raise HTTPException(status_code=404, detail=f"district {lgd_district_code} not found")
    return result


@router.get("/districts/{lgd_district_code}/explain")
def district_explain(lgd_district_code: int, profile: str | None = Query(default=None)) -> dict:
    result = scoring_service.get_explain(lgd_district_code, profile)
    if result is None:
        raise HTTPException(status_code=404, detail=f"district {lgd_district_code} not found")
    return result


@router.get("/districts/{lgd_district_code}/counterfactual")
def district_counterfactual(
    lgd_district_code: int,
    target_rank: int = Query(..., ge=1, description="the national rank this district wants to reach"),
    profile: str | None = Query(default=None),
) -> dict:
    result = scoring_service.get_counterfactual(lgd_district_code, target_rank, profile)
    if result is None:
        raise HTTPException(status_code=404, detail=f"district {lgd_district_code} not found")
    if "error" in result:
        raise HTTPException(status_code=422, detail=result["error"])
    return result
