"""Campaign service tests — eligibility + attribution.

Covers:
  - Master flag gate
  - enqueue: skips users without channel-appropriate consent
  - enqueue: skips users in cooldown for the same campaign
  - enqueue: skips users at the cross-campaign frequency cap
  - Skipped deliveries get a status + reason
  - Campaign not ACTIVE -> nothing queued
  - Send window enforcement
  - Engagement: mark_delivered / mark_opened / mark_clicked
  - Attribution: last-click within window wins
  - Attribution: clicks outside window are ignored
  - Attribution: once a delivery is attributed it doesn't get reattributed
  - Funnel aggregator
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

from app.models.campaign import (
    Campaign, CampaignChannel, CampaignDelivery, CampaignStatus,
    DeliveryStatus,
)
from app.models.tax_config import TaxConfig
from app.models.user import User, UserRole
from app.models.user_consent_preferences import UserConsentPreferences
from app.models.user_segment import (
    SegmentRuleType, UserSegment, UserSegmentMembership,
)
from app.services import campaign_service


async def _set(db, key, value):
    row = (await db.execute(
        select(TaxConfig).where(TaxConfig.key == key)
    )).scalar_one_or_none()
    if row is None:
        db.add(TaxConfig(key=key, value=json.dumps(value)))
    else:
        row.value = json.dumps(value)
    await db.commit()


async def _enable(db):
    await _set(db, "campaigns.enabled", True)


async def _user_with(
    db, *, uid, marketing=False, whatsapp=False,
):
    u = User(id=uid, email=f"{uid}@x.com", hashed_password="x",
             name="U", role=UserRole.STUDENT)
    db.add(u)
    db.add(UserConsentPreferences(
        user_id=uid,
        allow_analytics_tracking=True,
        allow_marketing_notifications=marketing,
        allow_whatsapp_updates=whatsapp,
    ))
    await db.commit()
    return u


async def _segment_with_members(db, *, member_user_ids: list[str]) -> UserSegment:
    seg = UserSegment(
        slug=f"seg-{member_user_ids[0]}",
        name="Test segment",
        rule_type=SegmentRuleType.HIGH_INTENT,
        rule_config_json="{}",
        is_active=True,
    )
    db.add(seg)
    await db.flush()
    for uid in member_user_ids:
        db.add(UserSegmentMembership(
            user_id=uid, segment_id=seg.id,
            is_active=True, score=10.0, reason="seed",
        ))
    await db.commit()
    return seg


async def _campaign(
    db, *, segment_id, slug="c1", channel=CampaignChannel.IN_APP,
    cooldown_hours=24, frequency_cap=3, frequency_window=7,
    status=CampaignStatus.ACTIVE,
    starts=None, ends=None,
) -> Campaign:
    c = Campaign(
        slug=slug, name=slug, body_template="hi",
        segment_id=segment_id, channel=channel,
        status=status,
        cooldown_hours=cooldown_hours,
        frequency_cap_per_user=frequency_cap,
        frequency_cap_window_days=frequency_window,
        send_window_starts=starts, send_window_ends=ends,
    )
    db.add(c)
    await db.commit()
    return c


# ---------- master flag --------------------------------------------------

@pytest.mark.asyncio
async def test_enqueue_master_flag_off(seeded_db):
    await _set(seeded_db, "campaigns.enabled", False)
    user = await _user_with(seeded_db, uid="u-1", marketing=True)
    seg = await _segment_with_members(seeded_db, member_user_ids=[user.id])
    camp = await _campaign(seeded_db, segment_id=seg.id)

    summary = await campaign_service.enqueue_eligible(
        seeded_db, campaign_id=camp.id,
    )
    assert summary.queued == 0
    assert "OFF" in summary.reasons[0]
    rows = (await seeded_db.execute(select(CampaignDelivery))).scalars().all()
    assert rows == []


# ---------- consent gate per channel -------------------------------------

@pytest.mark.asyncio
async def test_enqueue_skips_user_without_marketing_consent(seeded_db):
    await _enable(seeded_db)
    user = await _user_with(seeded_db, uid="u-no", marketing=False)
    seg = await _segment_with_members(seeded_db, member_user_ids=[user.id])
    camp = await _campaign(seeded_db, segment_id=seg.id,
                           channel=CampaignChannel.IN_APP)

    summary = await campaign_service.enqueue_eligible(
        seeded_db, campaign_id=camp.id,
    )
    assert summary.queued == 0
    assert summary.skipped_consent == 1

    row = (await seeded_db.execute(
        select(CampaignDelivery).where(CampaignDelivery.user_id == user.id)
    )).scalar_one()
    assert row.status == DeliveryStatus.SKIPPED_CONSENT


@pytest.mark.asyncio
async def test_whatsapp_uses_separate_consent_flag(seeded_db):
    """A user who allowed marketing but NOT WhatsApp must be skipped
    on a WHATSAPP campaign."""
    await _enable(seeded_db)
    user = await _user_with(seeded_db, uid="u-no-wa",
                            marketing=True, whatsapp=False)
    seg = await _segment_with_members(seeded_db, member_user_ids=[user.id])
    camp = await _campaign(seeded_db, segment_id=seg.id,
                           channel=CampaignChannel.WHATSAPP)

    summary = await campaign_service.enqueue_eligible(
        seeded_db, campaign_id=camp.id,
    )
    assert summary.skipped_consent == 1
    assert summary.queued == 0


@pytest.mark.asyncio
async def test_whatsapp_campaign_allowed_with_whatsapp_consent(seeded_db):
    await _enable(seeded_db)
    user = await _user_with(seeded_db, uid="u-wa",
                            marketing=False, whatsapp=True)
    seg = await _segment_with_members(seeded_db, member_user_ids=[user.id])
    camp = await _campaign(seeded_db, segment_id=seg.id,
                           channel=CampaignChannel.WHATSAPP)

    summary = await campaign_service.enqueue_eligible(
        seeded_db, campaign_id=camp.id,
    )
    assert summary.queued == 1


# ---------- cooldown ----------------------------------------------------

@pytest.mark.asyncio
async def test_cooldown_skips_repeat_within_window(seeded_db):
    await _enable(seeded_db)
    user = await _user_with(seeded_db, uid="u-cd", marketing=True)
    seg = await _segment_with_members(seeded_db, member_user_ids=[user.id])
    camp = await _campaign(seeded_db, segment_id=seg.id, cooldown_hours=24)

    # First enqueue → 1 queued
    s1 = await campaign_service.enqueue_eligible(
        seeded_db, campaign_id=camp.id,
    )
    assert s1.queued == 1

    # Immediate re-enqueue → in cooldown → skipped
    s2 = await campaign_service.enqueue_eligible(
        seeded_db, campaign_id=camp.id,
    )
    assert s2.queued == 0
    assert s2.skipped_cooldown == 1

    rows = (await seeded_db.execute(
        select(CampaignDelivery).where(CampaignDelivery.user_id == user.id)
    )).scalars().all()
    statuses = sorted(r.status.value for r in rows)
    assert statuses == ["QUEUED", "SKIPPED_COOLDOWN"]


@pytest.mark.asyncio
async def test_cooldown_zero_means_no_cooldown(seeded_db):
    await _enable(seeded_db)
    user = await _user_with(seeded_db, uid="u-cd0", marketing=True)
    seg = await _segment_with_members(seeded_db, member_user_ids=[user.id])
    camp = await _campaign(seeded_db, segment_id=seg.id,
                           cooldown_hours=0, frequency_cap=0)

    s1 = await campaign_service.enqueue_eligible(seeded_db, campaign_id=camp.id)
    s2 = await campaign_service.enqueue_eligible(seeded_db, campaign_id=camp.id)
    assert s1.queued == 1
    assert s2.queued == 1


# ---------- frequency cap (cross-campaign) ------------------------------

@pytest.mark.asyncio
async def test_frequency_cap_counts_across_campaigns(seeded_db):
    await _enable(seeded_db)
    user = await _user_with(seeded_db, uid="u-fc", marketing=True)
    seg = await _segment_with_members(seeded_db, member_user_ids=[user.id])

    # Three different campaigns, cap=2 across the 7d window
    c1 = await _campaign(seeded_db, segment_id=seg.id, slug="c1",
                         cooldown_hours=0, frequency_cap=2)
    c2 = await _campaign(seeded_db, segment_id=seg.id, slug="c2",
                         cooldown_hours=0, frequency_cap=2)
    c3 = await _campaign(seeded_db, segment_id=seg.id, slug="c3",
                         cooldown_hours=0, frequency_cap=2)

    s1 = await campaign_service.enqueue_eligible(seeded_db, campaign_id=c1.id)
    s2 = await campaign_service.enqueue_eligible(seeded_db, campaign_id=c2.id)
    s3 = await campaign_service.enqueue_eligible(seeded_db, campaign_id=c3.id)

    assert s1.queued == 1
    assert s2.queued == 1     # 2nd hit; still within cap
    assert s3.queued == 0     # 3rd hit; cap exceeded
    assert s3.skipped_frequency == 1


# ---------- campaign not ACTIVE -----------------------------------------

@pytest.mark.asyncio
async def test_draft_campaign_yields_nothing(seeded_db):
    await _enable(seeded_db)
    user = await _user_with(seeded_db, uid="u-draft", marketing=True)
    seg = await _segment_with_members(seeded_db, member_user_ids=[user.id])
    camp = await _campaign(seeded_db, segment_id=seg.id,
                           status=CampaignStatus.DRAFT)

    summary = await campaign_service.enqueue_eligible(
        seeded_db, campaign_id=camp.id,
    )
    assert summary.queued == 0
    assert "DRAFT" in summary.reasons[0]


# ---------- send window -------------------------------------------------

@pytest.mark.asyncio
async def test_future_send_window_yields_nothing(seeded_db):
    await _enable(seeded_db)
    user = await _user_with(seeded_db, uid="u-future", marketing=True)
    seg = await _segment_with_members(seeded_db, member_user_ids=[user.id])
    starts = datetime.utcnow() + timedelta(days=1)
    camp = await _campaign(seeded_db, segment_id=seg.id, starts=starts)

    summary = await campaign_service.enqueue_eligible(
        seeded_db, campaign_id=camp.id,
    )
    assert summary.queued == 0
    assert "not yet open" in summary.reasons[0]


# ---------- engagement marking ------------------------------------------

@pytest.mark.asyncio
async def test_mark_delivered_only_from_queued(seeded_db):
    await _enable(seeded_db)
    user = await _user_with(seeded_db, uid="u-mk", marketing=True)
    seg = await _segment_with_members(seeded_db, member_user_ids=[user.id])
    camp = await _campaign(seeded_db, segment_id=seg.id)
    await campaign_service.enqueue_eligible(seeded_db, campaign_id=camp.id)
    deliv = (await seeded_db.execute(select(CampaignDelivery))).scalar_one()

    out = await campaign_service.mark_delivered(
        seeded_db, delivery_id=deliv.id,
    )
    assert out.status == DeliveryStatus.DELIVERED
    assert out.delivered_at is not None

    # Calling again is a no-op (status is DELIVERED not QUEUED)
    out = await campaign_service.mark_delivered(
        seeded_db, delivery_id=deliv.id,
    )
    assert out.status == DeliveryStatus.DELIVERED


@pytest.mark.asyncio
async def test_mark_delivered_with_error_marks_failed(seeded_db):
    await _enable(seeded_db)
    user = await _user_with(seeded_db, uid="u-fail", marketing=True)
    seg = await _segment_with_members(seeded_db, member_user_ids=[user.id])
    camp = await _campaign(seeded_db, segment_id=seg.id)
    await campaign_service.enqueue_eligible(seeded_db, campaign_id=camp.id)
    deliv = (await seeded_db.execute(select(CampaignDelivery))).scalar_one()

    await campaign_service.mark_delivered(
        seeded_db, delivery_id=deliv.id, error="SMTP refused",
    )
    await seeded_db.refresh(deliv)
    assert deliv.status == DeliveryStatus.FAILED
    assert "SMTP" in (deliv.reason or "")


@pytest.mark.asyncio
async def test_click_implies_open_when_open_not_recorded(seeded_db):
    await _enable(seeded_db)
    user = await _user_with(seeded_db, uid="u-click", marketing=True)
    seg = await _segment_with_members(seeded_db, member_user_ids=[user.id])
    camp = await _campaign(seeded_db, segment_id=seg.id)
    await campaign_service.enqueue_eligible(seeded_db, campaign_id=camp.id)
    deliv = (await seeded_db.execute(select(CampaignDelivery))).scalar_one()

    await campaign_service.mark_clicked(seeded_db, delivery_id=deliv.id)
    await seeded_db.refresh(deliv)
    assert deliv.clicked_at is not None
    assert deliv.opened_at is not None


# ---------- attribution -------------------------------------------------

@pytest.mark.asyncio
async def test_attribute_booking_picks_most_recent_click(seeded_db):
    await _enable(seeded_db)
    user = await _user_with(seeded_db, uid="u-att", marketing=True)
    seg = await _segment_with_members(seeded_db, member_user_ids=[user.id])

    # Two campaigns the user has clicked. Most recent should win.
    c_old = await _campaign(seeded_db, segment_id=seg.id, slug="c-old",
                            cooldown_hours=0, frequency_cap=0)
    c_new = await _campaign(seeded_db, segment_id=seg.id, slug="c-new",
                            cooldown_hours=0, frequency_cap=0)

    # Insert deliveries manually with explicit clicked_at timestamps
    d_old = CampaignDelivery(
        campaign_id=c_old.id, user_id=user.id, channel=CampaignChannel.IN_APP,
        status=DeliveryStatus.DELIVERED,
        delivered_at=datetime.utcnow() - timedelta(days=3),
        clicked_at=datetime.utcnow() - timedelta(days=3),
    )
    d_new = CampaignDelivery(
        campaign_id=c_new.id, user_id=user.id, channel=CampaignChannel.IN_APP,
        status=DeliveryStatus.DELIVERED,
        delivered_at=datetime.utcnow() - timedelta(hours=1),
        clicked_at=datetime.utcnow() - timedelta(hours=1),
    )
    seeded_db.add_all([d_old, d_new])
    await seeded_db.commit()

    out = await campaign_service.attribute_booking(
        seeded_db, booking_id="bk-1", user_id=user.id,
    )
    await seeded_db.commit()
    assert out is not None
    assert out.id == d_new.id
    await seeded_db.refresh(d_old)
    await seeded_db.refresh(d_new)
    assert d_new.converted_booking_id == "bk-1"
    assert d_old.converted_booking_id is None


@pytest.mark.asyncio
async def test_attribute_booking_ignores_clicks_outside_window(seeded_db):
    """Set attribution window to 1 day; a 5-day-old click must be ignored."""
    await _enable(seeded_db)
    await _set(seeded_db, "campaigns.attribution_window_days", 1)
    user = await _user_with(seeded_db, uid="u-old-click", marketing=True)
    seg = await _segment_with_members(seeded_db, member_user_ids=[user.id])
    c = await _campaign(seeded_db, segment_id=seg.id)

    d = CampaignDelivery(
        campaign_id=c.id, user_id=user.id, channel=CampaignChannel.IN_APP,
        status=DeliveryStatus.DELIVERED,
        delivered_at=datetime.utcnow() - timedelta(days=5),
        clicked_at=datetime.utcnow() - timedelta(days=5),
    )
    seeded_db.add(d)
    await seeded_db.commit()

    out = await campaign_service.attribute_booking(
        seeded_db, booking_id="bk-2", user_id=user.id,
    )
    assert out is None
    await seeded_db.refresh(d)
    assert d.converted_booking_id is None


@pytest.mark.asyncio
async def test_attribute_booking_skips_already_attributed(seeded_db):
    """A delivery that already has a booking_id must not be reattributed
    to a different booking — first booking wins."""
    await _enable(seeded_db)
    user = await _user_with(seeded_db, uid="u-prior", marketing=True)
    seg = await _segment_with_members(seeded_db, member_user_ids=[user.id])
    c = await _campaign(seeded_db, segment_id=seg.id)

    d = CampaignDelivery(
        campaign_id=c.id, user_id=user.id, channel=CampaignChannel.IN_APP,
        status=DeliveryStatus.DELIVERED,
        delivered_at=datetime.utcnow() - timedelta(hours=1),
        clicked_at=datetime.utcnow() - timedelta(hours=1),
        converted_booking_id="bk-first",
        converted_at=datetime.utcnow() - timedelta(minutes=30),
    )
    seeded_db.add(d)
    await seeded_db.commit()

    out = await campaign_service.attribute_booking(
        seeded_db, booking_id="bk-second", user_id=user.id,
    )
    assert out is None      # no eligible click to attribute to
    await seeded_db.refresh(d)
    assert d.converted_booking_id == "bk-first"


@pytest.mark.asyncio
async def test_attribute_booking_noop_when_flag_off(seeded_db):
    await _set(seeded_db, "campaigns.enabled", False)
    out = await campaign_service.attribute_booking(
        seeded_db, booking_id="bk-x", user_id="anyone",
    )
    assert out is None


# ---------- funnel aggregator -------------------------------------------

@pytest.mark.asyncio
async def test_funnel_counts_funnel_widths_correctly(seeded_db):
    await _enable(seeded_db)
    seg = UserSegment(
        slug="seg-fnl", name="seg", rule_type=SegmentRuleType.HIGH_INTENT,
        rule_config_json="{}", is_active=True,
    )
    seeded_db.add(seg)
    await seeded_db.flush()
    c = await _campaign(seeded_db, segment_id=seg.id)
    # Synthesize a mix
    seeded_db.add_all([
        CampaignDelivery(
            campaign_id=c.id, user_id=f"u-{i}", channel=CampaignChannel.IN_APP,
            status=DeliveryStatus.DELIVERED,
            delivered_at=datetime.utcnow(),
            opened_at=(datetime.utcnow() if i < 4 else None),
            clicked_at=(datetime.utcnow() if i < 2 else None),
            converted_booking_id=("bk" if i == 0 else None),
        )
        for i in range(5)
    ])
    seeded_db.add(CampaignDelivery(
        campaign_id=c.id, user_id="u-cd", channel=CampaignChannel.IN_APP,
        status=DeliveryStatus.SKIPPED_COOLDOWN,
        reason="cd",
    ))
    seeded_db.add(CampaignDelivery(
        campaign_id=c.id, user_id="u-co", channel=CampaignChannel.IN_APP,
        status=DeliveryStatus.SKIPPED_CONSENT,
        reason="co",
    ))
    await seeded_db.commit()

    f = await campaign_service.funnel_for_campaign(
        seeded_db, campaign_id=c.id,
    )
    assert f.delivered == 5
    assert f.opened == 4
    assert f.clicked == 2
    assert f.converted == 1
    assert f.skipped_cooldown == 1
    assert f.skipped_consent == 1
