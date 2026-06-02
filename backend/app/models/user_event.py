"""User behavioral event — append-only firehose.

Foundation of the intelligence layer. Every meaningful user action lands here.
Downstream phases (profile aggregation, intent scoring, segmentation,
recommendations) read from this table; they do NOT write back to it.

Hard rules:
  - Append-only. No UPDATE / no DELETE except in response to a user
    right-to-erasure request (handled by event_tracking_service.delete_user_events).
  - `event_id` is client-supplied for idempotency. Duplicate POSTs of the
    same `event_id` are silently dropped (return 200 OK without re-insert).
  - `metadata` is free-form JSON. Schema discipline lives in the service
    layer (event_tracking_service validates known event_names).
"""
import enum
import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Index, String, Text, Enum

from app.database import Base


class EventCategory(str, enum.Enum):
    SEARCH = "SEARCH"
    VIEW = "VIEW"
    FILTER = "FILTER"
    INTENT = "INTENT"
    BOOKING = "BOOKING"
    PAYMENT = "PAYMENT"
    SAVE = "SAVE"
    COMPARE = "COMPARE"
    CONTACT = "CONTACT"
    AD = "AD"
    NOTIFICATION = "NOTIFICATION"
    CANCELLATION = "CANCELLATION"
    REFUND = "REFUND"
    # Internal — for events fired by the platform itself (not user-initiated).
    SYSTEM = "SYSTEM"


class EventEntityType(str, enum.Enum):
    READING_ROOM = "reading_room"
    CABIN = "cabin"
    ACCOMMODATION = "accommodation"
    OFFER = "offer"
    SEARCH = "search"
    BOOKING = "booking"
    AD = "ad"
    NOTIFICATION = "notification"
    REFUND = "refund"


class UserEvent(Base):
    __tablename__ = "user_events"

    # Server-side primary key. Independent of event_id so we can have
    # well-formed UUID indexing even when clients send opaque idempotency keys.
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    # Client-supplied idempotency key. Unique across all events. Duplicate
    # POSTs are dropped at the service layer.
    event_id = Column(String(80), nullable=False, unique=True, index=True)

    # Either a real user (post-login) or an anonymous browser session. Both
    # can be null only for SYSTEM events.
    user_id = Column(String, ForeignKey("users.id"), nullable=True, index=True)
    anonymous_session_id = Column(String(80), nullable=True, index=True)

    # Event identity
    event_name = Column(String(80), nullable=False, index=True)
    event_category = Column(
        Enum(EventCategory, native_enum=False), nullable=False, index=True,
    )

    # Target of the event (optional — search events have no entity)
    entity_type = Column(Enum(EventEntityType, native_enum=False), nullable=True)
    entity_id = Column(String, nullable=True, index=True)

    # Free-form JSON for event-specific fields. Keep small (< 4KB).
    metadata_json = Column(Text, nullable=True)

    # Client context
    device_type = Column(String(20), nullable=True)
    platform = Column(String(10), nullable=True)
    source_page = Column(String(255), nullable=True)
    referrer = Column(String(255), nullable=True)
    city = Column(String(80), nullable=True, index=True)
    location_query = Column(String(255), nullable=True)

    # Indexed for time-bucket aggregation queries in Phase 2.
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    __table_args__ = (
        # Common query patterns: user activity stream, anonymous funnel, entity heat.
        Index("ix_user_events_user_created", "user_id", "created_at"),
        Index("ix_user_events_anon_created", "anonymous_session_id", "created_at"),
        Index("ix_user_events_entity_created", "entity_type", "entity_id", "created_at"),
        Index("ix_user_events_category_created", "event_category", "created_at"),
    )
