"""Recommendation API (Phase 3) — four read surfaces + admin priority PATCH.

Privacy gates per surface:
  /for-me           — auth + allow_personalized_recommendations
  /similar          — no consent required (item-based)
  /trending         — no consent required (aggregate)
  /recently-viewed  — auth + allow_analytics_tracking

Every served impression is logged to `recommendation_logs` when the
`recommendations.log_impressions` flag is on. Phase 4 attribution reads
this log.
"""
from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import (
    get_current_super_admin, get_current_user, get_current_user_optional,
)
from app.models.recommendation_log import RecommendationSurface
from app.models.user import User
from app.services import recommendation_service


router = APIRouter(prefix="/recommendations", tags=["Intelligence: Recommendations"])


class RecommendationOut(BaseModel):
    listing_type: str
    listing_id: str
    name: str
    city: Optional[str]
    state: Optional[str]
    price: Optional[float]
    rank: int
    score: float
    reason_code: str
    extra: dict[str, Any]


def _to_out(recs) -> list[RecommendationOut]:
    return [RecommendationOut(**r.__dict__) for r in recs]


# ---------- four read surfaces -------------------------------------------

@router.get("/for-me", response_model=list[RecommendationOut])
async def for_me(
    limit: int = 10,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Personalized listings for the logged-in user.

    Returns [] if `recommendations.enabled` is OFF, if the user has not
    opted in to personalized recommendations, or if no profile exists yet.
    """
    if limit < 1 or limit > 50:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 50")
    recs = await recommendation_service.personalized_for_user(
        db, user_id=current_user.id, limit=limit,
    )
    await recommendation_service.log_impressions(
        db, user_id=current_user.id, anonymous_session_id=None,
        surface=RecommendationSurface.FOR_YOU, recommendations=recs,
    )
    await db.commit()
    return _to_out(recs)


@router.get("/similar", response_model=list[RecommendationOut])
async def similar(
    listing_type: str,
    listing_id: str,
    limit: int = 10,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    """Listings similar to the given one. Item-based: no consent needed."""
    if listing_type not in ("reading_room", "accommodation"):
        raise HTTPException(
            status_code=400,
            detail="listing_type must be 'reading_room' or 'accommodation'",
        )
    if limit < 1 or limit > 50:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 50")
    recs = await recommendation_service.similar_to_listing(
        db, listing_type=listing_type, listing_id=listing_id, limit=limit,
    )
    await recommendation_service.log_impressions(
        db,
        user_id=current_user.id if current_user else None,
        anonymous_session_id=None,
        surface=RecommendationSurface.SIMILAR, recommendations=recs,
    )
    await db.commit()
    return _to_out(recs)


@router.get("/trending", response_model=list[RecommendationOut])
async def trending(
    city: Optional[str] = None,
    window_days: int = 7,
    limit: int = 10,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    """City-level trending. No consent required (aggregate, not user-specific)."""
    if limit < 1 or limit > 50:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 50")
    if window_days < 1 or window_days > 90:
        raise HTTPException(
            status_code=400, detail="window_days must be between 1 and 90",
        )
    recs = await recommendation_service.trending_in_city(
        db, city=city, window_days=window_days, limit=limit,
    )
    await recommendation_service.log_impressions(
        db,
        user_id=current_user.id if current_user else None,
        anonymous_session_id=None,
        surface=RecommendationSurface.TRENDING, recommendations=recs,
    )
    await db.commit()
    return _to_out(recs)


@router.get("/recently-viewed", response_model=list[RecommendationOut])
async def recently_viewed(
    limit: int = 10,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """The user's recent VIEW events as recommendations.

    Returns [] when the user has not opted in to analytics tracking.
    """
    if limit < 1 or limit > 50:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 50")
    recs = await recommendation_service.recently_viewed_for_user(
        db, user_id=current_user.id, limit=limit,
    )
    await recommendation_service.log_impressions(
        db, user_id=current_user.id, anonymous_session_id=None,
        surface=RecommendationSurface.RECENTLY_VIEWED, recommendations=recs,
    )
    await db.commit()
    return _to_out(recs)


# ---------- super-admin priority PATCH ------------------------------------

admin_router = APIRouter(
    prefix="/super-admin/listings", tags=["Super Admin: Recommendations"],
)


class PriorityPatch(BaseModel):
    recommendation_priority: Optional[int] = None
    recommendation_excluded: Optional[bool] = None
    clear_priority: bool = False


@admin_router.patch("/{listing_type}/{listing_id}/recommendation")
async def patch_recommendation_controls(
    listing_type: str,
    listing_id: str,
    body: PriorityPatch,
    _: User = Depends(get_current_super_admin),
    db: AsyncSession = Depends(get_db),
):
    """Set / clear admin priority + hard-exclusion flag on a listing."""
    if listing_type == "reading_room":
        from app.models.reading_room import ReadingRoom
        listing = await db.get(ReadingRoom, listing_id)
    elif listing_type == "accommodation":
        from app.models.accommodation import Accommodation
        listing = await db.get(Accommodation, listing_id)
    else:
        raise HTTPException(status_code=400, detail="invalid listing_type")
    if listing is None:
        raise HTTPException(status_code=404, detail="listing not found")

    if body.clear_priority:
        listing.recommendation_priority = None
    elif body.recommendation_priority is not None:
        listing.recommendation_priority = body.recommendation_priority
    if body.recommendation_excluded is not None:
        listing.recommendation_excluded = body.recommendation_excluded
    await db.commit()
    return {
        "listing_type": listing_type,
        "listing_id": listing_id,
        "recommendation_priority": listing.recommendation_priority,
        "recommendation_excluded": listing.recommendation_excluded,
    }


router.include_router(admin_router)
