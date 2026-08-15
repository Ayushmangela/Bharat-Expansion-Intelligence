"""Business logic only, no SQL (docs/02-ARCHITECTURE.md layering rule)."""

from app.ml.counterfactual import compute_counterfactual
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


def get_counterfactual(lgd_district_code: int, target_rank: int, profile: str | None) -> dict | None:
    return compute_counterfactual(lgd_district_code, target_rank, profile or DEFAULT_PROFILE)


def get_similar_districts(lgd_district_code: int, profile: str | None, limit: int) -> dict | None:
    return scoring_repository.get_similar_districts(lgd_district_code, profile or DEFAULT_PROFILE, limit)


def compare_districts(lgd_district_codes: list[int], profile: str | None) -> dict | None:
    return scoring_repository.compare_districts(lgd_district_codes, profile or DEFAULT_PROFILE)
