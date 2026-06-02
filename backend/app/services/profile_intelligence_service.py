"""Profile aggregation — event stream -> UserIntelligenceProfile row.

Single writer for the profile table. Reads the recent event window for a
user, derives preference signals + intent score, and upserts one row.

Hard rules:
  - Pure derivation. We never look at user-input fields (name, email).
    Only behavior decides what we infer.
  - Idempotent: re-running for the same user with the same events produces
    the same row.
  - Bounded: only the last `intelligence.profile_window_days` (default 90)
    of events are scanned, to keep refresh cheap as the firehose grows.
  - Privacy-respecting: skipped entirely for users whose
    `allow_personalized_recommendations` is OFF, even if events are present.
    (Aggregation is what enables personalization; without consent we don't
    derive a profile.)

The aggregation runs after the firehose is consented; the scheduler
respects the master `intelligence.profile_aggregation_enabled` flag.
"""
from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Iterable, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user_event import EventCategory, UserEvent
from app.models.user_intelligence_profile import (
    IntentLevel, UserIntelligenceProfile,
)
from app.services import privacy_consent_service
from app.services.intent_scoring_service import score_events
from app.services.tax_engine import cfg_get, load_active_config


# How many preferences we surface — top-N counts.
TOP_N_LOCATIONS = 3
TOP_N_PROPERTY_TYPES = 3
TOP_N_AMENITIES = 5


@dataclass
class AggregationResult:
    user_id: str
    persisted: bool          # False if skipped (consent / no events / flag off)
    reason: Optional[str] = None
    raw_score: int = 0
    intent_level: Optional[IntentLevel] = None


# ---------- top-N pickers --------------------------------------------------

def _top_n_strings(values: Iterable[Optional[str]], n: int) -> list[str]:
    counts = Counter(v for v in values if v)
    return [v for v, _ in counts.most_common(n)]


def _parse_metadata(event: UserEvent) -> dict:
    if not event.metadata_json:
        return {}
    try:
        return json.loads(event.metadata_json)
    except (json.JSONDecodeError, TypeError):
        return {}


# ---------- preference derivation -----------------------------------------

def _derive_preferences(events: list[UserEvent]) -> dict:
    """Return a dict of preference fields ready to set on the profile row."""
    locations = _top_n_strings(
        (e.location_query for e in events if e.location_query),
        TOP_N_LOCATIONS,
    )
    cities = _top_n_strings((e.city for e in events if e.city), 1)
    preferred_city = cities[0] if cities else None

    # Property types come from entity_type on VIEW events.
    property_types = _top_n_strings(
        (e.entity_type.value if e.entity_type else None
         for e in events if e.event_category == EventCategory.VIEW),
        TOP_N_PROPERTY_TYPES,
    )

    # Amenities + price come from FILTER event metadata. We accept either
    # `amenities: ["AC","wifi"]` or repeated single-value `amenity` fields.
    amenities_acc: list[str] = []
    prices_seen: list[float] = []
    for e in events:
        if e.event_category != EventCategory.FILTER:
            continue
        meta = _parse_metadata(e)
        a = meta.get("amenities")
        if isinstance(a, list):
            amenities_acc.extend(str(x) for x in a if isinstance(x, (str, int)))
        elif isinstance(a, str):
            amenities_acc.append(a)
        for k in ("price_max", "price_min", "price"):
            v = meta.get(k)
            if isinstance(v, (int, float)) and v > 0:
                prices_seen.append(float(v))

    amenities = _top_n_strings(amenities_acc, TOP_N_AMENITIES)

    price_min = min(prices_seen) if prices_seen else None
    price_max = max(prices_seen) if prices_seen else None

    return {
        "preferred_city": preferred_city,
        "preferred_locations": locations,
        "preferred_property_types": property_types,
        "preferred_amenities": amenities,
        "preferred_price_min": price_min,
        "preferred_price_max": price_max,
    }


# ---------- behavior scores (0.0–1.0) -------------------------------------

def _saturate(x: float, scale: float) -> float:
    """Smooth 0–1 mapping that saturates at large values."""
    if x <= 0:
        return 0.0
    return min(1.0, x / scale)


