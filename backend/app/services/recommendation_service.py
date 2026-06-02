"""Rule-based recommendation engine (Phase 3).

Four surfaces:
  - personalized_for_user      — uses Phase 2 profile
  - similar_to_listing         — item-based (city + category + price band)
  - trending_in_city           — event-aggregated city heat
  - recently_viewed_for_user   — replays user's VIEW events

Hard eligibility rules (applied to every surface):
  1. Listing status must be LIVE
  2. Owner KYC must be VERIFIED or NOT_REQUIRED
  3. `maintenance_status != SUSPENDED_FOR_NONPAYMENT`
  4. `visibility_score > 0`
  5. `recommendation_excluded` must be False
  6. Listing not in the caller's `exclude_listing_ids` set (e.g., the one
     they're already viewing)

Ranking:
  base_score from surface-specific signals
  + bonus when `recommendation_priority` is set (admin boost)
  + bonus when `is_sponsored=True` and `sponsored_until` is in the future
  Final ordering is descending by computed score, with `recommendation_priority`
  always above un-prioritized listings.

All scoring weights live in `tax_config` so they can be tuned without redeploy.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Iterable, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.accommodation import Accommodation
from app.models.reading_room import (
    ListingStatus, MaintenanceStatus, ReadingRoom,
)
from app.models.recommendation_log import (
    RecommendationLog, RecommendationSurface,
)
from app.models.user import KYCStatus, User
from app.models.user_event import EventCategory, EventEntityType, UserEvent
from app.models.user_intelligence_profile import UserIntelligenceProfile
from app.services import privacy_consent_service
from app.services.tax_engine import cfg_get, load_active_config


# ---------- result type ----------------------------------------------------

@dataclass
class Recommendation:
    listing_type: str         # 'reading_room' | 'accommodation'
    listing_id: str
    name: str
    city: Optional[str]
    state: Optional[str]
    price: Optional[float]
    rank: int                 # 1-based
    score: float
    reason_code: str
    extra: dict[str, Any] = field(default_factory=dict)


# ---------- common eligibility filter --------------------------------------

def _filter_eligible_reading_rooms(stmt):
    return stmt.where(
        (ReadingRoom.status == ListingStatus.LIVE)
        & (ReadingRoom.maintenance_status != MaintenanceStatus.SUSPENDED_FOR_NONPAYMENT)
        & (ReadingRoom.visibility_score > 0)
        & (ReadingRoom.recommendation_excluded.is_(False))
    )


def _filter_eligible_accommodations(stmt):
    return stmt.where(
        (Accommodation.status == ListingStatus.LIVE)
        & (Accommodation.maintenance_status != MaintenanceStatus.SUSPENDED_FOR_NONPAYMENT)
        & (Accommodation.visibility_score > 0)
        & (Accommodation.recommendation_excluded.is_(False))
    )


async def _kyc_verified_owner_ids(
    db: AsyncSession, owner_ids: Iterable[str],
) -> set[str]:
    """Return the subset of owner_ids whose KYC passes the gate."""
    ids = list({oid for oid in owner_ids if oid})
    if not ids:
        return set()
    rows = (await db.execute(
        select(User.id, User.kyc_status).where(User.id.in_(ids))
    )).all()
    return {
        uid for uid, status in rows
        if status in (KYCStatus.VERIFIED, KYCStatus.NOT_REQUIRED)
    }


# ---------- scoring helpers -----------------------------------------------

def _w(config: dict[str, Any], key: str, default: float) -> float:
    val = config.get(key)
    if val is None:
        return default
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


def _apply_admin_boost(score: float, listing, config: dict[str, Any]) -> float:
    """Admin priority and active sponsorship boost the score."""
    boosted = score
    if listing.recommendation_priority is not None:
        boosted += float(listing.recommendation_priority) * _w(
            config, "recommendations.weight.admin_priority", 100.0,
        )
    if bool(listing.is_sponsored):
        until = listing.sponsored_until
        try:
            # sponsored_until may be a string or datetime depending on model
            if isinstance(until, str):
                exp = datetime.fromisoformat(until.replace("Z", "+00:00"))
                still_active = exp.replace(tzinfo=None) > datetime.utcnow()
            elif isinstance(until, datetime):
                still_active = until > datetime.utcnow()
            else:
                still_active = True
        except (TypeError, ValueError):
            still_active = True
        if still_active:
            boosted += _w(config, "recommendations.weight.sponsored", 20.0)
    return boosted


# ---------- 1. personalized_for_user --------------------------------------

async def personalized_for_user(
    db: AsyncSession,
    *,
    user_id: str,
    limit: int = 10,
    exclude_listing_ids: Optional[set[str]] = None,
) -> list[Recommendation]:
    """Use the user's profile to rank listings. Returns [] if consent
    missing, profile missing, or master flag off."""
    config = await load_active_config(db)
    if not bool(cfg_get(config, "recommendations.enabled", False)):
        return []
    if not await privacy_consent_service.is_personalization_allowed(
        db, user_id=user_id,
    ):
        return []

    profile = await db.get(UserIntelligenceProfile, user_id)
    if profile is None:
        return []

    exclude_listing_ids = exclude_listing_ids or set()
    preferred_locations = _parse_list(profile.preferred_locations_json)
    preferred_property_types = _parse_list(profile.preferred_property_types_json)

    # Pick which entity tables to query based on preferred property types.
    wants_reading_room = (
        not preferred_property_types
        or "reading_room" in preferred_property_types
        or "cabin" in preferred_property_types
    )
    wants_accommodation = (
        not preferred_property_types
        or any(t in preferred_property_types
               for t in ("accommodation", "pg", "hostel", "house"))
    )

    candidates: list[tuple[str, Any, float, str]] = []
    # (listing_type, model_row, base_score, reason_code)

    if wants_reading_room:
        stmt = _filter_eligible_reading_rooms(select(ReadingRoom))
        rows = (await db.execute(stmt.limit(500))).scalars().all()
        owner_ok = await _kyc_verified_owner_ids(db, (r.owner_id for r in rows))
        for r in rows:
            if r.id in exclude_listing_ids or r.owner_id not in owner_ok:
                continue
            score, reason = _score_against_profile(
                listing_city=r.city, listing_price=r.price_start,
                listing_location=r.locality or r.area,
                profile=profile, locations=preferred_locations, config=config,
            )
            candidates.append(("reading_room", r, score, reason))

    if wants_accommodation:
        stmt = _filter_eligible_accommodations(select(Accommodation))
        rows = (await db.execute(stmt.limit(500))).scalars().all()
        owner_ok = await _kyc_verified_owner_ids(db, (r.owner_id for r in rows))
        for r in rows:
            if r.id in exclude_listing_ids or r.owner_id not in owner_ok:
                continue
            score, reason = _score_against_profile(
                listing_city=r.city, listing_price=r.price,
                listing_location=r.locality or r.area,
                profile=profile, locations=preferred_locations, config=config,
            )
            candidates.append(("accommodation", r, score, reason))

    return _finalize(candidates, config=config, limit=limit)


def _score_against_profile(
    *,
    listing_city: Optional[str],
    listing_price: Optional[float],
    listing_location: Optional[str],
    profile: UserIntelligenceProfile,
    locations: list[str],
    config: dict[str, Any],
) -> tuple[float, str]:
    """Compute a base score for ONE listing against the user profile."""
    score = 0.0
    reason = "profile_match"

    # City match
    if profile.preferred_city and listing_city:
        if listing_city.lower() == profile.preferred_city.lower():
            score += _w(config, "recommendations.weight.city_match", 30.0)
            reason = "profile_city_match"

    # Location (neighborhood) match
    if listing_location:
        loc_l = listing_location.lower()
        if any(loc.lower() in loc_l or loc_l in loc.lower() for loc in locations):
            score += _w(config, "recommendations.weight.location_match", 20.0)
            reason = "profile_location_match"

    # Price band overlap
    if listing_price is not None:
        pmin = profile.preferred_price_min
        pmax = profile.preferred_price_max
        if pmin is None and pmax is None:
            pass
        else:
            in_band = (
                (pmin is None or listing_price >= pmin * 0.7)
                and (pmax is None or listing_price <= pmax * 1.3)
            )
            if in_band:
                score += _w(config, "recommendations.weight.price_match", 15.0)

    return score, reason


# ---------- 2. similar_to_listing -----------------------------------------

async def similar_to_listing(
    db: AsyncSession,
    *,
    listing_type: str,
    listing_id: str,
    limit: int = 10,
) -> list[Recommendation]:
    """Content-based: same city + same GST category + similar price band."""
    config = await load_active_config(db)
    if not bool(cfg_get(config, "recommendations.enabled", False)):
        return []

    if listing_type == "reading_room":
        source = await db.get(ReadingRoom, listing_id)
    elif listing_type == "accommodation":
        source = await db.get(Accommodation, listing_id)
    else:
        return []
    if source is None:
        return []

    source_price = float(source.price_start or source.price or 0) \
        if hasattr(source, "price_start") else float(source.price or 0)
    price_lo = source_price * 0.7 if source_price > 0 else None
    price_hi = source_price * 1.3 if source_price > 0 else None

    candidates: list[tuple[str, Any, float, str]] = []

    # Same-table same-city candidates
    if listing_type == "reading_room":
        stmt = _filter_eligible_reading_rooms(
            select(ReadingRoom).where(ReadingRoom.id != listing_id)
        )
        if source.city:
            stmt = stmt.where(ReadingRoom.city == source.city)
        rows = (await db.execute(stmt.limit(200))).scalars().all()
        owner_ok = await _kyc_verified_owner_ids(db, (r.owner_id for r in rows))
        for r in rows:
            if r.owner_id not in owner_ok:
                continue
            score = _w(config, "recommendations.weight.same_city", 20.0)
            if source.gst_category and r.gst_category == source.gst_category:
                score += _w(config, "recommendations.weight.same_category", 15.0)
            if price_lo is not None and r.price_start is not None:
                if price_lo <= float(r.price_start) <= price_hi:
                    score += _w(config, "recommendations.weight.price_match", 15.0)
            candidates.append(("reading_room", r, score, "similar_in_city"))
    else:
        stmt = _filter_eligible_accommodations(
            select(Accommodation).where(Accommodation.id != listing_id)
        )
        if source.city:
            stmt = stmt.where(Accommodation.city == source.city)
        rows = (await db.execute(stmt.limit(200))).scalars().all()
        owner_ok = await _kyc_verified_owner_ids(db, (r.owner_id for r in rows))
        for r in rows:
            if r.owner_id not in owner_ok:
                continue
            score = _w(config, "recommendations.weight.same_city", 20.0)
            if source.gst_category and r.gst_category == source.gst_category:
                score += _w(config, "recommendations.weight.same_category", 15.0)
            if price_lo is not None and r.price is not None:
                if price_lo <= float(r.price) <= price_hi:
                    score += _w(config, "recommendations.weight.price_match", 15.0)
            candidates.append(("accommodation", r, score, "similar_in_city"))

    return _finalize(candidates, config=config, limit=limit)


# ---------- 3. trending_in_city -------------------------------------------

async def trending_in_city(
    db: AsyncSession,
    *,
    city: Optional[str],
    limit: int = 10,
    window_days: int = 7,
) -> list[Recommendation]:
    """Aggregate VIEW/SAVE event counts per listing within a window."""
    config = await load_active_config(db)
    if not bool(cfg_get(config, "recommendations.enabled", False)):
        return []

    cutoff = datetime.utcnow() - timedelta(days=window_days)
    base = (
        select(
            UserEvent.entity_type,
            UserEvent.entity_id,
            func.count(UserEvent.id).label("hits"),
        )
        .where(
            (UserEvent.created_at >= cutoff)
            & (UserEvent.entity_id.isnot(None))
            & (UserEvent.event_category.in_([
                EventCategory.VIEW, EventCategory.SAVE, EventCategory.INTENT,
            ]))
        )
        .group_by(UserEvent.entity_type, UserEvent.entity_id)
        .order_by(func.count(UserEvent.id).desc())
        .limit(200)
    )
    if city:
        base = base.where(UserEvent.city == city)

    rows = (await db.execute(base)).all()

    candidates: list[tuple[str, Any, float, str]] = []
    rr_ids = [eid for (et, eid, _) in rows if et == EventEntityType.READING_ROOM]
    acc_ids = [eid for (et, eid, _) in rows if et == EventEntityType.ACCOMMODATION]
    hit_map = {(et.value if et else None, eid): hits for (et, eid, hits) in rows}

    if rr_ids:
        rr_rows = (await db.execute(
            _filter_eligible_reading_rooms(
                select(ReadingRoom).where(ReadingRoom.id.in_(rr_ids))
            )
        )).scalars().all()
        owner_ok = await _kyc_verified_owner_ids(db, (r.owner_id for r in rr_rows))
        for r in rr_rows:
            if r.owner_id not in owner_ok:
                continue
            hits = hit_map.get(("reading_room", r.id), 0)
            candidates.append((
                "reading_room", r, float(hits) * _w(
                    config, "recommendations.weight.trending_hit", 1.0,
                ), "trending",
            ))

    if acc_ids:
        acc_rows = (await db.execute(
            _filter_eligible_accommodations(
                select(Accommodation).where(Accommodation.id.in_(acc_ids))
            )
        )).scalars().all()
        owner_ok = await _kyc_verified_owner_ids(db, (r.owner_id for r in acc_rows))
        for r in acc_rows:
            if r.owner_id not in owner_ok:
                continue
            hits = hit_map.get(("accommodation", r.id), 0)
            candidates.append((
                "accommodation", r, float(hits) * _w(
                    config, "recommendations.weight.trending_hit", 1.0,
                ), "trending",
            ))

    return _finalize(candidates, config=config, limit=limit)


# ---------- 4. recently_viewed_for_user -----------------------------------

async def recently_viewed_for_user(
    db: AsyncSession,
    *,
    user_id: str,
    limit: int = 10,
) -> list[Recommendation]:
    """Replay the user's most recent VIEW events as recommendations.

    Requires `allow_analytics_tracking` because it reveals event history.
    """
    config = await load_active_config(db)
    if not bool(cfg_get(config, "recommendations.enabled", False)):
        return []
    # Stricter than the analytics legitimate-interest gate: surfacing the
    # user's own viewing history is personal data, so we require their
    # explicit opt-in flag on the consent row regardless of the global
    # `consent.required_for_analytics` setting.
    from app.models.user_consent_preferences import UserConsentPreferences
    consent_row = await db.get(UserConsentPreferences, user_id)
    if consent_row is None or not consent_row.allow_analytics_tracking:
        return []

    rows = (await db.execute(
        select(UserEvent)
        .where(
            (UserEvent.user_id == user_id)
            & (UserEvent.event_category == EventCategory.VIEW)
            & (UserEvent.entity_id.isnot(None))
        )
        .order_by(UserEvent.created_at.desc())
        .limit(limit * 3)   # over-fetch since some will dedupe / be inactive
    )).scalars().all()

    seen: set[str] = set()
    rr_ids: list[str] = []
    acc_ids: list[str] = []
    order: list[tuple[str, str]] = []   # (listing_type, listing_id) in click order
    for e in rows:
        key = f"{e.entity_type.value if e.entity_type else 'x'}:{e.entity_id}"
        if key in seen:
            continue
        seen.add(key)
        if e.entity_type == EventEntityType.READING_ROOM:
            rr_ids.append(e.entity_id)
            order.append(("reading_room", e.entity_id))
        elif e.entity_type == EventEntityType.ACCOMMODATION:
            acc_ids.append(e.entity_id)
            order.append(("accommodation", e.entity_id))

    rr_map: dict[str, ReadingRoom] = {}
    acc_map: dict[str, Accommodation] = {}
    if rr_ids:
        rrs = (await db.execute(
            _filter_eligible_reading_rooms(
                select(ReadingRoom).where(ReadingRoom.id.in_(rr_ids))
            )
        )).scalars().all()
        owner_ok = await _kyc_verified_owner_ids(db, (r.owner_id for r in rrs))
        rr_map = {r.id: r for r in rrs if r.owner_id in owner_ok}
    if acc_ids:
        accs = (await db.execute(
            _filter_eligible_accommodations(
                select(Accommodation).where(Accommodation.id.in_(acc_ids))
            )
        )).scalars().all()
        owner_ok = await _kyc_verified_owner_ids(db, (r.owner_id for r in accs))
        acc_map = {r.id: r for r in accs if r.owner_id in owner_ok}

    candidates: list[tuple[str, Any, float, str]] = []
    for i, (ltype, lid) in enumerate(order):
        listing = rr_map.get(lid) if ltype == "reading_room" else acc_map.get(lid)
        if listing is None:
            continue
        # Score by recency rank (earlier seen = higher score), bounded.
        score = max(1.0, 100.0 - i * 10.0)
        candidates.append((ltype, listing, score, "recently_viewed"))

    return _finalize(candidates, config=config, limit=limit)


# ---------- finalize: boost + sort + emit Recommendation rows --------------

def _to_recommendation(
    *, listing_type: str, listing, rank: int, score: float, reason_code: str,
) -> Recommendation:
    price = None
    if hasattr(listing, "price_start"):
        price = float(listing.price_start) if listing.price_start is not None else None
    elif hasattr(listing, "price"):
        price = float(listing.price) if listing.price is not None else None
    return Recommendation(
        listing_type=listing_type,
        listing_id=listing.id,
        name=listing.name,
        city=getattr(listing, "city", None),
        state=getattr(listing, "state", None),
        price=price,
        rank=rank,
        score=round(score, 4),
        reason_code=reason_code,
        extra={
            "is_sponsored": bool(getattr(listing, "is_sponsored", False)),
            "admin_priority": getattr(listing, "recommendation_priority", None),
        },
    )


def _finalize(
    candidates: list[tuple[str, Any, float, str]],
    *,
    config: dict[str, Any],
    limit: int,
) -> list[Recommendation]:
    # Apply admin + sponsorship boosts
    boosted = [
        (ltype, listing, _apply_admin_boost(score, listing, config), reason)
        for (ltype, listing, score, reason) in candidates
    ]
    boosted.sort(key=lambda x: x[2], reverse=True)
    out: list[Recommendation] = []
    for i, (ltype, listing, score, reason) in enumerate(boosted[:limit], start=1):
        out.append(_to_recommendation(
            listing_type=ltype, listing=listing,
            rank=i, score=score, reason_code=reason,
        ))
    return out


# ---------- logging --------------------------------------------------------

async def log_impressions(
    db: AsyncSession,
    *,
    user_id: Optional[str],
    anonymous_session_id: Optional[str],
    surface: RecommendationSurface,
    recommendations: list[Recommendation],
) -> None:
    """Append one row per served recommendation for attribution. Caller commits.

    No-ops when `recommendations.log_impressions` is OFF (saves DB churn when
    we're just testing/replaying surfaces in dev).
    """
    config = await load_active_config(db)
    if not bool(cfg_get(config, "recommendations.log_impressions", False)):
        return
    for rec in recommendations:
        db.add(RecommendationLog(
            user_id=user_id,
            anonymous_session_id=anonymous_session_id,
            surface=surface,
            listing_type=rec.listing_type,
            listing_id=rec.listing_id,
            rank=rec.rank,
            score=rec.score,
            reason_code=rec.reason_code,
        ))
    await db.flush()


# ---------- helpers --------------------------------------------------------

def _parse_list(s: Optional[str]) -> list[str]:
    if not s:
        return []
    try:
        v = json.loads(s)
        return v if isinstance(v, list) else []
    except (json.JSONDecodeError, TypeError):
        return []
