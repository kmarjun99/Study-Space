"""Intent scoring — pure functions, config-driven weights.

Reads from `user_events`. Produces an integer raw score plus an `IntentLevel`
classification. Hardcodes nothing — every weight + threshold lives in
`tax_config` so we can tune without redeploy.

Default weights (configurable via `intent.weight.*` keys):
  SEARCH               +1
  VIEW                 +2
  FILTER               +2
  SAVE                 +4
  COMPARE              +3
  CONTACT              +5
  availability check   +5   (event_name = 'check.availability')
  BOOKING start        +8   (event_name starts with 'booking.start')
  PAYMENT failed       +10  (event_name = 'payment.failed' or 'payment.abandoned')

Default thresholds (configurable via `intent.threshold_*` keys):
  raw < 5             -> LOW_INTENT
  5 <= raw < 15       -> MEDIUM_INTENT
  15 <= raw < 30      -> HIGH_INTENT
  raw >= 30 OR any HOT_LEAD trigger event present -> HOT_LEAD

A booking with `event_name='booking.completed'` resets to LOW_INTENT (the
user has converted; intent is satisfied).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from app.models.user_event import EventCategory, UserEvent
from app.models.user_intelligence_profile import IntentLevel


# Built-in defaults. Overridden per-key by `tax_config` values when present.
DEFAULT_WEIGHTS: dict[str, int] = {
    "intent.weight.search":              1,
    "intent.weight.view":                2,
    "intent.weight.filter":              2,
    "intent.weight.save":                4,
    "intent.weight.compare":             3,
    "intent.weight.contact":             5,
    "intent.weight.availability_check":  5,
    "intent.weight.booking_start":       8,
    "intent.weight.payment_fail":       10,
}

DEFAULT_THRESHOLDS: dict[str, int] = {
    "intent.threshold_medium": 5,
    "intent.threshold_high":   15,
    "intent.threshold_hot":    30,
}


@dataclass
class ScoreResult:
    raw_score: int
    level: IntentLevel
    contributing_events: int
    has_booking_started: bool
    has_payment_failed: bool
    has_booking_completed: bool


def _w(config: dict[str, Any], key: str) -> int:
    """Get a configured weight, falling back to the built-in default."""
    val = config.get(key)
    if val is None:
        return DEFAULT_WEIGHTS.get(key, 0)
    try:
        return int(val)
    except (TypeError, ValueError):
        return DEFAULT_WEIGHTS.get(key, 0)


def _t(config: dict[str, Any], key: str) -> int:
    val = config.get(key)
    if val is None:
        return DEFAULT_THRESHOLDS.get(key, 0)
    try:
        return int(val)
    except (TypeError, ValueError):
        return DEFAULT_THRESHOLDS.get(key, 0)


def weight_for_event(event: UserEvent, config: dict[str, Any]) -> int:
    """Pick the right weight for one event row.

    Dispatch is by `event_name` first (most specific) then falls back to
    `event_category`. Returns 0 for events that don't contribute to intent
    (NOTIFICATION, CANCELLATION, REFUND, SYSTEM).
    """
    name = (event.event_name or "").lower()
    if name == "payment.failed" or name == "payment.abandoned":
        return _w(config, "intent.weight.payment_fail")
    if name.startswith("booking.start"):
        return _w(config, "intent.weight.booking_start")
    if name == "check.availability" or "availability" in name:
        return _w(config, "intent.weight.availability_check")
    if name.startswith("compare"):
        return _w(config, "intent.weight.compare")
    if name.startswith("contact"):
        return _w(config, "intent.weight.contact")

    cat = event.event_category
    if cat == EventCategory.SEARCH:
        return _w(config, "intent.weight.search")
    if cat == EventCategory.VIEW:
        return _w(config, "intent.weight.view")
    if cat == EventCategory.FILTER:
        return _w(config, "intent.weight.filter")
    if cat == EventCategory.SAVE:
        return _w(config, "intent.weight.save")
    if cat == EventCategory.COMPARE:
        return _w(config, "intent.weight.compare")
    if cat == EventCategory.CONTACT:
        return _w(config, "intent.weight.contact")

    return 0


def classify(
    raw_score: int,
    *,
    has_booking_started: bool,
    has_payment_failed: bool,
    has_booking_completed: bool,
    config: dict[str, Any],
) -> IntentLevel:
    """Map raw score + special triggers to an IntentLevel.

    Hot-lead triggers take precedence over score thresholds: someone who
    abandoned payment is a hot lead even if their raw score is low.
    """
    if has_booking_completed:
        # Converted: reset to LOW until they exhibit fresh intent.
        return IntentLevel.LOW_INTENT
    if has_payment_failed or has_booking_started:
        return IntentLevel.HOT_LEAD

    hot = _t(config, "intent.threshold_hot")
    high = _t(config, "intent.threshold_high")
    medium = _t(config, "intent.threshold_medium")

    if raw_score >= hot:
        return IntentLevel.HOT_LEAD
    if raw_score >= high:
        return IntentLevel.HIGH_INTENT
    if raw_score >= medium:
        return IntentLevel.MEDIUM_INTENT
    return IntentLevel.LOW_INTENT


def score_events(events: Iterable[UserEvent], config: dict[str, Any]) -> ScoreResult:
    """Compute the raw score + classification for an event stream.

    Pure: no DB writes. Caller passes an already-fetched event list and the
    active config dict (from `load_active_config`). The aggregation service
    is what reads from the DB and persists.
    """
    raw = 0
    contributing = 0
    has_booking_started = False
    has_payment_failed = False
    has_booking_completed = False

    for event in events:
        name = (event.event_name or "").lower()
        if name == "booking.completed":
            has_booking_completed = True
            continue                       # completion doesn't add intent points
        if name.startswith("booking.start"):
            has_booking_started = True
        if name in ("payment.failed", "payment.abandoned"):
            has_payment_failed = True

        weight = weight_for_event(event, config)
        if weight > 0:
            raw += weight
            contributing += 1

    level = classify(
        raw,
        has_booking_started=has_booking_started,
        has_payment_failed=has_payment_failed,
        has_booking_completed=has_booking_completed,
        config=config,
    )
    return ScoreResult(
        raw_score=raw,
        level=level,
        contributing_events=contributing,
        has_booking_started=has_booking_started,
        has_payment_failed=has_payment_failed,
        has_booking_completed=has_booking_completed,
    )
