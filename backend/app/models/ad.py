
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Enum, ForeignKey, Boolean, DateTime, Integer
from app.database import Base
import enum


# TargetAudience remains an enum (simple, less likely to change frequently)
class TargetAudience(str, enum.Enum):
    STUDENT = "STUDENT"
    ADMIN = "ADMIN"
    ALL = "ALL"


class Ad(Base):
    """
    Advertisement entity.
    category_id references the dynamic ad_categories table.
    """
    __tablename__ = "ads"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String, nullable=False)
    description = Column(String, nullable=False)
    image_url = Column(String, nullable=False)
    cta_text = Column(String, nullable=False)
    link = Column(String, nullable=False)
    # Changed from Enum to String FK - references ad_categories.id
    category_id = Column(String, ForeignKey("ad_categories.id"), nullable=True)
    target_audience = Column(Enum(TargetAudience), default=TargetAudience.ALL)
    
    # Campaign Management
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    start_date = Column(DateTime, nullable=True)  # When to start showing
    end_date = Column(DateTime, nullable=True)    # When to stop showing
    
    # Analytics
    impression_count = Column(Integer, default=0)
    click_count = Column(Integer, default=0)

