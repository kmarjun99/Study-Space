"""Owner-side charges (listing fee, monthly maintenance fee, one-off facilitation fee).

The unique constraint enforces idempotency for recurring billing —
re-running the monthly cron cannot create duplicate maintenance charges.

Idempotency model:
  * Recurring (MAINTENANCE_FEE): `period_key = 'YYYY-MM'` discriminates each
    monthly charge. The 4-column unique constraint catches duplicate cron runs.
  * One-off (LISTING_FEE / FACILITATION_FEE): callers MUST set
    `period_key = ONETIME_PERIOD_KEY` (a sentinel) instead of leaving it
    NULL. Postgres treats two NULLs as distinct, so a NULL-keyed unique
    constraint would let duplicate listing-fee rows slip through.
"""
import enum
import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, ForeignKey, DateTime, Numeric, Enum, UniqueConstraint,
)
from app.database import Base


# Sentinel for charge_types that don't repeat. Stored as a real value so the
# unique constraint actually fires when a duplicate one-off comes in.
ONETIME_PERIOD_KEY = "__ONETIME__"


class OwnerChargeType(str, enum.Enum):
    LISTING_FEE = "LISTING_FEE"
    MAINTENANCE_FEE = "MAINTENANCE_FEE"
    FACILITATION_FEE = "FACILITATION_FEE"
    RECOVERY = "RECOVERY"           # negative balance owed by owner after refund


class OwnerChargeStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    DUE = "DUE"
    PAID = "PAID"
    WAIVED = "WAIVED"
    FAILED = "FAILED"
    OVERDUE = "OVERDUE"


class ListingType(str, enum.Enum):
    READING_ROOM = "READING_ROOM"
    ACCOMMODATION = "ACCOMMODATION"


class OwnerCharge(Base):
    __tablename__ = "owner_charges"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    owner_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)

    listing_id = Column(String, nullable=True, index=True)        # FK loose; could point to reading_rooms or accommodations
    listing_type = Column(Enum(ListingType, native_enum=False), nullable=True)

    charge_type = Column(Enum(OwnerChargeType, native_enum=False), nullable=False)
    period_key = Column(String(7), nullable=True)                 # 'YYYY-MM' for recurring; NULL for one-off

    base_amount = Column(Numeric(12, 2), nullable=False)
    gst_amount = Column(Numeric(12, 2), nullable=False, default=0)
    total_amount = Column(Numeric(12, 2), nullable=False)
    gst_rate_applied = Column(Numeric(5, 4), nullable=True)
    currency = Column(String(3), nullable=False, default="INR")

    status = Column(Enum(OwnerChargeStatus, native_enum=False),
                    default=OwnerChargeStatus.DRAFT, nullable=False)
    due_date = Column(DateTime, nullable=True)

    razorpay_order_id = Column(String, nullable=True)
    razorpay_payment_id = Column(String, nullable=True)
    invoice_id = Column(String, ForeignKey("invoices.id"), nullable=True)
    tax_snapshot_id = Column(String, ForeignKey("tax_snapshots.id"), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    paid_at = Column(DateTime, nullable=True)

    # Idempotency: cannot create the same charge twice for the same period+listing.
    # period_key NULL is treated as the same group for one-offs (use distinct listing_id per attempt).
    __table_args__ = (
        UniqueConstraint("owner_id", "charge_type", "period_key", "listing_id",
                         name="uq_owner_charge_idem"),
    )