def _derive_behavior_scores(events: list[UserEvent], raw_intent: int) -> dict:
    """Heuristic per-axis scores. Phase 4+ may swap these for ML models."""
    n = len(events)
    saves = sum(1 for e in events if e.event_category == EventCategory.SAVE)
    filters = sum(1 for e in events if e.event_category == EventCategory.FILTER)
    avail_checks = sum(
        1 for e in events
        if "availability" in (e.event_name or "").lower()
    )
    cancels = sum(1 for e in events if e.event_category == EventCategory.CANCELLATION)

    # Urgency: weighted by raw intent + how many availability checks landed.
    booking_urgency = _saturate(raw_intent + 4 * avail_checks, 50)

    # Budget sensitivity: lots of price filters relative to total events.
    budget_sensitivity = _saturate(filters * 3, max(10, n))

    # Location sensitivity: how concentrated their location_query usage is.
    locs = [e.location_query for e in events if e.location_query]
    if locs:
        top_loc = max(Counter(locs).values())
        location_sensitivity = top_loc / max(1, len(locs))
    else:
        location_sensitivity = 0.0

    # Premium interest: explicit signals in FILTER metadata (e.g., AC, private).
    premium_hits = 0
    for e in events:
        if e.event_category != EventCategory.FILTER:
            continue
        meta = _parse_metadata(e)
        amenities = meta.get("amenities") or []
        if isinstance(amenities, str):
            amenities = [amenities]
        for a in amenities:
            if str(a).lower() in {"ac", "private", "premium"}:
                premium_hits += 1
                break
    premium_interest = _saturate(premium_hits, 5)

    # Cancellation risk: cancels / saves ratio, capped.
    cancellation_risk = _saturate(cancels, 3)

    # Conversion probability: simple heuristic on raw intent + saves + checks.
    conversion_probability = _saturate(
        raw_intent + saves * 2 + avail_checks, 40,
    )

    return {
        "booking_urgency_score": round(booking_urgency, 4),
        "budget_sensitivity_score": round(budget_sensitivity, 4),
        "location_sensitivity_score": round(location_sensitivity, 4),
        "premium_interest_score": round(premium_interest, 4),
        "cancellation_risk_score": round(cancellation_risk, 4),
        "conversion_probability_score": round(conversion_probability, 4),
    }


def _derive_recency(events: list[UserEvent]) -> dict:
    """Last activity timestamps + most recent search/view tracking."""
    last_active_at: Optional[datetime] = None
    last_search_query: Optional[str] = None
    last_viewed_listing_id: Optional[str] = None
    last_booking_attempt_at: Optional[datetime] = None
    last_successful_booking_at: Optional[datetime] = None

    for e in sorted(events, key=lambda x: x.created_at):
        last_active_at = e.created_at
        if e.event_category == EventCategory.SEARCH and e.location_query:
            last_search_query = e.location_query
        if e.event_category == EventCategory.VIEW and e.entity_id:
            last_viewed_listing_id = e.entity_id
        name = (e.event_name or "").lower()
        if name.startswith("booking.start"):
            last_booking_attempt_at = e.created_at
        if name == "booking.completed":
            last_successful_booking_at = e.created_at

    return {
        "last_active_at": last_active_at,
        "last_search_query": last_search_query,
        "last_viewed_listing_id": last_viewed_listing_id,
        "last_booking_attempt_at": last_booking_attempt_at,
        "last_successful_booking_at": last_successful_booking_at,
    }


def _derive_confidence(events: list[UserEvent]) -> float:
    """Goes up with event count + category diversity. Saturates near 1.0."""
    if not events:
        return 0.0
    distinct_cats = len({e.event_category for e in events})
    by_count = _saturate(len(events), 30)
    by_diversity = _saturate(distinct_cats, 6)
    return round((by_count * 0.6) + (by_diversity * 0.4), 4)


# ---------- public API ----------------------------------------------------

async def _fetch_recent_events(
    db: AsyncSession, *, user_id: str, since: datetime,
) -> list[UserEvent]:
    rows = (await db.execute(
        select(UserEvent)
        .where(
            (UserEvent.user_id == user_id)
            & (UserEvent.created_at >= since)
        )
        .order_by(UserEvent.created_at.asc())
    )).scalars().all()
    return list(rows)


