"""
Location Master Model - Powers autocomplete, city switching, and location filtering.
"""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Float, Integer, Boolean, DateTime, Text
from app.database import Base


class Location(Base):
    """
    Master location table for India cities and localities.
    Venues reference this table instead of storing free-text city names.
    """
    __tablename__ = "locations"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # Geographic hierarchy
    country = Column(String(100), nullable=False, default="India")
    state = Column(String(100), nullable=False)
    city = Column(String(100), nullable=False)
    locality = Column(String(150), nullable=True)  # Kazhakkoottam, Indiranagar, etc.
    
    # Normalized fields for fast search (lowercase, trimmed)
    city_normalized = Column(String(100), nullable=False, index=True)
    locality_normalized = Column(String(150), nullable=True, index=True)
    
    # Combined search text for full-text search
    # Format: "city state locality" (all lowercase)
    search_text = Column(Text, nullable=False)
    
    # Coordinates for map display
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    
    # Popularitty tracking for sorting autocomplete results
    usage_count = Column(Integer, default=0)
    
    # Status
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    @property
    def display_name(self) -> str:
        """User-friendly display name for the location."""
        if self.locality:
            return f"{self.locality}, {self.city}"
        return f"{self.city}, {self.state}"
    
    @property
    def full_name(self) -> str:
        """Full location string."""
        parts = [self.locality, self.city, self.state, self.country]
        return ", ".join(p for p in parts if p)
    
    @classmethod
    def normalize(cls, text: str) -> str:
        """Normalize text for search matching."""
        if not text:
            return ""
        return text.lower().strip()
    
    @classmethod
    def create_search_text(cls, city: str, state: str, locality: str = None) -> str:
        """Create combined search text for full-text matching."""
        parts = [city, state]
        if locality:
            parts.append(locality)
        return " ".join(p.lower().strip() for p in parts if p)
