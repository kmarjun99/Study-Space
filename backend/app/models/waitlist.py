from sqlalchemy import Column, String, ForeignKey, DateTime, Enum, Boolean
from app.database import Base
from datetime import datetime
import uuid
import enum

class WaitlistStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    NOTIFIED = "NOTIFIED"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"
    CONVERTED = "CONVERTED"

class WaitlistEntry(Base):
    __tablename__ = "waitlist"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    cabin_id = Column(String, ForeignKey("cabins.id"), nullable=False)
    reading_room_id = Column(String, ForeignKey("reading_rooms.id"), nullable=False)
    owner_id = Column(String, nullable=True) # Added for easier owner queries
    
    status = Column(Enum(WaitlistStatus), default=WaitlistStatus.ACTIVE)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    notified_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True) # When the reservation window ends


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    title = Column(String, nullable=False)
    message = Column(String, nullable=False)
    read = Column(Boolean, default=False)
    type = Column(String, nullable=False) # 'info', 'success', 'warning', 'error'
    created_at = Column(DateTime, default=datetime.utcnow)
