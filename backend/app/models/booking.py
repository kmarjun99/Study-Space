import uuid
from sqlalchemy import Column, String, Float, ForeignKey, DateTime, Enum, Numeric
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


class GSTTreatment(str, enum.Enum):
    OWNER_REGISTERED = "OWNER_REGISTERED"   # Owner-issued tax invoice with owner GSTIN
    SEC_9_5 = "SEC_9_5"                     # Platform is deemed supplier; ECO tax invoice
    EXEMPT = "EXEMPT"                       # Supply is GST-exempt (e.g., residential dwelling)
    NOT_REGISTERED = "NOT_REGISTERED"       # Owner unregistered + not under Sec 9(5)
    LEGACY = "LEGACY"                       # Pre-accounting booking, backfilled
    NOT_COMPUTED = "NOT_COMPUTED"           # Accounting was off when booking was paid


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

    # Booking Duration Type (NEW)
    # Stores which duration was used: "1_DAY", "1_WEEK", "1_MONTH", "3_MONTHS", "6_MONTHS"
    duration_type = Column(String, nullable=True, default='1_MONTH')

    # ---- Tax breakdown (additive; null = legacy / accounting was off) ----
    # `amount` remains the GST-inclusive gross actually paid by the student.
    # Reverse-calc populates the splits below at payment-verify time.
    base_amount = Column(Numeric(12, 2), nullable=True)
    gst_amount = Column(Numeric(12, 2), nullable=True)
    gst_rate_applied = Column(Numeric(5, 4), nullable=True)
    gst_treatment = Column(
        Enum(GSTTreatment, native_enum=False),
        nullable=True,
        default=None,
    )
    place_of_supply_state = Column(String(2), nullable=True)
    frozen_tax_snapshot_id = Column(String, ForeignKey("tax_snapshots.id"), nullable=True)

    # Settlement bookkeeping (populated by settlement engine)
    paid_at = Column(DateTime, nullable=True)
    settled_at = Column(DateTime, nullable=True)
    settlement_run_id = Column(String, ForeignKey("settlement_runs.id"), nullable=True)

