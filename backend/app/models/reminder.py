import uuid
from datetime import datetime
from sqlalchemy import Column, String, Enum, DateTime, Text, ForeignKey, Boolean
from app.database import Base
import enum


class ReminderStatus(str, enum.Enum):
    PENDING = "pending"
    ACKNOWLEDGED = "acknowledged"
    COMPLETED = "completed"
    EXPIRED = "expired"


class ReminderType(str, enum.Enum):
    PHONE_VERIFICATION = "phone"
    EMAIL_VERIFICATION = "email"
    ADDRESS_VERIFICATION = "address"
    KYC_VERIFICATION = "kyc"
    PROFILE_COMPLETION = "profile"
    DOCUMENT_UPLOAD = "document"


class Reminder(Base):
    """
    Verification reminders sent by Super Admin to Users/Owners.
    Blocks certain actions until resolved.
    """
    __tablename__ = "reminders"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # Target user
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    user_name = Column(String, nullable=True)  # Cached for display
    user_email = Column(String, nullable=True)  # Cached for display
    
    # Reminder details
    reminder_type = Column(Enum(ReminderType), nullable=False)
    missing_fields = Column(String, nullable=True)  # JSON array of missing fields
    message = Column(Text, nullable=True)  # Custom message from admin
    
    # Actor info
    sent_by = Column(String, ForeignKey("users.id"), nullable=False)
    sent_by_name = Column(String, nullable=True)
    
    # Status
    status = Column(Enum(ReminderStatus), default=ReminderStatus.PENDING)
    
    # Blocking behavior
    blocks_listings = Column(Boolean, default=True)  # Blocks venue creation
    blocks_payments = Column(Boolean, default=True)  # Blocks payments
    blocks_bookings = Column(Boolean, default=False)  # Blocks booking (for students)
    
    # Timestamps
    sent_at = Column(DateTime, default=datetime.utcnow)
    acknowledged_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    
    # Email notification tracking
    email_sent = Column(Boolean, default=False)
    email_sent_at = Column(DateTime, nullable=True)
