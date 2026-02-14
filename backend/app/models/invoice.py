"""
Invoice Model - Stores generated invoice records
"""
import uuid
from sqlalchemy import Column, String, Float, ForeignKey, DateTime, Integer
from app.database import Base
from datetime import datetime


class Invoice(Base):
    """
    Stores invoice records for successful payments.
    Invoice numbers are sequential: SS-INV-YYYY-NNNNNN
    """
    __tablename__ = "invoices"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    invoice_number = Column(String, unique=True, nullable=False, index=True)
    
    # References
    booking_id = Column(String, ForeignKey("bookings.id"), nullable=False)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    payment_id = Column(String, ForeignKey("payment_transactions.id"), nullable=True)
    
    # Invoice details
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


def generate_invoice_number() -> str:
    """Generate sequential invoice number: SS-INV-YYYY-NNNNNN"""
    year = datetime.utcnow().year
    # In production, this should use a DB sequence or atomic counter
    # For now, using timestamp-based unique number
    timestamp = int(datetime.utcnow().timestamp() * 1000) % 1000000
    return f"SS-INV-{year}-{timestamp:06d}"
