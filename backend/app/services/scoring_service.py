"""Business logic only, no SQL (docs/02-ARCHITECTURE.md layering rule)."""

from app.repositories import scoring_repository

DEFAULT_PROFILE = "balanced"


def list_rankings(
    profile: str | None,
    state_code: int | None,
    q: str | None,
    min_score: float | None,
    ranked_only: bool,
    limit: int,
    offset: int,
    sort: str,
    direction: str,
) -> dict:
    profile_code = profile or DEFAULT_PROFILE
    items, total, meta = scoring_repository.list_rankings(
        profile_code, state_code, q, min_score, ranked_only, limit, offset, sort, direction
    )
    return {"items": items, "total": total, "limit": limit, "offset": offset, **meta}


def get_scorecard(lgd_district_code: int, profile: str | None) -> dict | None:
    return scoring_repository.get_scorecard(lgd_district_code, profile or DEFAULT_PROFILE)


def get_explain(lgd_district_code: int, profile: str | None) -> dict | None:
    return scoring_repository.get_explain(lgd_district_code, profile or DEFAULT_PROFILE)


def weight_meta() -> dict:
    return scoring_repository.weight_meta()
