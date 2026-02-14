import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Text
from app.database import Base


class Notification(Base):
    __tablename__ = "notifications"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    title = Column(String, nullable=False)
    message = Column(Text, nullable=False)
    read = Column(Boolean, default=False)
    date = Column(DateTime, default=datetime.utcnow)
    type = Column(String, default="info")  # info, success, warning, error
    message_id = Column(String, ForeignKey("messages.id"), nullable=True)  # Link to message if notification is about a message
