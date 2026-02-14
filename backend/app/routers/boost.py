"""
Boost Router - Plans created by Super Admin, Requests created by Owners
"""
from typing import List, Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from pydantic import BaseModel
from app.database import get_db
from app.models.boost_plan import BoostPlan, BoostPlanStatus, BoostApplicableTo, BoostPlacement
from app.models.boost_request import BoostRequest, BoostRequestStatus, VenueType
from app.models.user import User, UserRole
from app.models.reading_room import ReadingRoom
from app.models.accommodation import Accommodation
from app.deps import get_current_user, get_current_admin, get_current_user_optional


router = APIRouter(prefix="/boost", tags=["boost"])


# ============================================================
# SCHEMAS
# ============================================================

class BoostPlanCreate(BaseModel):
    name: str
    description: Optional[str] = None
    price: float
    duration_days: int
    applicable_to: str = "both"  # reading_room, accommodation, both
    placement: str = "featured_section"
    visibility_weight: int = 1
    status: str = "draft"


class BoostPlanUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None
    duration_days: Optional[int] = None
    applicable_to: Optional[str] = None
    placement: Optional[str] = None
    visibility_weight: Optional[int] = None
    status: Optional[str] = None


class BoostPlanResponse(BoostPlanCreate):
    id: str
    status: str
    created_by: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class BoostRequestCreate(BaseModel):
    venue_id: str
    venue_type: str  # reading_room, accommodation
    boost_plan_id: str


class BoostRequestResponse(BaseModel):
    id: str
    owner_id: str
    owner_name: Optional[str]
    venue_id: str
    venue_type: str
    venue_name: Optional[str]
    boost_plan_id: str
    plan_name: Optional[str]
    price: float
    duration_days: int
    placement: Optional[str]
    payment_id: Optional[str]
    status: str
    requested_at: datetime
    paid_at: Optional[datetime]
    approved_at: Optional[datetime]
    approved_by: Optional[str]
    expiry_date: Optional[datetime]
    admin_notes: Optional[str]
    rejection_reason: Optional[str]
    
    class Config:
        from_attributes = True


# ============================================================
# BOOST PLANS - SUPER ADMIN ONLY
# ============================================================

@router.get("/plans", response_model=List[BoostPlanResponse])
async def get_boost_plans(
    include_inactive: bool = False,
    db: AsyncSession = Depends(get_db)
):
    """
    Get all boost plans.
    Owners see only ACTIVE plans. Super Admin can see all via include_inactive=True.
    """
    # If include_inactive is False, filter by active ONLY
    query = select(BoostPlan)
    if not include_inactive:
        query = query.filter(BoostPlan.status == "active")
    
    query = query.order_by(BoostPlan.price)
    
    result = await db.execute(query)
    plans = result.scalars().all()
    print(f"DEBUG: Found {len(plans)} plans (Include Inactive: {include_inactive})")
    
    return plans


@router.post("/plans", response_model=BoostPlanResponse)
async def create_boost_plan(
    plan: BoostPlanCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Create a new boost plan. Super Admin only."""
    print(f"DEBUG: create_boost_plan called by {current_user.email} with role {current_user.role}")
    if current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=403, detail="Only Super Admin can create boost plans")
    
    new_plan = BoostPlan(
        name=plan.name,
        description=plan.description,
        price=plan.price,
        duration_days=plan.duration_days,
        applicable_to=plan.applicable_to,
        placement=plan.placement,
        visibility_weight=plan.visibility_weight,
        status=plan.status,  # Use status from payload
        created_by=current_user.id
    )
    
    db.add(new_plan)
    await db.commit()
    await db.refresh(new_plan)
    
    return new_plan


@router.put("/plans/{plan_id}", response_model=BoostPlanResponse)
async def update_boost_plan(
    plan_id: str,
    updates: BoostPlanUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Update a boost plan. Super Admin only."""
    if current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=403, detail="Only Super Admin can update boost plans")
    
    result = await db.execute(select(BoostPlan).where(BoostPlan.id == plan_id))
    plan = result.scalars().first()
    if not plan:
        raise HTTPException(status_code=404, detail="Boost plan not found")
    
    update_data = updates.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(plan, key, value)
    
    await db.commit()
    await db.refresh(plan)
    
    return plan


