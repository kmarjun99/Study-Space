"""Campaign delivery + attribution service.

`enqueue_eligible(campaign_id)` is the workhorse: it walks active segment
members, applies consent + cooldown + frequency cap, and emits one
`CampaignDelivery` row per user — with a clear `status` and `reason` so
audit logs are self-documenting.

This module never sends anything. Phase 4C will provide a delivery worker
that takes QUEUED rows and dispatches via the existing email_service /
notification table / WhatsApp integration, then flips status to DELIVERED.

Attribution: when a booking confirms, `attribute_booking()` finds the
most-recent CLICKED delivery for that user inside
`campaigns.attribution_window_days` and stamps `converted_booking_id`.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.campaign import (
    Campaign, CampaignChannel, CampaignDelivery, CampaignStatus,
    DeliveryStatus,
)
from app.models.user_consent_preferences import UserConsentPreferences
from app.models.user_segment import UserSegmentMembership
from app.services.tax_engine import cfg_get, load_active_config


@dataclass
class EnqueueSummary:
    queued: int = 0
    skipped_consent: int = 0
    skipped_cooldown: int = 0
    skipped_frequency: int = 0
    reasons: list[str] = field(default_factory=list)


# ---------- consent ---------------------------------------------------------

def _required_consent_field(channel: CampaignChannel) -> str:
    """Which consent flag gates this channel."""
    if channel == CampaignChannel.WHATSAPP:
        return "allow_whatsapp_updates"
    # IN_APP / EMAIL / PUSH all gated by marketing notifications
    return "allow_marketing_notifications"


async def _has_consent(
    db: AsyncSession, *, user_id: str, channel: CampaignChannel,
) -> bool:
    row = await db.get(UserConsentPreferences, user_id)
    if row is None:
        return False
    field = _required_consent_field(channel)
    return bool(getattr(row, field, False))


# ---------- cooldown + frequency cap ---------------------------------------

async def _within_cooldown(
    db: AsyncSession,
    *,
    campaign_id: str,
    user_id: str,
    cooldown_hours: int,
) -> bool:
    if cooldown_hours <= 0:
        return False
    cutoff = datetime.utcnow() - timedelta(hours=cooldown_hours)
    row = (await db.execute(
        select(CampaignDelivery.id).where(and_(
            CampaignDelivery.campaign_id == campaign_id,
            CampaignDelivery.user_id == user_id,
            # ONLY count real deliveries (or queued/in-flight) — skipped rows
            # don't reset the cooldown.
            CampaignDelivery.status.in_([
                DeliveryStatus.QUEUED, DeliveryStatus.DELIVERED,
            ]),
            CampaignDelivery.queued_at >= cutoff,
        ))
        .limit(1)
    )).first()
    return row is not None


async def _frequency_cap_hit(
    db: AsyncSession,
    *,
    user_id: str,
    cap: int,
    window_days: int,
) -> bool:
    if cap <= 0 or window_days <= 0:
        return False
    cutoff = datetime.utcnow() - timedelta(days=window_days)
    n = (await db.execute(
        select(func.count(CampaignDelivery.id)).where(and_(
            CampaignDelivery.user_id == user_id,
            CampaignDelivery.status.in_([
                DeliveryStatus.QUEUED, DeliveryStatus.DELIVERED,
            ]),
            CampaignDelivery.queued_at >= cutoff,
        ))
    )).scalar_one()
    return int(n) >= cap


# ---------- public: enqueue_eligible ----------------------------------------

async def enqueue_eligible(
    db: AsyncSession, *, campaign_id: str,
) -> EnqueueSummary:
    """Walk the campaign's segment and queue one delivery per eligible user.

    Always writes one `CampaignDelivery` per evaluated user — eligible
    users get QUEUED, ineligible ones get a SKIPPED_* row with reason.
    This makes "why didn't user X get the message" auditable.

    Caller commits.
    """
    summary = EnqueueSummary()

    config = await load_active_config(db)
    if not bool(cfg_get(config, "campaigns.enabled", False)):
        summary.reasons.append("campaigns.enabled is OFF")
        return summary

    campaign = await db.get(Campaign, campaign_id)
    if campaign is None:
        summary.reasons.append("campaign not found")
        return summary
    if campaign.status != CampaignStatus.ACTIVE:
        summary.reasons.append(f"campaign status={campaign.status.value}")
        return summary

    now = datetime.utcnow()
    if campaign.send_window_starts and now < campaign.send_window_starts:
        summary.reasons.append("send window not yet open")
        return summary
    if campaign.send_window_ends and now > campaign.send_window_ends:
        summary.reasons.append("send window closed")
        return summary

    members = (await db.execute(
        select(UserSegmentMembership).where(and_(
            UserSegmentMembership.segment_id == campaign.segment_id,
            UserSegmentMembership.is_active.is_(True),
        ))
    )).scalars().all()

    for member in members:
        # 1. Consent gate
        if not await _has_consent(
            db, user_id=member.user_id, channel=campaign.channel,
        ):
            db.add(CampaignDelivery(
                campaign_id=campaign.id, user_id=member.user_id,
                channel=campaign.channel,
                status=DeliveryStatus.SKIPPED_CONSENT,
                reason=f"no consent for channel={campaign.channel.value}",
            ))
            summary.skipped_consent += 1
            continue

        # 2. Cooldown
        if await _within_cooldown(
            db, campaign_id=campaign.id, user_id=member.user_id,
            cooldown_hours=campaign.cooldown_hours,
        ):
            db.add(CampaignDelivery(
                campaign_id=campaign.id, user_id=member.user_id,
                channel=campaign.channel,
                status=DeliveryStatus.SKIPPED_COOLDOWN,
                reason=f"within {campaign.cooldown_hours}h cooldown",
            ))
            summary.skipped_cooldown += 1
            continue

        # 3. Frequency cap (cross-campaign)
        if await _frequency_cap_hit(
            db, user_id=member.user_id,
            cap=campaign.frequency_cap_per_user,
            window_days=campaign.frequency_cap_window_days,
        ):
            db.add(CampaignDelivery(
                campaign_id=campaign.id, user_id=member.user_id,
                channel=campaign.channel,
                status=DeliveryStatus.SKIPPED_FREQUENCY,
                reason=(
                    f"frequency cap {campaign.frequency_cap_per_user} "
                    f"hit in {campaign.frequency_cap_window_days}d window"
                ),
            ))
            summary.skipped_frequency += 1
            continue

        # Eligible — queue
        db.add(CampaignDelivery(
            campaign_id=campaign.id, user_id=member.user_id,
            channel=campaign.channel,
            status=DeliveryStatus.QUEUED,
        ))
        summary.queued += 1

    await db.flush()
    return summary


# ---------- engagement marking --------------------------------------------

async def _set_delivery_field(
    db: AsyncSession,
    *,
    delivery_id: str,
    field_name: str,
    new_status: Optional[DeliveryStatus] = None,
    extra_status_only_if: Optional[set[DeliveryStatus]] = None,
) -> Optional[CampaignDelivery]:
    row = await db.get(CampaignDelivery, delivery_id)
    if row is None:
        return None
    setattr(row, field_name, datetime.utcnow())
    if new_status is not None:
        if extra_status_only_if is None or row.status in extra_status_only_if:
            row.status = new_status
    await db.flush()
    return row


async def mark_delivered(
    db: AsyncSession, *, delivery_id: str, error: Optional[str] = None,
) -> Optional[CampaignDelivery]:
    """Phase 4C delivery worker calls this after a real send.

    Only flips QUEUED → DELIVERED. If `error` is supplied, status becomes
    FAILED and `error` is recorded.
    """
    row = await db.get(CampaignDelivery, delivery_id)
    if row is None:
        return None
    if row.status not in (DeliveryStatus.QUEUED,):
        return row
    if error:
        row.status = DeliveryStatus.FAILED
        row.reason = error[:2000]
    else:
        row.status = DeliveryStatus.DELIVERED
        row.delivered_at = datetime.utcnow()
    await db.flush()
    return row


async def mark_opened(
    db: AsyncSession, *, delivery_id: str,
) -> Optional[CampaignDelivery]:
    return await _set_delivery_field(
        db, delivery_id=delivery_id, field_name="opened_at",
    )


async def mark_clicked(
    db: AsyncSession, *, delivery_id: str,
) -> Optional[CampaignDelivery]:
    row = await db.get(CampaignDelivery, delivery_id)
    if row is None:
        return None
    row.clicked_at = datetime.utcnow()
    # A click implies open, even if the open beacon failed.
    if row.opened_at is None:
        row.opened_at = row.clicked_at
    await db.flush()
    return row


# ---------- attribution ---------------------------------------------------

async def attribute_booking(
    db: AsyncSession, *, booking_id: str, user_id: str,
) -> Optional[CampaignDelivery]:
    """Find the most recent CLICKED delivery for `user_id` inside the
    attribution window and stamp `converted_booking_id` + `converted_at`.

    Last-click-wins. Returns the attributed delivery (or None).
    Caller commits.
    """
    config = await load_active_config(db)
    if not bool(cfg_get(config, "campaigns.enabled", False)):
        return None

    window_days = int(cfg_get(
        config, "campaigns.attribution_window_days", 7,
    ))
    cutoff = datetime.utcnow() - timedelta(days=window_days)

    row = (await db.execute(
        select(CampaignDelivery)
        .where(and_(
            CampaignDelivery.user_id == user_id,
            CampaignDelivery.clicked_at.isnot(None),
            CampaignDelivery.clicked_at >= cutoff,
            # Only count first attribution — don't overwrite a previous one.
            CampaignDelivery.converted_booking_id.is_(None),
        ))
        .order_by(CampaignDelivery.clicked_at.desc())
        .limit(1)
    )).scalar_one_or_none()
    if row is None:
        return None

    row.converted_booking_id = booking_id
    row.converted_at = datetime.utcnow()
    await db.flush()
    return row


# ---------- read helpers --------------------------------------------------

async def list_campaigns(
    db: AsyncSession, *, include_completed: bool = True,
) -> list[Campaign]:
    stmt = select(Campaign).order_by(Campaign.created_at.desc())
    if not include_completed:
        stmt = stmt.where(Campaign.status != CampaignStatus.COMPLETED)
    rows = (await db.execute(stmt)).scalars().all()
    return list(rows)


async def list_deliveries(
    db: AsyncSession, *, campaign_id: str,
    status: Optional[DeliveryStatus] = None,
    limit: int = 200, offset: int = 0,
) -> list[CampaignDelivery]:
    stmt = select(CampaignDelivery).where(
        CampaignDelivery.campaign_id == campaign_id,
    ).order_by(CampaignDelivery.queued_at.desc())
    if status is not None:
        stmt = stmt.where(CampaignDelivery.status == status)
    stmt = stmt.offset(offset).limit(limit)
    rows = (await db.execute(stmt)).scalars().all()
    return list(rows)


@dataclass
class CampaignFunnel:
    campaign_id: str
    queued: int = 0
    delivered: int = 0
    opened: int = 0
    clicked: int = 0
    converted: int = 0
    skipped_consent: int = 0
    skipped_cooldown: int = 0
    skipped_frequency: int = 0
    failed: int = 0


async def funnel_for_campaign(
    db: AsyncSession, *, campaign_id: str,
) -> CampaignFunnel:
    """Aggregate counts for the campaign — fuels the admin dashboard."""
    rows = (await db.execute(
        select(CampaignDelivery)
        .where(CampaignDelivery.campaign_id == campaign_id)
    )).scalars().all()
    out = CampaignFunnel(campaign_id=campaign_id)
    for r in rows:
        if r.status == DeliveryStatus.SKIPPED_CONSENT:
            out.skipped_consent += 1
            continue
        if r.status == DeliveryStatus.SKIPPED_COOLDOWN:
            out.skipped_cooldown += 1
            continue
        if r.status == DeliveryStatus.SKIPPED_FREQUENCY:
            out.skipped_frequency += 1
            continue
        if r.status == DeliveryStatus.FAILED:
            out.failed += 1
            continue
        # Count the funnel as wide as the user got
        out.queued += 1
        if r.delivered_at is not None:
            out.delivered += 1
        if r.opened_at is not None:
            out.opened += 1
        if r.clicked_at is not None:
            out.clicked += 1
        if r.converted_booking_id is not None:
            out.converted += 1
    return out
