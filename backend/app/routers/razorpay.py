from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

from app.database import get_db
from app.models.booking import Booking, PaymentStatus
from app.models.user import User
from app.services.payment_service import payment_service
from app.deps import get_current_user

router = APIRouter(prefix="/payments", tags=["Razorpay Payments"])


class CreateOrderRequest(BaseModel):
    booking_id: str
    amount: float


class CreateOrderResponse(BaseModel):
    order_id: str
    amount: int  # in paise
    currency: str
    razorpay_key_id: str


class VerifyPaymentRequest(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str
    booking_id: str


class RefundRequest(BaseModel):
    booking_id: str
    amount: Optional[float] = None
    reason: Optional[str] = None


@router.post("/create-order", response_model=CreateOrderResponse)
async def create_payment_order(
    request: CreateOrderRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Create a Razorpay order for a booking
    """
    # Verify booking exists and belongs to user
    result = await db.execute(
        select(Booking).where(
            Booking.id == request.booking_id,
            Booking.user_id == current_user.id
        )
    )
    booking = result.scalar_one_or_none()
    
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    
    if booking.payment_status == PaymentStatus.PAID:
        raise HTTPException(status_code=400, detail="Booking already paid")
    
    # Create Razorpay order
    order = payment_service.create_order(
        amount=request.amount,
        receipt=f"booking_{booking.id}",
        notes={
            "booking_id": booking.id,
            "user_id": current_user.id,
            "user_email": current_user.email or ""
        }
    )
    
    # Update booking with order ID (store in transaction_id temporarily)
    booking.transaction_id = order["id"]
    await db.commit()
    
    return CreateOrderResponse(
        order_id=order["id"],
        amount=order["amount"],
        currency=order["currency"],
        razorpay_key_id=payment_service.razorpay_key_id
    )


@router.post("/verify")
async def verify_payment(
    request: VerifyPaymentRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Verify Razorpay payment signature and update booking
    """
    # Verify signature
    is_valid = payment_service.verify_payment_signature(
        request.razorpay_order_id,
        request.razorpay_payment_id,
        request.razorpay_signature
    )
    
    if not is_valid:
        raise HTTPException(status_code=400, detail="Invalid payment signature")
    
    # Fetch payment details from Razorpay
    payment = payment_service.fetch_payment(request.razorpay_payment_id)
    
    # Update booking
    result = await db.execute(
        select(Booking).where(
            Booking.id == request.booking_id,
            Booking.user_id == current_user.id
        )
    )
    booking = result.scalar_one_or_none()
    
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    
    # Update payment status
    booking.payment_status = PaymentStatus.PAID
    booking.transaction_id = request.razorpay_payment_id
    
    await db.commit()
    await db.refresh(booking)
    
    # Send booking confirmation email
    try:
        from app.services.email_service import send_booking_confirmation_email
        from app.models.reading_room import Cabin, ReadingRoom
        from app.models.accommodation import Accommodation
        
        venue_name = "Venue"
        venue_address = ""
        cabin_number = None
        booking_type = "booking"
        
        if booking.cabin_id:
            cabin_result = await db.execute(select(Cabin).where(Cabin.id == booking.cabin_id))
            cabin = cabin_result.scalar_one_or_none()
            if cabin:
                cabin_number = cabin.number
                room_result = await db.execute(select(ReadingRoom).where(ReadingRoom.id == cabin.reading_room_id))
                room = room_result.scalar_one_or_none()
                if room:
                    venue_name = room.name
                    venue_address = room.address or ""
            booking_type = "cabin"
        elif booking.accommodation_id:
            acc_result = await db.execute(select(Accommodation).where(Accommodation.id == booking.accommodation_id))
            accommodation = acc_result.scalar_one_or_none()
            if accommodation:
                venue_name = accommodation.name
                venue_address = accommodation.address or ""
            booking_type = "accommodation"
        
        await send_booking_confirmation_email(
            recipient_email=current_user.email,
            recipient_name=current_user.name,
            booking_details={
                "venue_name": venue_name,
                "booking_type": booking_type,
                "start_date": booking.start_date.strftime("%d %B %Y") if booking.start_date else "N/A",
                "end_date": booking.end_date.strftime("%d %B %Y") if booking.end_date else "N/A",
                "amount": f"{booking.amount:,.2f}",
                "transaction_id": request.razorpay_payment_id,
                "venue_address": venue_address,
                "cabin_number": cabin_number
            }
        )
    except Exception as email_error:
        print(f"Failed to send booking confirmation email: {email_error}")
    
    return {
        "success": True,
        "message": "Payment verified successfully",
        "booking_id": booking.id,
        "payment_id": request.razorpay_payment_id,
        "amount": payment["amount"] / 100  # Convert paise to rupees
    }


@router.post("/refund")
async def refund_payment(
    request: RefundRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Process refund for a booking (Admin/Owner only for now)
    """
    # Verify booking exists
    result = await db.execute(
        select(Booking).where(Booking.id == request.booking_id)
    )
    booking = result.scalar_one_or_none()
    
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    
    if booking.payment_status != PaymentStatus.PAID:
        raise HTTPException(status_code=400, detail="Booking is not paid")
    
    # Process refund
    refund = payment_service.refund_payment(
        payment_id=booking.transaction_id,
        amount=request.amount,
        notes={"reason": request.reason or "User requested refund"}
    )
    
    # Update booking status
    booking.payment_status = PaymentStatus.REFUNDED
    await db.commit()
    
    return {
        "success": True,
        "message": "Refund processed successfully",
        "refund_id": refund["id"],
        "amount": refund["amount"] / 100
    }


@router.get("/status/{booking_id}")
async def get_payment_status(
    booking_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get payment status for a booking
    """
    result = await db.execute(
        select(Booking).where(
            Booking.id == booking_id,
            Booking.user_id == current_user.id
        )
    )
    booking = result.scalar_one_or_none()
    
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    
    return {
        "booking_id": booking.id,
        "payment_status": booking.payment_status.value if booking.payment_status else "PENDING",
        "transaction_id": booking.transaction_id,
        "amount": booking.amount
    }
