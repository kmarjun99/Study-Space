"""Notification automation tests (Phase 4C).

Covers:
  - Master flag gate (notification_automation.enabled)
  - 4 triggers: BOOKING_ABANDONED, REPEAT_SEARCH_NO_BOOKING,
    AVAILABILITY_CHECKED_NO_BOOKING, PAYMENT_FAILED
  - Trigger excludes users who completed a booking
  - Consent gate per channel
  - Rule-scoped cooldown
  - Frequency cap shared with campaigns
  - Inactive rule → no-op
  - Dispatcher: IN_APP writes a Notification row, flips DELIVERED
  - Dispatcher: EMAIL with no recipient → FAILED
  - Dispatcher: PUSH/WHATSAPP → FAILED with stub reason
  - Dispatcher: template substitution
  - Dispatcher: master flag off → no-op
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime
from unittest.mock import patch

import pytest
from sqlalchemy import select

from app.models.campaign import (
    CampaignChannel, CampaignDelivery, DeliveryStatus,
)
from app.models.waitlist import Notification
from app.models.notification_rule import NotificationRule, TriggerType
from app.models.tax_config import TaxConfig
from app.models.user import User, UserRole
from app.models.user_consent_preferences import UserConsentPreferences
from app.models.user_event import EventCategory, UserEvent
from app.services import (
    notification_automation_service, notification_dispatcher_service,
)


# --------- helpers ---------------------------------------------------------

async def _set(db, key, value):
    row = (await db.execute(
        select(TaxConfig).where(TaxConfig.key == key)
    )).scalar_one_or_none()
    if row is None:
        db.add(TaxConfig(key=key, value=json.dumps(value)))
    else:
        row.value = json.dumps(value)
    await db.commit()


async def _enable_automation(db):
    await _set(db, "notification_automation.enabled", True)


async def _user(db, *, uid=None, name="Alice", email=None,
                marketing=True, whatsapp=False):
    uid = uid or str(uuid.uuid4())
    email = email or f"{uid[:8]}@x.com"
    db.add(User(
        id=uid, email=email, hashed_password="x",
        name=name, role=UserRole.STUDENT,
    ))
    db.add(UserConsentPreferences(
        user_id=uid,
        allow_analytics_tracking=True,
        allow_marketing_notifications=marketing,
        allow_whatsapp_updates=whatsapp,
    ))
    await db.commit()
    return uid


async def _event(db, *, user_id, name, category=EventCategory.BOOKING,
                  when=None):
    db.add(UserEvent(
        event_id=str(uuid.uuid4()),
        user_id=user_id,
        event_name=name, event_category=category,
        created_at=when or datetime.utcnow(),
    ))
    await db.commit()


async def _rule(db, *,
                trigger=TriggerType.BOOKING_ABANDONED,
                channel=CampaignChannel.IN_APP,
                window_minutes=120, min_event_count=1,
                cooldown_hours=24, frequency_cap=3, frequency_window=7,
                active=True, body="Hi {{first_name}}, come back!"):
    r = NotificationRule(
        slug=f"r-{uuid.uuid4().hex[:8]}",
        name="Test rule", body_template=body,
        subject_template="StudySpace nudge",
        trigger_type=trigger, trigger_window_minutes=window_minutes,
        min_event_count=min_event_count,
        channel=channel,
        cooldown_hours=cooldown_hours,
        frequency_cap_per_user=frequency_cap,
        frequency_cap_window_days=frequency_window,
        is_active=active,
    )
    db.add(r)
    await db.commit()
    await db.refresh(r)
    return r


# --------- evaluate / triggers ---------------------------------------------

@pytest.mark.asyncio
async def test_evaluate_master_flag_off(seeded_db):
    db = seeded_db
    uid = await _user(db)
    await _event(db, user_id=uid, name="booking.start")
    rule = await _rule(db)
    summary = await notification_automation_service.evaluate_rule(
        db, rule_id=rule.id,
    )
    assert summary.queued == 0
    assert "OFF" in (summary.reasons[0] if summary.reasons else "")


@pytest.mark.asyncio
async def test_inactive_rule_yields_nothing(seeded_db):
    db = seeded_db
    await _enable_automation(db)
    uid = await _user(db)
    await _event(db, user_id=uid, name="booking.start")
    rule = await _rule(db, active=False)
    summary = await notification_automation_service.evaluate_rule(
        db, rule_id=rule.id,
    )
    assert summary.queued == 0
    assert any("not active" in r for r in summary.reasons)


@pytest.mark.asyncio
async def test_booking_abandoned_fires(seeded_db):
    db = seeded_db
    await _enable_automation(db)
    uid = await _user(db)
    await _event(db, user_id=uid, name="booking.start")
    rule = await _rule(db, trigger=TriggerType.BOOKING_ABANDONED)
    summary = await notification_automation_service.evaluate_rule(
        db, rule_id=rule.id,
    )
    assert summary.queued == 1


@pytest.mark.asyncio
async def test_booking_completed_within_window_excludes_user(seeded_db):
    db = seeded_db
    await _enable_automation(db)
    uid = await _user(db)
    await _event(db, user_id=uid, name="booking.start")
    await _event(db, user_id=uid, name="booking.completed")
    rule = await _rule(db, trigger=TriggerType.BOOKING_ABANDONED)
    summary = await notification_automation_service.evaluate_rule(
        db, rule_id=rule.id,
    )
    assert summary.queued == 0


@pytest.mark.asyncio
async def test_repeat_search_no_booking(seeded_db):
    db = seeded_db
    await _enable_automation(db)
    uid = await _user(db)
    for _ in range(3):
        await _event(db, user_id=uid, name="search.performed",
                     category=EventCategory.SEARCH)
    rule = await _rule(
        db, trigger=TriggerType.REPEAT_SEARCH_NO_BOOKING, min_event_count=3,
    )
    summary = await notification_automation_service.evaluate_rule(
        db, rule_id=rule.id,
    )
    assert summary.queued == 1


@pytest.mark.asyncio
async def test_repeat_search_below_threshold_skips(seeded_db):
    db = seeded_db
    await _enable_automation(db)
    uid = await _user(db)
    await _event(db, user_id=uid, name="search.performed",
                 category=EventCategory.SEARCH)
    rule = await _rule(
        db, trigger=TriggerType.REPEAT_SEARCH_NO_BOOKING, min_event_count=3,
    )
    summary = await notification_automation_service.evaluate_rule(
        db, rule_id=rule.id,
    )
    assert summary.queued == 0


@pytest.mark.asyncio
async def test_availability_check_no_booking_fires(seeded_db):
    db = seeded_db
    await _enable_automation(db)
    uid = await _user(db)
    await _event(db, user_id=uid, name="cabin.availability.viewed",
                 category=EventCategory.VIEW)
    rule = await _rule(
        db, trigger=TriggerType.AVAILABILITY_CHECKED_NO_BOOKING,
    )
    summary = await notification_automation_service.evaluate_rule(
        db, rule_id=rule.id,
    )
    assert summary.queued == 1


@pytest.mark.asyncio
async def test_payment_failed_fires(seeded_db):
    db = seeded_db
    await _enable_automation(db)
    uid = await _user(db)
    await _event(db, user_id=uid, name="payment.failed",
                 category=EventCategory.PAYMENT)
    rule = await _rule(db, trigger=TriggerType.PAYMENT_FAILED)
    summary = await notification_automation_service.evaluate_rule(
        db, rule_id=rule.id,
    )
    assert summary.queued == 1


# --------- gates -----------------------------------------------------------

@pytest.mark.asyncio
async def test_no_marketing_consent_skips_in_app(seeded_db):
    db = seeded_db
    await _enable_automation(db)
    uid = await _user(db, marketing=False)
    await _event(db, user_id=uid, name="booking.start")
    rule = await _rule(db, channel=CampaignChannel.IN_APP)
    summary = await notification_automation_service.evaluate_rule(
        db, rule_id=rule.id,
    )
    assert summary.queued == 0
    assert summary.skipped_consent == 1
    rows = (await db.execute(
        select(CampaignDelivery).where(
            CampaignDelivery.notification_rule_id == rule.id,
        )
    )).scalars().all()
    assert rows[0].status == DeliveryStatus.SKIPPED_CONSENT


@pytest.mark.asyncio
async def test_whatsapp_uses_separate_consent(seeded_db):
    db = seeded_db
    await _enable_automation(db)
    uid = await _user(db, marketing=True, whatsapp=False)
    await _event(db, user_id=uid, name="booking.start")
    rule = await _rule(db, channel=CampaignChannel.WHATSAPP)
    summary = await notification_automation_service.evaluate_rule(
        db, rule_id=rule.id,
    )
    assert summary.skipped_consent == 1


@pytest.mark.asyncio
async def test_rule_cooldown_prevents_immediate_re_fire(seeded_db):
    db = seeded_db
    await _enable_automation(db)
    uid = await _user(db)
    await _event(db, user_id=uid, name="booking.start")
    rule = await _rule(db, cooldown_hours=24)
    s1 = await notification_automation_service.evaluate_rule(
        db, rule_id=rule.id,
    )
    s2 = await notification_automation_service.evaluate_rule(
        db, rule_id=rule.id,
    )
    assert s1.queued == 1 and s2.queued == 0
    assert s2.skipped_cooldown == 1


@pytest.mark.asyncio
async def test_frequency_cap_shared_across_rules(seeded_db):
    db = seeded_db
    await _enable_automation(db)
    uid = await _user(db)
    await _event(db, user_id=uid, name="booking.start")
    await _event(db, user_id=uid, name="payment.failed",
                 category=EventCategory.PAYMENT)
    r1 = await _rule(db, frequency_cap=1, cooldown_hours=0)
    r2 = await _rule(
        db, trigger=TriggerType.PAYMENT_FAILED,
        frequency_cap=1, cooldown_hours=0,
    )
    s1 = await notification_automation_service.evaluate_rule(
        db, rule_id=r1.id,
    )
    s2 = await notification_automation_service.evaluate_rule(
        db, rule_id=r2.id,
    )
    assert s1.queued == 1
    assert s2.queued == 0
    assert s2.skipped_frequency == 1


# --------- dispatcher ------------------------------------------------------

@pytest.mark.asyncio
async def test_dispatch_in_app_creates_notification_row(seeded_db):
    db = seeded_db
    await _enable_automation(db)
    uid = await _user(db, name="Aarav Kumar")
    await _event(db, user_id=uid, name="booking.start")
    rule = await _rule(db, channel=CampaignChannel.IN_APP)
    await notification_automation_service.evaluate_rule(db, rule_id=rule.id)
    await db.commit()

    summary = await notification_dispatcher_service.dispatch_pending(db)
    await db.commit()
    assert summary.delivered == 1
    assert summary.failed == 0

    notifs = (await db.execute(
        select(Notification).where(Notification.user_id == uid)
    )).scalars().all()
    assert len(notifs) == 1
    # Template substitution: {{first_name}} → "Aarav"
    assert "Aarav" in notifs[0].message


@pytest.mark.asyncio
async def test_dispatch_master_flag_off_noop(seeded_db):
    db = seeded_db
    await _enable_automation(db)
    uid = await _user(db)
    await _event(db, user_id=uid, name="booking.start")
    rule = await _rule(db, channel=CampaignChannel.IN_APP)
    await notification_automation_service.evaluate_rule(db, rule_id=rule.id)
    await db.commit()

    await _set(db, "notification_automation.enabled", False)
    summary = await notification_dispatcher_service.dispatch_pending(db)
    assert summary.delivered == 0
    # Delivery still QUEUED
    row = (await db.execute(
        select(CampaignDelivery).where(
            CampaignDelivery.notification_rule_id == rule.id,
        )
    )).scalar_one()
    assert row.status == DeliveryStatus.QUEUED


@pytest.mark.asyncio
async def test_dispatch_push_marks_failed_with_stub_reason(seeded_db):
    db = seeded_db
    await _enable_automation(db)
    uid = await _user(db)
    await _event(db, user_id=uid, name="booking.start")
    rule = await _rule(db, channel=CampaignChannel.PUSH)
    await notification_automation_service.evaluate_rule(db, rule_id=rule.id)
    await db.commit()

    summary = await notification_dispatcher_service.dispatch_pending(db)
    await db.commit()
    assert summary.failed == 1
    row = (await db.execute(
        select(CampaignDelivery).where(
            CampaignDelivery.notification_rule_id == rule.id,
        )
    )).scalar_one()
    assert row.status == DeliveryStatus.FAILED
    assert "push" in (row.reason or "").lower()


@pytest.mark.asyncio
async def test_dispatch_email_calls_email_service(seeded_db):
    db = seeded_db
    await _enable_automation(db)
    uid = await _user(db, email="test@example.com")
    await _event(db, user_id=uid, name="booking.start")
    rule = await _rule(db, channel=CampaignChannel.EMAIL)
    await notification_automation_service.evaluate_rule(db, rule_id=rule.id)
    await db.commit()

    async def _fake_send(to, subject, html):
        return True

    with patch(
        "app.services.email_service._send_email", side_effect=_fake_send,
    ):
        summary = await notification_dispatcher_service.dispatch_pending(db)
        await db.commit()
    assert summary.delivered == 1
    assert summary.failed == 0


@pytest.mark.asyncio
async def test_dispatch_email_transient_failure_retries_then_fails(seeded_db):
    """A transient SMTP error keeps the delivery QUEUED and retries it on the
    next tick, up to MAX_DISPATCH_ATTEMPTS, after which it becomes FAILED."""
    db = seeded_db
    await _enable_automation(db)
    uid = await _user(db, email="test@example.com")
    await _event(db, user_id=uid, name="booking.start")
    rule = await _rule(db, channel=CampaignChannel.EMAIL)
    await notification_automation_service.evaluate_rule(db, rule_id=rule.id)
    await db.commit()

    async def _explode(to, subject, html):
        raise RuntimeError("smtp blew up")

    async def _row():
        return (await db.execute(
            select(CampaignDelivery).where(
                CampaignDelivery.notification_rule_id == rule.id,
            )
        )).scalar_one()

    with patch(
        "app.services.email_service._send_email", side_effect=_explode,
    ):
        # Attempts 1 and 2: transient → stays QUEUED, counted as retried.
        for expected_attempts in (1, 2):
            summary = await notification_dispatcher_service.dispatch_pending(db)
            await db.commit()
            assert summary.retried == 1
            assert summary.failed == 0
            row = await _row()
            assert row.status == DeliveryStatus.QUEUED
            assert row.dispatch_attempts == expected_attempts

        # Attempt 3 hits the cap → permanent FAILED.
        summary = await notification_dispatcher_service.dispatch_pending(db)
        await db.commit()
        assert summary.failed == 1
        assert summary.retried == 0

    row = await _row()
    assert row.status == DeliveryStatus.FAILED
    assert row.dispatch_attempts == 3
    assert "smtp" in (row.reason or "")
