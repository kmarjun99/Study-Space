"""Settlement run + line items.

A `SettlementRun` is one per (owner, period). Its `SettlementLine` rows
itemize the bookings included plus any deductions applied (TCS, TDS,
maintenance fees offset, refunds).

The unique constraint on (owner_id, period_start, period_end) prevents
duplicate runs for the same window — the daily cron is therefore idempotent.
"""
import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Column, String, ForeignKey, DateTime, Numeric, Enum, UniqueConstraint, Text,
)

from app.database import Base


class SettlementStatus(str, enum.Enum):
    DRAFT = "DRAFT"               # accumulating
    READY = "READY"               # totals frozen, awaiting payout
    PAID = "PAID"                 # RazorpayX UTR captured
    FAILED = "FAILED"             # payout attempt failed
    NEGATIVE_HELD = "NEGATIVE_HELD"  # refunds + deductions > collections


class SettlementLineKind(str, enum.Enum):
    BOOKING = "BOOKING"                   # owner-payable from a paid booking
    REFUND = "REFUND"                     # debit against owner payable
    TCS_CGST = "TCS_CGST"
    TCS_SGST = "TCS_SGST"
    TCS_IGST = "TCS_IGST"
    TDS_194O = "TDS_194O"
    MAINTENANCE_OFFSET = "MAINTENANCE_OFFSET"  # unpaid maintenance fee offset against payable
    ADJUSTMENT = "ADJUSTMENT"             # super-admin override


class SettlementRun(Base):
    __tablename__ = "settlement_runs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    owner_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)

    period_start = Column(DateTime, nullable=False)
    period_end = Column(DateTime, nullable=False)

    gross = Column(Numeric(14, 2), nullable=False, default=0)            # Σ booking owner-payable
    refunds = Column(Numeric(14, 2), nullable=False, default=0)
    platform_offset = Column(Numeric(14, 2), nullable=False, default=0)  # maintenance fee deducted
    tcs_total = Column(Numeric(14, 2), nullable=False, default=0)
    tds_total = Column(Numeric(14, 2), nullable=False, default=0)
    net_payout = Column(Numeric(14, 2), nullable=False, default=0)

    status = Column(Enum(SettlementStatus, native_enum=False),
                    nullable=False, default=SettlementStatus.DRAFT)

    payout_ref = Column(String, nullable=True)        # RazorpayX UTR / payout id
    payout_at = Column(DateTime, nullable=True)
    failure_reason = Column(Text, nullable=True)

    statement_invoice_id = Column(String, ForeignKey("invoices.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("owner_id", "period_start", "period_end",
                         name="uq_settlement_run_window"),
    )


class SettlementLine(Base):
    __tablename__ = "settlement_lines"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    run_id = Column(String, ForeignKey("settlement_runs.id"), nullable=False, index=True)
    kind = Column(Enum(SettlementLineKind, native_enum=False), nullable=False)

    # Reference: booking_id for BOOKING/REFUND, owner_charge_id for MAINTENANCE_OFFSET, etc.
    reference_type = Column(String(30), nullable=True)
    reference_id = Column(String, nullable=True, index=True)

    base_amount = Column(Numeric(12, 2), nullable=False, default=0)   # gross before deductions
    deduction = Column(Numeric(12, 2), nullable=False, default=0)     # amount subtracted from net
    net = Column(Numeric(12, 2), nullable=False, default=0)           # base - deduction
    narration = Column(String(255), nullable=True)
