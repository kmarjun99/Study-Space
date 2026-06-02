"""Intent scoring tests — pure functions, no DB.

Contracts:
  - Each event category contributes its configured weight
  - Unknown / non-contributing events score 0
  - Booking-start forces HOT_LEAD regardless of raw score
  - Payment-failed forces HOT_LEAD
  - Booking-completed resets to LOW_INTENT (intent satisfied)
  - Classification respects configured thresholds
  - Config overrides built-in defaults
"""
from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

import pytest

from app.models.user_event import EventCategory
from app.models.user_intelligence_profile import IntentLevel
from app.services.intent_scoring_service import (
    DEFAULT_THRESHOLDS, DEFAULT_WEIGHTS, classify, score_events, weight_for_event,
)


def _event(*, name: str, category: EventCategory, when=None):
    """Lightweight stand-in for UserEvent — scoring is read-only."""
    return SimpleNamespace(
        event_name=name,
        event_category=category,
        created_at=when or datetime.utcnow(),
    )


# ---------- weight_for_event ---------------------------------------------

def test_search_uses_default_weight():
    e = _event(name="search.location", category=EventCategory.SEARCH)
    assert weight_for_event(e, config={}) == DEFAULT_WEIGHTS["intent.weight.search"]


def test_payment_failed_picks_named_weight():
    e = _event(name="payment.failed", category=EventCategory.PAYMENT)
    assert weight_for_event(e, config={}) == DEFAULT_WEIGHTS["intent.weight.payment_fail"]


def test_availability_check_picks_specific_weight():
    e = _event(name="check.availability", category=EventCategory.INTENT)
    assert weight_for_event(e, config={}) == DEFAULT_WEIGHTS["intent.weight.availability_check"]


def test_booking_start_picks_specific_weight():
    e = _event(name="booking.start.cabin", category=EventCategory.BOOKING)
    assert weight_for_event(e, config={}) == DEFAULT_WEIGHTS["intent.weight.booking_start"]


def test_zero_weight_for_non_contributing_categories():
    for cat in (EventCategory.NOTIFICATION, EventCategory.CANCELLATION,
                EventCategory.REFUND, EventCategory.SYSTEM):
        e = _event(name="x", category=cat)
        assert weight_for_event(e, config={}) == 0


def test_config_overrides_default_weight():
    config = {"intent.weight.search": 7}
    e = _event(name="search.location", category=EventCategory.SEARCH)
    assert weight_for_event(e, config=config) == 7


# ---------- classify ------------------------------------------------------

def test_classify_low_intent_for_zero_score():
    out = classify(0, has_booking_started=False,
                   has_payment_failed=False, has_booking_completed=False,
                   config={})
    assert out == IntentLevel.LOW_INTENT


def test_classify_medium_at_threshold():
    out = classify(DEFAULT_THRESHOLDS["intent.threshold_medium"],
                   has_booking_started=False, has_payment_failed=False,
                   has_booking_completed=False, config={})
    assert out == IntentLevel.MEDIUM_INTENT


def test_classify_high_at_threshold():
    out = classify(DEFAULT_THRESHOLDS["intent.threshold_high"],
                   has_booking_started=False, has_payment_failed=False,
                   has_booking_completed=False, config={})
    assert out == IntentLevel.HIGH_INTENT


def test_classify_hot_at_threshold():
    out = classify(DEFAULT_THRESHOLDS["intent.threshold_hot"],
                   has_booking_started=False, has_payment_failed=False,
                   has_booking_completed=False, config={})
    assert out == IntentLevel.HOT_LEAD


def test_booking_started_forces_hot_lead():
    """A user who started booking is hot regardless of score."""
    out = classify(1, has_booking_started=True,
                   has_payment_failed=False, has_booking_completed=False,
                   config={})
    assert out == IntentLevel.HOT_LEAD


def test_payment_failed_forces_hot_lead():
    out = classify(1, has_booking_started=False,
                   has_payment_failed=True, has_booking_completed=False,
                   config={})
    assert out == IntentLevel.HOT_LEAD


def test_booking_completed_resets_to_low():
    """A user who completed booking has satisfied intent — reset."""
    out = classify(50, has_booking_started=True,
                   has_payment_failed=True, has_booking_completed=True,
                   config={})
    assert out == IntentLevel.LOW_INTENT


def test_config_overrides_thresholds():
    """Override all three thresholds so they form a consistent ladder."""
    config = {
        "intent.threshold_medium": 100,
        "intent.threshold_high":   200,
        "intent.threshold_hot":    500,
    }
    # 99 < 100 -> LOW
    out = classify(99, has_booking_started=False,
                   has_payment_failed=False, has_booking_completed=False,
                   config=config)
    assert out == IntentLevel.LOW_INTENT
    # 100 hits the new MEDIUM threshold exactly
    out = classify(100, has_booking_started=False,
                   has_payment_failed=False, has_booking_completed=False,
                   config=config)
    assert out == IntentLevel.MEDIUM_INTENT


# ---------- score_events -------------------------------------------------

def test_score_events_sums_correctly():
    events = [
        _event(name="search.location", category=EventCategory.SEARCH),
        _event(name="search.location", category=EventCategory.SEARCH),
        _event(name="view.reading_room", category=EventCategory.VIEW),
        _event(name="save", category=EventCategory.SAVE),
    ]
    result = score_events(events, config={})
    # 1+1+2+4 = 8
    assert result.raw_score == 8
    assert result.contributing_events == 4
    assert result.level == IntentLevel.MEDIUM_INTENT
    assert not result.has_booking_started
    assert not result.has_payment_failed


def test_score_events_detects_booking_start():
    events = [
        _event(name="view.reading_room", category=EventCategory.VIEW),
        _event(name="booking.start", category=EventCategory.BOOKING),
    ]
    result = score_events(events, config={})
    assert result.has_booking_started is True
    assert result.level == IntentLevel.HOT_LEAD


def test_score_events_detects_payment_fail():
    events = [_event(name="payment.failed", category=EventCategory.PAYMENT)]
    result = score_events(events, config={})
    assert result.has_payment_failed is True
    assert result.level == IntentLevel.HOT_LEAD


def test_score_events_with_booking_completed_resets_level():
    events = [
        _event(name="booking.start", category=EventCategory.BOOKING),
        _event(name="payment.failed", category=EventCategory.PAYMENT),
        _event(name="booking.completed", category=EventCategory.BOOKING),
    ]
    result = score_events(events, config={})
    assert result.has_booking_completed is True
    # Even with booking_start + payment_failed, completion wins.
    assert result.level == IntentLevel.LOW_INTENT


def test_score_events_empty_stream():
    result = score_events([], config={})
    assert result.raw_score == 0
    assert result.contributing_events == 0
    assert result.level == IntentLevel.LOW_INTENT


def test_non_contributing_events_dont_count_as_contributing():
    events = [
        _event(name="x", category=EventCategory.NOTIFICATION),
        _event(name="x", category=EventCategory.SYSTEM),
        _event(name="view", category=EventCategory.VIEW),
    ]
    result = score_events(events, config={})
    assert result.contributing_events == 1
    assert result.raw_score == DEFAULT_WEIGHTS["intent.weight.view"]