@router.delete("/plans/{plan_id}")
async def delete_boost_plan(
    plan_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Delete a boost plan. Super Admin only."""
    if current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=403, detail="Only Super Admin can delete boost plans")
    
    result = await db.execute(select(BoostPlan).where(BoostPlan.id == plan_id))
    plan = result.scalars().first()
    if not plan:
        raise HTTPException(status_code=404, detail="Boost plan not found")
    
    await db.delete(plan)
    await db.commit()
    
    return {"message": "Boost plan deleted successfully"}


# ============================================================
# BOOST REQUESTS - OWNERS
# ============================================================

@router.post("/request", response_model=BoostRequestResponse)
async def create_boost_request(
    request: BoostRequestCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)  # Changed from get_current_admin - Owners create requests
):
    """
    Create a boost request for a venue.
    This creates a REQUEST only - NOT activation.
    Owner must pay, then Super Admin must approve.
    """
    # Get the plan
    result = await db.execute(select(BoostPlan).where(BoostPlan.id == request.boost_plan_id))
    plan = result.scalars().first()
    if not plan:
        raise HTTPException(status_code=404, detail="Boost plan not found")
    
    if plan.status != BoostPlanStatus.ACTIVE:
        raise HTTPException(status_code=400, detail="This boost plan is not active")
    
    # BUSINESS RULE: Check for existing pending/active boost requests for this venue
    pending_statuses = [BoostRequestStatus.INITIATED, BoostRequestStatus.PAYMENT_PENDING, 
                        BoostRequestStatus.PAID, BoostRequestStatus.ADMIN_REVIEW, 
                        BoostRequestStatus.APPROVED, BoostRequestStatus.ACTIVE]
    existing_result = await db.execute(
        select(BoostRequest).where(
            BoostRequest.venue_id == request.venue_id,
            BoostRequest.owner_id == current_user.id,
            BoostRequest.status.in_(pending_statuses)
        )
    )
    existing_request = existing_result.scalars().first()
    if existing_request:
        raise HTTPException(
            status_code=400, 
            detail=f"You already have a pending or active boost request for this venue (Status: {existing_request.status.value}). Please wait for it to be processed or expire before submitting a new one."
        )
    
    # Get venue details
    venue_name = ""
    if request.venue_type == "reading_room":
        result = await db.execute(select(ReadingRoom).where(ReadingRoom.id == request.venue_id))
        venue = result.scalars().first()
        if not venue:
            raise HTTPException(status_code=404, detail="Reading room not found")
        if venue.owner_id != current_user.id:
            raise HTTPException(status_code=403, detail="Not authorized")
        venue_name = venue.name
    else:
        result = await db.execute(select(Accommodation).where(Accommodation.id == request.venue_id))
        venue = result.scalars().first()
        if not venue:
            raise HTTPException(status_code=404, detail="Accommodation not found")
        if venue.owner_id != current_user.id:
            raise HTTPException(status_code=403, detail="Not authorized")
        venue_name = venue.name
    
    # Create the request
    new_request = BoostRequest(
        owner_id=current_user.id,
        owner_name=current_user.name,
        owner_email=current_user.email,
        venue_id=request.venue_id,
        venue_type=VenueType(request.venue_type),
        venue_name=venue_name,
        boost_plan_id=plan.id,
        plan_name=plan.name,
        price=plan.price,
        duration_days=plan.duration_days,
        placement=plan.placement.value if hasattr(plan.placement, 'value') else str(plan.placement),
        status=BoostRequestStatus.PAYMENT_PENDING
    )
    
    db.add(new_request)
    await db.commit()
    await db.refresh(new_request)
    
    return BoostRequestResponse(
        id=new_request.id,
        owner_id=new_request.owner_id,
        owner_name=new_request.owner_name,
        venue_id=new_request.venue_id,
        venue_type=new_request.venue_type.value,
        venue_name=new_request.venue_name,
        boost_plan_id=new_request.boost_plan_id,
        plan_name=new_request.plan_name,
        price=new_request.price,
        duration_days=new_request.duration_days,
        placement=new_request.placement,
        payment_id=new_request.payment_id,
        status=new_request.status.value,
        requested_at=new_request.requested_at,
        paid_at=new_request.paid_at,
        approved_at=new_request.approved_at,
        approved_by=new_request.approved_by,
        expiry_date=new_request.expiry_date,
        admin_notes=new_request.admin_notes,
        rejection_reason=new_request.rejection_reason
    )


@router.get("/my-requests", response_model=List[BoostRequestResponse])
async def get_my_boost_requests(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all boost requests for the current owner."""
    result = await db.execute(
        select(BoostRequest)
        .where(BoostRequest.owner_id == current_user.id)
        .order_by(BoostRequest.requested_at.desc())
    )
    requests = result.scalars().all()
    
    return [
        BoostRequestResponse(
            id=r.id,
            owner_id=r.owner_id,
            owner_name=r.owner_name,
            venue_id=r.venue_id,
            venue_type=r.venue_type.value if hasattr(r.venue_type, 'value') else str(r.venue_type),
            venue_name=r.venue_name,
            boost_plan_id=r.boost_plan_id,
            plan_name=r.plan_name,
            price=r.price,
            duration_days=r.duration_days,
            placement=r.placement,
            payment_id=r.payment_id,
            status=r.status.value if hasattr(r.status, 'value') else str(r.status),
            requested_at=r.requested_at,
            paid_at=r.paid_at,
            approved_at=r.approved_at,
            approved_by=r.approved_by,
            expiry_date=r.expiry_date,
            admin_notes=r.admin_notes,
            rejection_reason=r.rejection_reason
        )
        for r in requests
    ]


# Import Razorpay client from payments router or initialize here
from app.routers.payments import razorpay_client
import razorpay

class PaymentConfirmation(BaseModel):
    payment_id: str
    order_id: str
    signature: str

@router.put("/request/{request_id}/pay")
async def mark_request_paid(
    request_id: str,
    payment_data: PaymentConfirmation,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Mark a boost request as paid after verifying Razorpay signature.
    Payment does NOT activate - admin approval needed.
    """
    try:
        # CHECK FOR MOCK MODE
        if payment_data.order_id.startswith("order_mock_"):
             print("MOCK BOOST: Skipping signature verification")
        else:
             # 1. Verify Signature
            params_dict = {
                'razorpay_order_id': payment_data.order_id,
                'razorpay_payment_id': payment_data.payment_id,
                'razorpay_signature': payment_data.signature
            }
            razorpay_client.utility.verify_payment_signature(params_dict)

    except razorpay.errors.SignatureVerificationError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid payment signature"
        )
    except Exception as e:
        print(f"Boost Payment Verification Error: {e}")
        raise HTTPException(status_code=500, detail="Payment verification failed")

    # 2. Update Request Status
    result = await db.execute(select(BoostRequest).where(BoostRequest.id == request_id))
    req = result.scalars().first()
    if not req:
        raise HTTPException(status_code=404, detail="Boost request not found")
    
    if req.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    req.payment_id = payment_data.payment_id
    req.paid_at = datetime.utcnow()
    req.status = BoostRequestStatus.PAID
    
    await db.commit()
    
    return {"message": "Payment recorded and verified. Pending admin approval."}


# ============================================================
# BOOST REQUESTS - SUPER ADMIN APPROVAL
# ============================================================

@router.get("/requests", response_model=List[BoostRequestResponse])
async def get_all_boost_requests(
    status_filter: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Get all boost requests. Super Admin only."""
    if current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=403, detail="Super Admin only")
    
    query = select(BoostRequest).order_by(BoostRequest.requested_at.desc())
    
    if status_filter:
        query = query.where(BoostRequest.status == BoostRequestStatus(status_filter))
    
    result = await db.execute(query)
    requests = result.scalars().all()
    
    return [
        BoostRequestResponse(
            id=r.id,
            owner_id=r.owner_id,
            owner_name=r.owner_name,
            venue_id=r.venue_id,
            venue_type=r.venue_type.value if hasattr(r.venue_type, 'value') else str(r.venue_type),
            venue_name=r.venue_name,
            boost_plan_id=r.boost_plan_id,
            plan_name=r.plan_name,
            price=r.price,
            duration_days=r.duration_days,
            placement=r.placement,
            payment_id=r.payment_id,
            status=r.status.value if hasattr(r.status, 'value') else str(r.status),
            requested_at=r.requested_at,
            paid_at=r.paid_at,
            approved_at=r.approved_at,
            approved_by=r.approved_by,
            expiry_date=r.expiry_date,
            admin_notes=r.admin_notes,
            rejection_reason=r.rejection_reason
        )
        for r in requests
    ]


class ApprovalRequest(BaseModel):
    admin_notes: Optional[str] = None


@router.put("/requests/{request_id}/approve")
async def approve_boost_request(
    request_id: str,
    approval: ApprovalRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Approve a boost request. Super Admin only."""
    if current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=403, detail="Super Admin only")
    
    result = await db.execute(select(BoostRequest).where(BoostRequest.id == request_id))
    req = result.scalars().first()
    if not req:
        raise HTTPException(status_code=404, detail="Boost request not found")
    
    # Allow approval for pending statuses (PAYMENT_PENDING means owner is ready, just waiting for manual payment confirmation in some cases)
    allowed_statuses = [BoostRequestStatus.INITIATED, BoostRequestStatus.PAYMENT_PENDING, 
                        BoostRequestStatus.PAID, BoostRequestStatus.ADMIN_REVIEW]
    if req.status not in allowed_statuses:
        raise HTTPException(status_code=400, detail=f"Cannot approve request in {req.status.value} status")
    
    now = datetime.utcnow()
    req.status = BoostRequestStatus.APPROVED
    req.approved_at = now
    req.approved_by = current_user.id
    req.activated_at = now
    req.expiry_date = now + timedelta(days=req.duration_days)
    req.admin_notes = approval.admin_notes
    
    await db.commit()
    
    return {"message": "Boost request approved and activated", "expiry_date": req.expiry_date.isoformat()}


class RejectionRequest(BaseModel):
    reason: str
    admin_notes: Optional[str] = None


@router.put("/requests/{request_id}/reject")
async def reject_boost_request(
    request_id: str,
    rejection: RejectionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Reject a boost request. Super Admin only."""
    if current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=403, detail="Super Admin only")
    
    result = await db.execute(select(BoostRequest).where(BoostRequest.id == request_id))
    req = result.scalars().first()
    if not req:
        raise HTTPException(status_code=404, detail="Boost request not found")
    
    req.status = BoostRequestStatus.REJECTED
    req.rejection_reason = rejection.reason
    req.admin_notes = rejection.admin_notes
    
    await db.commit()
    
    return {"message": "Boost request rejected"}


# ============================================================
# FEATURED LISTINGS - PUBLIC
# ============================================================

@router.get("/featured")
async def get_featured_listings(
    venue_type: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """
    Get featured listings (approved boosts that haven't expired).
    This is what users see - ONLY approved + valid listings.
    """
    now = datetime.utcnow()
    
    query = select(BoostRequest).where(
        BoostRequest.status == BoostRequestStatus.APPROVED,
        BoostRequest.expiry_date > now
    )
    
    if venue_type:
        query = query.where(BoostRequest.venue_type == VenueType(venue_type))
    
    result = await db.execute(query)
    featured = result.scalars().all()
    
    return [
        {
            "venue_id": f.venue_id,
            "venue_type": f.venue_type.value if hasattr(f.venue_type, 'value') else str(f.venue_type),
            "venue_name": f.venue_name,
            "placement": f.placement,
            "expiry_date": f.expiry_date.isoformat() if f.expiry_date else None
        }
        for f in featured
    ]
