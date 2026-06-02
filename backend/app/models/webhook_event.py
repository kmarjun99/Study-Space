"""Idempotent webhook intake.

Insert is unique on `(gateway, event_id)`; if a duplicate POST arrives, the
INSERT fails and the handler returns 200 without re-processing.
"""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Text, UniqueConstraint
from app.database import Base


class WebhookEvent(Base):
    __tablename__ = "webhook_events"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    gateway = Column(String(30), nullable=False)        # razorpay, razorpayx, etc.
    event_id = Column(String(120), nullable=False)
    event_type = Column(String(60), nullable=True)
    payload = Column(Text, nullable=False)              # raw JSON
    signature = Column(String(255), nullable=True)
    status = Column(String(20), nullable=False, default="PENDING")  # PENDING / PROCESSED / FAILED
    error = Column(Text, nullable=True)
    received_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    processed_at = Column(DateTime, nullable=True)
    attempts = Column(String(3), nullable=False, default="0")

    __table_args__ = (
        UniqueConstraint("gateway", "event_id", name="uq_webhook_event_id"),
    )
