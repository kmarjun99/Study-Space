from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.reading_room import (
    Cabin,
    MaintenanceStatus,
    OperationalAccessOverride,
    ReadingRoom,
    ListingStatus,
)
from app.models.subscription_plan import SubscriptionPlan


ACTIVE_TRUST_STATUSES = {"CLEAR", "UNDER_REVIEW"}


@dataclass
class OwnerOperationalAccess:
    reading_room_id: str
    can_operate: bool
    reason_code: Optional[str] = None
    message: str = ""
    missing_requirements: list[str] = field(default_factory=list)
    listing_status: Optional[str] = None
    is_verified: bool = False
    trust_status: str = "CLEAR"
    plan_status: str = "NONE"
    paid_access_expires_at: Optional[datetime] = None
    free_access_until: Optional[datetime] = None
    admin_blocked: bool = False

    def to_dict(self) -> dict:
        return {
            "reading_room_id": self.reading_room_id,
            "can_operate": self.can_operate,
            "reason_code": self.reason_code,
            "message": self.message,
            "missing_requirements": self.missing_requirements,
            "listing_status": self.listing_status,
            "is_verified": self.is_verified,
            "trust_status": self.trust_status,
            "plan_status": self.plan_status,
            "paid_access_expires_at": self.paid_access_expires_at,
            "free_access_until": self.free_access_until,
            "admin_blocked": self.admin_blocked,
        }


def _blocked(room: ReadingRoom, code: str, message: str, *, missing: Optional[list[str]] = None) -> OwnerOperationalAccess:
    return OwnerOperationalAccess(
        reading_room_id=room.id,
        can_operate=False,
        reason_code=code,
        message=message,
        missing_requirements=missing or [],
        listing_status=room.status.value if room.status else None,
        is_verified=bool(room.is_verified),
        trust_status=getattr(room, "trust_status", None) or "CLEAR",
        free_access_until=getattr(room, "operational_access_until", None),
        admin_blocked=(getattr(room, "operational_access_override", None) == OperationalAccessOverride.BLOCKED.value),
    )


def _duration_prices_valid(room: ReadingRoom) -> bool:
    if not room.duration_prices:
        return False
    try:
        prices = json.loads(room.duration_prices) if isinstance(room.duration_prices, str) else room.duration_prices
    except (TypeError, json.JSONDecodeError):
        return False
    if not isinstance(prices, dict):
        return False
    for value in prices.values():
        try:
            if value is not None and float(value) > 0:
                return True
        except (TypeError, ValueError):
            continue
    return False


async def evaluate_reading_room_operational_access(
    db: AsyncSession,
    room: ReadingRoom,
    *,
    now: Optional[datetime] = None,
) -> OwnerOperationalAccess:
    current = now or datetime.utcnow()
    override = getattr(room, "operational_access_override", None) or OperationalAccessOverride.NONE.value
    trust_status = getattr(room, "trust_status", None) or "CLEAR"

    if override == OperationalAccessOverride.BLOCKED.value:
        return _blocked(
            room,
            "ADMIN_BLOCKED",
            "This reading room is blocked by admin and cannot perform owner operations.",
        )

    if room.status != ListingStatus.LIVE:
        return _blocked(
            room,
            "VENUE_NOT_LIVE",
            "This reading room is not live yet. Complete payment and admin verification before adding students.",
        )

    if not room.is_verified:
        return _blocked(
            room,
            "VENUE_NOT_VERIFIED",
            "This reading room must be verified by admin before owner operations are enabled.",
        )

    if trust_status not in ACTIVE_TRUST_STATUSES:
        return _blocked(
            room,
            "VENUE_SUSPENDED",
            "This reading room is restricted by Trust & Safety and cannot perform owner operations.",
        )

    if getattr(room, "maintenance_status", None) == MaintenanceStatus.SUSPENDED_FOR_NONPAYMENT:
        return _blocked(
            room,
            "VENUE_SUSPENDED",
            "This reading room is suspended for non-payment and cannot perform owner operations.",
        )

    missing: list[str] = []
    if not room.name:
        missing.append("name")
    if not room.address:
        missing.append("address")
    if not room.contact_phone:
        missing.append("contact phone")
    if not room.price_start and not _duration_prices_valid(room):
        missing.append("pricing")
    if not room.allowed_booking_durations:
        missing.append("allowed booking durations")
    if not _duration_prices_valid(room):
        missing.append("duration prices")
    has_cabin = await db.scalar(select(Cabin.id).where(Cabin.reading_room_id == room.id).limit(1))
    if not has_cabin:
        missing.append("cabins")

    if missing:
        return _blocked(
            room,
            "MISSING_BUSINESS_DATA",
            "Complete the reading room business and cabin pricing setup before adding students.",
            missing=missing,
        )

    free_until = getattr(room, "operational_access_until", None)
    if override == OperationalAccessOverride.FREE_GRANTED.value and free_until and free_until >= current:
        access = OwnerOperationalAccess(
            reading_room_id=room.id,
            can_operate=True,
            message="Operational access is enabled through an admin-granted free access window.",
            listing_status=room.status.value if room.status else None,
            is_verified=bool(room.is_verified),
            trust_status=trust_status,
            plan_status="FREE_GRANTED",
            free_access_until=free_until,
        )
        return access

    paid_expires_at: Optional[datetime] = None
    plan_status = "NONE"
    if room.subscription_plan_id and room.payment_date:
        plan = await db.scalar(select(SubscriptionPlan).where(SubscriptionPlan.id == room.subscription_plan_id))
        if plan and plan.is_active:
            paid_expires_at = room.payment_date + timedelta(days=plan.duration_days)
            plan_status = "ACTIVE" if paid_expires_at >= current else "EXPIRED"
        elif plan:
            plan_status = "INACTIVE_PLAN"
        else:
            plan_status = "PLAN_NOT_FOUND"

    if paid_expires_at and paid_expires_at >= current:
        return OwnerOperationalAccess(
            reading_room_id=room.id,
            can_operate=True,
            message="Operational access is enabled through an active paid plan.",
            listing_status=room.status.value if room.status else None,
            is_verified=bool(room.is_verified),
            trust_status=trust_status,
            plan_status=plan_status,
            paid_access_expires_at=paid_expires_at,
            free_access_until=free_until,
        )

    return OwnerOperationalAccess(
        reading_room_id=room.id,
        can_operate=False,
        reason_code="PLAN_INACTIVE",
        message="This reading room needs an active paid plan or admin-granted free access before adding students.",
        missing_requirements=[],
        listing_status=room.status.value if room.status else None,
        is_verified=bool(room.is_verified),
        trust_status=trust_status,
        plan_status=plan_status,
        paid_access_expires_at=paid_expires_at,
        free_access_until=free_until,
    )


async def assert_reading_room_operational_access(
    db: AsyncSession,
    room: ReadingRoom,
    *,
    now: Optional[datetime] = None,
) -> OwnerOperationalAccess:
    access = await evaluate_reading_room_operational_access(db, room, now=now)
    if not access.can_operate:
        raise HTTPException(
            status_code=403,
            detail={
                "code": access.reason_code,
                "message": access.message,
                "missing_requirements": access.missing_requirements,
                "access": access.to_dict(),
            },
        )
    return access
