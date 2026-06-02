"""Campaign API (Phase 4B).

Super-admin CRUD + enqueue + funnel summary. Engagement-mark endpoints
(opened/clicked) accept a delivery_id and are designed to be called by:
  - The notification fire worker (Phase 4C) when sending succeeds
  - Webhooks from the email / WhatsApp provider when the user engages
  - Pixel/beacon redirects that record clicks then redirect to the listing
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_super_admin
from app.models.campaign import (
    Campaign, CampaignChannel, CampaignDelivery, CampaignStatus,
    DeliveryStatus,
)
from app.models.user import User
from app.services import campaign_service


router = APIRouter(tags=["Intelligence: Campaigns"])


class CampaignOut(BaseModel):
    id: str
    slug: str
    name: str
    description: Optional[str]
    body_template: str
    segment_id: str
    channel: str
    status: str
    cooldown_hours: int
    frequency_cap_per_user: int
    frequency_cap_window_days: int
    send_window_starts: Optional[str]
    send_window_ends: Optional[str]
    created_by: Optional[str]
    created_at: str
    updated_at: str


def _to_camp(c: Campaign) -> CampaignOut:
    return CampaignOut(
        id=c.id, slug=c.slug, name=c.name, description=c.description,
        body_template=c.body_template,
        segment_id=c.segment_id,
        channel=c.channel.value, status=c.status.value,
        cooldown_hours=c.cooldown_hours,
        frequency_cap_per_user=c.frequency_cap_per_user,
        frequency_cap_window_days=c.frequency_cap_window_days,
        send_window_starts=(
            c.send_window_starts.isoformat() if c.send_window_starts else None
        ),
        send_window_ends=(
            c.send_window_ends.isoformat() if c.send_window_ends else None
        ),
        created_by=c.created_by,
        created_at=c.created_at.isoformat(),
        updated_at=c.updated_at.isoformat(),
    )


class DeliveryOut(BaseModel):
    id: str
    campaign_id: str
    user_id: str
    channel: str
    status: str
    queued_at: str
    delivered_at: Optional[str]
    opened_at: Optional[str]
    clicked_at: Optional[str]
    converted_at: Optional[str]
    converted_booking_id: Optional[str]
    reason: Optional[str]


def _to_deliv(d: CampaignDelivery) -> DeliveryOut:
    return DeliveryOut(
        id=d.id, campaign_id=d.campaign_id, user_id=d.user_id,
        channel=d.channel.value, status=d.status.value,
        queued_at=d.queued_at.isoformat(),
        delivered_at=d.delivered_at.isoformat() if d.delivered_at else None,
        opened_at=d.opened_at.isoformat() if d.opened_at else None,
        clicked_at=d.clicked_at.isoformat() if d.clicked_at else None,
        converted_at=d.converted_at.isoformat() if d.converted_at else None,
        converted_booking_id=d.converted_booking_id,
        reason=d.reason,
    )


# ---------- super-admin CRUD ---------------------------------------------

admin_router = APIRouter(
    prefix="/super-admin/campaigns", tags=["Super Admin: Campaigns"],
)


class CampaignIn(BaseModel):
    slug: str
    name: str
    description: Optional[str] = None
    body_template: str
    segment_id: str
    channel: str
    cooldown_hours: int = 24
    frequency_cap_per_user: int = 3
    frequency_cap_window_days: int = 7
    send_window_starts: Optional[str] = None
    send_window_ends: Optional[str] = None


class CampaignPatch(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    body_template: Optional[str] = None
    status: Optional[str] = None
    cooldown_hours: Optional[int] = None
    frequency_cap_per_user: Optional[int] = None
    frequency_cap_window_days: Optional[int] = None
    send_window_starts: Optional[str] = None
    send_window_ends: Optional[str] = None


def _parse_dt(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError as exc:
        raise HTTPException(
            status_code=400, detail=f"invalid datetime: {s}",
        ) from exc


@admin_router.get("", response_model=list[CampaignOut])
async def list_all(
    include_completed: bool = True,
    _: User = Depends(get_current_super_admin),
    db: AsyncSession = Depends(get_db),
):
    rows = await campaign_service.list_campaigns(
        db, include_completed=include_completed,
    )
    return [_to_camp(r) for r in rows]


@admin_router.post("", response_model=CampaignOut)
async def create_campaign(
    body: CampaignIn,
    actor: User = Depends(get_current_super_admin),
    db: AsyncSession = Depends(get_db),
):
    try:
        channel = CampaignChannel(body.channel)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"invalid channel: {body.channel}") from exc

    row = Campaign(
        slug=body.slug, name=body.name, description=body.description,
        body_template=body.body_template,
        segment_id=body.segment_id,
        channel=channel,
        status=CampaignStatus.DRAFT,
        cooldown_hours=body.cooldown_hours,
        frequency_cap_per_user=body.frequency_cap_per_user,
        frequency_cap_window_days=body.frequency_cap_window_days,
        send_window_starts=_parse_dt(body.send_window_starts),
        send_window_ends=_parse_dt(body.send_window_ends),
        created_by=actor.id,
    )
    db.add(row)
    try:
        await db.commit()
    except Exception as exc:
        await db.rollback()
        raise HTTPException(
            status_code=400, detail=f"could not create campaign: {exc}",
        ) from exc
    await db.refresh(row)
    return _to_camp(row)


@admin_router.patch("/{campaign_id}", response_model=CampaignOut)
async def patch_campaign(
    campaign_id: str,
    body: CampaignPatch,
    _: User = Depends(get_current_super_admin),
    db: AsyncSession = Depends(get_db),
):
    row = await db.get(Campaign, campaign_id)
    if row is None:
        raise HTTPException(status_code=404, detail="campaign not found")
    if body.name is not None:
        row.name = body.name
    if body.description is not None:
        row.description = body.description
    if body.body_template is not None:
        row.body_template = body.body_template
    if body.status is not None:
        try:
            row.status = CampaignStatus(body.status)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=f"invalid status: {body.status}") from exc
    if body.cooldown_hours is not None:
        row.cooldown_hours = body.cooldown_hours
    if body.frequency_cap_per_user is not None:
        row.frequency_cap_per_user = body.frequency_cap_per_user
    if body.frequency_cap_window_days is not None:
        row.frequency_cap_window_days = body.frequency_cap_window_days
    if body.send_window_starts is not None:
        row.send_window_starts = _parse_dt(body.send_window_starts)
    if body.send_window_ends is not None:
        row.send_window_ends = _parse_dt(body.send_window_ends)
    await db.commit()
    await db.refresh(row)
    return _to_camp(row)


@admin_router.post("/{campaign_id}/enqueue")
async def trigger_enqueue(
    campaign_id: str,
    _: User = Depends(get_current_super_admin),
    db: AsyncSession = Depends(get_db),
):
    summary = await campaign_service.enqueue_eligible(
        db, campaign_id=campaign_id,
    )
    await db.commit()
    return {
        "queued": summary.queued,
        "skipped_consent": summary.skipped_consent,
        "skipped_cooldown": summary.skipped_cooldown,
        "skipped_frequency": summary.skipped_frequency,
        "reasons": summary.reasons,
    }


@admin_router.get(
    "/{campaign_id}/deliveries", response_model=list[DeliveryOut],
)
async def list_campaign_deliveries(
    campaign_id: str,
    status: Optional[str] = None,
    limit: int = 200,
    offset: int = 0,
    _: User = Depends(get_current_super_admin),
    db: AsyncSession = Depends(get_db),
):
    target: Optional[DeliveryStatus] = None
    if status:
        try:
            target = DeliveryStatus(status)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=f"invalid status: {status}") from exc
    rows = await campaign_service.list_deliveries(
        db, campaign_id=campaign_id, status=target, limit=limit, offset=offset,
    )
    return [_to_deliv(r) for r in rows]


@admin_router.get("/{campaign_id}/funnel")
async def get_funnel(
    campaign_id: str,
    _: User = Depends(get_current_super_admin),
    db: AsyncSession = Depends(get_db),
):
    f = await campaign_service.funnel_for_campaign(db, campaign_id=campaign_id)
    return {
        "campaign_id": f.campaign_id,
        "queued": f.queued, "delivered": f.delivered,
        "opened": f.opened, "clicked": f.clicked, "converted": f.converted,
        "skipped_consent": f.skipped_consent,
        "skipped_cooldown": f.skipped_cooldown,
        "skipped_frequency": f.skipped_frequency,
        "failed": f.failed,
    }


# ---------- engagement marking (called by integrations / pixels) ----------

@router.post("/campaign-deliveries/{delivery_id}/opened")
async def record_opened(
    delivery_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Public endpoint hit by tracking pixels / email-open beacons. No auth
    because the beacon URL is the secret; production should add a signed
    token in the URL to prevent forgery."""
    row = await campaign_service.mark_opened(db, delivery_id=delivery_id)
    if row is None:
        raise HTTPException(status_code=404, detail="delivery not found")
    await db.commit()
    return {"ok": True}


@router.post("/campaign-deliveries/{delivery_id}/clicked")
async def record_clicked(
    delivery_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Public — same as opened. Pixel redirect endpoint flows through here
    before pointing the user to the listing."""
    row = await campaign_service.mark_clicked(db, delivery_id=delivery_id)
    if row is None:
        raise HTTPException(status_code=404, detail="delivery not found")
    await db.commit()
    return {"ok": True}


class MarkDeliveredBody(BaseModel):
    error: Optional[str] = None


@router.post("/campaign-deliveries/{delivery_id}/delivered")
async def record_delivered(
    delivery_id: str,
    body: MarkDeliveredBody,
    _: User = Depends(get_current_super_admin),
    db: AsyncSession = Depends(get_db),
):
    """Called by the Phase 4C send worker after attempting delivery."""
    row = await campaign_service.mark_delivered(
        db, delivery_id=delivery_id, error=body.error,
    )
    if row is None:
        raise HTTPException(status_code=404, detail="delivery not found")
    await db.commit()
    return _to_deliv(row)


router.include_router(admin_router)
