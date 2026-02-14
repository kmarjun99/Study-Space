from pydantic import BaseModel, field_validator
from typing import List, Optional, Union
from datetime import datetime
import json
from app.models.reading_room import CabinStatus, ListingStatus

class CabinBase(BaseModel):
    number: str
    floor: int
    amenities: Optional[Union[List[str], str]] = []
    price: float
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
    reading_room_id: str
    current_occupant_id: Optional[str] = None
    amenities: List[str] = [] # Override to ensure response is always List
    zone: Optional[str] = None
    row_label: Optional[str] = None
    # Hold system fields
    held_by_user_id: Optional[str] = None
    hold_expires_at: Optional[str] = None

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

class ReadingRoomResponse(ReadingRoomBase):
    id: str
    owner_id: str
    is_sponsored: bool = False
    is_verified: bool = False
    status: ListingStatus = ListingStatus.DRAFT
    image_url: Optional[str] = None # Computed prop
    created_at: Optional[datetime] = None  # Submission date
    _distance: Optional[float] = None # Calculated field
    
    # Override fields to be strict Lists
    amenities: List[str] = []
    images: List[str] = []

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

    class Config:
        from_attributes = True
