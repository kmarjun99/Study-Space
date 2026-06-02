"""Campaign + CampaignDelivery models (Phase 4B).

A `Campaign` is an admin-defined outreach targeting a `UserSegment`. Each
delivery to one user produces one `CampaignDelivery` row, which threads the
funnel: QUEUED → DELIVERED → OPENED → CLICKED → CONVERTED (stamps a
booking_id when attributed).

Hard rules enforced at the service layer:
  - Consent gate per channel (marketing for IN_APP/EMAIL/PUSH, WhatsApp for WHATSAPP)
  - Cooldown: same user × same campaign cannot deliver again within
    `cooldown_hours`
  - Frequency cap: across ALL campaigns a user can receive at most
    `frequency_cap_per_user` deliveries in `frequency_cap_window_days`
  - Skipped deliveries get a status (SKIPPED_*) + reason for auditability

Attribution: when a booking confirms, find the most recent CLICKED delivery
for that user within `campaigns.attribution_window_days` and stamp it.
"""
import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean, Column, DateTime, Enum, ForeignKey, Index, Integer, String, Text,
)

from app.database import Base


class CampaignStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"


class CampaignChannel(str, enum.Enum):
    IN_APP = "IN_APP"
    EMAIL = "EMAIL"
    PUSH = "PUSH"
    WHATSAPP = "WHATSAPP"


class DeliveryStatus(str, enum.Enum):
    QUEUED = "QUEUED"
    DELIVERED = "DELIVERED"
    FAILED = "FAILED"
    SKIPPED_COOLDOWN = "SKIPPED_COOLDOWN"
    SKIPPED_FREQUENCY = "SKIPPED_FREQUENCY"
    SKIPPED_CONSENT = "SKIPPED_CONSENT"


class Campaign(Base):
    __tablename__ = "campaigns"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    slug = Column(String(80), nullable=False, unique=True, index=True)
    name = Column(String(120), nullable=False)
    description = Column(Text, nullable=True)
    body_template = Column(Text, nullable=False)        # message text / template

    # Targeting
    segment_id = Column(String, ForeignKey("user_segments.id"), nullable=False)

    # Delivery
    channel = Column(Enum(CampaignChannel, native_enum=False), nullable=False)
    status = Column(
        Enum(CampaignStatus, native_enum=False),
        nullable=False, default=CampaignStatus.DRAFT,
    )

    # Throttling
    cooldown_hours = Column(Integer, nullable=False, default=24)
    frequency_cap_per_user = Column(Integer, nullable=False, default=3)
    frequency_cap_window_days = Column(Integer, nullable=False, default=7)

    # Optional time window
    send_window_starts = Column(DateTime, nullable=True)
    send_window_ends = Column(DateTime, nullable=True)

    created_by = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False,
    )


class CampaignDelivery(Base):
    __tablename__ = "campaign_deliveries"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    # One of campaign_id / notification_rule_id is set (XOR enforced at service layer).
    # Campaign-driven deliveries originate from Phase 4B; rule-driven ones from Phase 4C.
    campaign_id = Column(String, ForeignKey("campaigns.id"),
                         nullable=True, index=True)
    notification_rule_id = Column(
        String, ForeignKey("notification_rules.id"),
        nullable=True, index=True,
    )
    user_id = Column(String, ForeignKey("users.id"),
                     nullable=False, index=True)

    channel = Column(Enum(CampaignChannel, native_enum=False), nullable=False)
    status = Column(
        Enum(DeliveryStatus, native_enum=False),
        nullable=False, default=DeliveryStatus.QUEUED,
    )

    # Funnel timestamps — null until each step happens
    queued_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    delivered_at = Column(DateTime, nullable=True)
    opened_at = Column(DateTime, nullable=True)
    clicked_at = Column(DateTime, nullable=True)
    converted_at = Column(DateTime, nullable=True)
    converted_booking_id = Column(String, ForeignKey("bookings.id"), nullable=True)

    # Why a SKIPPED_* delivery skipped, or why a FAILED delivery failed.
    reason = Column(Text, nullable=True)
    is_personalized = Column(Boolean, nullable=False, default=False)

    # Number of dispatch attempts made. Transient failures (e.g. SMTP errors)
    # leave the row QUEUED for the next tick to retry, up to a bounded max;
    # permanent failures (no email, unconfigured channel) go straight to FAILED.
    dispatch_attempts = Column(Integer, nullable=False, default=0, server_default="0")

    __table_args__ = (
        Index("ix_camp_deliv_campaign_user",
              "campaign_id", "user_id", "queued_at"),
        Index("ix_camp_deliv_user_status",
              "user_id", "status", "delivered_at"),
        Index("ix_camp_deliv_user_clicked", "user_id", "clicked_at"),
    )
