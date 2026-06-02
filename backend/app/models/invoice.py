"""
Invoice Model - Stores generated invoice records.

GST-aware extension: each invoice now belongs to a doc_type-specific series
(PLATFORM_TAX_INVOICE / OWNER_TAX_INVOICE / ECO_TAX_INVOICE / NON_GST_RECEIPT /
CREDIT_NOTE / SETTLEMENT_STATEMENT / LEGACY) and carries a CGST/SGST/IGST split.

Legacy rows pre-dating this change have `doc_type='LEGACY'` and the original
free-form `invoice_number` preserved.
"""
import enum
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Float, ForeignKey, DateTime, Integer, Numeric, Text, Enum, Index
from app.database import Base


class InvoiceDocType(str, enum.Enum):
    PLATFORM_TAX_INVOICE = "PLATFORM_TAX_INVOICE"
    OWNER_TAX_INVOICE = "OWNER_TAX_INVOICE"
    ECO_TAX_INVOICE = "ECO_TAX_INVOICE"
    NON_GST_RECEIPT = "NON_GST_RECEIPT"
    CREDIT_NOTE = "CREDIT_NOTE"
    SETTLEMENT_STATEMENT = "SETTLEMENT_STATEMENT"
    LEGACY = "LEGACY"


class Invoice(Base):
    """
    Stores invoice records for successful payments.
    New series numbers: SS/{series_code}/{fiscal_year}/{NNNNNN}
    Legacy rows keep their original SS-INV-YYYY-NNNNNN.
    """
    __tablename__ = "invoices"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    invoice_number = Column(String, unique=True, nullable=False, index=True)

    # References
    booking_id = Column(String, ForeignKey("bookings.id"), nullable=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    payment_id = Column(String, ForeignKey("payment_transactions.id"), nullable=True)
    owner_charge_id = Column(String, ForeignKey("owner_charges.id"), nullable=True)

    # Invoice details (Float kept for backward compatibility with legacy rows)
    amount = Column(Float, nullable=False)
    tax_amount = Column(Float, default=0.0)
    total_amount = Column(Float, nullable=False)

    # Venue info (denormalized for invoice permanence)
    venue_name = Column(String, nullable=False)
    venue_address = Column(String, nullable=True)
    seat_details = Column(String, nullable=True)  # e.g., "Cabin A12, Floor 2"

    # Duration
    plan_duration = Column(String, nullable=True)  # e.g., "1 Month"
    start_date = Column(DateTime, nullable=True)
    end_date = Column(DateTime, nullable=True)

    # Timestamps
    generated_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # ---- GST / series fields (additive; null on legacy rows) ----
    doc_type = Column(Enum(InvoiceDocType, native_enum=False),
                      nullable=False, default=InvoiceDocType.LEGACY)
    series_code = Column(String(10), nullable=True)            # PLF / OBI / ECO / RCT / CN / STM
    fiscal_year = Column(String(7), nullable=True)             # e.g., '25-26'
    sequence_no = Column(Integer, nullable=True)

    supplier_party_id = Column(String, ForeignKey("parties.id"), nullable=True)
    recipient_party_id = Column(String, ForeignKey("parties.id"), nullable=True)

    place_of_supply_state = Column(String(2), nullable=True)
    cgst = Column(Numeric(12, 2), nullable=True)
    sgst = Column(Numeric(12, 2), nullable=True)
    igst = Column(Numeric(12, 2), nullable=True)
    cess = Column(Numeric(12, 2), nullable=True)
    base_amount = Column(Numeric(12, 2), nullable=True)         # taxable value (gross less GST)

    hsn_sac = Column(String(10), nullable=True)
    irn = Column(String(64), nullable=True)                     # for future e-invoicing
    qr_payload = Column(Text, nullable=True)

    tax_snapshot_id = Column(String, ForeignKey("tax_snapshots.id"), nullable=True)

    __table_args__ = (
        Index("ix_invoice_series_seq", "series_code", "fiscal_year", "sequence_no", unique=True),
        # Partial unique on owner_charge_id (where not null) — belt-and-braces
        # alongside the SELECT FOR UPDATE in mark_charge_paid. If two callers
        # ever do race past the lock, this catches the second writer at the
        # database layer rather than silently double-billing the owner.
        Index(
            "ux_invoice_owner_charge_not_null",
            "owner_charge_id",
            unique=True,
            postgresql_where=Column("owner_charge_id").isnot(None),
            sqlite_where=Column("owner_charge_id").isnot(None),
        ),
    )


def generate_invoice_number() -> str:
    """Legacy helper kept for backward compatibility with existing callers.

    New code MUST go through `app.services.invoice_series_service.next_number`
    which uses an atomic counter and produces collision-free series numbers.
    """
    year = datetime.utcnow().year
    timestamp = int(datetime.utcnow().timestamp() * 1000) % 1000000
    return f"SS-INV-{year}-{timestamp:06d}"
