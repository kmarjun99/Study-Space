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
from app.deps import get_current_user, dev_only

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
    is_demo: bool = False


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
    
    # 🆕 Determine payment type based on venue status
    # If venue is already VERIFICATION_PENDING or LIVE, it's an upgrade/resubmission
    is_upgrade = venue.status in [ListingStatus.VERIFICATION_PENDING, ListingStatus.LIVE]
    current_plan = None
    
    # Validate upgrade if venue has existing subscription
    if venue.subscription_plan_id:
        current_plan_result = await db.execute(
            select(SubscriptionPlan).where(SubscriptionPlan.id == venue.subscription_plan_id)
        )
        current_plan = current_plan_result.scalar_one_or_none()
        
        if current_plan and current_plan.id != plan.id:
            # Trying to change plan - validate it's higher tier
            if plan.price <= current_plan.price:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Can only upgrade to higher-tier plans. Current: {current_plan.name} (₹{current_plan.price}), Selected: {plan.name} (₹{plan.price})"
                )
        elif current_plan and current_plan.id == plan.id:
            # Trying to pay for same plan again
            raise HTTPException(
                status_code=400, 
                detail=f"You already have the {current_plan.name} plan. Please select a different plan to upgrade."
            )
    
    # Validate venue status for new payments only
    if not is_upgrade:
        if venue.status not in [ListingStatus.DRAFT, ListingStatus.REJECTED]:
            raise HTTPException(
                status_code=400, 
                detail=f"Venue status must be DRAFT or REJECTED for initial payment. Current status: {venue.status}"
            )
    
    # Create Razorpay order
    order = payment_service.create_order(
        amount=request.amount,
        receipt=f"venue_{'upgrade' if is_upgrade else 'new'}_{request.venue_type}_{request.venue_id}",
        notes={
            "venue_id": request.venue_id,
            "venue_type": request.venue_type,
            "subscription_plan_id": request.subscription_plan_id,
            "owner_id": current_user.id,
            "owner_email": current_user.email or "",
            "is_upgrade": str(is_upgrade),
            "previous_plan_id": current_plan.id if current_plan else ""
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
        },
        is_demo=order.get("is_demo", False)
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
    
    # 🆕 Detect if this is an upgrade
    is_upgrade = bool(venue.subscription_plan_id)
    previous_status = venue.status
    
    # Update venue - for upgrades, keep existing status
    if not is_upgrade:
        # New payment - set to VERIFICATION_PENDING
        venue.status = ListingStatus.VERIFICATION_PENDING
    # else: keep current status (VERIFICATION_PENDING or LIVE)
    
    venue.subscription_plan_id = request.subscription_plan_id
    venue.payment_id = request.razorpay_payment_id
    # ReadingRoom.payment_date is DateTime; Accommodation.payment_date is String
    venue.payment_date = datetime.utcnow() if request.venue_type == 'reading_room' else datetime.utcnow().isoformat()
    
    await db.commit()
    
    # Fetch payment details
    try:
        payment_info = payment_service.fetch_payment(request.razorpay_payment_id)
    except Exception as e:
        print(f"Could not fetch payment info: {e}")
        payment_info = {"amount": 0, "method": "card"}
    
    message = (
        f"Plan upgraded successfully. Status: {venue.status.value}"
        if is_upgrade 
        else "Payment verified successfully. Venue submitted for admin approval."
    )
    
    return {
        "message": message,
        "venue_id": request.venue_id,
        "status": venue.status,
        "payment_id": request.razorpay_payment_id,
        "subscription_plan": {
            "name": plan.name,
            "duration_days": plan.duration_days
        },
        "amount": payment_info.get("amount", 0) / 100,  # Convert paise to rupees
        "is_upgrade": is_upgrade
    }


@router.post("/dev-bypass", dependencies=[Depends(dev_only)])
async def dev_bypass_payment(
    request: CreateVenueOrderRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    DEVELOPMENT ONLY: Bypass payment gateway and mark venue as paid.

    Gated by `dev_only` — returns 404 in production. To enable on a
    non-dev environment temporarily (e.g. staging diagnostics), set
    `ENABLE_DEV_BYPASS=true` in the deploy's env vars. The override is
    read at request time so it can be toggled without a redeploy.

    Previously this endpoint was reachable on prod with only standard
    auth, meaning any authenticated owner could mark their own venue as
    paid for any plan without going through Razorpay. That was a
    critical revenue-loss path.
    """
    try:
        print(f"[DEV-BYPASS] Request received: {request.dict()}")
        print(f"[DEV-BYPASS] User: {current_user.email}")
        
        # Verify subscription plan
        plan_result = await db.execute(
            select(SubscriptionPlan).where(SubscriptionPlan.id == request.subscription_plan_id)
        )
        plan = plan_result.scalar_one_or_none()
        
        if not plan:
            print(f"[DEV-BYPASS] Plan not found: {request.subscription_plan_id}")
            raise HTTPException(status_code=404, detail="Subscription plan not found")
        
        print(f"[DEV-BYPASS] Found plan: {plan.name}")
        
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
            print(f"[DEV-BYPASS] Venue not found: {request.venue_id} (type: {request.venue_type})")
            raise HTTPException(status_code=404, detail="Venue not found")
        
        print(f"[DEV-BYPASS] Found venue: {venue.name}")
        
        # Validate venue data
        errors = []
        if not venue.name: errors.append("Name")
        if not venue.address: errors.append("Address")
        if not venue.city: errors.append("City")
        if not venue.contact_phone: errors.append("Phone")
        
        print(f"[DEV-BYPASS] Validating images. venue.images = {venue.images}")
        
        # Image validation - handle both JSON string and list formats
        import json
        valid_images = False
        if venue.images:
            try:
                # Handle case where images might already be a list (from Pydantic)
                if isinstance(venue.images, list):
                    imgs = venue.images
                elif isinstance(venue.images, str):
                    imgs = json.loads(venue.images)
                else:
                    imgs = []
                
                print(f"[DEV-BYPASS] Parsed images: {imgs}, type: {type(imgs)}, count: {len(imgs) if isinstance(imgs, list) else 0}")
                if isinstance(imgs, list) and len(imgs) >= 4:
                    valid_images = True
            except json.JSONDecodeError as img_error:
                print(f"[DEV-BYPASS] JSON decode error for images: {img_error}")
            except Exception as img_error:
                print(f"[DEV-BYPASS] Image validation error: {img_error}")
        
        print(f"[DEV-BYPASS] Image validation result: valid={valid_images}")
        
        if not valid_images:
            errors.append("Minimum 4 Images")
        
        print(f"[DEV-BYPASS] Validation errors: {errors}")
        
        if errors:
            raise HTTPException(
                status_code=400, 
                detail=f"Cannot complete submission. Incomplete venue details: {', '.join(errors)}"
            )
        
        # 🆕 Detect if this is an upgrade
        is_upgrade = bool(venue.subscription_plan_id)
        
        # Update venue - for upgrades, keep existing status
        if not is_upgrade:
            # New payment - set to VERIFICATION_PENDING
            venue.status = ListingStatus.VERIFICATION_PENDING
        # else: keep current status (VERIFICATION_PENDING or LIVE)
        
        venue.subscription_plan_id = request.subscription_plan_id
        venue.payment_id = f"dev_bypass_{datetime.utcnow().timestamp()}"
        # ReadingRoom.payment_date is DateTime; Accommodation.payment_date is String
        venue.payment_date = datetime.utcnow() if request.venue_type == 'reading_room' else datetime.utcnow().isoformat()
        
        await db.commit()
        await db.refresh(venue)
        
        message = (
            f"Plan upgraded successfully (dev mode). Status: {venue.status.value}"
            if is_upgrade 
            else "Venue submitted successfully (dev mode). Awaiting admin approval."
        )
        
        return {
            "message": message,
            "venue_id": request.venue_id,
            "status": venue.status.value if hasattr(venue.status, 'value') else str(venue.status),
            "subscription_plan": {
                "name": plan.name,
                "duration_days": plan.duration_days
            },
            "is_upgrade": is_upgrade
        }
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        error_detail = f"Payment processing error: {str(e)}\n{traceback.format_exc()}"
        print(error_detail)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


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
