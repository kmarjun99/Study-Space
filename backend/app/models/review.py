import uuid
from sqlalchemy import Column, String, Integer, ForeignKey, DateTime, Index
from sqlalchemy.orm import relationship
from app.database import Base
from datetime import datetime

class Review(Base):
    __tablename__ = "reviews"
    __table_args__ = (
        Index('ix_unique_review_reading_room', 'user_id', 'reading_room_id', unique=True, sqlite_where=Column("reading_room_id").isnot(None)),
        Index('ix_unique_review_accommodation', 'user_id', 'accommodation_id', unique=True, sqlite_where=Column("accommodation_id").isnot(None)),
        {'extend_existing': True}
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    reading_room_id = Column(String, ForeignKey("reading_rooms.id"), nullable=True)
    accommodation_id = Column(String, ForeignKey("accommodations.id"), nullable=True)
    rating = Column(Integer, nullable=False)
    comment = Column(String, nullable=True)
    # date column removed - using created_at
    created_at = Column(DateTime, default=datetime.utcnow)

    # user = relationship("User")
