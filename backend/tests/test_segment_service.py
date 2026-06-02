"""Segment service tests.

Covers:
  - All 7 predicates against representative inputs
  - Master flag gates recompute
  - Consent gate (users without allow_personalized_recommendations skipped)
  - Membership lifecycle: enter, refresh, exit (history preserved)
  - Idempotent re-evaluation
  - segments_for_user transparency surface
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.models.tax_config import TaxConfig
from app.models.user import User, UserRole
from app.models.user_consent_preferences import UserConsentPreferences
from app.models.user_event import EventCategory, UserEvent
from app.models.user_intelligence_profile import (
    IntentLevel, UserIntelligenceProfile,
)
from app.models.user_segment import (
    SegmentRuleType, UserSegment, UserSegmentMembership,
)
from app.services import segment_service


async def _set(db, key, value):
    row = (await db.execute(
        select(TaxConfig).where(TaxConfig.key == key)
    )).scalar_one_or_none()
    if row is None:
        db.add(TaxConfig(key=key, value=json.dumps(value)))
    else:
        row.value = json.dumps(value)
    await db.commit()


async def _user(db, uid="u-seg", consent=True) -> User:
    u = User(id=uid, email=f"{uid}@x.com", hashed_password="x",
             name="U", role=UserRole.STUDENT)
    db.add(u)
    if consent:
        db.add(UserConsentPreferences(
            user_id=uid,
            allow_analytics_tracking=True,
            allow_personalized_recommendations=True,
        ))
    await db.commit()
    return u


def _profile(*, uid, intent=IntentLevel.MEDIUM_INTENT, raw=10,
             city=None, price_max=None, amenities=None):
    return UserIntelligenceProfile(
        user_id=uid,
        preferred_city=city,
        preferred_price_max=price_max,
        preferred_amenities_json=(
            json.dumps(amenities) if amenities is not None else None
        ),
        intent_level=intent,
        raw_intent_score=raw,
        event_count=5,
    )


# ============== predicate dispatch tests ==============

def test_dispatch_high_intent_matches_hot_lead():
    profile = SimpleNamespace(
        intent_level=IntentLevel.HOT_LEAD,
        raw_intent_score=50,
    )
    result = segment_service.evaluate(
        SegmentRuleType.HIGH_INTENT,
        profile=profile, recent_events=[], rule_config={},
    )
    assert result.matches is True
    assert "HOT_LEAD" in result.reason


def test_dispatch_high_intent_skips_low():
    profile = SimpleNamespace(
        intent_level=IntentLevel.LOW_INTENT,
        raw_intent_score=2,
    )
    result = segment_service.evaluate(
        SegmentRuleType.HIGH_INTENT,
        profile=profile, recent_events=[], rule_config={},
    )
    assert result.matches is False


def test_budget_band_below_threshold_matches():
    profile = SimpleNamespace(preferred_price_max=2500.0)
    result = segment_service.evaluate(
        SegmentRuleType.BUDGET_BAND,
        profile=profile, recent_events=[],
        rule_config={"max_price": 3000},
    )
    assert result.matches is True


def test_budget_band_no_config_no_match():
    profile = SimpleNamespace(preferred_price_max=2500.0)
    result = segment_service.evaluate(
        SegmentRuleType.BUDGET_BAND,
        profile=profile, recent_events=[], rule_config={},
    )
    assert result.matches is False


def test_city_interest_case_insensitive():
    profile = SimpleNamespace(preferred_city="Kochi", event_count=10)
    result = segment_service.evaluate(
        SegmentRuleType.CITY_INTEREST,
        profile=profile, recent_events=[],
        rule_config={"city": "kochi"},
    )
    assert result.matches is True


def test_amenity_interest_matches_when_in_list():
    profile = SimpleNamespace(
        preferred_amenities_json=json.dumps(["AC", "wifi"]),
    )
    result = segment_service.evaluate(
        SegmentRuleType.AMENITY_INTEREST,
        profile=profile, recent_events=[],
        rule_config={"amenity": "AC"},
    )
    assert result.matches is True


def test_payment_abandoned_matches_on_event():
    events = [
        SimpleNamespace(event_name="payment.failed",
                        event_category=EventCategory.PAYMENT),
    ]
    result = segment_service.evaluate(
        SegmentRuleType.PAYMENT_ABANDONED,
        profile=None, recent_events=events, rule_config={},
    )
    assert result.matches is True


def test_repeat_search_no_booking_uses_min_count():
    events = [
        SimpleNamespace(event_name="search.location",
                        event_category=EventCategory.SEARCH)
        for _ in range(3)
    ]
    result = segment_service.evaluate(
        SegmentRuleType.REPEAT_SEARCH_NO_BOOKING,
        profile=None, recent_events=events,
        rule_config={"min_searches": 3},
    )
    assert result.matches is True


def test_repeat_search_excluded_if_booking_completed():
    events = [
        SimpleNamespace(event_name="search", event_category=EventCategory.SEARCH),
        SimpleNamespace(event_name="search", event_category=EventCategory.SEARCH),
        SimpleNamespace(event_name="search", event_category=EventCategory.SEARCH),
        SimpleNamespace(event_name="booking.completed",
                        event_category=EventCategory.BOOKING),
    ]
    result = segment_service.evaluate(
        SegmentRuleType.REPEAT_SEARCH_NO_BOOKING,
        profile=None, recent_events=events,
        rule_config={"min_searches": 3},
    )
    assert result.matches is False


def test_cancelled_users_matches_on_event():
    events = [
        SimpleNamespace(event_name="booking.cancelled",
                        event_category=EventCategory.CANCELLATION),
    ]
    result = segment_service.evaluate(
        SegmentRuleType.CANCELLED_USERS,
        profile=None, recent_events=events, rule_config={},
    )
    assert result.matches is True


# ============== recompute master flag ==============

@pytest.mark.asyncio
async def test_recompute_skipped_when_flag_off(seeded_db):
    await _set(seeded_db, "segments.enabled", False)
    user = await _user(seeded_db)
    seeded_db.add(_profile(uid=user.id, intent=IntentLevel.HOT_LEAD, raw=50))
    seeded_db.add(UserSegment(
        slug="hot",
        name="Hot leads",
        rule_type=SegmentRuleType.HIGH_INTENT,
        rule_config_json="{}",
        is_active=True,
    ))
    await seeded_db.commit()

    summary = await segment_service.recompute_all_active_segments(seeded_db)
    assert summary.segments_evaluated == 0
    assert "OFF" in summary.skipped[0]
    members = (await seeded_db.execute(
        select(UserSegmentMembership)
    )).scalars().all()
    assert members == []


# ============== consent gate ==============

@pytest.mark.asyncio
async def test_users_without_personalization_consent_skipped(seeded_db):
    await _set(seeded_db, "segments.enabled", True)
    user = await _user(seeded_db, consent=False)    # no consent
    seeded_db.add(_profile(uid=user.id, intent=IntentLevel.HOT_LEAD, raw=50))
    seg = UserSegment(
        slug="hot",
        name="Hot leads",
        rule_type=SegmentRuleType.HIGH_INTENT,
        rule_config_json="{}",
        is_active=True,
    )
    seeded_db.add(seg)
    await seeded_db.commit()

    summary = await segment_service.recompute_all_active_segments(seeded_db)
    assert summary.segments_evaluated == 1
    assert summary.memberships_entered == 0   # consent gate blocked


# ============== membership lifecycle ==============

@pytest.mark.asyncio
async def test_user_enters_segment_when_match(seeded_db):
    await _set(seeded_db, "segments.enabled", True)
    user = await _user(seeded_db)
    seeded_db.add(_profile(uid=user.id, intent=IntentLevel.HOT_LEAD, raw=50))
    seg = UserSegment(
        slug="hot",
        name="Hot leads",
        rule_type=SegmentRuleType.HIGH_INTENT,
        rule_config_json="{}",
        is_active=True,
    )
    seeded_db.add(seg)
    await seeded_db.commit()

    summary = await segment_service.recompute_all_active_segments(seeded_db)
    assert summary.memberships_entered == 1

    rows = (await seeded_db.execute(
        select(UserSegmentMembership)
    )).scalars().all()
    assert len(rows) == 1
    assert rows[0].is_active is True
    assert rows[0].user_id == user.id
    assert "HOT_LEAD" in (rows[0].reason or "")


@pytest.mark.asyncio
async def test_recompute_is_idempotent(seeded_db):
    """Re-running with the same data produces the same single membership row."""
    await _set(seeded_db, "segments.enabled", True)
    user = await _user(seeded_db)
    seeded_db.add(_profile(uid=user.id, intent=IntentLevel.HOT_LEAD, raw=50))
    seg = UserSegment(
        slug="hot",
        name="Hot leads",
        rule_type=SegmentRuleType.HIGH_INTENT,
        rule_config_json="{}",
        is_active=True,
    )
    seeded_db.add(seg)
    await seeded_db.commit()

    s1 = await segment_service.recompute_all_active_segments(seeded_db)
    s2 = await segment_service.recompute_all_active_segments(seeded_db)

    assert s1.memberships_entered == 1
    assert s2.memberships_entered == 0

    rows = (await seeded_db.execute(
        select(UserSegmentMembership)
    )).scalars().all()
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_user_exits_when_no_longer_matches(seeded_db):
    """When a user stops matching, the existing row is marked inactive
    (exited_at stamped) — history preserved, not deleted."""
    await _set(seeded_db, "segments.enabled", True)
    user = await _user(seeded_db)
    seeded_db.add(_profile(uid=user.id, intent=IntentLevel.HOT_LEAD, raw=50))
    seg = UserSegment(
        slug="hot",
        name="Hot leads",
        rule_type=SegmentRuleType.HIGH_INTENT,
        rule_config_json="{}",
        is_active=True,
    )
    seeded_db.add(seg)
    await seeded_db.commit()

    await segment_service.recompute_all_active_segments(seeded_db)

    # Flip user to LOW_INTENT
    profile = await seeded_db.get(UserIntelligenceProfile, user.id)
    profile.intent_level = IntentLevel.LOW_INTENT
    await seeded_db.commit()

    summary = await segment_service.recompute_all_active_segments(seeded_db)
    assert summary.memberships_exited == 1

    rows = (await seeded_db.execute(
        select(UserSegmentMembership)
    )).scalars().all()
    assert len(rows) == 1     # history preserved
    assert rows[0].is_active is False
    assert rows[0].exited_at is not None


@pytest.mark.asyncio
async def test_recompute_updates_score_on_existing_member(seeded_db):
    """A still-matching user gets score/reason refreshed without a new row."""
    await _set(seeded_db, "segments.enabled", True)
    user = await _user(seeded_db)
    seeded_db.add(_profile(uid=user.id, intent=IntentLevel.HOT_LEAD, raw=50))
    seg = UserSegment(
        slug="hot",
        name="Hot leads",
        rule_type=SegmentRuleType.HIGH_INTENT,
        rule_config_json="{}",
        is_active=True,
    )
    seeded_db.add(seg)
    await seeded_db.commit()

    await segment_service.recompute_all_active_segments(seeded_db)
    membership = (await seeded_db.execute(
        select(UserSegmentMembership)
    )).scalar_one()
    first_score = membership.score
    first_entered = membership.entered_at

    # Profile gets even hotter
    profile = await seeded_db.get(UserIntelligenceProfile, user.id)
    profile.raw_intent_score = 200
    await seeded_db.commit()

    await segment_service.recompute_all_active_segments(seeded_db)
    membership = (await seeded_db.execute(
        select(UserSegmentMembership)
    )).scalar_one()
    assert membership.score > first_score
    # entered_at didn't change — same membership row
    assert membership.entered_at == first_entered


# ============== inactive segment skipped ==============

@pytest.mark.asyncio
async def test_inactive_segments_skipped(seeded_db):
    await _set(seeded_db, "segments.enabled", True)
    user = await _user(seeded_db)
    seeded_db.add(_profile(uid=user.id, intent=IntentLevel.HOT_LEAD, raw=50))
    seeded_db.add(UserSegment(
        slug="hot-disabled",
        name="Disabled",
        rule_type=SegmentRuleType.HIGH_INTENT,
        rule_config_json="{}",
        is_active=False,    # disabled
    ))
    await seeded_db.commit()

    summary = await segment_service.recompute_all_active_segments(seeded_db)
    assert summary.segments_evaluated == 0
    assert summary.memberships_entered == 0


# ============== transparency surface ==============

@pytest.mark.asyncio
async def test_segments_for_user_returns_active_only(seeded_db):
    await _set(seeded_db, "segments.enabled", True)
    user = await _user(seeded_db)
    seeded_db.add(_profile(uid=user.id, intent=IntentLevel.HOT_LEAD, raw=50))
    seg = UserSegment(
        slug="hot",
        name="Hot leads",
        rule_type=SegmentRuleType.HIGH_INTENT,
        rule_config_json="{}",
        is_active=True,
    )
    seeded_db.add(seg)
    await seeded_db.commit()

    await segment_service.recompute_all_active_segments(seeded_db)
    pairs = await segment_service.segments_for_user(
        seeded_db, user_id=user.id,
    )
    assert len(pairs) == 1
    assert pairs[0][0].slug == "hot"

    # After user exits, transparency surface returns []
    profile = await seeded_db.get(UserIntelligenceProfile, user.id)
    profile.intent_level = IntentLevel.LOW_INTENT
    await seeded_db.commit()
    await segment_service.recompute_all_active_segments(seeded_db)
    pairs = await segment_service.segments_for_user(
        seeded_db, user_id=user.id,
    )
    assert pairs == []
