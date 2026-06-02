"""
SubscriptionPlan Model - Venue listing subscription plans created by Super Admin
"""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Float, Integer, DateTime, Text, Boolean, JSON
from app.database import Base


class SubscriptionPlan(Base):
    """
    Subscription plans for venue listings.
    Super Admin creates plans, Owners pay to list venues.
    """
    __tablename__ = "subscription_plans"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    price = Column(Float, nullable=False)
    duration_days = Column(Integer, nullable=False, default=30)
    features = Column(JSON, nullable=True, default=list)  # List of feature strings
    is_active = Column(Boolean, default=True, nullable=False)
    is_default = Column(Boolean, default=False, nullable=False)
    created_by = Column(String, nullable=False)  # Super Admin ID
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
