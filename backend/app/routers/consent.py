"""User consent preference CRUD.

GET returns the current row (auto-created with defaults if missing).
PUT does a partial update — only fields actually sent are touched.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user
from app.models.user import User
from app.services import privacy_consent_service


router = APIRouter(prefix="/users/me/consent", tags=["Intelligence: Consent"])


class ConsentOut(BaseModel):
    user_id: str
    allow_analytics_tracking: bool
    allow_personalized_recommendations: bool
    allow_marketing_notifications: bool
    allow_whatsapp_updates: bool
    allow_location_based_suggestions: bool
    consent_policy_version: Optional[str]
    updated_at: str


class ConsentUpdate(BaseModel):
    allow_analytics_tracking: Optional[bool] = None
    allow_personalized_recommendations: Optional[bool] = None
    allow_marketing_notifications: Optional[bool] = None
    allow_whatsapp_updates: Optional[bool] = None
    allow_location_based_suggestions: Optional[bool] = None
    consent_policy_version: Optional[str] = None
    # "I changed my mind, turn everything off" shortcut.
    revoke_all: bool = False


def _to_out(row) -> ConsentOut:
    return ConsentOut(
        user_id=row.user_id,
        allow_analytics_tracking=bool(row.allow_analytics_tracking),
        allow_personalized_recommendations=bool(row.allow_personalized_recommendations),
        allow_marketing_notifications=bool(row.allow_marketing_notifications),
        allow_whatsapp_updates=bool(row.allow_whatsapp_updates),
        allow_location_based_suggestions=bool(row.allow_location_based_suggestions),
        consent_policy_version=row.consent_policy_version,
        updated_at=row.updated_at.isoformat() if row.updated_at else "",
    )


@router.get("", response_model=ConsentOut)
async def get_my_consent(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    row = await privacy_consent_service.get_or_create(db, user_id=current_user.id)
    await db.commit()
    return _to_out(row)


@router.put("", response_model=ConsentOut)
async def update_my_consent(
    body: ConsentUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if body.revoke_all:
        await privacy_consent_service.revoke_all_consents(
            db, user_id=current_user.id,
        )
        await db.commit()
        row = await privacy_consent_service.get_or_create(
            db, user_id=current_user.id,
        )
        return _to_out(row)

    row = await privacy_consent_service.update_preferences(
        db,
        user_id=current_user.id,
        allow_analytics_tracking=body.allow_analytics_tracking,
        allow_personalized_recommendations=body.allow_personalized_recommendations,
        allow_marketing_notifications=body.allow_marketing_notifications,
        allow_whatsapp_updates=body.allow_whatsapp_updates,
        allow_location_based_suggestions=body.allow_location_based_suggestions,
        consent_policy_version=body.consent_policy_version,
    )
    await db.commit()
    return _to_out(row)
