"""Recommendation service tests — 4 surfaces + rules + privacy gates.

Hard rules tested:
  - Master flag OFF -> all surfaces return []
  - Listings with non-LIVE status are never surfaced
  - Listings with suspended-for-nonpayment maintenance are never surfaced
  - recommendation_excluded forces hard exclusion
  - Owner without VERIFIED/NOT_REQUIRED KYC blocks the listing
  - Admin recommendation_priority lifts a listing above un-prioritized ones
  - personalized_for_user requires allow_personalized_recommendations
  - recently_viewed_for_user requires allow_analytics_tracking
  - similar / trending don't require user consent
  - log_impressions writes one RecommendationLog row per served item
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

from app.models.accommodation import Accommodation, AccommodationType, Gender
from app.models.reading_room import (
    ListingStatus, MaintenanceStatus, ReadingRoom,
)
from app.models.recommendation_log import (
    RecommendationLog, RecommendationSurface,
)
from app.models.tax_config import TaxConfig
from app.models.user import KYCStatus, User, UserRole
from app.models.user_consent_preferences import UserConsentPreferences
from app.models.user_event import EventCategory, EventEntityType, UserEvent
from app.models.user_intelligence_profile import IntentLevel, UserIntelligenceProfile
from app.services import recommendation_service


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
    await _set(db, "recommendations.enabled", True)
    # is_analytics_allowed (used by recently_viewed) depends on the events
    # master flag, so we flip it on here too.
    await _set(db, "events.enabled", True)


async def _verified_owner(db, *, uid="o-rec") -> User:
    o = User(id=uid, email=f"{uid}@x.com", hashed_password="x",
             name="Owner", role=UserRole.ADMIN,
             kyc_status=KYCStatus.VERIFIED)
    db.add(o)
    await db.flush()
    return o


async def _unverified_owner(db, *, uid="o-bad") -> User:
    o = User(id=uid, email=f"{uid}@x.com", hashed_password="x",
             name="Owner", role=UserRole.ADMIN,
             kyc_status=KYCStatus.PENDING)
    db.add(o)
    await db.flush()
    return o


async def _student(db, *, uid="s-rec", consent_personalize=True,
                   consent_analytics=True) -> User:
    s = User(id=uid, email=f"{uid}@x.com", hashed_password="x",
             name="Student", role=UserRole.STUDENT)
    db.add(s)
    if consent_personalize or consent_analytics:
        db.add(UserConsentPreferences(
            user_id=uid,
            allow_analytics_tracking=consent_analytics,
            allow_personalized_recommendations=consent_personalize,
        ))
    await db.commit()
    return s


def _make_room(*, rid, owner_id, name="Acme", city="Kochi",
               locality="Kaloor", price=2500.0, status=ListingStatus.LIVE,
               maintenance=MaintenanceStatus.CURRENT,
               excluded=False, priority=None, gst_category="HOSTEL_PG"):
    return ReadingRoom(
        id=rid, owner_id=owner_id, name=name,
        address=f"{locality}, {city}",
        city=city, locality=locality, area=locality, state="KL",
        price_start=price,
        status=status,
        maintenance_status=maintenance,
        visibility_score=1.0,
        gst_category=gst_category,
        recommendation_priority=priority,
        recommendation_excluded=excluded,
    )


def _make_acc(*, aid, owner_id, name="PG", city="Kochi",
              price=2500.0, status=ListingStatus.LIVE,
              gst_category="HOSTEL_PG"):
    return Accommodation(
        id=aid, owner_id=owner_id, name=name,
        type=AccommodationType.PG, gender=Gender.UNISEX,
        address=f"-, {city}", price=price, sharing="single",
        city=city, state="KL",
        status=status, gst_category=gst_category,
        visibility_score=1.0,
        recommendation_excluded=False,
    )


# ---------- master flag ---------------------------------------------------

@pytest.mark.asyncio
async def test_master_flag_off_returns_empty(seeded_db):
    await _set(seeded_db, "recommendations.enabled", False)
    o = await _verified_owner(seeded_db)
    seeded_db.add(_make_room(rid="r1", owner_id=o.id))
    student = await _student(seeded_db)
    await seeded_db.commit()
    out = await recommendation_service.personalized_for_user(
        seeded_db, user_id=student.id,
    )
    assert out == []


# ---------- personalized_for_user ---------------------------------------

async def _seed_for_personalize(db):
    """Standard fixture: verified owner, 2 listings in Kochi, profile prefers Kochi/Kaloor."""
    await _enable(db)
    o = await _verified_owner(db)
    db.add_all([
        _make_room(rid="r-match", owner_id=o.id,
                   city="Kochi", locality="Kaloor", price=2500.0),
        _make_room(rid="r-other-city", owner_id=o.id,
                   city="Bengaluru", locality="MG", price=2500.0),
    ])
    student = await _student(db)
    db.add(UserIntelligenceProfile(
        user_id=student.id, preferred_city="Kochi",
        preferred_locations_json=json.dumps(["Kaloor"]),
        preferred_property_types_json=json.dumps(["reading_room"]),
        preferred_amenities_json=json.dumps([]),
        preferred_price_min=2000.0, preferred_price_max=3000.0,
        intent_level=IntentLevel.MEDIUM_INTENT,
        raw_intent_score=10,
    ))
    await db.commit()
    return student


@pytest.mark.asyncio
async def test_personalized_returns_matches(seeded_db):
    student = await _seed_for_personalize(seeded_db)
    out = await recommendation_service.personalized_for_user(
        seeded_db, user_id=student.id,
    )
    assert any(r.listing_id == "r-match" for r in out)
    # City-match listing ranks above the cross-city decoy
    assert out[0].listing_id == "r-match"
    assert "city_match" in out[0].reason_code or "location_match" in out[0].reason_code


@pytest.mark.asyncio
async def test_personalized_requires_consent(seeded_db):
    await _enable(seeded_db)
    o = await _verified_owner(seeded_db)
    seeded_db.add(_make_room(rid="r1", owner_id=o.id))
    student = await _student(seeded_db, consent_personalize=False)
    seeded_db.add(UserIntelligenceProfile(
        user_id=student.id, preferred_city="Kochi",
        intent_level=IntentLevel.MEDIUM_INTENT, raw_intent_score=5,
    ))
    await seeded_db.commit()
    out = await recommendation_service.personalized_for_user(
        seeded_db, user_id=student.id,
    )
    assert out == []


@pytest.mark.asyncio
async def test_personalized_returns_empty_when_no_profile(seeded_db):
    await _enable(seeded_db)
    student = await _student(seeded_db)
    out = await recommendation_service.personalized_for_user(
        seeded_db, user_id=student.id,
    )
    assert out == []


# ---------- hard rules ---------------------------------------------------

@pytest.mark.asyncio
async def test_excludes_non_live_listing(seeded_db):
    await _enable(seeded_db)
    o = await _verified_owner(seeded_db)
    seeded_db.add(_make_room(rid="r-draft", owner_id=o.id,
                             status=ListingStatus.DRAFT))
    seeded_db.add(_make_room(rid="r-live", owner_id=o.id))
    student = await _student(seeded_db)
    seeded_db.add(UserIntelligenceProfile(
        user_id=student.id, preferred_city="Kochi",
        intent_level=IntentLevel.MEDIUM_INTENT, raw_intent_score=5,
    ))
    await seeded_db.commit()

    out = await recommendation_service.personalized_for_user(
        seeded_db, user_id=student.id,
    )
    ids = {r.listing_id for r in out}
    assert "r-live" in ids
    assert "r-draft" not in ids


@pytest.mark.asyncio
async def test_excludes_suspended_for_nonpayment(seeded_db):
    await _enable(seeded_db)
    o = await _verified_owner(seeded_db)
    seeded_db.add(_make_room(
        rid="r-suspended", owner_id=o.id,
        maintenance=MaintenanceStatus.SUSPENDED_FOR_NONPAYMENT,
    ))
    student = await _student(seeded_db)
    seeded_db.add(UserIntelligenceProfile(
        user_id=student.id, preferred_city="Kochi",
        intent_level=IntentLevel.MEDIUM_INTENT, raw_intent_score=5,
    ))
    await seeded_db.commit()
    out = await recommendation_service.personalized_for_user(
        seeded_db, user_id=student.id,
    )
    assert out == []


@pytest.mark.asyncio
async def test_excludes_when_recommendation_excluded_flag_set(seeded_db):
    await _enable(seeded_db)
    o = await _verified_owner(seeded_db)
    seeded_db.add(_make_room(rid="r-banned", owner_id=o.id, excluded=True))
    student = await _student(seeded_db)
    seeded_db.add(UserIntelligenceProfile(
        user_id=student.id, preferred_city="Kochi",
        intent_level=IntentLevel.MEDIUM_INTENT, raw_intent_score=5,
    ))
    await seeded_db.commit()
    out = await recommendation_service.personalized_for_user(
        seeded_db, user_id=student.id,
    )
    assert out == []


@pytest.mark.asyncio
async def test_excludes_owner_with_pending_kyc(seeded_db):
    await _enable(seeded_db)
    bad = await _unverified_owner(seeded_db, uid="o-pending")
    good = await _verified_owner(seeded_db, uid="o-good")
    seeded_db.add(_make_room(rid="r-bad-kyc", owner_id=bad.id))
    seeded_db.add(_make_room(rid="r-good-kyc", owner_id=good.id))
    student = await _student(seeded_db)
    seeded_db.add(UserIntelligenceProfile(
        user_id=student.id, preferred_city="Kochi",
        intent_level=IntentLevel.MEDIUM_INTENT, raw_intent_score=5,
    ))
    await seeded_db.commit()
    out = await recommendation_service.personalized_for_user(
        seeded_db, user_id=student.id,
    )
    ids = {r.listing_id for r in out}
    assert "r-good-kyc" in ids
    assert "r-bad-kyc" not in ids


# ---------- admin priority boost ----------------------------------------

@pytest.mark.asyncio
async def test_admin_priority_lifts_listing_above_others(seeded_db):
    await _enable(seeded_db)
    o = await _verified_owner(seeded_db)
    # Without priority, both listings would score equally on city match
    seeded_db.add(_make_room(rid="r-normal", owner_id=o.id))
    seeded_db.add(_make_room(rid="r-priority", owner_id=o.id, priority=5))
    student = await _student(seeded_db)
    seeded_db.add(UserIntelligenceProfile(
        user_id=student.id, preferred_city="Kochi",
        intent_level=IntentLevel.MEDIUM_INTENT, raw_intent_score=5,
    ))
    await seeded_db.commit()
    out = await recommendation_service.personalized_for_user(
        seeded_db, user_id=student.id,
    )
    assert out[0].listing_id == "r-priority"


# ---------- similar_to_listing ------------------------------------------

@pytest.mark.asyncio
async def test_similar_no_consent_required(seeded_db):
    """similar is item-based; anonymous callers should get results."""
    await _enable(seeded_db)
    o = await _verified_owner(seeded_db)
    seeded_db.add(_make_room(rid="r-src", owner_id=o.id,
                             city="Kochi", price=2500.0,
                             gst_category="HOSTEL_PG"))
    seeded_db.add(_make_room(rid="r-other", owner_id=o.id,
                             city="Kochi", price=2400.0,
                             gst_category="HOSTEL_PG"))
    await seeded_db.commit()

    out = await recommendation_service.similar_to_listing(
        seeded_db, listing_type="reading_room", listing_id="r-src",
    )
    assert any(r.listing_id == "r-other" for r in out)
    # Source itself never appears in its own similar list
    assert not any(r.listing_id == "r-src" for r in out)


@pytest.mark.asyncio
async def test_similar_returns_empty_when_source_missing(seeded_db):
    await _enable(seeded_db)
    out = await recommendation_service.similar_to_listing(
        seeded_db, listing_type="reading_room", listing_id="nope",
    )
    assert out == []


# ---------- trending_in_city --------------------------------------------

@pytest.mark.asyncio
async def test_trending_aggregates_view_events(seeded_db):
    await _enable(seeded_db)
    o = await _verified_owner(seeded_db)
    seeded_db.add(_make_room(rid="r-hot", owner_id=o.id, city="Kochi"))
    seeded_db.add(_make_room(rid="r-cold", owner_id=o.id, city="Kochi"))
    await seeded_db.commit()

    for i in range(5):
        seeded_db.add(UserEvent(
            event_id=f"v-hot-{i}",
            anonymous_session_id="anon-1",
            event_name="view.reading_room",
            event_category=EventCategory.VIEW,
            entity_type=EventEntityType.READING_ROOM,
            entity_id="r-hot",
            city="Kochi",
        ))
    seeded_db.add(UserEvent(
        event_id="v-cold-0",
        anonymous_session_id="anon-1",
        event_name="view.reading_room",
        event_category=EventCategory.VIEW,
        entity_type=EventEntityType.READING_ROOM,
        entity_id="r-cold",
        city="Kochi",
    ))
    await seeded_db.commit()

    out = await recommendation_service.trending_in_city(
        seeded_db, city="Kochi",
    )
    assert out[0].listing_id == "r-hot"


# ---------- recently_viewed_for_user ------------------------------------

@pytest.mark.asyncio
async def test_recently_viewed_requires_analytics_consent(seeded_db):
    await _enable(seeded_db)
    o = await _verified_owner(seeded_db)
    seeded_db.add(_make_room(rid="r-rv", owner_id=o.id))
    student = await _student(seeded_db, consent_analytics=False,
                             consent_personalize=False)
    seeded_db.add(UserEvent(
        event_id="rv-1", user_id=student.id,
        event_name="view.reading_room",
        event_category=EventCategory.VIEW,
        entity_type=EventEntityType.READING_ROOM,
        entity_id="r-rv",
    ))
    await seeded_db.commit()

    out = await recommendation_service.recently_viewed_for_user(
        seeded_db, user_id=student.id,
    )
    assert out == []


@pytest.mark.asyncio
async def test_recently_viewed_dedupes_and_orders_by_recency(seeded_db):
    await _enable(seeded_db)
    o = await _verified_owner(seeded_db)
    seeded_db.add(_make_room(rid="r-a", owner_id=o.id))
    seeded_db.add(_make_room(rid="r-b", owner_id=o.id))
    student = await _student(seeded_db)

    # 3 views on r-a, then 1 view on r-b (most recent)
    base = datetime.utcnow() - timedelta(minutes=5)
    for i in range(3):
        seeded_db.add(UserEvent(
            event_id=f"rv-a-{i}", user_id=student.id,
            event_name="view.reading_room",
            event_category=EventCategory.VIEW,
            entity_type=EventEntityType.READING_ROOM,
            entity_id="r-a",
            created_at=base + timedelta(seconds=i),
        ))
    seeded_db.add(UserEvent(
        event_id="rv-b-0", user_id=student.id,
        event_name="view.reading_room",
        event_category=EventCategory.VIEW,
        entity_type=EventEntityType.READING_ROOM,
        entity_id="r-b",
        created_at=base + timedelta(minutes=10),
    ))
    await seeded_db.commit()

    out = await recommendation_service.recently_viewed_for_user(
        seeded_db, user_id=student.id,
    )
    ids = [r.listing_id for r in out]
    # Most recent first
    assert ids[0] == "r-b"
    # r-a only appears once despite 3 views
    assert ids.count("r-a") == 1


# ---------- log_impressions ---------------------------------------------

@pytest.mark.asyncio
async def test_log_impressions_writes_one_row_per_rec_when_enabled(seeded_db):
    await _enable(seeded_db)
    await _set(seeded_db, "recommendations.log_impressions", True)
    o = await _verified_owner(seeded_db)
    seeded_db.add(_make_room(rid="r-log-1", owner_id=o.id))
    seeded_db.add(_make_room(rid="r-log-2", owner_id=o.id))
    student = await _student(seeded_db)
    seeded_db.add(UserIntelligenceProfile(
        user_id=student.id, preferred_city="Kochi",
        intent_level=IntentLevel.MEDIUM_INTENT, raw_intent_score=5,
    ))
    await seeded_db.commit()

    recs = await recommendation_service.personalized_for_user(
        seeded_db, user_id=student.id,
    )
    assert len(recs) >= 1
    await recommendation_service.log_impressions(
        seeded_db, user_id=student.id, anonymous_session_id=None,
        surface=RecommendationSurface.FOR_YOU, recommendations=recs,
    )
    await seeded_db.commit()

    rows = (await seeded_db.execute(select(RecommendationLog))).scalars().all()
    assert len(rows) == len(recs)
    assert all(r.surface == RecommendationSurface.FOR_YOU for r in rows)


@pytest.mark.asyncio
async def test_log_impressions_noop_when_flag_off(seeded_db):
    await _enable(seeded_db)
    await _set(seeded_db, "recommendations.log_impressions", False)
    o = await _verified_owner(seeded_db)
    seeded_db.add(_make_room(rid="r-no-log", owner_id=o.id))
    student = await _student(seeded_db)
    seeded_db.add(UserIntelligenceProfile(
        user_id=student.id, preferred_city="Kochi",
        intent_level=IntentLevel.MEDIUM_INTENT, raw_intent_score=5,
    ))
    await seeded_db.commit()

    recs = await recommendation_service.personalized_for_user(
        seeded_db, user_id=student.id,
    )
    await recommendation_service.log_impressions(
        seeded_db, user_id=student.id, anonymous_session_id=None,
        surface=RecommendationSurface.FOR_YOU, recommendations=recs,
    )
    await seeded_db.commit()

    rows = (await seeded_db.execute(select(RecommendationLog))).scalars().all()
    assert rows == []
