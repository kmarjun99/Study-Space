import uuid
from sqlalchemy import Column, String, Float, ForeignKey, DateTime, Enum
from app.database import Base

import enum
from datetime import datetime

class BookingStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"
    HELD = "HELD"  # New status for temporary locks

class PaymentStatus(str, enum.Enum):
    PAID = "PAID"
    PENDING = "PENDING"
    REFUNDED = "REFUNDED"


class SettlementStatus(str, enum.Enum):
    NOT_SETTLED = "NOT_SETTLED"
    SETTLED = "SETTLED"
    ON_HOLD = "ON_HOLD"

class Booking(Base):
    __tablename__ = "bookings"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    cabin_id = Column(String, ForeignKey("cabins.id"), nullable=True)
    accommodation_id = Column(String, ForeignKey("accommodations.id"), nullable=True)
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)  # Added Created At
    amount = Column(Float, nullable=False)
    status = Column(Enum(BookingStatus), default=BookingStatus.ACTIVE)
    expires_at = Column(DateTime, nullable=True)  # Lock expiry
    payment_status = Column(Enum(PaymentStatus), default=PaymentStatus.PENDING)
    transaction_id = Column(String, nullable=True)
    settlement_status = Column(Enum(SettlementStatus), default=SettlementStatus.NOT_SETTLED)

