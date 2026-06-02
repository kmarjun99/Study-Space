from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from decimal import Decimal

from app.models.booking import BookingStatus, PaymentStatus, SettlementStatus, GSTTreatment

class BookingBase(BaseModel):
    start_date: datetime
    end_date: datetime
    amount: float
    status: BookingStatus = BookingStatus.ACTIVE
    payment_status: PaymentStatus = PaymentStatus.PENDING
    transaction_id: Optional[str] = None
    duration_type: Optional[str] = '1_MONTH'  # NEW: Booking duration type

    settlement_status: SettlementStatus = SettlementStatus.NOT_SETTLED
    venue_name: Optional[str] = None
    owner_name: Optional[str] = None
    owner_id: Optional[str] = None
    cabin_number: Optional[str] = None

class BookingCreate(BookingBase):
    user_id: Optional[str] = None
    cabin_id: Optional[str] = None
    accommodation_id: Optional[str] = None
    duration_type: Optional[str] = '1_MONTH'  # Required for creation


class BookingResponse(BookingBase):
    id: str
    user_id: str
    cabin_id: Optional[str] = None
    accommodation_id: Optional[str] = None
    created_at: datetime

    # GST + settlement fields populated by the accounting shadow + settlement
    # engine. ALL nullable so legacy bookings (paid before accounting.enabled)
    # serialize cleanly with these as None. Super-admin Bookings page reads
    # these to render the real owner-payable / GST split — without them the
    # UI falls back to a hardcoded 90/10 commission split that has no
    # relationship to actual ledger postings.
    base_amount: Optional[Decimal] = None
    gst_amount: Optional[Decimal] = None
    gst_rate_applied: Optional[Decimal] = None
    gst_treatment: Optional[GSTTreatment] = None
    place_of_supply_state: Optional[str] = None
    paid_at: Optional[datetime] = None
    settled_at: Optional[datetime] = None
    settlement_run_id: Optional[str] = None

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
