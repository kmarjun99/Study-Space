
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, JSON, DateTime, Enum as SQLEnum
from app.database import Base
import enum


class CategoryStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


class AdCategory(Base):
    """
    Dynamic Ad Category entity - managed by Super Admin.
    Categories are fetched from backend, not hardcoded in frontend.
    """
    __tablename__ = "ad_categories"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(100), nullable=False, unique=True)
    slug = Column(String(100), nullable=False, unique=True)
    description = Column(Text, nullable=True)
    icon = Column(String(50), nullable=True)  # Lucide icon name
    group = Column(String(50), nullable=True)  # Student, Housing, Business, Platform
    applicable_to = Column(JSON, default=["USER", "OWNER"])  # Who can be targeted
    status = Column(SQLEnum(CategoryStatus), default=CategoryStatus.ACTIVE)
    display_order = Column(String, default="0")  # For sorting in dropdown
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
