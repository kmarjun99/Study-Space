"""Intelligence profile API.

Two surfaces:
  - **Student transparency**: `GET /users/me/intelligence-profile` — what
    has StudySpace inferred about my preferences and intent?
  - **Super-admin**: list profiles filtered by intent level + manual
    rebuild triggers.

The student-facing endpoint is the privacy mirror of `GET /events/me` from
Phase 1: events are *what was tracked*, profile is *what was inferred*.
Both are essential for an honest "show me my data" promise.
"""
from __future__ import annotations

import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_super_admin, get_current_user
from app.models.user import User
from app.models.user_intelligence_profile import (
    IntentLevel, UserIntelligenceProfile,
)
from app.services import profile_intelligence_service


router = APIRouter(tags=["Intelligence: Profile"])


# ---------- schemas --------------------------------------------------------

class IntelligenceProfileOut(BaseModel):
    user_id: str
    preferred_city: Optional[str]
    preferred_locations: list[str]
    preferred_property_types: list[str]
    preferred_amenities: list[str]
    preferred_price_min: Optional[float]
    preferred_price_max: Optional[float]
    preferred_study_time: Optional[str]
    booking_urgency_score: float
    budget_sensitivity_score: float
    location_sensitivity_score: float
    premium_interest_score: float
    cancellation_risk_score: float
    conversion_probability_score: float
    raw_intent_score: int
    intent_level: str
    last_active_at: Optional[str]
    last_search_query: Optional[str]
    last_viewed_listing_id: Optional[str]
    last_booking_attempt_at: Optional[str]
    last_successful_booking_at: Optional[str]
    profile_confidence_score: float
    event_count: int
    updated_at: str


def _parse_list(s: Optional[str]) -> list[str]:
    if not s:
        return []
    try:
        v = json.loads(s)
        return v if isinstance(v, list) else []
    except (json.JSONDecodeError, TypeError):
        return []


def _to_out(row: UserIntelligenceProfile) -> IntelligenceProfileOut:
    return IntelligenceProfileOut(
        user_id=row.user_id,
        preferred_city=row.preferred_city,
        preferred_locations=_parse_list(row.preferred_locations_json),
        preferred_property_types=_parse_list(row.preferred_property_types_json),
        preferred_amenities=_parse_list(row.preferred_amenities_json),
        preferred_price_min=row.preferred_price_min,
        preferred_price_max=row.preferred_price_max,
        preferred_study_time=row.preferred_study_time,
        booking_urgency_score=float(row.booking_urgency_score),
        budget_sensitivity_score=float(row.budget_sensitivity_score),
        location_sensitivity_score=float(row.location_sensitivity_score),
        premium_interest_score=float(row.premium_interest_score),
        cancellation_risk_score=float(row.cancellation_risk_score),
        conversion_probability_score=float(row.conversion_probability_score),
        raw_intent_score=int(row.raw_intent_score),
        intent_level=row.intent_level.value if row.intent_level else "LOW_INTENT",
        last_active_at=row.last_active_at.isoformat() if row.last_active_at else None,
        last_search_query=row.last_search_query,
        last_viewed_listing_id=row.last_viewed_listing_id,
        last_booking_attempt_at=(
            row.last_booking_attempt_at.isoformat()
            if row.last_booking_attempt_at else None
        ),
        last_successful_booking_at=(
            row.last_successful_booking_at.isoformat()
            if row.last_successful_booking_at else None
        ),
        profile_confidence_score=float(row.profile_confidence_score),
        event_count=int(row.event_count),
        updated_at=row.updated_at.isoformat() if row.updated_at else "",
    )


# ---------- student transparency ------------------------------------------

@router.get(
    "/users/me/intelligence-profile",
    response_model=Optional[IntelligenceProfileOut],
)
async def get_my_intelligence_profile(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Returns the derived profile for the current user, or `null` if no
    profile has been built yet (consent denied, or no recent events)."""
    row = await profile_intelligence_service.get_profile_for_user(
        db, user_id=current_user.id,
    )
    return _to_out(row) if row is not None else None


# ---------- super-admin ---------------------------------------------------

admin_router = APIRouter(
    prefix="/super-admin/intelligence", tags=["Super Admin: Intelligence"],
)


@admin_router.get("/profiles", response_model=list[IntelligenceProfileOut])
async def list_intelligence_profiles(
    level: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    _: User = Depends(get_current_super_admin),
    db: AsyncSession = Depends(get_db),
):
    """List derived profiles. Optional `?level=HIGH_INTENT` filter."""
    if limit < 1 or limit > 500:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 500")
    target: Optional[IntentLevel] = None
    if level:
        try:
            target = IntentLevel(level)
        except ValueError as exc:
            raise HTTPException(
                status_code=400, detail=f"invalid intent level: {level}",
            ) from exc
    rows = await profile_intelligence_service.list_profiles_by_intent(
        db, level=target, limit=limit, offset=offset,
    )
    return [_to_out(r) for r in rows]


class RebuildRequest(BaseModel):
    user_id: Optional[str] = None        # rebuild one user
    since_days: int = 1                  # otherwise: rebuild active users since N days


@admin_router.post("/rebuild")
async def trigger_rebuild(
    body: RebuildRequest,
    _: User = Depends(get_current_super_admin),
    db: AsyncSession = Depends(get_db),
):
    """Manual rebuild — either one user, or a sweep of recent activity."""
    if body.user_id:
        result = await profile_intelligence_service.rebuild_profile_for_user(
            db, user_id=body.user_id,
        )
        await db.commit()
        return {
            "user_id": result.user_id,
            "persisted": result.persisted,
            "reason": result.reason,
            "raw_score": result.raw_score,
            "intent_level": (
                result.intent_level.value if result.intent_level else None
            ),
        }
    summary = await profile_intelligence_service.rebuild_all_active_profiles(
        db, since_days=body.since_days,
    )
    return summary


# Mount the admin sub-router under the main router.
router.include_router(admin_router)
