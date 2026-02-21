from sqlalchemy import Column, String, DateTime, JSON
from sqlalchemy.sql import func
import uuid
from datetime import datetime, timedelta, timezone
from app.database import Base


class PendingRegistration(Base):
    __tablename__ = "pending_registrations"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String, nullable=False, unique=True, index=True)
    hashed_password = Column(String, nullable=False)
    name = Column(String, nullable=False)
    role = Column(String, nullable=False)
    phone = Column(String, nullable=True)
    avatar_url = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=False)
    
    def is_expired(self):
        """Check if pending registration has expired (24 hours)"""
        now = datetime.now(timezone.utc)
        if self.expires_at.tzinfo is None:
            self_expires_at = self.expires_at.replace(tzinfo=timezone.utc)
        else:
            self_expires_at = self.expires_at
            
        return now > self_expires_at
