from pydantic import BaseModel, field_validator, Field
from typing import List, Optional, Union, Dict
from datetime import datetime
import json
from app.models.reading_room import CabinStatus, ListingStatus

class CabinBase(BaseModel):
    number: str
    floor: int
    amenities: Optional[Union[List[str], str]] = Field(
        default_factory=list,
        validate_default=True,
    )
    price: Optional[float] = None  # Optional: defaults to reading room's priceStart if not provided
    status: CabinStatus = CabinStatus.AVAILABLE
    zone: Optional[str] = None
    row_label: Optional[str] = None

class CabinCreate(CabinBase):
    @field_validator('amenities')
    @classmethod
    def validate_amenities(cls, v):
        if isinstance(v, list):
            return ",".join(v)
        return v

class CabinUpdate(BaseModel):
    status: Optional[CabinStatus] = None
    price: Optional[float] = None
    amenities: Optional[Union[List[str], str]] = None
    current_occupant_id: Optional[str] = None
    
    @field_validator('amenities')
    @classmethod
    def validate_amenities(cls, v):
        if isinstance(v, list):
            return ",".join(v)
        return v

class CabinResponse(CabinBase):
    id: str
    reading_room_id: str = Field(serialization_alias="readingRoomId")
    current_occupant_id: Optional[str] = Field(default=None, serialization_alias="currentOccupantId")
    amenities: List[str] = Field(default_factory=list) # Override to ensure response is always List
    price: float  # Required in response - always set to reading room's price
    zone: Optional[str] = None
    row_label: Optional[str] = Field(default=None, serialization_alias="rowLabel")
    # Hold system fields
    held_by_user_id: Optional[str] = Field(default=None, serialization_alias="heldByUserId")
    hold_expires_at: Optional[str] = Field(default=None, serialization_alias="holdExpiresAt")

    @field_validator('amenities', mode='before')
    @classmethod
    def parse_amenities(cls, v):
        if isinstance(v, str):
            return [x.strip() for x in v.split(',') if x.strip()]
        if v is None:
            return []
        return v

    class Config:
        from_attributes = True

class ReadingRoomBase(BaseModel):
    name: str
    address: str
    description: Optional[str] = None
    images: Optional[Union[List[str], str]] = None 
    amenities: Optional[Union[List[str], str]] = None
    contact_phone: Optional[str] = None
    price_start: Optional[float] = None
    # Location
    city: Optional[str] = None
    area: Optional[str] = None
    locality: Optional[str] = None
    state: Optional[str] = None
    pincode: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    location_id: Optional[str] = None  # Reference to locations master table
    
    # Booking Duration Configuration (NEW)
    allowed_booking_durations: Optional[Union[List[str], str]] = None
    duration_prices: Optional[Union[Dict[str, float], str]] = None

class ReadingRoomCreate(ReadingRoomBase):
    @field_validator('amenities')
    @classmethod
    def validate_amenities(cls, v):
        if isinstance(v, list):
            return ",".join(v)
        return v
    
    @field_validator('images')
    @classmethod
    def validate_images(cls, v):
        if isinstance(v, list):
            return json.dumps(v)
        return v
    
    @field_validator('allowed_booking_durations')
    @classmethod
    def validate_durations(cls, v):
        if isinstance(v, list):
            return json.dumps(v)
        return v
    
    @field_validator('duration_prices')
    @classmethod
    def validate_prices(cls, v):
        if isinstance(v, dict):
            return json.dumps(v)
        return v

class ReadingRoomUpdate(BaseModel):
    name: Optional[str] = None
    address: Optional[str] = None
    description: Optional[str] = None
    images: Optional[Union[List[str], str]] = None
    amenities: Optional[Union[List[str], str]] = None
    contact_phone: Optional[str] = None
    price_start: Optional[float] = None
    city: Optional[str] = None
    area: Optional[str] = None
    locality: Optional[str] = None
    state: Optional[str] = None
    pincode: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    location_id: Optional[str] = None  # Reference to locations master table
    status: Optional[ListingStatus] = None
    
    # Booking Duration Configuration (NEW)
    allowed_booking_durations: Optional[Union[List[str], str]] = None
    duration_prices: Optional[Union[Dict[str, float], str]] = None

    @field_validator('amenities')
    @classmethod
    def validate_amenities(cls, v):
        if isinstance(v, list):
            return ",".join(v)
        return v

    @field_validator('images')
    @classmethod
    def validate_images(cls, v):
        if isinstance(v, list):
            return json.dumps(v)
        return v
    
    @field_validator('allowed_booking_durations')
    @classmethod
    def validate_durations(cls, v):
        if isinstance(v, list):
            return json.dumps(v)
        return v
    
    @field_validator('duration_prices')
    @classmethod
    def validate_prices(cls, v):
        if isinstance(v, dict):
            return json.dumps(v)
        return v

