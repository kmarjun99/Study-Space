import uuid
from sqlalchemy import Column, String, Integer, Float, ForeignKey, Enum, Boolean
from app.database import Base
import enum

class Gender(str, enum.Enum):
    MALE = "MALE"
    FEMALE = "FEMALE"
    UNISEX = "UNISEX"

class AccommodationType(str, enum.Enum):
    PG = "PG"
    HOSTEL = "HOSTEL"


from app.models.reading_room import ListingStatus

class Accommodation(Base):
    __tablename__ = "accommodations"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    owner_id = Column(String, ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False)
    type = Column(Enum(AccommodationType), nullable=False)
    gender = Column(Enum(Gender), nullable=False)
    
    # Workflow
    status = Column(Enum(ListingStatus), default=ListingStatus.DRAFT)
    is_verified = Column(Boolean, default=False)
    
    address = Column(String, nullable=False)
    price = Column(Float, nullable=False)
    sharing = Column(String, nullable=False)
    amenities = Column(String, nullable=True) # Comma-separated
    images = Column(String, nullable=True) # JSON list
    contact_phone = Column(String, nullable=True)
    rating = Column(Float, default=0.0)

    # Location Data (legacy - kept for backward compatibility)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    city = Column(String, nullable=True)
    area = Column(String, nullable=True)
    locality = Column(String, nullable=True)
    pincode = Column(String, nullable=True)
    state = Column(String, nullable=True)
    
    # NEW: Reference to master locations table
    location_id = Column(String, ForeignKey("locations.id"), nullable=True, index=True)
    
    # Payment & Subscription tracking
    subscription_plan_id = Column(String, ForeignKey("subscription_plans.id"), nullable=True)
    payment_id = Column(String, nullable=True)  # Razorpay payment ID
    payment_date = Column(String, nullable=True)  # Using String for datetime to avoid migration issues
    
    @property
    def image_url(self):
        # Fallback for frontend
        if self.images:
            try:
                import json
                imgs = json.loads(self.images)
                return imgs[0] if imgs else None
            except:
                return self.images
        return None
