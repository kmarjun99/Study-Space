"""Derived user intelligence profile (Phase 2).

One row per user. Recalculated from the `user_events` firehose by the
profile aggregation service. **Never updated by user input** — this is a
machine-derived view of behavior.

Three groups of fields:
  1. Preference signals (preferred_city, price band, amenities, …)
     derived from repeated SEARCH/FILTER/VIEW events.
  2. Intent score + level — current "how close to booking" snapshot.
  3. Per-user timestamps for the most recent activity of each kind.

All scores are stored as 0.0–1.0 floats so the meaning is consistent across
the codebase. Raw weighted-event totals are not persisted; they're a query
intermediate.
"""
import enum
from datetime import datetime

from sqlalchemy import (
    Column, DateTime, Float, ForeignKey, Integer, String, Text,
    Enum as SAEnum,
)

from app.database import Base


class IntentLevel(str, enum.Enum):
    """Coarse classification of how close the user is to converting.

    Score ranges (driven by config keys `intent.threshold_*`):
      LOW_INTENT     — passive browsing, low signal density
      MEDIUM_INTENT  — repeated searches / views; meaningful interest
      HIGH_INTENT    — saves, comparisons, availability checks
      HOT_LEAD       — booking started; payment may have failed
    """
    LOW_INTENT = "LOW_INTENT"
    MEDIUM_INTENT = "MEDIUM_INTENT"
    HIGH_INTENT = "HIGH_INTENT"
    HOT_LEAD = "HOT_LEAD"


class UserIntelligenceProfile(Base):
    __tablename__ = "user_intelligence_profiles"

    user_id = Column(String, ForeignKey("users.id"), primary_key=True)

    # ---- preference signals (JSON for lists; scalars otherwise) ----
    preferred_city = Column(String(80), nullable=True)
    preferred_locations_json = Column(Text, nullable=True)         # JSON list of strings
    preferred_property_types_json = Column(Text, nullable=True)    # JSON list
    preferred_price_min = Column(Float, nullable=True)
    preferred_price_max = Column(Float, nullable=True)
    preferred_amenities_json = Column(Text, nullable=True)         # JSON list
    preferred_study_time = Column(String(40), nullable=True)        # 'morning' / 'evening' / null

    # ---- intent / behavior scores (0.0–1.0) ----
    booking_urgency_score = Column(Float, nullable=False, default=0.0)
    budget_sensitivity_score = Column(Float, nullable=False, default=0.0)
    location_sensitivity_score = Column(Float, nullable=False, default=0.0)
    premium_interest_score = Column(Float, nullable=False, default=0.0)
    cancellation_risk_score = Column(Float, nullable=False, default=0.0)
    conversion_probability_score = Column(Float, nullable=False, default=0.0)

    # ---- current intent snapshot ----
    raw_intent_score = Column(Integer, nullable=False, default=0)   # un-normalized weighted total
    intent_level = Column(
        SAEnum(IntentLevel, native_enum=False),
        nullable=False, default=IntentLevel.LOW_INTENT,
    )

    # ---- recency ----
    last_active_at = Column(DateTime, nullable=True)
    last_search_query = Column(String(255), nullable=True)
    last_viewed_listing_id = Column(String, nullable=True)
    last_booking_attempt_at = Column(DateTime, nullable=True)
    last_successful_booking_at = Column(DateTime, nullable=True)

    # ---- confidence ----
    # Goes up with event count and event diversity; saturates near 1.0.
    profile_confidence_score = Column(Float, nullable=False, default=0.0)
    event_count = Column(Integer, nullable=False, default=0)

    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False,
    )