class ReadingRoomResponse(ReadingRoomBase):
    id: str
    owner_id: str = Field(serialization_alias="ownerId")
    is_sponsored: bool = Field(default=False, serialization_alias="isSponsored")
    is_verified: bool = Field(default=False, serialization_alias="isVerified")
    status: ListingStatus = ListingStatus.DRAFT
    image_url: Optional[str] = Field(default=None, serialization_alias="imageUrl") # Computed prop
    created_at: Optional[datetime] = Field(default=None, serialization_alias="createdAt")  # Submission date
    operational_access_override: str = Field(default="NONE", serialization_alias="operationalAccessOverride")
    operational_access_until: Optional[datetime] = Field(default=None, serialization_alias="operationalAccessUntil")
    operational_access_reason: Optional[str] = Field(default=None, serialization_alias="operationalAccessReason")
    operational_access_updated_by: Optional[str] = Field(default=None, serialization_alias="operationalAccessUpdatedBy")
    operational_access_updated_at: Optional[datetime] = Field(default=None, serialization_alias="operationalAccessUpdatedAt")
    _distance: Optional[float] = None # Calculated field
    
    # Override fields to be strict Lists/Dicts with camelCase aliases for frontend
    amenities: List[str] = []
    images: List[str] = []
    allowed_booking_durations: List[str] = Field(
        default=["1_DAY", "1_WEEK", "1_MONTH", "3_MONTHS", "6_MONTHS"],
        serialization_alias="allowedBookingDurations"
    )
    duration_prices: Dict[str, Optional[float]] = Field(
        default={},
        serialization_alias="durationPrices"
    )

    @field_validator('amenities', mode='before')
    @classmethod
    def parse_amenities(cls, v):
        if isinstance(v, str):
            # Handle potential JSON string or CSV
            if v.startswith('['):
                try: return json.loads(v)
                except: pass
            return [x.strip() for x in v.split(',') if x.strip()]
        if v is None:
            return []
        return v

    @field_validator('images', mode='before')
    @classmethod
    def parse_images(cls, v):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except:
                return []
        if v is None:
            return []
        return v
    
    @field_validator('allowed_booking_durations', mode='before')
    @classmethod
    def parse_durations(cls, v):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except:
                return ["1_MONTH"]
        if v is None:
            return ["1_DAY", "1_WEEK", "1_MONTH", "3_MONTHS", "6_MONTHS"]
        return v
    
    @field_validator('duration_prices', mode='before')
    @classmethod
    def parse_prices(cls, v):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except:
                return {}
        if v is None:
            return {}
        return v

    class Config:
        from_attributes = True


class ReadingRoomSummaryResponse(BaseModel):
    id: str
    owner_id: str = Field(serialization_alias="ownerId")
    name: str
    address: str
    city: Optional[str] = None
    status: ListingStatus = ListingStatus.DRAFT
    is_verified: bool = Field(default=False, serialization_alias="isVerified")
    image_url: Optional[str] = Field(default=None, serialization_alias="imageUrl")
    has_images: bool = Field(default=False, serialization_alias="hasImages")
    operational_access_override: str = Field(default="NONE", serialization_alias="operationalAccessOverride")
    operational_access_until: Optional[datetime] = Field(default=None, serialization_alias="operationalAccessUntil")

    class Config:
        from_attributes = True
        populate_by_name = True
        # Pydantic v2: Use serialization aliases in responses
        json_schema_serialization_defaults_required = True


class DurationConfigUpdate(BaseModel):
    """Schema for updating booking duration configuration"""
    allowed_booking_durations: List[str]
    duration_prices: Dict[str, float]
    
    @field_validator('allowed_booking_durations')
    @classmethod
    def validate_durations(cls, v):
        valid_types = ["1_DAY", "1_WEEK", "1_MONTH", "3_MONTHS", "6_MONTHS"]
        if not v or len(v) == 0:
            raise ValueError("At least one booking duration must be enabled")
        for duration in v:
            if duration not in valid_types:
                raise ValueError(f"Invalid duration type: {duration}")
        return v
    
    @field_validator('duration_prices')
    @classmethod
    def validate_prices(cls, v, info):
        # Ensure all enabled durations have valid prices
        durations = info.data.get('allowed_booking_durations', [])
        for duration in durations:
            if duration not in v or v[duration] is None or v[duration] <= 0:
                raise ValueError(f"Valid price required for duration: {duration}")
        return v
