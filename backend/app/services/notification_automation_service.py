"""Notification automation service (Phase 4C).

Trigger-based outreach. For each ACTIVE NotificationRule, this service:
  1. Finds the candidate users (those whose recent events match the trigger).
  2. Applies the same gate stack as campaigns — consent, cooldown,
     frequency-cap — using shared helpers from campaign_service.
  3. Writes one CampaignDelivery row per evaluated user with
     `notification_rule_id` set and `campaign_id` NULL. Eligible users get
     QUEUED; ineligible ones get SKIPPED_* with a `reason` for audit.

Cooldown for rules is rule-scoped (don't re-fire same rule for same user
within `cooldown_hours`). Frequency cap is cross-rule + cross-campaign
(same as Phase 4B) — a user can receive at most N deliveries / window
across all automation.

This module never sends anything. The dispatcher
(notification_dispatcher_service) consumes QUEUED rows.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.campaign import (
    CampaignChannel, CampaignDelivery, DeliveryStatus,
)
from app.models.notification_rule import NotificationRule, TriggerType
from app.models.user_event import UserEvent
from app.services.campaign_service import _has_consent, _frequency_cap_hit
from app.services.tax_engine import cfg_get, load_active_config


@dataclass
class RuleEnqueueSummary:
    rule_id: str
    queued: int = 0
    skipped_consent: int = 0
    skipped_cooldown: int = 0
    skipped_frequency: int = 0
    reasons: list[str] = field(default_factory=list)


# ---------- cooldown (rule-scoped) -----------------------------------------

async def _rule_within_cooldown(
    db: AsyncSession,
    *,
    rule_id: str,
    user_id: str,
    cooldown_hours: int,
) -> bool:
    if cooldown_hours <= 0:
        return False
    cutoff = datetime.utcnow() - timedelta(hours=cooldown_hours)
    row = (await db.execute(
        select(CampaignDelivery.id).where(and_(
            CampaignDelivery.notification_rule_id == rule_id,
            CampaignDelivery.user_id == user_id,
            CampaignDelivery.status.in_([
                DeliveryStatus.QUEUED, DeliveryStatus.DELIVERED,
            ]),
            CampaignDelivery.queued_at >= cutoff,
        ))
        .limit(1)
    )).first()
    return row is not None


# ---------- trigger evaluators ---------------------------------------------
#
# Each evaluator returns the list of user_ids whose recent event stream
# matches the trigger. Pure read-only.

async def _users_with_booking_abandoned(
    db: AsyncSession, *, window_minutes: int,
) -> list[str]:
    """booking.start within window AND no booking.completed since."""
    since = datetime.utcnow() - timedelta(minutes=window_minutes)
    starts = (await db.execute(
        select(UserEvent.user_id, func.max(UserEvent.created_at).label("started_at"))
        .where(and_(
            UserEvent.user_id.isnot(None),
            UserEvent.event_name == "booking.start",
            UserEvent.created_at >= since,
        ))
        .group_by(UserEvent.user_id)
    )).all()

    completed = {
        row[0] for row in (await db.execute(
            select(UserEvent.user_id)
            .where(and_(
                UserEvent.user_id.isnot(None),
                UserEvent.event_name == "booking.completed",
                UserEvent.created_at >= since,
            ))
        )).all()
    }

    # Filter out users whose latest completion is AFTER the latest start.
    out: list[str] = []
    for user_id, _started_at in starts:
        if user_id in completed:
            # Cheap check — exclude if any completion exists in window.
            # Strict definition (completion after start) would need a per-user
            # comparison; this gives fewer false positives at the cost of
            # missing users who completed an earlier booking but abandoned a
            # later one within the same window. Acceptable for the trigger.
            continue
        out.append(user_id)
    return out


async def _users_with_repeat_search_no_booking(
    db: AsyncSession, *, window_minutes: int, min_event_count: int,
) -> list[str]:
    since = datetime.utcnow() - timedelta(minutes=window_minutes)
    rows = (await db.execute(
        select(UserEvent.user_id, func.count(UserEvent.id).label("n"))
        .where(and_(
            UserEvent.user_id.isnot(None),
            UserEvent.event_name == "search.performed",
            UserEvent.created_at >= since,
        ))
        .group_by(UserEvent.user_id)
        .having(func.count(UserEvent.id) >= min_event_count)
    )).all()

    completed = {
        row[0] for row in (await db.execute(
            select(UserEvent.user_id)
            .where(and_(
                UserEvent.user_id.isnot(None),
                UserEvent.event_name == "booking.completed",
                UserEvent.created_at >= since,
            ))
        )).all()
    }
    return [user_id for user_id, _n in rows if user_id not in completed]


async def _users_with_availability_check_no_booking(
    db: AsyncSession, *, window_minutes: int,
) -> list[str]:
    since = datetime.utcnow() - timedelta(minutes=window_minutes)
    rows = (await db.execute(
        select(UserEvent.user_id).where(and_(
            UserEvent.user_id.isnot(None),
            UserEvent.event_name.like("%availability%"),
            UserEvent.created_at >= since,
        )).distinct()
    )).all()
    candidates = {r[0] for r in rows}

    completed = {
        row[0] for row in (await db.execute(
            select(UserEvent.user_id)
            .where(and_(
                UserEvent.user_id.isnot(None),
                UserEvent.event_name == "booking.completed",
                UserEvent.created_at >= since,
            ))
        )).all()
    }
    return [u for u in candidates if u not in completed]


async def _users_with_payment_failed(
    db: AsyncSession, *, window_minutes: int,
) -> list[str]:
    since = datetime.utcnow() - timedelta(minutes=window_minutes)
    rows = (await db.execute(
        select(UserEvent.user_id).where(and_(
            UserEvent.user_id.isnot(None),
            UserEvent.event_name.in_(["payment.failed", "payment.abandoned"]),
            UserEvent.created_at >= since,
        )).distinct()
    )).all()
    candidates = {r[0] for r in rows}

    completed = {
        row[0] for row in (await db.execute(
            select(UserEvent.user_id)
            .where(and_(
                UserEvent.user_id.isnot(None),
                UserEvent.event_name == "booking.completed",
                UserEvent.created_at >= since,
            ))
        )).all()
    }
    return [u for u in candidates if u not in completed]


_TRIGGER_DISPATCH = {
    TriggerType.BOOKING_ABANDONED: _users_with_booking_abandoned,
    TriggerType.AVAILABILITY_CHECKED_NO_BOOKING:
        _users_with_availability_check_no_booking,
    TriggerType.PAYMENT_FAILED: _users_with_payment_failed,
}


async def _candidates_for_rule(
    db: AsyncSession, rule: NotificationRule,
) -> list[str]:
    if rule.trigger_type == TriggerType.REPEAT_SEARCH_NO_BOOKING:
        return await _users_with_repeat_search_no_booking(
            db,
            window_minutes=rule.trigger_window_minutes,
            min_event_count=rule.min_event_count,
        )
    fn = _TRIGGER_DISPATCH.get(rule.trigger_type)
    if fn is None:
        return []
    return await fn(db, window_minutes=rule.trigger_window_minutes)


# ---------- public: evaluate_rule + evaluate_all ---------------------------

async def evaluate_rule(
    db: AsyncSession, *, rule_id: str,
) -> RuleEnqueueSummary:
    """Evaluate one rule. Writes QUEUED + SKIPPED_* rows. Caller commits."""
    summary = RuleEnqueueSummary(rule_id=rule_id)

    config = await load_active_config(db)
    if not bool(cfg_get(config, "notification_automation.enabled", False)):
        summary.reasons.append("notification_automation.enabled is OFF")
        return summary

    rule = await db.get(NotificationRule, rule_id)
    if rule is None:
        summary.reasons.append("rule not found")
        return summary
    if not rule.is_active:
        summary.reasons.append("rule is not active")
        return summary

    candidates = await _candidates_for_rule(db, rule)
    channel: CampaignChannel = rule.channel

    for user_id in candidates:
        # 1. Consent
        if not await _has_consent(db, user_id=user_id, channel=channel):
            db.add(CampaignDelivery(
                notification_rule_id=rule.id, user_id=user_id,
                channel=channel, status=DeliveryStatus.SKIPPED_CONSENT,
                reason=f"no consent for channel={channel.value}",
            ))
            summary.skipped_consent += 1
            continue

        # 2. Cooldown (rule-scoped)
        if await _rule_within_cooldown(
            db, rule_id=rule.id, user_id=user_id,
            cooldown_hours=rule.cooldown_hours,
        ):
            db.add(CampaignDelivery(
                notification_rule_id=rule.id, user_id=user_id,
                channel=channel, status=DeliveryStatus.SKIPPED_COOLDOWN,
                reason=f"within {rule.cooldown_hours}h cooldown for rule",
            ))
            summary.skipped_cooldown += 1
            continue

        # 3. Frequency cap (cross-rule + cross-campaign)
        if await _frequency_cap_hit(
            db, user_id=user_id,
            cap=rule.frequency_cap_per_user,
            window_days=rule.frequency_cap_window_days,
        ):
            db.add(CampaignDelivery(
                notification_rule_id=rule.id, user_id=user_id,
                channel=channel, status=DeliveryStatus.SKIPPED_FREQUENCY,
                reason=(
                    f"frequency cap {rule.frequency_cap_per_user} "
                    f"hit in {rule.frequency_cap_window_days}d window"
                ),
            ))
            summary.skipped_frequency += 1
            continue

        db.add(CampaignDelivery(
            notification_rule_id=rule.id, user_id=user_id,
            channel=channel, status=DeliveryStatus.QUEUED,
        ))
        summary.queued += 1

    await db.flush()
    return summary


async def evaluate_all_active_rules(
    db: AsyncSession,
) -> list[RuleEnqueueSummary]:
    """Used by the scheduler. Returns one summary per rule."""
    config = await load_active_config(db)
    if not bool(cfg_get(config, "notification_automation.enabled", False)):
        return []
    rules = (await db.execute(
        select(NotificationRule).where(NotificationRule.is_active.is_(True))
    )).scalars().all()
    out: list[RuleEnqueueSummary] = []
    for rule in rules:
        out.append(await evaluate_rule(db, rule_id=rule.id))
    return out


# ---------- read helpers ---------------------------------------------------

async def list_rules(
    db: AsyncSession, *, include_inactive: bool = True,
) -> list[NotificationRule]:
    stmt = select(NotificationRule).order_by(NotificationRule.created_at.desc())
    if not include_inactive:
        stmt = stmt.where(NotificationRule.is_active.is_(True))
    rows = (await db.execute(stmt)).scalars().all()
    return list(rows)


async def list_rule_deliveries(
    db: AsyncSession, *, rule_id: str,
    status: Optional[DeliveryStatus] = None,
    limit: int = 200, offset: int = 0,
) -> list[CampaignDelivery]:
    stmt = select(CampaignDelivery).where(
        CampaignDelivery.notification_rule_id == rule_id,
    ).order_by(CampaignDelivery.queued_at.desc())
    if status is not None:
        stmt = stmt.where(CampaignDelivery.status == status)
    stmt = stmt.offset(offset).limit(limit)
    rows = (await db.execute(stmt)).scalars().all()
    return list(rows)
