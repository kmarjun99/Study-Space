from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field

from app.models.booking import BookingStatus, PaymentStatus
from app.services.booking_validator import BookingDurationType
from app.services.renewal_service import RenewalStatus


class OwnerStudentAssignmentCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=120)
    email: EmailStr
    phone: Optional[str] = Field(default=None, max_length=30)
    reading_room_id: str
    cabin_id: str
    duration_type: str = BookingDurationType.ONE_MONTH
    joining_date: date
    amount: Optional[float] = Field(default=None, ge=0)
    payment_status: PaymentStatus = PaymentStatus.PENDING
    payment_reference: Optional[str] = Field(default=None, max_length=120)
    send_invite: bool = True


class OwnerBookingRenewRequest(BaseModel):
    duration_type: Optional[str] = None
    amount: Optional[float] = Field(default=None, ge=0)
    payment_status: PaymentStatus = PaymentStatus.PAID
    payment_reference: Optional[str] = Field(default=None, max_length=120)


class OwnerMarkPaidRequest(BaseModel):
    amount: Optional[float] = Field(default=None, ge=0)
    payment_reference: Optional[str] = Field(default=None, max_length=120)


class OwnerStudentRow(BaseModel):
    student_id: str
    name: str
    email: str
    phone: Optional[str] = None
    verification_status: str
    must_set_password: bool = False
    booking_id: Optional[str] = None
    cabin_id: Optional[str] = None
    cabin_number: Optional[str] = None
    reading_room_id: Optional[str] = None
    reading_room_name: Optional[str] = None
    joining_date: Optional[str] = None
    expiry_date: Optional[str] = None
    renewal_window_start: Optional[str] = None
    renewal_window_end: Optional[str] = None
    renewal_status: Optional[RenewalStatus] = None
    renewal_day: Optional[int] = None
    payment_status: Optional[PaymentStatus] = None
    booking_status: Optional[BookingStatus] = None
    amount: Optional[float] = None
    duration_type: Optional[str] = None
    created_at: Optional[datetime] = None


class OwnerStudentActionResponse(BaseModel):
    success: bool
    message: str
    student: Optional[OwnerStudentRow] = None
