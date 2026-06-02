"""Admin-defined audience segments.

A segment is a named rule. Super-admin picks a `rule_type` (e.g.,
HIGH_INTENT, BUDGET_BAND) and provides `rule_config` JSON with the rule's
parameters (e.g., `{"max_price": 3000}` for BUDGET_BAND).

`UserSegmentMembership` rows record which users are currently in each segment
(plus history via `entered_at` / `exited_at`). Membership is recomputed
nightly by the segment service.

Phase 4B (campaigns) will join campaigns -> segment_id; Phase 4C
(notifications) will join notification_rules -> segment_id.
"""
import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean, Column, DateTime, Enum, Float, ForeignKey, Index, String, Text,
    UniqueConstraint,
)

from app.database import Base


class SegmentRuleType(str, enum.Enum):
    """Which predicate evaluates this segment.

    The dispatcher in segment_service maps this enum to a callable that
    reads (profile, recent_events, rule_config) and returns
    (matches: bool, score: float, reason: str).
    """
    HIGH_INTENT = "HIGH_INTENT"
    BUDGET_BAND = "BUDGET_BAND"
    CITY_INTEREST = "CITY_INTEREST"
    AMENITY_INTEREST = "AMENITY_INTEREST"
    PAYMENT_ABANDONED = "PAYMENT_ABANDONED"
    REPEAT_SEARCH_NO_BOOKING = "REPEAT_SEARCH_NO_BOOKING"
    CANCELLED_USERS = "CANCELLED_USERS"


class UserSegment(Base):
    __tablename__ = "user_segments"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    # Human-readable identifiers
    slug = Column(String(80), nullable=False, unique=True, index=True)
    name = Column(String(120), nullable=False)
    description = Column(Text, nullable=True)

    # Rule definition
    rule_type = Column(Enum(SegmentRuleType, native_enum=False), nullable=False)
    rule_config_json = Column(Text, nullable=True)   # JSON-encoded {key: value}

    # Lifecycle
    is_active = Column(Boolean, nullable=False, default=True)
    created_by = Column(String, nullable=True)       # super-admin user id
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False,
    )


class UserSegmentMembership(Base):
    __tablename__ = "user_segment_memberships"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    segment_id = Column(String, ForeignKey("user_segments.id"), nullable=False, index=True)

    # When the user first matched the rule (most recent entry)
    entered_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    # When they stopped matching. Null while currently in the segment.
    exited_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)

    # Score from the predicate (e.g., higher for hotter intent)
    score = Column(Float, nullable=False, default=0.0)
    # Human-readable explanation of WHY they matched ("intent=HOT_LEAD; raw=42")
    reason = Column(Text, nullable=True)

    __table_args__ = (
        # A user can only be ACTIVELY in a segment once. History rows
        # (exited_at IS NOT NULL) can repeat for the same (user, segment)
        # as the user enters and leaves.
        UniqueConstraint(
            "user_id", "segment_id", "entered_at",
            name="uq_segment_membership_entry",
        ),
        Index("ix_segment_membership_segment_active",
              "segment_id", "is_active"),
        Index("ix_segment_membership_user_active",
              "user_id", "is_active"),
    )
