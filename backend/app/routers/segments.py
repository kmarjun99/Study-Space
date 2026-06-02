"""Segment API (Phase 4A).

Super-admin endpoints:
  - GET    /super-admin/segments
  - POST   /super-admin/segments
  - PATCH  /super-admin/segments/{id}
  - DELETE /super-admin/segments/{id}    (soft delete: marks is_active=False)
  - GET    /super-admin/segments/{id}/members
  - POST   /super-admin/segments/recompute (manual trigger)

Student transparency:
  - GET /users/me/segments               which segments am I in?
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_super_admin, get_current_user
from app.models.user import User
from app.models.user_segment import (
    SegmentRuleType, UserSegment, UserSegmentMembership,
)
from app.services import segment_service


router = APIRouter(tags=["Intelligence: Segments"])


class SegmentOut(BaseModel):
    id: str
    slug: str
    name: str
    description: Optional[str]
    rule_type: str
    rule_config: dict[str, Any]
    is_active: bool
    created_by: Optional[str]
    created_at: str
    updated_at: str


def _to_segment_out(s: UserSegment) -> SegmentOut:
    config: dict[str, Any] = {}
    if s.rule_config_json:
        try:
            parsed = json.loads(s.rule_config_json)
            if isinstance(parsed, dict):
                config = parsed
        except (json.JSONDecodeError, TypeError):
            pass
    return SegmentOut(
        id=s.id, slug=s.slug, name=s.name, description=s.description,
        rule_type=s.rule_type.value, rule_config=config,
        is_active=bool(s.is_active),
        created_by=s.created_by,
        created_at=s.created_at.isoformat(),
        updated_at=s.updated_at.isoformat(),
    )


class MembershipOut(BaseModel):
    user_id: str
    score: float
    reason: Optional[str]
    entered_at: str
    is_active: bool


def _to_membership_out(m: UserSegmentMembership) -> MembershipOut:
    return MembershipOut(
        user_id=m.user_id, score=float(m.score),
        reason=m.reason,
        entered_at=m.entered_at.isoformat(),
        is_active=bool(m.is_active),
    )


# ---------- super-admin -----------------------------------------------------

admin_router = APIRouter(
    prefix="/super-admin/segments", tags=["Super Admin: Segments"],
)


class SegmentIn(BaseModel):
    slug: str
    name: str
    description: Optional[str] = None
    rule_type: str
    rule_config: dict[str, Any] = {}


class SegmentPatch(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    rule_config: Optional[dict[str, Any]] = None
    is_active: Optional[bool] = None


@admin_router.get("", response_model=list[SegmentOut])
async def list_all_segments(
    include_inactive: bool = False,
    _: User = Depends(get_current_super_admin),
    db: AsyncSession = Depends(get_db),
):
    rows = await segment_service.list_segments(
        db, include_inactive=include_inactive,
    )
    return [_to_segment_out(r) for r in rows]


@admin_router.post("", response_model=SegmentOut)
async def create_segment(
    body: SegmentIn,
    actor: User = Depends(get_current_super_admin),
    db: AsyncSession = Depends(get_db),
):
    try:
        rule_type = SegmentRuleType(body.rule_type)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"invalid rule_type: {body.rule_type}",
        ) from exc

    row = UserSegment(
        slug=body.slug,
        name=body.name,
        description=body.description,
        rule_type=rule_type,
        rule_config_json=json.dumps(body.rule_config),
        is_active=True,
        created_by=actor.id,
    )
    db.add(row)
    try:
        await db.commit()
    except Exception as exc:
        await db.rollback()
        raise HTTPException(
            status_code=400, detail=f"could not create segment: {exc}",
        ) from exc
    await db.refresh(row)
    return _to_segment_out(row)


@admin_router.patch("/{segment_id}", response_model=SegmentOut)
async def patch_segment(
    segment_id: str,
    body: SegmentPatch,
    _: User = Depends(get_current_super_admin),
    db: AsyncSession = Depends(get_db),
):
    row = await db.get(UserSegment, segment_id)
    if row is None:
        raise HTTPException(status_code=404, detail="segment not found")
    if body.name is not None:
        row.name = body.name
    if body.description is not None:
        row.description = body.description
    if body.rule_config is not None:
        row.rule_config_json = json.dumps(body.rule_config)
    if body.is_active is not None:
        row.is_active = body.is_active
    await db.commit()
    await db.refresh(row)
    return _to_segment_out(row)


@admin_router.delete("/{segment_id}", response_model=SegmentOut)
async def soft_delete_segment(
    segment_id: str,
    _: User = Depends(get_current_super_admin),
    db: AsyncSession = Depends(get_db),
):
    """Mark a segment inactive. We never hard-delete because memberships
    reference the row historically."""
    row = await db.get(UserSegment, segment_id)
    if row is None:
        raise HTTPException(status_code=404, detail="segment not found")
    row.is_active = False
    row.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(row)
    return _to_segment_out(row)


@admin_router.get("/{segment_id}/members", response_model=list[MembershipOut])
async def list_members(
    segment_id: str,
    limit: int = 200,
    offset: int = 0,
    _: User = Depends(get_current_super_admin),
    db: AsyncSession = Depends(get_db),
):
    if limit < 1 or limit > 1000:
        raise HTTPException(status_code=400, detail="limit must be 1..1000")
    seg = await db.get(UserSegment, segment_id)
    if seg is None:
        raise HTTPException(status_code=404, detail="segment not found")
    rows = await segment_service.list_active_members(
        db, segment_id=segment_id, limit=limit, offset=offset,
    )
    return [_to_membership_out(r) for r in rows]


@admin_router.post("/recompute")
async def recompute_now(
    _: User = Depends(get_current_super_admin),
    db: AsyncSession = Depends(get_db),
):
    summary = await segment_service.recompute_all_active_segments(db)
    return {
        "segments_evaluated": summary.segments_evaluated,
        "memberships_entered": summary.memberships_entered,
        "memberships_exited": summary.memberships_exited,
        "skipped": summary.skipped or [],
    }


# ---------- student transparency ------------------------------------------

class MySegmentOut(BaseModel):
    segment_slug: str
    segment_name: str
    rule_type: str
    score: float
    reason: Optional[str]
    entered_at: str


@router.get("/users/me/segments", response_model=list[MySegmentOut])
async def list_my_segments(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Which audience segments does StudySpace currently place me in?

    Privacy mirror: companion to /events/me + /users/me/intelligence-profile.
    """
    pairs = await segment_service.segments_for_user(
        db, user_id=current_user.id,
    )
    return [
        MySegmentOut(
            segment_slug=seg.slug,
            segment_name=seg.name,
            rule_type=seg.rule_type.value,
            score=float(mem.score),
            reason=mem.reason,
            entered_at=mem.entered_at.isoformat(),
        )
        for seg, mem in pairs
    ]


router.include_router(admin_router)
