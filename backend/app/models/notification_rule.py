"""NotificationRule model (Phase 4C — notification automation).

A NotificationRule is an admin-defined trigger-based outreach. Unlike a
Campaign (which targets a static segment on demand), a rule fires
automatically when a user's behavior matches a trigger condition.

Triggers (evaluator lives in notification_automation_service):
  - BOOKING_ABANDONED: user has a recent booking.start event but no
    booking.completed within trigger_window_minutes.
  - REPEAT_SEARCH_NO_BOOKING: ≥ min_event_count SEARCH events in the
    trigger_window_minutes window, no completed bookings.
  - AVAILABILITY_CHECKED_NO_BOOKING: availability check event but no
    booking.completed within trigger_window_minutes.
  - PAYMENT_FAILED: a recent payment.failed event with no later
    booking.completed.

When a trigger matches, the rule writes a CampaignDelivery row pointing at
itself (notification_rule_id set, campaign_id NULL). The dispatcher then
sends through the chosen channel and flips the row to DELIVERED/FAILED.

Throttling reuses the same cooldown + frequency-cap logic as campaigns,
applied against this rule's deliveries (cooldown is rule-scoped; frequency
cap is cross-rule, cross-campaign).
"""
import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean, Column, DateTime, Enum, Integer, String, Text,
)

from app.database import Base
from app.models.campaign import CampaignChannel


class TriggerType(str, enum.Enum):
    BOOKING_ABANDONED = "BOOKING_ABANDONED"
    REPEAT_SEARCH_NO_BOOKING = "REPEAT_SEARCH_NO_BOOKING"
    AVAILABILITY_CHECKED_NO_BOOKING = "AVAILABILITY_CHECKED_NO_BOOKING"
    PAYMENT_FAILED = "PAYMENT_FAILED"


class NotificationRule(Base):
    __tablename__ = "notification_rules"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    slug = Column(String(80), nullable=False, unique=True, index=True)
    name = Column(String(120), nullable=False)
    description = Column(Text, nullable=True)
    body_template = Column(Text, nullable=False)
    subject_template = Column(String(200), nullable=True)

    trigger_type = Column(
        Enum(TriggerType, native_enum=False), nullable=False, index=True,
    )
    # Window the evaluator looks back over (minutes).
    trigger_window_minutes = Column(Integer, nullable=False, default=120)
    # For REPEAT_SEARCH_NO_BOOKING: minimum number of matching events to fire.
    min_event_count = Column(Integer, nullable=False, default=1)

    channel = Column(Enum(CampaignChannel, native_enum=False), nullable=False)

    # Throttling — same semantics as Campaign.
    cooldown_hours = Column(Integer, nullable=False, default=24)
    frequency_cap_per_user = Column(Integer, nullable=False, default=3)
    frequency_cap_window_days = Column(Integer, nullable=False, default=7)

    is_active = Column(Boolean, nullable=False, default=False)
    created_by = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False,
    )
