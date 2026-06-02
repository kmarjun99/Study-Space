"""
BoostPlan Model - Created by Super Admin for visibility promotion
"""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Float, Integer, DateTime, Text
from app.database import Base
import enum


# Keep enums for validation but use String columns for SQLite compatibility
class BoostPlanStatus(str, enum.Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    INACTIVE = "inactive"


class BoostApplicableTo(str, enum.Enum):
    READING_ROOM = "reading_room"
    ACCOMMODATION = "accommodation"
    BOTH = "both"


class BoostPlacement(str, enum.Enum):
    FEATURED_SECTION = "featured_section"
    TOP_LIST = "top_list"
    BANNER = "banner"


class BoostPlan(Base):
    """
    Boost plans created by Super Admin.
    Owners can select from ACTIVE plans to boost their venues.
    """
    __tablename__ = "boost_plans"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    price = Column(Float, nullable=False)
    duration_days = Column(Integer, nullable=False)
    # Use String instead of Enum for SQLite compatibility
    applicable_to = Column(String(50), default="both", nullable=False)
    placement = Column(String(50), default="featured_section", nullable=False)
    visibility_weight = Column(Integer, default=1)  # Higher = more visible
    status = Column(String(50), default="draft", nullable=False)
    created_by = Column(String, nullable=False)  # Super Admin ID
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