async def rebuild_profile_for_user(
    db: AsyncSession, *, user_id: str,
) -> AggregationResult:
    """Read recent events for one user; upsert the derived profile row.

    Caller commits.
    """
    config = await load_active_config(db)
    if not bool(cfg_get(config, "intelligence.profile_aggregation_enabled", False)):
        return AggregationResult(
            user_id=user_id, persisted=False,
            reason="intelligence.profile_aggregation_enabled is OFF",
        )
    if not await privacy_consent_service.is_personalization_allowed(
        db, user_id=user_id,
    ):
        return AggregationResult(
            user_id=user_id, persisted=False,
            reason="user has not opted in to personalized recommendations",
        )

    window_days = int(cfg_get(config, "intelligence.profile_window_days", 90))
    since = datetime.utcnow() - timedelta(days=window_days)
    events = await _fetch_recent_events(db, user_id=user_id, since=since)
    if not events:
        return AggregationResult(
            user_id=user_id, persisted=False,
            reason="no events in window",
        )

    score = score_events(events, config)
    preferences = _derive_preferences(events)
    behavior = _derive_behavior_scores(events, raw_intent=score.raw_score)
    recency = _derive_recency(events)
    confidence = _derive_confidence(events)

    row = await db.get(UserIntelligenceProfile, user_id)
    if row is None:
        row = UserIntelligenceProfile(user_id=user_id)
        db.add(row)

    # Preferences
    row.preferred_city = preferences["preferred_city"]
    row.preferred_locations_json = json.dumps(preferences["preferred_locations"])
    row.preferred_property_types_json = json.dumps(preferences["preferred_property_types"])
    row.preferred_amenities_json = json.dumps(preferences["preferred_amenities"])
    row.preferred_price_min = preferences["preferred_price_min"]
    row.preferred_price_max = preferences["preferred_price_max"]
    # We don't have a heuristic for preferred_study_time yet — left null.

    # Behavior scores
    row.booking_urgency_score = behavior["booking_urgency_score"]
    row.budget_sensitivity_score = behavior["budget_sensitivity_score"]
    row.location_sensitivity_score = behavior["location_sensitivity_score"]
    row.premium_interest_score = behavior["premium_interest_score"]
    row.cancellation_risk_score = behavior["cancellation_risk_score"]
    row.conversion_probability_score = behavior["conversion_probability_score"]

    # Intent
    row.raw_intent_score = score.raw_score
    row.intent_level = score.level

    # Recency
    row.last_active_at = recency["last_active_at"]
    row.last_search_query = recency["last_search_query"]
    row.last_viewed_listing_id = recency["last_viewed_listing_id"]
    row.last_booking_attempt_at = recency["last_booking_attempt_at"]
    row.last_successful_booking_at = recency["last_successful_booking_at"]

    # Confidence
    row.profile_confidence_score = confidence
    row.event_count = len(events)

    await db.flush()
    return AggregationResult(
        user_id=user_id, persisted=True,
        raw_score=score.raw_score, intent_level=score.level,
    )


async def rebuild_all_active_profiles(
    db: AsyncSession, *, since_days: int = 1,
) -> dict:
    """Cron entry. Rebuild profiles for users with activity in the last
    `since_days` days. Returns a summary {scanned, persisted, skipped}.
    """
    config = await load_active_config(db)
    if not bool(cfg_get(config, "intelligence.profile_aggregation_enabled", False)):
        return {"skipped": "intelligence.profile_aggregation_enabled is OFF"}

    cutoff = datetime.utcnow() - timedelta(days=since_days)
    distinct_user_ids = (await db.execute(
        select(UserEvent.user_id)
        .where(
            (UserEvent.user_id.isnot(None))
            & (UserEvent.created_at >= cutoff)
        )
        .distinct()
    )).scalars().all()

    persisted = 0
    skipped = 0
    for uid in distinct_user_ids:
        result = await rebuild_profile_for_user(db, user_id=uid)
        if result.persisted:
            persisted += 1
        else:
            skipped += 1
    await db.commit()
    return {
        "scanned": len(distinct_user_ids),
        "persisted": persisted,
        "skipped": skipped,
    }


# ---------- read helpers --------------------------------------------------

async def get_profile_for_user(
    db: AsyncSession, *, user_id: str,
) -> Optional[UserIntelligenceProfile]:
    return await db.get(UserIntelligenceProfile, user_id)


async def list_profiles_by_intent(
    db: AsyncSession, *, level: Optional[IntentLevel] = None,
    limit: int = 100, offset: int = 0,
) -> list[UserIntelligenceProfile]:
    stmt = select(UserIntelligenceProfile).order_by(
        UserIntelligenceProfile.raw_intent_score.desc()
    )
    if level is not None:
        stmt = stmt.where(UserIntelligenceProfile.intent_level == level)
    stmt = stmt.offset(offset).limit(limit)
    rows = (await db.execute(stmt)).scalars().all()
    return list(rows)
