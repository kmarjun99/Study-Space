"""
BoostRequest Model - Created when Owner requests a boost for their venue
"""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Float, Integer, DateTime, Text, Enum, ForeignKey
from app.database import Base
import enum


class BoostRequestStatus(str, enum.Enum):
    INITIATED = "initiated"           # Owner started request
    PAYMENT_PENDING = "payment_pending"  # Awaiting payment
    PAID = "paid"                     # Payment successful
    ADMIN_REVIEW = "admin_review"     # Under Super Admin review
    APPROVED = "approved"             # Super Admin approved
    REJECTED = "rejected"             # Super Admin rejected
    ACTIVE = "active"                 # Currently boosting
    EXPIRED = "expired"               # Boost period ended


class VenueType(str, enum.Enum):
    READING_ROOM = "reading_room"
    ACCOMMODATION = "accommodation"


class BoostRequest(Base):
    """
    Boost requests created by owners.
    Payment does NOT activate - Super Admin approval required.
    """
    __tablename__ = "boost_requests"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # Owner info
    owner_id = Column(String, nullable=False)
    owner_name = Column(String(100), nullable=True)
    owner_email = Column(String(100), nullable=True)
    
    # Venue info
    venue_id = Column(String, nullable=False)
    venue_type = Column(Enum(VenueType), nullable=False)
    venue_name = Column(String(200), nullable=True)
    
    # Plan info (denormalized for historical record)
    boost_plan_id = Column(String, ForeignKey("boost_plans.id"), nullable=False)
    plan_name = Column(String(100), nullable=True)
    price = Column(Float, nullable=False)
    duration_days = Column(Integer, nullable=False)
    placement = Column(String(50), nullable=True)
    
    # Payment info
    payment_id = Column(String, nullable=True)  # Nullable until payment
    payment_proof_url = Column(String(500), nullable=True)
    
    # Status
    status = Column(
        Enum(BoostRequestStatus),
        default=BoostRequestStatus.INITIATED,
        nullable=False
    )
    
    # Timestamps
    requested_at = Column(DateTime, default=datetime.utcnow)
    paid_at = Column(DateTime, nullable=True)
    approved_at = Column(DateTime, nullable=True)
    approved_by = Column(String, nullable=True)  # Super Admin ID
    activated_at = Column(DateTime, nullable=True)
    expiry_date = Column(DateTime, nullable=True)
    
    # Admin notes
    admin_notes = Column(Text, nullable=True)
    rejection_reason = Column(Text, nullable=True)
