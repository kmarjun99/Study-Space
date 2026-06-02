from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class ReviewBase(BaseModel):
    reading_room_id: Optional[str] = None
    accommodation_id: Optional[str] = None
    rating: int
    comment: Optional[str] = None

class ReviewCreate(ReviewBase):
    pass
    # date removed from schema

class ReviewResponse(ReviewBase):
    id: str
    user_id: str
    created_at: datetime

    class Config:
        from_attributes = True
