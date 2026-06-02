import uuid
from datetime import datetime
from sqlalchemy import Column, String, Enum, DateTime, Text, ForeignKey
from app.database import Base
import enum


class TrustFlagType(str, enum.Enum):
    WEAK_DESCRIPTION = "weak_description"
    FAKE_ADDRESS = "fake_address"
    SUSPICIOUS_ACTIVITY = "suspicious_activity"
    MISSING_PHONE = "missing_phone"
    MISSING_IMAGES = "missing_images"
    POLICY_VIOLATION = "policy_violation"
    OTHER = "other"


class TrustFlagStatus(str, enum.Enum):
    ACTIVE = "active"
    OWNER_RESUBMITTED = "owner_resubmitted"
    RESOLVED = "resolved"
    REJECTED = "rejected"
    ESCALATED = "escalated"


class TrustFlag(Base):
    """
    Trust flags raised by Super Admin on venues/accommodations.
    Triggers restrictions on Owner actions and visibility to Users.
    """
    __tablename__ = "trust_flags"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # Target entity (venue or accommodation)
    entity_type = Column(String, nullable=False)  # 'reading_room' or 'accommodation'
    entity_id = Column(String, nullable=False)
    entity_name = Column(String, nullable=True)  # Cached for display
    
    # Flag details
    flag_type = Column(Enum(TrustFlagType), nullable=False)
    custom_reason = Column(Text, nullable=True)  # For 'other' type or additional details
    
    # Actor info
    raised_by = Column(String, ForeignKey("users.id"), nullable=False)
    raised_by_name = Column(String, nullable=True)  # Cached for display
    
    # Status and resolution
    status = Column(Enum(TrustFlagStatus), default=TrustFlagStatus.ACTIVE)
    resolution_notes = Column(Text, nullable=True)
    resolved_by = Column(String, ForeignKey("users.id"), nullable=True)
    resolved_by_name = Column(String, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)
    
    # Owner resubmission
    owner_notes = Column(Text, nullable=True)  # Notes from owner when resubmitting
    resubmitted_at = Column(DateTime, nullable=True)
