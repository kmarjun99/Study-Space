"""
Venue Payment Router - Handle subscription payments for venue listings
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

from app.database import get_db
from app.models.reading_room import ReadingRoom, ListingStatus
from app.models.accommodation import Accommodation
from app.models.subscription_plan import SubscriptionPlan
from app.models.user import User
from app.services.payment_service import payment_service
from app.deps import get_current_user

router = APIRouter(prefix="/payments/venue", tags=["Venue Payments"])


class CreateVenueOrderRequest(BaseModel):
    venue_id: str
    venue_type: str  # 'reading_room' or 'accommodation'
    subscription_plan_id: str
    amount: float  # Total including GST


class CreateVenueOrderResponse(BaseModel):
    order_id: str
    amount: int  # in paise
    currency: str
    razorpay_key_id: str
    subscription_plan: dict


class VerifyVenuePaymentRequest(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str
    venue_id: str
    venue_type: str
    subscription_plan_id: str


@router.post("/create-order", response_model=CreateVenueOrderResponse)
async def create_venue_payment_order(
    request: CreateVenueOrderRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Create a Razorpay order for venue subscription payment
    """
    # Verify subscription plan exists and is active
    plan_result = await db.execute(
        select(SubscriptionPlan).where(
            SubscriptionPlan.id == request.subscription_plan_id,
            SubscriptionPlan.is_active == True
        )
    )
    plan = plan_result.scalar_one_or_none()
    
    if not plan:
        raise HTTPException(status_code=404, detail="Subscription plan not found or inactive")
    
    # Verify venue exists and belongs to user
    venue = None
    if request.venue_type == 'reading_room':
        venue_result = await db.execute(
            select(ReadingRoom).where(
                ReadingRoom.id == request.venue_id,
                ReadingRoom.owner_id == current_user.id
            )
        )
        venue = venue_result.scalar_one_or_none()
    elif request.venue_type == 'accommodation':
        venue_result = await db.execute(
            select(Accommodation).where(
                Accommodation.id == request.venue_id,
                Accommodation.owner_id == current_user.id
            )
        )
        venue = venue_result.scalar_one_or_none()
    
    if not venue:
        raise HTTPException(status_code=404, detail="Venue not found or not authorized")
    
    # Check if venue is in correct status for payment
    if venue.status not in [ListingStatus.DRAFT, ListingStatus.REJECTED]:
        raise HTTPException(
            status_code=400, 
            detail=f"Cannot process payment. Venue status: {venue.status}"
        )
    
    # Create Razorpay order
    order = payment_service.create_order(
        amount=request.amount,
        receipt=f"venue_{request.venue_type}_{request.venue_id}",
        notes={
            "venue_id": request.venue_id,
            "venue_type": request.venue_type,
            "subscription_plan_id": request.subscription_plan_id,
            "owner_id": current_user.id,
            "owner_email": current_user.email or ""
        }
    )
    
    return CreateVenueOrderResponse(
        order_id=order["id"],
        amount=order["amount"],
        currency=order["currency"],
        razorpay_key_id=payment_service.razorpay_key_id,
        subscription_plan={
            "id": plan.id,
            "name": plan.name,
            "price": plan.price,
            "duration_days": plan.duration_days
        }
    )


