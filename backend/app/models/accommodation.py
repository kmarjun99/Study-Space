import uuid
from sqlalchemy import Column, String, Integer, Float, ForeignKey, Enum, Boolean, Numeric, SmallInteger
from app.database import Base
import enum

class Gender(str, enum.Enum):
    MALE = "MALE"
    FEMALE = "FEMALE"
    UNISEX = "UNISEX"

class AccommodationType(str, enum.Enum):
    PG = "PG"
    HOSTEL = "HOSTEL"
    HOUSE = "HOUSE"


from app.models.reading_room import ListingStatus, MaintenanceStatus, PriceDisplayMode

class Accommodation(Base):
    __tablename__ = "accommodations"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    owner_id = Column(String, ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False)
    type = Column(Enum(AccommodationType, native_enum=False), nullable=False)
    gender = Column(Enum(Gender, native_enum=False), nullable=False)
    
    # Workflow
    status = Column(Enum(ListingStatus, native_enum=False), default=ListingStatus.DRAFT)
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

    # ---- Accounting & maintenance billing (additive; null = legacy behaviour) ----
    gst_category = Column(String(30), nullable=True)
    gst_sac = Column(String(10), nullable=True)
    gst_rate_override = Column(Numeric(5, 4), nullable=True)
    billing_anchor_day = Column(SmallInteger, nullable=True, default=1)
    maintenance_status = Column(
        Enum(MaintenanceStatus, native_enum=False),
        nullable=False,
        default=MaintenanceStatus.CURRENT,
    )
    visibility_score = Column(Numeric(4, 3), nullable=False, default=1.000)
    # Per-listing override for GST display. See PriceDisplayMode docstring.
    price_display_mode = Column(
        Enum(PriceDisplayMode, native_enum=False),
        nullable=True,
        default=None,
    )

    # ---- Phase 3 recommendation controls (admin-only) ----
    recommendation_priority = Column(Integer, nullable=True, default=None)
    recommendation_excluded = Column(Boolean, nullable=False, default=False)

    # SEO slug — used as the public URL component (e.g. /pgs/abc-pg-koramangala-bangalore).
    # Unique across all accommodations; backfilled by migrate_add_listing_slugs.py.
    slug = Column(String(120), nullable=True, unique=True, index=True)

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
