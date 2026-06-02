"""Owner insights + admin dashboard tests (Phase 5).

Covers:
  - Master flag off → service returns None
  - summary_for_owner aggregates impressions / views / saves / inquiries / bookings
  - k-anonymity: per-listing conversion rates suppressed below threshold
  - Owner sees only their own listings
  - admin_dashboard.build_dashboard funnel ordering
  - admin_dashboard.top_cities groups + orders by searches
  - admin_dashboard.segments returns active counts
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

from app.models.booking import Booking, BookingStatus
from app.models.campaign import (
    CampaignChannel, CampaignDelivery, DeliveryStatus,
)
from app.models.favorite import Favorite
from app.models.notification_rule import NotificationRule, TriggerType
from app.models.reading_room import Cabin, CabinStatus, ListingStatus, ReadingRoom
from app.models.recommendation_log import RecommendationLog, RecommendationSurface
from app.models.tax_config import TaxConfig
from app.models.user import User, UserRole
from app.models.user_event import EventCategory, UserEvent
from app.models.user_segment import (
    SegmentRuleType, UserSegment, UserSegmentMembership,
)
from app.services import admin_dashboard_service, owner_insights_service


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
    await _set(db, "insights.enabled", True)


async def _owner(db, *, uid=None):
    uid = uid or str(uuid.uuid4())
    db.add(User(
        id=uid, email=f"{uid[:8]}@x.com", hashed_password="x",
        name="Owner", role=UserRole.ADMIN,
    ))
    await db.commit()
    return uid


async def _student(db, *, uid=None):
    uid = uid or str(uuid.uuid4())
    db.add(User(
        id=uid, email=f"{uid[:8]}@x.com", hashed_password="x",
        name="Student", role=UserRole.STUDENT,
    ))
    await db.commit()
    return uid


async def _listing(db, *, owner_id, name="Test RR") -> str:
    row = ReadingRoom(
        owner_id=owner_id, name=name, address="addr",
        status=ListingStatus.LIVE,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row.id


async def _event(db, *, user_id, name, category, entity_id=None,
                  city=None, when=None):
    db.add(UserEvent(
        event_id=str(uuid.uuid4()),
        user_id=user_id, event_name=name,
        event_category=category, entity_id=entity_id,
        city=city, created_at=when or datetime.utcnow(),
    ))
    await db.commit()


# ---------- master flag ---------------------------------------------------

@pytest.mark.asyncio
async def test_owner_summary_master_flag_off(seeded_db):
    db = seeded_db
    owner_id = await _owner(db)
    await _listing(db, owner_id=owner_id)
    result = await owner_insights_service.summary_for_owner(
        db, owner_id=owner_id,
    )
    assert result is None


@pytest.mark.asyncio
async def test_admin_dashboard_master_flag_off(seeded_db):
    db = seeded_db
    result = await admin_dashboard_service.build_dashboard(db)
    assert result is None


# ---------- owner aggregation ---------------------------------------------

@pytest.mark.asyncio
async def test_owner_summary_aggregates_counts(seeded_db):
    db = seeded_db
    await _enable(db)
    owner_id = await _owner(db)
    listing_id = await _listing(db, owner_id=owner_id)

    # 8 distinct viewers, 10 views, 2 saves
    for i in range(8):
        viewer = await _student(db)
        await _event(db, user_id=viewer, name="reading_room.viewed",
                     category=EventCategory.VIEW, entity_id=listing_id)
        if i < 2:
            db.add(Favorite(
                user_id=viewer, reading_room_id=listing_id,
            ))
    # +2 extra views from existing users
    viewer_again = await _student(db)
    await _event(db, user_id=viewer_again, name="reading_room.viewed",
                 category=EventCategory.VIEW, entity_id=listing_id)
    await _event(db, user_id=viewer_again, name="reading_room.viewed",
                 category=EventCategory.VIEW, entity_id=listing_id)

    # 3 impressions, 1 click
    for i in range(3):
        db.add(RecommendationLog(
            id=str(uuid.uuid4()),
            user_id=await _student(db),
            listing_id=listing_id, listing_type="reading_room",
            surface=RecommendationSurface.FOR_YOU,
            rank=1, score=10.0,
            clicked_at=datetime.utcnow() if i == 0 else None,
        ))
    await db.commit()

    summary = await owner_insights_service.summary_for_owner(
        db, owner_id=owner_id,
    )
    assert summary is not None
    assert len(summary.listings) == 1
    li = summary.listings[0]
    assert li.listing_id == listing_id
    assert li.views == 10
    assert li.distinct_viewers == 9
    assert li.saves == 2
    assert li.impressions == 3
    assert li.clicks == 1
    # 9 distinct viewers >= k=5 → ratios exposed (no inquiries / bookings yet)
    assert li.view_to_inquiry_rate == 0.0
    assert li.view_to_booking_rate == 0.0
    assert li.low_volume_suppressed is False


@pytest.mark.asyncio
async def test_owner_summary_suppresses_low_volume_ratios(seeded_db):
    db = seeded_db
    await _enable(db)
    owner_id = await _owner(db)
    listing_id = await _listing(db, owner_id=owner_id)

    # Only 2 distinct viewers (below default k=5)
    for _ in range(2):
        viewer = await _student(db)
        await _event(db, user_id=viewer, name="reading_room.viewed",
                     category=EventCategory.VIEW, entity_id=listing_id)

    summary = await owner_insights_service.summary_for_owner(
        db, owner_id=owner_id,
    )
    li = summary.listings[0]
    assert li.distinct_viewers == 2
    assert li.view_to_inquiry_rate is None
    assert li.view_to_booking_rate is None
    assert li.low_volume_suppressed is True


@pytest.mark.asyncio
async def test_owner_summary_only_own_listings(seeded_db):
    db = seeded_db
    await _enable(db)
    me = await _owner(db)
    them = await _owner(db)
    mine = await _listing(db, owner_id=me, name="mine")
    theirs = await _listing(db, owner_id=them, name="theirs")

    summary = await owner_insights_service.summary_for_owner(
        db, owner_id=me,
    )
    listing_ids = {li.listing_id for li in summary.listings}
    assert mine in listing_ids
    assert theirs not in listing_ids


@pytest.mark.asyncio
async def test_owner_summary_counts_bookings_via_cabins(seeded_db):
    db = seeded_db
    await _enable(db)
    owner_id = await _owner(db)
    listing_id = await _listing(db, owner_id=owner_id)
    student_id = await _student(db)

    cabin = Cabin(
        reading_room_id=listing_id, number="A1", floor=1,
        status=CabinStatus.OCCUPIED, price=1000.0,
    )
    db.add(cabin)
    await db.commit()
    await db.refresh(cabin)

    booking = Booking(
        user_id=student_id, cabin_id=cabin.id,
        amount=1000.0, status=BookingStatus.ACTIVE,
        start_date=datetime.utcnow(),
        end_date=datetime.utcnow() + timedelta(days=30),
    )
    db.add(booking)
    await db.commit()

    summary = await owner_insights_service.summary_for_owner(
        db, owner_id=owner_id,
    )
    assert summary.listings[0].bookings == 1


# ---------- admin dashboard -----------------------------------------------

@pytest.mark.asyncio
async def test_admin_dashboard_funnel_order(seeded_db):
    db = seeded_db
    await _enable(db)
    student_id = await _student(db)
    await _event(db, user_id=student_id, name="search.performed",
                 category=EventCategory.SEARCH)
    await _event(db, user_id=student_id, name="room.viewed",
                 category=EventCategory.VIEW)

    result = await admin_dashboard_service.build_dashboard(db)
    assert result is not None
    names = [s.name for s in result.funnel]
    assert names == ["search", "view", "save", "contact", "book"]
    funnel = {s.name: s.count for s in result.funnel}
    assert funnel["search"] == 1
    assert funnel["view"] == 1


@pytest.mark.asyncio
async def test_admin_dashboard_top_cities_ordered_by_searches(seeded_db):
    db = seeded_db
    await _enable(db)
    u = await _student(db)
    for _ in range(3):
        await _event(db, user_id=u, name="search.performed",
                     category=EventCategory.SEARCH, city="Bangalore")
    await _event(db, user_id=u, name="search.performed",
                 category=EventCategory.SEARCH, city="Kochi")

    result = await admin_dashboard_service.build_dashboard(db)
    cities = [c.city for c in result.top_cities]
    assert cities[0] == "Bangalore"
    assert "Kochi" in cities


@pytest.mark.asyncio
async def test_admin_dashboard_segment_counts(seeded_db):
    db = seeded_db
    await _enable(db)
    u1 = await _student(db)
    u2 = await _student(db)
    seg = UserSegment(
        slug="hi", name="High intent",
        rule_type=SegmentRuleType.HIGH_INTENT,
        rule_config_json="{}", is_active=True,
    )
    db.add(seg)
    await db.flush()
    for uid in (u1, u2):
        db.add(UserSegmentMembership(
            user_id=uid, segment_id=seg.id, is_active=True,
            score=10.0, reason="seed",
        ))
    await db.commit()

    result = await admin_dashboard_service.build_dashboard(db)
    matched = [s for s in result.segments if s.slug == "hi"]
    assert matched and matched[0].active_members == 2


@pytest.mark.asyncio
async def test_admin_dashboard_automation_snapshot(seeded_db):
    db = seeded_db
    await _enable(db)
    rule = NotificationRule(
        slug="r1", name="r1", body_template="hi",
        trigger_type=TriggerType.BOOKING_ABANDONED,
        channel=CampaignChannel.IN_APP, is_active=True,
    )
    db.add(rule)
    await db.flush()
    student_id = await _student(db)
    db.add(CampaignDelivery(
        notification_rule_id=rule.id, user_id=student_id,
        channel=CampaignChannel.IN_APP,
        status=DeliveryStatus.DELIVERED,
        delivered_at=datetime.utcnow(),
    ))
    await db.commit()

    result = await admin_dashboard_service.build_dashboard(db)
    assert result.automation.active_rules == 1
    assert result.automation.delivered_total == 1
