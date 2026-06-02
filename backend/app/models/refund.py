import uuid
from sqlalchemy import Column, String, Float, ForeignKey, DateTime, Enum, Text
from app.database import Base

import enum
from datetime import datetime


class RefundStatus(str, enum.Enum):
    REQUESTED = "REQUESTED"
    UNDER_REVIEW = "UNDER_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    PROCESSED = "PROCESSED"
    FAILED = "FAILED"


class RefundReason(str, enum.Enum):
    BOOKING_CANCELLED = "BOOKING_CANCELLED"
    SEAT_UNAVAILABLE = "SEAT_UNAVAILABLE"
    ADMIN_CORRECTION = "ADMIN_CORRECTION"
    DUPLICATE_PAYMENT = "DUPLICATE_PAYMENT"
    SERVICE_ISSUE = "SERVICE_ISSUE"
    OTHER = "OTHER"


class Refund(Base):
    __tablename__ = "refunds"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    booking_id = Column(String, ForeignKey("bookings.id"), nullable=False)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    amount = Column(Float, nullable=False)
    reason = Column(Enum(RefundReason), default=RefundReason.OTHER)
    reason_text = Column(Text, nullable=True)  # User's description
    status = Column(Enum(RefundStatus), default=RefundStatus.REQUESTED)
    
    # Timestamps
    requested_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    reviewed_at = Column(DateTime, nullable=True)
    processed_at = Column(DateTime, nullable=True)
    
    # Admin tracking
    reviewed_by = Column(String, ForeignKey("users.id"), nullable=True)
    admin_notes = Column(Text, nullable=True)  # Internal notes, not visible to user
    
    # Gateway info (for processed refunds)
    gateway_ref = Column(String, nullable=True)  # Razorpay/Stripe refund ID
