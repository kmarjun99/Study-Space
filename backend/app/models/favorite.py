import uuid
from datetime import datetime
from sqlalchemy import Column, String, ForeignKey, DateTime, UniqueConstraint
from app.database import Base


class Favorite(Base):
    """
    User favorites/wishlist for accommodations and reading rooms.
    """
    __tablename__ = "favorites"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    # Can favorite either accommodation or reading room
    accommodation_id = Column(String, ForeignKey("accommodations.id", ondelete="CASCADE"), nullable=True)
    reading_room_id = Column(String, ForeignKey("reading_rooms.id", ondelete="CASCADE"), nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Ensure user can't favorite same item twice
    __table_args__ = (
        UniqueConstraint('user_id', 'accommodation_id', name='unique_user_accommodation_favorite'),
        UniqueConstraint('user_id', 'reading_room_id', name='unique_user_reading_room_favorite'),
    )
