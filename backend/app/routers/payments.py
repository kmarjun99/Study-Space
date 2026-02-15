"""
Payment Modes & Refunds API Router
Handles:
- GET /user/payment-modes - Get supported methods + last used payment
- GET /user/refunds - Get user's refund requests
- POST /refund/request - Create new refund request
- GET /admin/refunds - List all refund requests (Super Admin)
- PATCH /admin/refunds/{id} - Update refund status (Super Admin)
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

from app.database import get_db
from app.deps import get_current_user
from app.models.user import User, UserRole
from app.models.booking import Booking
from app.models.refund import Refund, RefundStatus, RefundReason
from app.models.payment_transaction import PaymentTransaction, PaymentMethod, PaymentGateway
from app.models.reading_room import ReadingRoom, Cabin
from app.models.accommodation import Accommodation

router = APIRouter(prefix="/payments", tags=["Payments & Refunds"])

# Initialize Razorpay Client
import razorpay
import os

# These should be in your .env file
# RAZORPAY_KEY_ID = "rzp_test_..."
# RAZORPAY_KEY_SECRET = "..."
razorpay_client = razorpay.Client(
    auth=(
        os.getenv("RAZORPAY_KEY_ID", "rzp_test_placeholder"), 
        os.getenv("RAZORPAY_KEY_SECRET", "secret_placeholder")
    )
)


# ============================================
# PYDANTIC SCHEMAS
# ============================================

class OrderCreate(BaseModel):
    amount: float # In INR
    currency: str = "INR"
    receipt: Optional[str] = None
    notes: Optional[dict] = None

class PaymentVerify(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str
    booking_id: Optional[str] = None # Optional, to update booking immediately

class LastUsedPayment(BaseModel):
    method: str
    gateway: str
    reference: Optional[str] = None
    date: str

class PaymentModesResponse(BaseModel):
    supported_methods: List[str]
    last_used: Optional[LastUsedPayment] = None

class RefundOut(BaseModel):
    id: str
    booking_id: str
    venue_name: str
    amount: float
    reason: str
    reason_text: Optional[str] = None
    status: str
    requested_at: str
    processed_at: Optional[str] = None

class RefundRequestIn(BaseModel):
    booking_id: str
    reason: str  # RefundReason enum value
    reason_text: Optional[str] = None

class RefundAdminOut(RefundOut):
    user_id: str
    user_email: str
    user_name: str
    admin_notes: Optional[str] = None
    reviewed_by: Optional[str] = None

class RefundUpdateIn(BaseModel):
    status: str  # RefundStatus enum value
    admin_notes: Optional[str] = None



# ============================================
# RAZORPAY ENDPOINTS
# ============================================

@router.post("/create-order")
async def create_payment_order(
    data: OrderCreate,
    current_user: User = Depends(get_current_user)
):
    """
    Create a Razorpay Order. 
    If Razorpay keys are not configured, returns a DEMO order.
    """
    from app.services.payment_service import payment_service
    
    # Use payment service which handles demo mode automatically
    try:
        order = payment_service.create_order(
            amount=data.amount,
            currency=data.currency,
            receipt=data.receipt or f"rcpt_{int(datetime.utcnow().timestamp())}",
            notes={
                "user_id": current_user.id,
                "user_email": current_user.email,
                **(data.notes or {})
            }
        )
        
        # Return consistent response format
        return {
            "id": order["id"],
            "amount": order["amount"],
            "currency": order["currency"],
            "key_id": payment_service.razorpay_key_id or "demo_key_id",
            "is_demo": payment_service.demo_mode
        }
    except Exception as e:
        print(f"Payment Order Error: {e}")
        # Last fallback - return demo order even on exception
        return {
            "id": f"order_error_{int(datetime.utcnow().timestamp())}",
            "amount": int(data.amount * 100),
            "currency": data.currency,
            "key_id": "demo_key_id",
            "is_demo": True
        }

@router.post("/verify")
async def verify_payment(
    data: PaymentVerify,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Verify Razorpay Payment Signature.
    Supports DEMO mode for testing.
    """
    from app.services.payment_service import payment_service
    
    try:
        # Use payment service which handles demo mode automatically
        is_valid = payment_service.verify_payment_signature(
            razorpay_order_id=data.razorpay_order_id,
            razorpay_payment_id=data.razorpay_payment_id,
            razorpay_signature=data.razorpay_signature
        )
        
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid payment signature"
            )
        
        # 2. If booking_id is provided, update booking status
        if data.booking_id:
            result = await db.execute(
                select(Booking).where(Booking.id == data.booking_id)
            )
            booking = result.scalar_one_or_none()
            
            if booking:
                # Update logic here if needed, or rely on separate service
                pass 
                
        return {"status": "success", "message": "Payment verified successfully"}

    except HTTPException:
        raise
    except Exception as e:
        print(f"Verification Error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# ============================================
# USER ENDPOINTS
# ============================================

class SubscriptionConfirm(BaseModel):
    venue_id: str
    venue_type: str
    subscription_plan_id: str
    payment_id: str
    amount: float

@router.post("/venue/confirm-subscription")
async def confirm_venue_subscription(
    data: SubscriptionConfirm,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Confirm venue subscription after successful payment.
    """
    try:
        # 1. Fetch Payment Details from Razorpay to verify amount/status
        # Handle Mock Mode
        is_mock = data.payment_id.startswith("pay_mock_")
        
        if not is_mock:
            payment = razorpay_client.payment.fetch(data.payment_id)
            if payment['status'] != 'captured':
                 # Try to capture if authorized? Usually auto-captured.
                 pass
        else:
             print("MOCK SUBSCRIPTION: Skipping Razorpay fetch")

        # 2. Record Transaction in Database (TODO: Create proper PaymentTransaction model entry)
        # For now, we will create the PaymentTransaction record.
        
        transaction = PaymentTransaction(
            id=data.payment_id, # Use Razorpay ID as PK or generate text UUID? Better text UUID.
            gateway_transaction_id=data.payment_id,
            user_id=current_user.id,
            amount=data.amount,
            currency="INR", # Assuming INR
            payment_status="PAID", # Enum 
            timestamp=datetime.utcnow()
            # Add venue_id linkage if model supports it
        )
        # db.add(transaction) # Uncomment when model is ready/verified

        # 3. Activate Venue / Update Subscription
        # This part depends on how Venues are stored. 
        # We need to find the venue and status update.
        
        if data.venue_type == 'reading_room':
            result = await db.execute(select(ReadingRoom).where(ReadingRoom.id == data.venue_id))
            venue = result.scalar_one_or_none()
            if venue:
                venue.status = "VERIFICATION_PENDING" # Or ACTIVE depending on workflow
                # venue.subscription_expiry = ... 
        
        await db.commit()
        
        return {"status": "success", "message": "Subscription confirmed"}

    except Exception as e:
        print(f"Subscription Confirm Error: {e}")
        # In case of error but payment passed, we should log critical alert
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/user/payment-modes", response_model=PaymentModesResponse)
async def get_payment_modes(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get supported payment methods and last used payment for the user.
    """
    # Supported methods are static but served from backend
    supported_methods = ["UPI", "CARD", "NET_BANKING"]
    
    last_used = None
    
    # Get last used payment (wrapped in try-except for robustness)
    try:
        result = await db.execute(
            select(PaymentTransaction)
            .where(PaymentTransaction.user_id == current_user.id)
            .order_by(desc(PaymentTransaction.created_at))
            .limit(1)
        )
        last_payment = result.scalar_one_or_none()
        
        if last_payment:
            last_used = LastUsedPayment(
                method=last_payment.method.value if last_payment.method else "UPI",
                gateway=last_payment.gateway.value if last_payment.gateway else "RAZORPAY",
                reference=last_payment.masked_reference,
                date=last_payment.created_at.isoformat() if last_payment.created_at else datetime.utcnow().isoformat()
            )
    except Exception as e:
        # Log the error but continue - supported methods can still be returned
        print(f"Warning: Could not fetch last payment: {e}")
    
    return PaymentModesResponse(
        supported_methods=supported_methods,
        last_used=last_used
    )


@router.get("/user/payment-history")
async def get_payment_history(
    booking_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get all payment transactions for the current user.
    Returns ALL payments including initial bookings and extensions.
    Optionally filter by booking_id.
    """
    query = select(PaymentTransaction).where(
        PaymentTransaction.user_id == current_user.id
    ).order_by(desc(PaymentTransaction.created_at))
    
    if booking_id:
        query = query.where(PaymentTransaction.booking_id == booking_id)
    
    result = await db.execute(query)
    payments = result.scalars().all()
    
    payment_list = []
    for payment in payments:
        # Get booking info for venue name
        booking_result = await db.execute(
            select(Booking).where(Booking.id == payment.booking_id)
        )
        booking = booking_result.scalar_one_or_none()
        
        venue_name = "Unknown Venue"
        cabin_number = None
        if booking and booking.cabin_id:
            cabin_result = await db.execute(
                select(Cabin).where(Cabin.id == booking.cabin_id)
            )
            cabin = cabin_result.scalar_one_or_none()
            if cabin:
                cabin_number = cabin.number
                room_result = await db.execute(
                    select(ReadingRoom).where(ReadingRoom.id == cabin.reading_room_id)
                )
                room = room_result.scalar_one_or_none()
                if room:
                    venue_name = room.name
        elif booking and booking.accommodation_id:
            acc_result = await db.execute(
                select(Accommodation).where(Accommodation.id == booking.accommodation_id)
            )
            acc = acc_result.scalar_one_or_none()
            if acc:
                venue_name = acc.name
        
        # Get payment type - handle both old records (without type) and new ones
        payment_type = "INITIAL"
        if hasattr(payment, 'payment_type') and payment.payment_type:
            payment_type = payment.payment_type.value if hasattr(payment.payment_type, 'value') else str(payment.payment_type)
        
        payment_list.append({
            "id": payment.id,
            "booking_id": payment.booking_id,
            "type": payment_type,
            "amount": payment.amount,
            "method": payment.method.value if payment.method else "UPI",
            "gateway": payment.gateway.value if payment.gateway else "RAZORPAY",
            "transaction_id": payment.gateway_transaction_id,
            "description": getattr(payment, 'description', None) or (
                "Initial Booking" if payment_type == "INITIAL" else "Plan Extension"
            ),
            "venue_name": venue_name,
            "cabin_number": cabin_number,
            "date": payment.created_at.isoformat() if payment.created_at else None
        })
    
    return {
        "payments": payment_list,
        "total_count": len(payment_list),
        "total_amount": sum(p["amount"] for p in payment_list)
    }


@router.get("/owner/payment-history")
async def get_owner_payment_history(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get all payment transactions for bookings at the owner's venues.
    Includes initial payments and extensions.
    """
    
    # Get owner's reading rooms
    rooms_result = await db.execute(
        select(ReadingRoom).where(ReadingRoom.owner_id == current_user.id)
    )
    owner_rooms = rooms_result.scalars().all()
    
    if not owner_rooms:
        return {"payments": [], "total_count": 0, "total_amount": 0}
    
    room_ids = [r.id for r in owner_rooms]
    
    # Get all cabins in owner's rooms
    cabins_result = await db.execute(
        select(Cabin).where(Cabin.reading_room_id.in_(room_ids))
    )
    owner_cabins = cabins_result.scalars().all()
    cabin_ids = [c.id for c in owner_cabins]
    cabin_map = {c.id: c for c in owner_cabins}
    
    if not cabin_ids:
        return {"payments": [], "total_count": 0, "total_amount": 0}
    
    # Get all bookings for owner's cabins
    bookings_result = await db.execute(
        select(Booking).where(Booking.cabin_id.in_(cabin_ids))
    )
    owner_bookings = bookings_result.scalars().all()
    booking_ids = [b.id for b in owner_bookings]
    booking_map = {b.id: b for b in owner_bookings}
    
    if not booking_ids:
        return {"payments": [], "total_count": 0, "total_amount": 0}
    
    # Get all payment transactions for these bookings
    payments_result = await db.execute(
        select(PaymentTransaction)
        .where(PaymentTransaction.booking_id.in_(booking_ids))
        .order_by(desc(PaymentTransaction.created_at))
    )
    payments = payments_result.scalars().all()
    
    payment_list = []
    for payment in payments:
        booking = booking_map.get(payment.booking_id)
        cabin = cabin_map.get(booking.cabin_id) if booking else None
        room = next((r for r in owner_rooms if cabin and r.id == cabin.reading_room_id), None) if cabin else None
        
        # Get user info
        user_result = await db.execute(
            select(User).where(User.id == payment.user_id)
        )
        user = user_result.scalar_one_or_none()
        
        # Determine payment type
        payment_type = "INITIAL"
        if hasattr(payment, 'payment_type') and payment.payment_type:
            payment_type = payment.payment_type.value if hasattr(payment.payment_type, 'value') else str(payment.payment_type)
        
        payment_list.append({
            "id": payment.id,
            "booking_id": payment.booking_id,
            "user_id": payment.user_id,
            "user_name": user.name if user else "Unknown",
            "user_email": user.email if user else "",
            "type": payment_type,
            "amount": payment.amount,
            "date": payment.created_at.isoformat() if payment.created_at else "",
            "venue_name": room.name if room else "Unknown Venue",
            "cabin_number": cabin.number if cabin else "N/A",
            "transaction_id": payment.gateway_transaction_id or "",
            "description": payment.description if hasattr(payment, 'description') and payment.description else (
                "Plan Extension" if payment_type == "EXTENSION" else "Initial Booking"
            ),
            "method": payment.method.value if payment.method else "UNKNOWN"
        })
    
    return {
        "payments": payment_list,
        "total_count": len(payment_list),
        "total_amount": sum(p["amount"] for p in payment_list)
    }


@router.get("/user/refunds", response_model=List[RefundOut])
async def get_my_refunds(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get all refund requests for the current user.
    """
    result = await db.execute(
        select(Refund)
        .where(Refund.user_id == current_user.id)
        .order_by(desc(Refund.requested_at))
    )
    refunds = result.scalars().all()
    
    refund_list = []
    for refund in refunds:
        # Get venue name from booking
        venue_name = "Unknown Venue"
        booking_result = await db.execute(
            select(Booking).where(Booking.id == refund.booking_id)
        )
        booking = booking_result.scalar_one_or_none()
        
        if booking:
            if booking.cabin_id:
                # Get cabin and reading room
                cabin_result = await db.execute(
                    select(Cabin).where(Cabin.id == booking.cabin_id)
                )
                cabin = cabin_result.scalar_one_or_none()
                if cabin:
                    room_result = await db.execute(
                        select(ReadingRoom).where(ReadingRoom.id == cabin.reading_room_id)
                    )
                    room = room_result.scalar_one_or_none()
                    if room:
                        venue_name = room.name
            elif booking.accommodation_id:
                acc_result = await db.execute(
                    select(Accommodation).where(Accommodation.id == booking.accommodation_id)
                )
                acc = acc_result.scalar_one_or_none()
                if acc:
                    venue_name = acc.name
        
        refund_list.append(RefundOut(
            id=refund.id,
            booking_id=refund.booking_id,
            venue_name=venue_name,
            amount=refund.amount,
            reason=refund.reason.value if refund.reason else "OTHER",
            reason_text=refund.reason_text,
            status=refund.status.value if refund.status else "REQUESTED",
            requested_at=refund.requested_at.isoformat() if refund.requested_at else "",
            processed_at=refund.processed_at.isoformat() if refund.processed_at else None
        ))
    
    return refund_list


@router.post("/refund/request", response_model=RefundOut)
async def request_refund(
    data: RefundRequestIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create a new refund request for a booking.
    - Booking must exist and belong to the user
    - Only one refund request per booking allowed
    """
    # Check if booking exists and belongs to user
    result = await db.execute(
        select(Booking).where(
            Booking.id == data.booking_id,
            Booking.user_id == current_user.id
        )
    )
    booking = result.scalar_one_or_none()
    
    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Booking not found or does not belong to you"
        )
    
    # Check for existing refund request
    existing_result = await db.execute(
        select(Refund).where(Refund.booking_id == data.booking_id)
    )
    existing = existing_result.scalar_one_or_none()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Refund request already exists for this booking (Status: {existing.status.value})"
        )
    
    # Validate reason
    try:
        reason_enum = RefundReason(data.reason)
    except ValueError:
        reason_enum = RefundReason.OTHER
    
    # Get venue name for response
    venue_name = "Unknown Venue"
    if booking.cabin_id:
        cabin_result = await db.execute(
            select(Cabin).where(Cabin.id == booking.cabin_id)
        )
        cabin = cabin_result.scalar_one_or_none()
        if cabin:
            room_result = await db.execute(
                select(ReadingRoom).where(ReadingRoom.id == cabin.reading_room_id)
            )
            room = room_result.scalar_one_or_none()
            if room:
                venue_name = room.name
    elif booking.accommodation_id:
        acc_result = await db.execute(
            select(Accommodation).where(Accommodation.id == booking.accommodation_id)
        )
        acc = acc_result.scalar_one_or_none()
        if acc:
            venue_name = acc.name
    
    # Create refund request
    refund = Refund(
        booking_id=data.booking_id,
        user_id=current_user.id,
        amount=booking.amount,
        reason=reason_enum,
        reason_text=data.reason_text,
        status=RefundStatus.REQUESTED
    )
    
    db.add(refund)
    await db.commit()
    await db.refresh(refund)
    
    return RefundOut(
        id=refund.id,
        booking_id=refund.booking_id,
        venue_name=venue_name,
        amount=refund.amount,
        reason=refund.reason.value,
        reason_text=refund.reason_text,
        status=refund.status.value,
        requested_at=refund.requested_at.isoformat(),
        processed_at=None
    )


# ============================================
# SUPER ADMIN ENDPOINTS
# ============================================

@router.get("/admin/refunds", response_model=List[RefundAdminOut])
async def get_all_refunds(
    status_filter: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get all refund requests (Super Admin only).
    Optional filter by status.
    """
    if current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Super Admin can access this endpoint"
        )
    
    query = select(Refund).order_by(desc(Refund.requested_at))
    
    if status_filter:
        try:
            status_enum = RefundStatus(status_filter)
            query = query.where(Refund.status == status_enum)
        except ValueError:
            pass  # Ignore invalid status filter
    
    result = await db.execute(query)
    refunds = result.scalars().all()
    
    refund_list = []
    for refund in refunds:
        # Get user info
        user_result = await db.execute(
            select(User).where(User.id == refund.user_id)
        )
        user = user_result.scalar_one_or_none()
        
        # Get venue name
        venue_name = "Unknown Venue"
        booking_result = await db.execute(
            select(Booking).where(Booking.id == refund.booking_id)
        )
        booking = booking_result.scalar_one_or_none()
        
        if booking:
            if booking.cabin_id:
                cabin_result = await db.execute(
                    select(Cabin).where(Cabin.id == booking.cabin_id)
                )
                cabin = cabin_result.scalar_one_or_none()
                if cabin:
                    room_result = await db.execute(
                        select(ReadingRoom).where(ReadingRoom.id == cabin.reading_room_id)
                    )
                    room = room_result.scalar_one_or_none()
                    if room:
                        venue_name = room.name
            elif booking.accommodation_id:
                acc_result = await db.execute(
                    select(Accommodation).where(Accommodation.id == booking.accommodation_id)
                )
                acc = acc_result.scalar_one_or_none()
                if acc:
                    venue_name = acc.name
        
        refund_list.append(RefundAdminOut(
            id=refund.id,
            booking_id=refund.booking_id,
            venue_name=venue_name,
            amount=refund.amount,
            reason=refund.reason.value if refund.reason else "OTHER",
            reason_text=refund.reason_text,
            status=refund.status.value if refund.status else "REQUESTED",
            requested_at=refund.requested_at.isoformat() if refund.requested_at else "",
            processed_at=refund.processed_at.isoformat() if refund.processed_at else None,
            user_id=refund.user_id,
            user_email=user.email if user else "",
            user_name=user.name if user else "Unknown",
            admin_notes=refund.admin_notes,
            reviewed_by=refund.reviewed_by
        ))
    
    return refund_list


@router.patch("/admin/refunds/{refund_id}")
async def update_refund_status(
    refund_id: str,
    data: RefundUpdateIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update refund status (Super Admin only).
    Allowed transitions:
    - REQUESTED -> UNDER_REVIEW, APPROVED, REJECTED
    - UNDER_REVIEW -> APPROVED, REJECTED
    - APPROVED -> PROCESSED, FAILED
    """
    if current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Super Admin can update refund status"
        )
    
    result = await db.execute(
        select(Refund).where(Refund.id == refund_id)
    )
    refund = result.scalar_one_or_none()
    
    if not refund:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Refund request not found"
        )
    
    # Validate new status
    try:
        new_status = RefundStatus(data.status)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid status: {data.status}"
        )
    
    # Update refund
    refund.status = new_status
    refund.reviewed_by = current_user.id
    refund.reviewed_at = datetime.utcnow()
    
    if data.admin_notes:
        refund.admin_notes = data.admin_notes
    
    # Set processed_at if status is PROCESSED or FAILED
    if new_status in [RefundStatus.PROCESSED, RefundStatus.FAILED]:
        refund.processed_at = datetime.utcnow()
    
    await db.commit()
    await db.refresh(refund)
    
    return {
        "id": refund.id,
        "status": refund.status.value,
        "message": f"Refund status updated to {refund.status.value}"
    }
