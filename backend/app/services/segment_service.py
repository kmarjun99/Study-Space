"""Segment evaluation + membership management.

Predicate dispatch table:
  HIGH_INTENT              -> matches when profile.intent_level >= HIGH_INTENT
  BUDGET_BAND              -> preferred_price_max <= rule_config['max_price']
  CITY_INTEREST            -> preferred_city == rule_config['city']
  AMENITY_INTEREST         -> rule_config['amenity'] in preferred_amenities
  PAYMENT_ABANDONED        -> has payment.failed/abandoned event in window
  REPEAT_SEARCH_NO_BOOKING -> >= rule_config['min_searches'] SEARCH events in
                              window, with no booking.completed inside the same window
  CANCELLED_USERS          -> has CANCELLATION event in window

Hard rules:
  - Master flag `segments.enabled` must be ON; otherwise the recompute is a no-op
  - Only users with `allow_personalized_recommendations` are evaluated
  - Existing memberships flip to inactive (exited_at stamped) when the user
    no longer matches; we never delete history
  - Inactive segments are skipped
  - All windows are configurable via `segments.window_days` (default 30)
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Callable, Optional

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user_event import EventCategory, UserEvent
from app.models.user_intelligence_profile import (
    IntentLevel, UserIntelligenceProfile,
)
from app.models.user_segment import (
    SegmentRuleType, UserSegment, UserSegmentMembership,
)
from app.services import privacy_consent_service
from app.services.tax_engine import cfg_get, load_active_config


@dataclass
class EvalResult:
    matches: bool
    score: float = 0.0
    reason: str = ""


@dataclass
class RecomputeSummary:
    segments_evaluated: int = 0
    users_evaluated: int = 0
    memberships_entered: int = 0
    memberships_exited: int = 0
    skipped: list[str] = None


# ---------- predicate registry --------------------------------------------

def _eval_high_intent(
    profile: UserIntelligenceProfile,
    events: list[UserEvent],
    rule_config: dict[str, Any],
) -> EvalResult:
    if profile is None or profile.intent_level is None:
        return EvalResult(False)
    if profile.intent_level in (IntentLevel.HIGH_INTENT, IntentLevel.HOT_LEAD):
        return EvalResult(
            True,
            score=float(profile.raw_intent_score),
            reason=f"intent={profile.intent_level.value}; raw={profile.raw_intent_score}",
        )
    return EvalResult(False)


def _eval_budget_band(
    profile: UserIntelligenceProfile,
    events: list[UserEvent],
    rule_config: dict[str, Any],
) -> EvalResult:
    if profile is None or profile.preferred_price_max is None:
        return EvalResult(False)
    threshold = rule_config.get("max_price")
    if threshold is None:
        return EvalResult(False)
    try:
        threshold_f = float(threshold)
    except (TypeError, ValueError):
        return EvalResult(False)
    if profile.preferred_price_max <= threshold_f:
        return EvalResult(
            True,
            score=float(threshold_f - profile.preferred_price_max),
            reason=f"preferred_price_max={profile.preferred_price_max} <= {threshold_f}",
        )
    return EvalResult(False)


def _eval_city_interest(
    profile: UserIntelligenceProfile,
    events: list[UserEvent],
    rule_config: dict[str, Any],
) -> EvalResult:
    if profile is None or not profile.preferred_city:
        return EvalResult(False)
    target = rule_config.get("city")
    if not target:
        return EvalResult(False)
    if profile.preferred_city.lower() == str(target).lower():
        return EvalResult(
            True,
            score=float(profile.event_count),
            reason=f"preferred_city={profile.preferred_city}",
        )
    return EvalResult(False)


def _eval_amenity_interest(
    profile: UserIntelligenceProfile,
    events: list[UserEvent],
    rule_config: dict[str, Any],
) -> EvalResult:
    if profile is None or not profile.preferred_amenities_json:
        return EvalResult(False)
    target = rule_config.get("amenity")
    if not target:
        return EvalResult(False)
    try:
        amenities = json.loads(profile.preferred_amenities_json)
    except (json.JSONDecodeError, TypeError):
        return EvalResult(False)
    if not isinstance(amenities, list):
        return EvalResult(False)
    target_l = str(target).lower()
    matches = [a for a in amenities if str(a).lower() == target_l]
    if matches:
        return EvalResult(
            True,
            score=float(len(matches)),
            reason=f"amenity={target} in preferences",
        )
    return EvalResult(False)


def _eval_payment_abandoned(
    profile: UserIntelligenceProfile,
    events: list[UserEvent],
    rule_config: dict[str, Any],
) -> EvalResult:
    hits = [
        e for e in events
        if (e.event_name or "").lower() in ("payment.failed", "payment.abandoned")
    ]
    if hits:
        return EvalResult(
            True,
            score=float(len(hits)),
            reason=f"payment-fail count={len(hits)}",
        )
    return EvalResult(False)


def _eval_repeat_search_no_booking(
    profile: UserIntelligenceProfile,
    events: list[UserEvent],
    rule_config: dict[str, Any],
) -> EvalResult:
    min_searches = int(rule_config.get("min_searches", 3))
    searches = sum(
        1 for e in events if e.event_category == EventCategory.SEARCH
    )
    completed = any(
        (e.event_name or "").lower() == "booking.completed" for e in events
    )
    if searches >= min_searches and not completed:
        return EvalResult(
            True,
            score=float(searches),
            reason=f"searches={searches} no completed booking",
        )
    return EvalResult(False)


def _eval_cancelled(
    profile: UserIntelligenceProfile,
    events: list[UserEvent],
    rule_config: dict[str, Any],
) -> EvalResult:
    hits = [
        e for e in events if e.event_category == EventCategory.CANCELLATION
    ]
    if hits:
        return EvalResult(
            True,
            score=float(len(hits)),
            reason=f"cancellation count={len(hits)}",
        )
    return EvalResult(False)


PREDICATES: dict[
    SegmentRuleType,
    Callable[[Optional[UserIntelligenceProfile], list[UserEvent], dict[str, Any]],
             EvalResult],
] = {
    SegmentRuleType.HIGH_INTENT:              _eval_high_intent,
    SegmentRuleType.BUDGET_BAND:              _eval_budget_band,
    SegmentRuleType.CITY_INTEREST:            _eval_city_interest,
    SegmentRuleType.AMENITY_INTEREST:         _eval_amenity_interest,
    SegmentRuleType.PAYMENT_ABANDONED:        _eval_payment_abandoned,
    SegmentRuleType.REPEAT_SEARCH_NO_BOOKING: _eval_repeat_search_no_booking,
    SegmentRuleType.CANCELLED_USERS:          _eval_cancelled,
}


def evaluate(
    rule_type: SegmentRuleType,
    *,
    profile: Optional[UserIntelligenceProfile],
    recent_events: list[UserEvent],
    rule_config: dict[str, Any],
) -> EvalResult:
    """Public — dispatch one rule. Used by tests."""
    predicate = PREDICATES.get(rule_type)
    if predicate is None:
        return EvalResult(False, reason=f"no predicate for {rule_type.value}")
    return predicate(profile, recent_events, rule_config)


# ---------- recompute --------------------------------------------------------

async def _fetch_recent_events(
    db: AsyncSession, *, user_id: str, since: datetime,
) -> list[UserEvent]:
    rows = (await db.execute(
        select(UserEvent)
        .where(
            (UserEvent.user_id == user_id)
            & (UserEvent.created_at >= since)
        )
    )).scalars().all()
    return list(rows)


def _parse_rule_config(s: Optional[str]) -> dict[str, Any]:
    if not s:
        return {}
    try:
        v = json.loads(s)
        return v if isinstance(v, dict) else {}
    except (json.JSONDecodeError, TypeError):
        return {}


async def _active_memberships_for(
    db: AsyncSession, *, segment_id: str,
) -> dict[str, UserSegmentMembership]:
    rows = (await db.execute(
        select(UserSegmentMembership).where(
            (UserSegmentMembership.segment_id == segment_id)
            & (UserSegmentMembership.is_active.is_(True))
        )
    )).scalars().all()
    return {r.user_id: r for r in rows}


async def recompute_segment(
    db: AsyncSession, *, segment_id: str, since_days: Optional[int] = None,
) -> tuple[int, int]:
    """Evaluate one segment against every consenting user with a profile.

    Returns `(entered, exited)`. Caller commits.
    """
    config = await load_active_config(db)
    window = int(cfg_get(config, "segments.window_days",
                         since_days if since_days is not None else 30))
    since = datetime.utcnow() - timedelta(days=window)

    segment = await db.get(UserSegment, segment_id)
    if segment is None or not segment.is_active:
        return 0, 0
    rule_config = _parse_rule_config(segment.rule_config_json)

    # All consenting users with a profile in scope.
    profiles = (await db.execute(select(UserIntelligenceProfile))).scalars().all()

    existing = await _active_memberships_for(db, segment_id=segment_id)
    entered = 0
    exited = 0
    now = datetime.utcnow()

    for profile in profiles:
        if not await privacy_consent_service.is_personalization_allowed(
            db, user_id=profile.user_id,
        ):
            continue
        recent = await _fetch_recent_events(db, user_id=profile.user_id, since=since)
        result = evaluate(
            segment.rule_type,
            profile=profile, recent_events=recent, rule_config=rule_config,
        )

        current = existing.pop(profile.user_id, None)
        if result.matches:
            if current is None:
                db.add(UserSegmentMembership(
                    user_id=profile.user_id, segment_id=segment_id,
                    entered_at=now, is_active=True,
                    score=result.score, reason=result.reason,
                ))
                entered += 1
            else:
                # Already in; refresh score/reason without changing entered_at
                current.score = result.score
                current.reason = result.reason
        else:
            if current is not None:
                current.is_active = False
                current.exited_at = now
                exited += 1

    # Anyone left in `existing` had no profile this run -> mark inactive.
    for stale in existing.values():
        stale.is_active = False
        stale.exited_at = now
        exited += 1

    await db.flush()
    return entered, exited


async def recompute_all_active_segments(
    db: AsyncSession,
) -> RecomputeSummary:
    """Cron entry — recompute every `is_active` segment."""
    config = await load_active_config(db)
    summary = RecomputeSummary(skipped=[])
    if not bool(cfg_get(config, "segments.enabled", False)):
        summary.skipped.append("segments.enabled is OFF")
        return summary

    segments = (await db.execute(
        select(UserSegment).where(UserSegment.is_active.is_(True))
    )).scalars().all()

    for seg in segments:
        entered, exited = await recompute_segment(db, segment_id=seg.id)
        summary.segments_evaluated += 1
        summary.memberships_entered += entered
        summary.memberships_exited += exited

    await db.commit()
    return summary


# ---------- read helpers --------------------------------------------------

async def list_segments(
    db: AsyncSession, *, include_inactive: bool = False,
) -> list[UserSegment]:
    stmt = select(UserSegment).order_by(UserSegment.created_at.desc())
    if not include_inactive:
        stmt = stmt.where(UserSegment.is_active.is_(True))
    rows = (await db.execute(stmt)).scalars().all()
    return list(rows)


async def list_active_members(
    db: AsyncSession, *, segment_id: str, limit: int = 200, offset: int = 0,
) -> list[UserSegmentMembership]:
    rows = (await db.execute(
        select(UserSegmentMembership)
        .where(and_(
            UserSegmentMembership.segment_id == segment_id,
            UserSegmentMembership.is_active.is_(True),
        ))
        .order_by(UserSegmentMembership.score.desc())
        .offset(offset)
        .limit(limit)
    )).scalars().all()
    return list(rows)


async def segments_for_user(
    db: AsyncSession, *, user_id: str,
) -> list[tuple[UserSegment, UserSegmentMembership]]:
    """Used by the student transparency endpoint."""
    rows = (await db.execute(
        select(UserSegment, UserSegmentMembership)
        .join(
            UserSegmentMembership,
            UserSegmentMembership.segment_id == UserSegment.id,
        )
        .where(and_(
            UserSegmentMembership.user_id == user_id,
            UserSegmentMembership.is_active.is_(True),
        ))
    )).all()
    return [(seg, mem) for seg, mem in rows]
