import uuid
from sqlalchemy import Column, String, Float, ForeignKey, DateTime, Enum
from app.database import Base

import enum
from datetime import datetime


class PaymentMethod(str, enum.Enum):
    UPI = "UPI"
    CARD = "CARD"
    NET_BANKING = "NET_BANKING"
    WALLET = "WALLET"


class PaymentGateway(str, enum.Enum):
    RAZORPAY = "RAZORPAY"
    STRIPE = "STRIPE"
    PAYTM = "PAYTM"
    MANUAL = "MANUAL"  # For admin-initiated or offline payments


class PaymentType(str, enum.Enum):
    """Type of payment transaction"""
    INITIAL = "INITIAL"      # First payment when booking is created
    EXTENSION = "EXTENSION"  # Payment for extending the booking
    REFUND = "REFUND"        # Refund payment (negative)


class PaymentTransaction(Base):
    """
    Records each payment transaction for auditing and history.
    Each booking can have multiple payments (initial + extensions).
    """
    __tablename__ = "payment_transactions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    booking_id = Column(String, ForeignKey("bookings.id"), nullable=False)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    
    # Payment type (INITIAL, EXTENSION, REFUND)
    payment_type = Column(Enum(PaymentType), default=PaymentType.INITIAL, nullable=False)
    
    # Payment details
    method = Column(Enum(PaymentMethod), nullable=False)
    gateway = Column(Enum(PaymentGateway), default=PaymentGateway.RAZORPAY)
    masked_reference = Column(String, nullable=True)  # e.g., "upi-****@okicici" or "****4242"
    
    # Amount
    amount = Column(Float, nullable=False)
    
    # Gateway reference
    gateway_transaction_id = Column(String, nullable=True)
    
    # Description for extensions
    description = Column(String, nullable=True)  # e.g., "Plan extended by 3 months"
    
    # Timestamp
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

