"""Notification dispatcher (Phase 4C).

Picks QUEUED CampaignDelivery rows — both rule-driven and campaign-driven —
and fires them through the channel-appropriate transport, then flips the
row to DELIVERED or FAILED.

Channels:
  - IN_APP: insert a row into the existing `notifications` table. Always
    succeeds (DB write).
  - EMAIL: dispatch via `email_service._send_email`. Failures (SMTP error,
    no recipient) mark the delivery FAILED with the exception message.
  - PUSH: stub — marks FAILED with "push not configured". Phase 4D will
    integrate FCM / APNs.
  - WHATSAPP: stub — marks FAILED with "whatsapp not configured". Phase 4D.

Template variables: simple {{name}} and {{first_name}} substitution from
the user record. No Jinja, no MJML — keep it dependency-free.

This service NEVER raises out of `dispatch_pending`; per-delivery errors
are captured into `reason`.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.campaign import (
    Campaign, CampaignChannel, CampaignDelivery, DeliveryStatus,
)
# NOTE: Use the Notification class that's actually registered with Base
# at app startup (via app.models.waitlist). There's a pre-existing duplicate
# Notification class in app/models/notification.py that's only lazy-imported
# from routers/notifications.py; using it here would cause a metadata clash.
from app.models.waitlist import Notification
from app.models.notification_rule import NotificationRule
from app.models.user import User
from app.services import email_service
from app.services.tax_engine import cfg_get, load_active_config


# Max dispatch attempts before a transient failure becomes permanent FAILED.
# Each retry waits for the next scheduler tick (~30 min), giving natural backoff.
MAX_DISPATCH_ATTEMPTS = 3


@dataclass
class DispatchSummary:
    delivered: int = 0
    failed: int = 0
    skipped_already_done: int = 0
    retried: int = 0


_TEMPLATE_RE = re.compile(r"\{\{\s*(\w+)\s*\}\}")


def _render(template: str, *, user: User) -> str:
    """Tiny mustache-style substitution. Unknown keys collapse to ''."""
    first_name = (user.name or "there").strip().split(" ")[0]
    substitutions = {
        "name": user.name or "",
        "first_name": first_name,
        "email": user.email or "",
    }

    def _sub(match: re.Match) -> str:
        return substitutions.get(match.group(1), "")

    return _TEMPLATE_RE.sub(_sub, template)


async def _resolve_template_and_subject(
    db: AsyncSession, delivery: CampaignDelivery,
) -> tuple[str, str]:
    """Return (body_template, subject_template) for this delivery."""
    if delivery.notification_rule_id:
        rule = await db.get(NotificationRule, delivery.notification_rule_id)
        if rule is None:
            return "", "mySpace"
        return rule.body_template, (rule.subject_template or rule.name)
    if delivery.campaign_id:
        camp = await db.get(Campaign, delivery.campaign_id)
        if camp is None:
            return "", "mySpace"
        return camp.body_template, camp.name
    return "", "mySpace"


async def _dispatch_one(
    db: AsyncSession, delivery: CampaignDelivery,
) -> tuple[bool, Optional[str], bool]:
    """Return (success, error_msg, transient).

    `transient` is True when a retry could plausibly succeed (e.g. an SMTP
    hiccup). Permanent failures — missing email, unconfigured channel, bad
    template — return transient=False so the caller fails them immediately
    instead of retrying forever.
    """
    user = await db.get(User, delivery.user_id)
    if user is None:
        return False, "user not found", False

    body, subject = await _resolve_template_and_subject(db, delivery)
    if not body:
        return False, "empty body template", False
    rendered_body = _render(body, user=user)
    rendered_subject = _render(subject or "mySpace", user=user)

    channel = delivery.channel

    if channel == CampaignChannel.IN_APP:
        db.add(Notification(
            user_id=user.id,
            title=rendered_subject[:200],
            message=rendered_body,
            type="info",
        ))
        return True, None, False

    if channel == CampaignChannel.EMAIL:
        if not user.email:
            return False, "user has no email", False
        try:
            ok = await email_service._send_email(
                user.email, rendered_subject, rendered_body,
            )
        except Exception as exc:
            # Transport raised — likely transient (network/SMTP). Retry.
            return False, f"email error: {exc}"[:2000], True
        if not ok:
            # Transport returned a soft failure — retry within bounds.
            return False, "email transport returned False", True
        return True, None, False

    if channel == CampaignChannel.PUSH:
        return False, "push not configured (Phase 4D)", False

    if channel == CampaignChannel.WHATSAPP:
        return False, "whatsapp not configured (Phase 4D)", False

    return False, f"unknown channel {channel}", False


async def dispatch_pending(
    db: AsyncSession, *, limit: int = 100,
) -> DispatchSummary:
    """Send up to `limit` QUEUED deliveries. Caller commits.

    Always gated by `notification_automation.enabled` — when OFF this is a
    no-op so existing flows are never touched.
    """
    summary = DispatchSummary()
    config = await load_active_config(db)
    if not bool(cfg_get(config, "notification_automation.enabled", False)):
        return summary

    rows = (await db.execute(
        select(CampaignDelivery)
        .where(CampaignDelivery.status == DeliveryStatus.QUEUED)
        .order_by(CampaignDelivery.queued_at.asc())
        .limit(limit)
    )).scalars().all()

    for row in rows:
        ok, err, transient = await _dispatch_one(db, row)
        row.dispatch_attempts = (row.dispatch_attempts or 0) + 1
        if ok:
            row.status = DeliveryStatus.DELIVERED
            row.delivered_at = datetime.utcnow()
            summary.delivered += 1
        elif transient and row.dispatch_attempts < MAX_DISPATCH_ATTEMPTS:
            # Leave QUEUED so the next tick retries it (~30 min backoff).
            row.reason = (
                f"retry {row.dispatch_attempts}/{MAX_DISPATCH_ATTEMPTS}: "
                f"{err or 'unknown error'}"
            )[:2000]
            summary.retried += 1
        else:
            row.status = DeliveryStatus.FAILED
            row.reason = (err or "unknown error")[:2000]
            summary.failed += 1
        await db.flush()

    return summary
