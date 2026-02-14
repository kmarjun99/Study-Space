from pydantic import BaseModel
from typing import Optional, List
from app.models.accommodation import Gender, AccommodationType

from app.models.reading_room import ListingStatus

class AccommodationBase(BaseModel):
    name: str
    type: AccommodationType
    gender: Gender
    address: str
    price: float
    sharing: str
    amenities: Optional[str] = None
    images: Optional[str] = None # JSON string
    contact_phone: Optional[str] = None
    rating: Optional[float] = 0.0
    # Location
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    city: Optional[str] = None
    area: Optional[str] = None
    locality: Optional[str] = None
    state: Optional[str] = None
    pincode: Optional[str] = None
    location_id: Optional[str] = None  # Reference to locations master table

class AccommodationCreate(AccommodationBase):
    pass

class AccommodationUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[AccommodationType] = None
    gender: Optional[Gender] = None
    address: Optional[str] = None
    price: Optional[float] = None
    sharing: Optional[str] = None
    amenities: Optional[str] = None
    images: Optional[str] = None
    contact_phone: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    city: Optional[str] = None
    area: Optional[str] = None
    locality: Optional[str] = None
    state: Optional[str] = None
    pincode: Optional[str] = None
    location_id: Optional[str] = None  # Reference to locations master table
    status: Optional[ListingStatus] = None

class AccommodationResponse(AccommodationBase):
    id: str
    owner_id: str
    is_verified: bool = False
    status: ListingStatus = ListingStatus.DRAFT
    image_url: Optional[str] = None # Computed

    class Config:
        from_attributes = True
