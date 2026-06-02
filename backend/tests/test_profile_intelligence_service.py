"""Profile aggregation tests.

Contracts:
  - Master flag OFF -> service is a no-op
  - User without `allow_personalized_recommendations` -> skipped
  - User with no events in window -> skipped (no row created)
  - Repeated SEARCH on the same location -> preferred_city + preferred_locations set
  - VIEW events drive preferred_property_types
  - FILTER metadata drives preferred_amenities + price range
  - Intent score persists on the row
  - Re-running for the same events produces the same output (idempotent)
  - rebuild_all_active_profiles only scans recent activity
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

from app.models.tax_config import TaxConfig
from app.models.user import User, UserRole
from app.models.user_consent_preferences import UserConsentPreferences
from app.models.user_event import EventCategory, EventEntityType, UserEvent
from app.models.user_intelligence_profile import IntentLevel, UserIntelligenceProfile
from app.services import profile_intelligence_service


async def _set(db, key, value):
    row = (await db.execute(
        select(TaxConfig).where(TaxConfig.key == key)
    )).scalar_one_or_none()
    if row is None:
        db.add(TaxConfig(key=key, value=json.dumps(value)))
    else:
        row.value = json.dumps(value)
    await db.commit()


async def _enable_phase2(db):
    await _set(db, "events.enabled", True)
    await _set(db, "intelligence.profile_aggregation_enabled", True)


async def _consenting_user(db, *, uid="u-ip", consent=True) -> User:
    u = User(id=uid, email=f"{uid}@x.com", hashed_password="x",
             name="U", role=UserRole.STUDENT)
    db.add(u)
    await db.flush()
    if consent:
        db.add(UserConsentPreferences(
            user_id=uid,
            allow_analytics_tracking=True,
            allow_personalized_recommendations=True,
        ))
    await db.commit()
    return u


def _add_event(db, *, user_id, name, category, entity_type=None,
               city=None, location_query=None, metadata=None, when=None):
    row = UserEvent(
        event_id=f"evt-{user_id}-{name}-{datetime.utcnow().timestamp()}-{id(metadata)}",
        user_id=user_id, event_name=name,
        event_category=category,
        entity_type=entity_type,
        city=city, location_query=location_query,
        metadata_json=json.dumps(metadata) if metadata else None,
        created_at=when or datetime.utcnow(),
    )
    db.add(row)
    return row


# ---------- master flag ---------------------------------------------------

@pytest.mark.asyncio
async def test_master_flag_off_skips_rebuild(seeded_db):
    await _set(seeded_db, "intelligence.profile_aggregation_enabled", False)
    user = await _consenting_user(seeded_db)

    result = await profile_intelligence_service.rebuild_profile_for_user(
        seeded_db, user_id=user.id,
    )
    await seeded_db.commit()
    assert result.persisted is False
    assert "OFF" in (result.reason or "")
    # No profile row created
    row = await seeded_db.get(UserIntelligenceProfile, user.id)
    assert row is None


# ---------- consent gate --------------------------------------------------

@pytest.mark.asyncio
async def test_user_without_personalization_consent_is_skipped(seeded_db):
    await _enable_phase2(seeded_db)
    user = await _consenting_user(seeded_db, consent=False)
    _add_event(seeded_db, user_id=user.id, name="search.location",
               category=EventCategory.SEARCH, city="Kochi",
               location_query="Kaloor")
    await seeded_db.commit()

    result = await profile_intelligence_service.rebuild_profile_for_user(
        seeded_db, user_id=user.id,
    )
    await seeded_db.commit()
    assert result.persisted is False
    assert "consent" in (result.reason or "").lower() or "opted" in (result.reason or "").lower()
    row = await seeded_db.get(UserIntelligenceProfile, user.id)
    assert row is None


# ---------- empty stream --------------------------------------------------

@pytest.mark.asyncio
async def test_no_events_in_window_returns_no_row(seeded_db):
    await _enable_phase2(seeded_db)
    user = await _consenting_user(seeded_db)
    result = await profile_intelligence_service.rebuild_profile_for_user(
        seeded_db, user_id=user.id,
    )
    assert result.persisted is False
    assert "no events" in (result.reason or "").lower()


# ---------- preference derivation -----------------------------------------

@pytest.mark.asyncio
async def test_preferred_city_and_locations_from_searches(seeded_db):
    await _enable_phase2(seeded_db)
    user = await _consenting_user(seeded_db)
    for _ in range(3):
        _add_event(seeded_db, user_id=user.id, name="search.location",
                   category=EventCategory.SEARCH,
                   city="Kochi", location_query="Kaloor")
    _add_event(seeded_db, user_id=user.id, name="search.location",
               category=EventCategory.SEARCH,
               city="Kochi", location_query="Edappally")
    await seeded_db.commit()

    result = await profile_intelligence_service.rebuild_profile_for_user(
        seeded_db, user_id=user.id,
    )
    await seeded_db.commit()
    assert result.persisted is True

    row = await seeded_db.get(UserIntelligenceProfile, user.id)
    assert row.preferred_city == "Kochi"
    locs = json.loads(row.preferred_locations_json)
    assert "Kaloor" in locs       # most-searched first


@pytest.mark.asyncio
async def test_preferred_property_types_from_views(seeded_db):
    await _enable_phase2(seeded_db)
    user = await _consenting_user(seeded_db)
    for _ in range(3):
        _add_event(seeded_db, user_id=user.id, name="view.reading_room",
                   category=EventCategory.VIEW,
                   entity_type=EventEntityType.READING_ROOM)
    _add_event(seeded_db, user_id=user.id, name="view.accommodation",
               category=EventCategory.VIEW,
               entity_type=EventEntityType.ACCOMMODATION)
    await seeded_db.commit()

    await profile_intelligence_service.rebuild_profile_for_user(
        seeded_db, user_id=user.id,
    )
    await seeded_db.commit()

    row = await seeded_db.get(UserIntelligenceProfile, user.id)
    types = json.loads(row.preferred_property_types_json)
    assert types[0] == "reading_room"


@pytest.mark.asyncio
async def test_filter_metadata_drives_amenities_and_prices(seeded_db):
    await _enable_phase2(seeded_db)
    user = await _consenting_user(seeded_db)
    _add_event(seeded_db, user_id=user.id, name="filter.applied",
               category=EventCategory.FILTER,
               metadata={"amenities": ["AC", "wifi"], "price_max": 3000})
    _add_event(seeded_db, user_id=user.id, name="filter.applied",
               category=EventCategory.FILTER,
               metadata={"amenities": ["AC"], "price_max": 2500})
    await seeded_db.commit()

    await profile_intelligence_service.rebuild_profile_for_user(
        seeded_db, user_id=user.id,
    )
    await seeded_db.commit()

    row = await seeded_db.get(UserIntelligenceProfile, user.id)
    amenities = json.loads(row.preferred_amenities_json)
    assert "AC" in amenities
    assert row.preferred_price_max == 3000.0
    assert row.preferred_price_min == 2500.0


# ---------- intent persistence -------------------------------------------

@pytest.mark.asyncio
async def test_intent_level_persisted_from_events(seeded_db):
    await _enable_phase2(seeded_db)
    user = await _consenting_user(seeded_db)
    # Booking start should force HOT_LEAD regardless of score.
    _add_event(seeded_db, user_id=user.id, name="view",
               category=EventCategory.VIEW)
    _add_event(seeded_db, user_id=user.id, name="booking.start",
               category=EventCategory.BOOKING)
    await seeded_db.commit()

    await profile_intelligence_service.rebuild_profile_for_user(
        seeded_db, user_id=user.id,
    )
    await seeded_db.commit()
    row = await seeded_db.get(UserIntelligenceProfile, user.id)
    assert row.intent_level == IntentLevel.HOT_LEAD
    assert row.raw_intent_score > 0


@pytest.mark.asyncio
async def test_booking_completed_resets_intent_to_low(seeded_db):
    await _enable_phase2(seeded_db)
    user = await _consenting_user(seeded_db)
    _add_event(seeded_db, user_id=user.id, name="booking.start",
               category=EventCategory.BOOKING)
    _add_event(seeded_db, user_id=user.id, name="booking.completed",
               category=EventCategory.BOOKING)
    await seeded_db.commit()

    await profile_intelligence_service.rebuild_profile_for_user(
        seeded_db, user_id=user.id,
    )
    await seeded_db.commit()
    row = await seeded_db.get(UserIntelligenceProfile, user.id)
    assert row.intent_level == IntentLevel.LOW_INTENT
    assert row.last_successful_booking_at is not None


# ---------- idempotency --------------------------------------------------

@pytest.mark.asyncio
async def test_repeated_rebuild_is_idempotent(seeded_db):
    await _enable_phase2(seeded_db)
    user = await _consenting_user(seeded_db)
    for _ in range(3):
        _add_event(seeded_db, user_id=user.id, name="search.location",
                   category=EventCategory.SEARCH,
                   city="Kochi", location_query="Kaloor")
    await seeded_db.commit()

    await profile_intelligence_service.rebuild_profile_for_user(
        seeded_db, user_id=user.id,
    )
    await seeded_db.commit()
    row1 = await seeded_db.get(UserIntelligenceProfile, user.id)
    score1 = row1.raw_intent_score
    city1 = row1.preferred_city

    await profile_intelligence_service.rebuild_profile_for_user(
        seeded_db, user_id=user.id,
    )
    await seeded_db.commit()
    row2 = await seeded_db.get(UserIntelligenceProfile, user.id)
    assert row2.raw_intent_score == score1
    assert row2.preferred_city == city1

    # Exactly one row exists
    rows = (await seeded_db.execute(select(UserIntelligenceProfile))).scalars().all()
    assert len(rows) == 1


# ---------- rebuild_all_active_profiles ----------------------------------

@pytest.mark.asyncio
async def test_rebuild_all_only_processes_recent(seeded_db):
    """Users with activity outside the since_days window are skipped."""
    await _enable_phase2(seeded_db)
    recent_user = await _consenting_user(seeded_db, uid="u-recent")
    stale_user = await _consenting_user(seeded_db, uid="u-stale")

    _add_event(seeded_db, user_id=recent_user.id, name="search",
               category=EventCategory.SEARCH, city="Kochi")
    _add_event(seeded_db, user_id=stale_user.id, name="search",
               category=EventCategory.SEARCH, city="Kochi",
               when=datetime.utcnow() - timedelta(days=30))
    await seeded_db.commit()

    summary = await profile_intelligence_service.rebuild_all_active_profiles(
        seeded_db, since_days=1,
    )
    assert summary["scanned"] == 1
    assert summary["persisted"] == 1

    # Recent user got a profile; stale user did not.
    assert (await seeded_db.get(UserIntelligenceProfile, recent_user.id)) is not None
    assert (await seeded_db.get(UserIntelligenceProfile, stale_user.id)) is None


@pytest.mark.asyncio
async def test_rebuild_all_skips_when_flag_off(seeded_db):
    await _set(seeded_db, "intelligence.profile_aggregation_enabled", False)
    summary = await profile_intelligence_service.rebuild_all_active_profiles(
        seeded_db,
    )
    assert "skipped" in summary
