import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, Float, ForeignKey, Boolean, Enum, ARRAY, DateTime, Numeric, SmallInteger
from sqlalchemy.orm import relationship
from app.database import Base
import enum

class CabinStatus(str, enum.Enum):
    AVAILABLE = "AVAILABLE"
    OCCUPIED = "OCCUPIED"
    MAINTENANCE = "MAINTENANCE"
    RESERVED = "RESERVED"


class ListingStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    PAYMENT_PENDING = "PAYMENT_PENDING"
    VERIFICATION_PENDING = "VERIFICATION_PENDING"
    LIVE = "LIVE"
    REJECTED = "REJECTED"
    SUSPENDED = "SUSPENDED"


class MaintenanceStatus(str, enum.Enum):
    CURRENT = "CURRENT"
    OVERDUE = "OVERDUE"
    SUSPENDED_FOR_NONPAYMENT = "SUSPENDED_FOR_NONPAYMENT"


class PriceDisplayMode(str, enum.Enum):
    """How the listing price is to be interpreted in customer-facing UI.

    GST_INCLUDED  — the price shown to the student already contains GST;
                    the engine reverse-calculates the base + GST split.
    GST_EXTRA     — the price shown is the BASE; the booking flow must add
                    GST on top before charging.

    `None` (column unset) means "fall back to the global config key
    `gst.booking.pricing_is_inclusive`". Only honored end-to-end when the
    feature flag `feature.per_listing_price_mode` is `true` — otherwise the
    column is purely informational and the global flag wins. See
    docs/TRANSACTION_FLOW_DESIGN.md §4.
    """
    GST_INCLUDED = "GST_INCLUDED"
    GST_EXTRA = "GST_EXTRA"


# TrustStatus is stored as String column with values: CLEAR, FLAGGED, UNDER_REVIEW, SUSPENDED

class ReadingRoom(Base):
    __tablename__ = "reading_rooms"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    owner_id = Column(String, ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False)
    address = Column(String, nullable=False)
    description = Column(String, nullable=True)
    # Changed from single image_url to images (JSON string of list)
    images = Column(String, nullable=True) 
    # Backward compatibility accessor if needed, or simply remove image_url and migrate
    amenities = Column(String, nullable=True) 
    contact_phone = Column(String, nullable=True)
    price_start = Column(Float, nullable=True)
    
    # Workflow
    status = Column(Enum(ListingStatus, native_enum=False), default=ListingStatus.DRAFT)
    is_verified = Column(Boolean, default=False) 
    
    # Trust & Safety (Super Admin controlled)
    trust_status = Column(String, default="CLEAR")  # Values: CLEAR, FLAGGED, UNDER_REVIEW, SUSPENDED
    
    is_sponsored = Column(Boolean, default=False)
    sponsored_until = Column(String, nullable=True)

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
    payment_date = Column(DateTime, nullable=True)
    
    # Submission timestamp
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Booking Duration Configuration (NEW)
    # Stores JSON array of allowed duration types: ["1_DAY", "1_WEEK", "1_MONTH", "3_MONTHS", "6_MONTHS"]
    allowed_booking_durations = Column(String, nullable=True, default='["1_DAY", "1_WEEK", "1_MONTH", "3_MONTHS", "6_MONTHS"]')
    
    # Stores JSON object with custom prices per duration: {"1_DAY": 150, "1_WEEK": 900, "1_MONTH": 3000, ...}
    duration_prices = Column(String, nullable=True)

    # ---- Accounting & maintenance billing (additive; null = legacy behaviour) ----
    gst_category = Column(String(30), nullable=True)        # HOTEL_LIKE / SHORT_STAY / HOSTEL_PG / READING_ROOM / OTHER
    gst_sac = Column(String(10), nullable=True)             # SAC code (e.g., 996311)
    gst_rate_override = Column(Numeric(5, 4), nullable=True)  # null = use config default
    billing_anchor_day = Column(SmallInteger, nullable=True, default=1)  # 1-28
    maintenance_status = Column(
        Enum(MaintenanceStatus, native_enum=False),
        nullable=False,
        default=MaintenanceStatus.CURRENT,
    )
    visibility_score = Column(Numeric(4, 3), nullable=False, default=1.000)
    # Per-listing override for GST display (see PriceDisplayMode docstring).
    # Null = use the global config flag `gst.booking.pricing_is_inclusive`.
    price_display_mode = Column(
        Enum(PriceDisplayMode, native_enum=False),
        nullable=True,
        default=None,
    )

    # ---- Phase 3 recommendation controls (admin-only) ----
    # Higher = ranked earlier. NULL = use computed score only.
    recommendation_priority = Column(Integer, nullable=True, default=None)
    # When True, listing is hard-excluded from all recommendation surfaces
    # regardless of score. Used for content moderation / temporary holds
    # that don't warrant a full SUSPENDED transition.
    recommendation_excluded = Column(Boolean, nullable=False, default=False)

    # SEO slug — used as the public URL component (e.g. /reading-rooms/abc-reading-room-kakkanad-kochi).
    # Unique across all reading rooms; backfilled by migrate_add_listing_slugs.py.
    slug = Column(String(120), nullable=True, unique=True, index=True)

    cabins = relationship("Cabin", back_populates="reading_room")
    
    @property
    def image_url(self):
        # Fallback for frontend that expects single image_url
        if self.images:
            try:
                import json
                imgs = json.loads(self.images)
                return imgs[0] if imgs else None
            except:
                return self.images # Fallback if stored as raw string previously
        return None

class Cabin(Base):
    __tablename__ = "cabins"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    reading_room_id = Column(String, ForeignKey("reading_rooms.id"), nullable=False)
    number = Column(String, nullable=False)
    floor = Column(Integer, nullable=False)
    amenities = Column(String, nullable=True)
    price = Column(Float, nullable=False)
    status = Column(Enum(CabinStatus), default=CabinStatus.AVAILABLE)
    current_occupant_id = Column(String, ForeignKey("users.id"), nullable=True)
    
    # Owner-defined seat positioning
    zone = Column(String, nullable=True)  # 'FRONT', 'MIDDLE', 'BACK'
    row_label = Column(String, nullable=True)  # 'A', 'B', 'C', etc.
    
    # Temporary Hold System (BookMyShow-style)
    held_by_user_id = Column(String, ForeignKey("users.id"), nullable=True)
    hold_expires_at = Column(String, nullable=True)  # ISO timestamp

    reading_room = relationship("ReadingRoom", back_populates="cabins")
    
    def is_held(self) -> bool:
        """Check if cabin is currently held by someone"""
        if not self.held_by_user_id or not self.hold_expires_at:
            return False
        from datetime import datetime
        try:
            expires = datetime.fromisoformat(self.hold_expires_at.replace('Z', '+00:00'))
            return datetime.now(expires.tzinfo) < expires
        except:
            return False
    
    def is_held_by(self, user_id: str) -> bool:
        """Check if cabin is held by specific user"""
        return self.is_held() and self.held_by_user_id == user_id

