import uuid
from sqlalchemy import Column, String, Text, ForeignKey, Enum, DateTime
from sqlalchemy.sql import func
from app.database import Base
import enum

class InquiryStatus(str, enum.Enum):
    PENDING = "PENDING"      # Awaiting owner response
    REPLIED = "REPLIED"      # Owner has replied
    CLOSED = "CLOSED"        # Inquiry closed

class InquiryType(str, enum.Enum):
    QUESTION = "QUESTION"    # General question
    VISIT = "VISIT"          # Visit request

class Inquiry(Base):
    __tablename__ = "inquiries"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    accommodation_id = Column(String, ForeignKey("accommodations.id"), nullable=False)
    student_id = Column(String, ForeignKey("users.id"), nullable=False)
    owner_id = Column(String, ForeignKey("users.id"), nullable=False)
    
    # Inquiry details
    type = Column(Enum(InquiryType), default=InquiryType.QUESTION)
    question = Column(Text, nullable=False)
    student_name = Column(String, nullable=False)
    student_phone = Column(String, nullable=True)
    
    # Visit-specific fields
    preferred_date = Column(String, nullable=True)
    preferred_time = Column(String, nullable=True)
    
    # Owner reply
    reply = Column(Text, nullable=True)
    status = Column(Enum(InquiryStatus), default=InquiryStatus.PENDING)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    replied_at = Column(DateTime(timezone=True), nullable=True)