@router.post("/verify")
async def verify_venue_payment(
    request: VerifyVenuePaymentRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Verify Razorpay payment signature and update venue status
    """
    # Verify payment signature
    is_valid = payment_service.verify_payment_signature(
        request.razorpay_order_id,
        request.razorpay_payment_id,
        request.razorpay_signature
    )
    
    if not is_valid:
        raise HTTPException(status_code=400, detail="Invalid payment signature")
    
    # Verify subscription plan
    plan_result = await db.execute(
        select(SubscriptionPlan).where(SubscriptionPlan.id == request.subscription_plan_id)
    )
    plan = plan_result.scalar_one_or_none()
    
    if not plan:
        raise HTTPException(status_code=404, detail="Subscription plan not found")
    
    # Get venue and update status
    venue = None
    if request.venue_type == 'reading_room':
        venue_result = await db.execute(
            select(ReadingRoom).where(
                ReadingRoom.id == request.venue_id,
                ReadingRoom.owner_id == current_user.id
            )
        )
        venue = venue_result.scalar_one_or_none()
    elif request.venue_type == 'accommodation':
        venue_result = await db.execute(
            select(Accommodation).where(
                Accommodation.id == request.venue_id,
                Accommodation.owner_id == current_user.id
            )
        )
        venue = venue_result.scalar_one_or_none()
    
    if not venue:
        raise HTTPException(status_code=404, detail="Venue not found")
    
    # Validate venue data before marking as paid
    errors = []
    if not venue.name: errors.append("Name")
    if not venue.address: errors.append("Address")
    if not venue.city: errors.append("City")
    if not venue.contact_phone: errors.append("Phone")
    
    # Image validation
    import json
    valid_images = False
    if venue.images:
        try:
            imgs = json.loads(venue.images)
            if isinstance(imgs, list) and len(imgs) >= 4:
                valid_images = True
        except:
            pass
    
    if not valid_images:
        errors.append("Minimum 4 Images")
    
    if errors:
        raise HTTPException(
            status_code=400, 
            detail=f"Cannot complete payment. Incomplete venue details: {', '.join(errors)}"
        )
    
    # Update venue status to VERIFICATION_PENDING
    venue.status = ListingStatus.VERIFICATION_PENDING
    venue.subscription_plan_id = request.subscription_plan_id
    venue.payment_id = request.razorpay_payment_id
    venue.payment_date = datetime.utcnow()
    
    await db.commit()
    
    # Fetch payment details
    try:
        payment_info = payment_service.fetch_payment(request.razorpay_payment_id)
    except Exception as e:
        print(f"Could not fetch payment info: {e}")
        payment_info = {"amount": 0, "method": "card"}
    
    return {
        "message": "Payment verified successfully. Venue submitted for admin approval.",
        "venue_id": request.venue_id,
        "status": venue.status,
        "payment_id": request.razorpay_payment_id,
        "subscription_plan": {
            "name": plan.name,
            "duration_days": plan.duration_days
        },
        "amount": payment_info.get("amount", 0) / 100  # Convert paise to rupees
    }


@router.post("/dev-bypass")
async def dev_bypass_payment(
    request: CreateVenueOrderRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    DEVELOPMENT ONLY: Bypass payment gateway and mark venue as paid
    """
    # Verify subscription plan
    plan_result = await db.execute(
        select(SubscriptionPlan).where(SubscriptionPlan.id == request.subscription_plan_id)
    )
    plan = plan_result.scalar_one_or_none()
    
    if not plan:
        raise HTTPException(status_code=404, detail="Subscription plan not found")
    
    # Get venue and update status
    venue = None
    if request.venue_type == 'reading_room':
        venue_result = await db.execute(
            select(ReadingRoom).where(
                ReadingRoom.id == request.venue_id,
                ReadingRoom.owner_id == current_user.id
            )
        )
        venue = venue_result.scalar_one_or_none()
    elif request.venue_type == 'accommodation':
        venue_result = await db.execute(
            select(Accommodation).where(
                Accommodation.id == request.venue_id,
                Accommodation.owner_id == current_user.id
            )
        )
        venue = venue_result.scalar_one_or_none()
    
    if not venue:
        raise HTTPException(status_code=404, detail="Venue not found")
    
    # Validate venue data
    errors = []
    if not venue.name: errors.append("Name")
    if not venue.address: errors.append("Address")
    if not venue.city: errors.append("City")
    if not venue.contact_phone: errors.append("Phone")
    
    # Image validation
    import json
    valid_images = False
    if venue.images:
        try:
            imgs = json.loads(venue.images)
            if isinstance(imgs, list) and len(imgs) >= 4:
                valid_images = True
        except:
            pass
    
    if not valid_images:
        errors.append("Minimum 4 Images")
    
    if errors:
        raise HTTPException(
            status_code=400, 
            detail=f"Cannot complete submission. Incomplete venue details: {', '.join(errors)}"
        )
    
    # Update venue status to VERIFICATION_PENDING
    venue.status = ListingStatus.VERIFICATION_PENDING
    venue.subscription_plan_id = request.subscription_plan_id
    venue.payment_id = f"dev_bypass_{datetime.utcnow().timestamp()}"
    venue.payment_date = datetime.utcnow()
    
    await db.commit()
    
    return {
        "message": "Venue submitted successfully (dev mode). Awaiting admin approval.",
        "venue_id": request.venue_id,
        "status": venue.status,
        "subscription_plan": {
            "name": plan.name,
            "duration_days": plan.duration_days
        }
    }


@router.get("/status/{venue_id}")
async def get_venue_payment_status(
    venue_id: str,
    venue_type: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get payment status for a venue
    """
    venue = None
    if venue_type == 'reading_room':
        venue_result = await db.execute(
            select(ReadingRoom).where(
                ReadingRoom.id == venue_id,
                ReadingRoom.owner_id == current_user.id
            )
        )
        venue = venue_result.scalar_one_or_none()
    elif venue_type == 'accommodation':
        venue_result = await db.execute(
            select(Accommodation).where(
                Accommodation.id == venue_id,
                Accommodation.owner_id == current_user.id
            )
        )
        venue = venue_result.scalar_one_or_none()
    
    if not venue:
        raise HTTPException(status_code=404, detail="Venue not found")
    
    payment_status = "unpaid"
    if venue.status in [ListingStatus.VERIFICATION_PENDING, ListingStatus.LIVE]:
        payment_status = "paid"
    
    return {
        "venue_id": venue_id,
        "status": venue.status,
        "payment_status": payment_status,
        "payment_id": getattr(venue, 'payment_id', None),
        "payment_date": getattr(venue, 'payment_date', None),
        "subscription_plan_id": getattr(venue, 'subscription_plan_id', None)
    }
