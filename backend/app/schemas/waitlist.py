from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class WaitlistEntryBase(BaseModel):
    cabin_id: str = Field(serialization_alias="cabinId")
    reading_room_id: str = Field(serialization_alias="readingRoomId")

class WaitlistEntryCreate(WaitlistEntryBase):
    pass

class WaitlistEntryResponse(WaitlistEntryBase):
    id: str
    user_id: str = Field(serialization_alias="userId")
    created_at: datetime = Field(serialization_alias="date")
    status: str
    notified_at: Optional[datetime] = Field(None, serialization_alias="notifiedAt")
    expires_at: Optional[datetime] = Field(None, serialization_alias="expiresAt")
    
    # Enriched Data
    venue_name: Optional[str] = Field(None, serialization_alias="venueName")
    venue_address: Optional[str] = Field(None, serialization_alias="venueAddress")
    cabin_number: Optional[str] = Field(None, serialization_alias="cabinNumber")
    priority_position: Optional[int] = Field(None, serialization_alias="priorityPosition")
    
    # User Details
    user_name: Optional[str] = Field(None, serialization_alias="userName")
    user_email: Optional[str] = Field(None, serialization_alias="userEmail")

    class Config:
        from_attributes = True

class NotificationBase(BaseModel):
    title: str
    message: str
    type: str # 'info', 'success', 'warning', 'error'
    read: bool = False

class NotificationCreate(NotificationBase):
    user_id: str = Field(serialization_alias="userId")

class NotificationResponse(NotificationBase):
    id: str
    user_id: str = Field(serialization_alias="userId")
    created_at: datetime = Field(serialization_alias="date")

    class Config:
        from_attributes = True
