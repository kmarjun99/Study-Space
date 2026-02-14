from pydantic import BaseModel
from typing import Optional
from datetime import datetime

from app.models.booking import BookingStatus, PaymentStatus, SettlementStatus

class BookingBase(BaseModel):
    start_date: datetime
    end_date: datetime
    amount: float
    status: BookingStatus = BookingStatus.ACTIVE
    payment_status: PaymentStatus = PaymentStatus.PENDING
    transaction_id: Optional[str] = None

    settlement_status: SettlementStatus = SettlementStatus.NOT_SETTLED
    venue_name: Optional[str] = None
    owner_name: Optional[str] = None
    owner_id: Optional[str] = None
    cabin_number: Optional[str] = None

class BookingCreate(BookingBase):
    user_id: Optional[str] = None
    cabin_id: Optional[str] = None
    accommodation_id: Optional[str] = None


class BookingResponse(BookingBase):
    id: str
    user_id: str
    cabin_id: Optional[str] = None
    accommodation_id: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True

class ReviewBase(BaseModel):
    rating: float
    comment: Optional[str] = None

class ReviewCreate(ReviewBase):
    reading_room_id: Optional[str] = None
    accommodation_id: Optional[str] = None

class ReviewResponse(ReviewBase):
    id: str
    user_id: str
    date: datetime

    class Config:
        from_attributes = True
