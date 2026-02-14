from typing import List, Optional
from pydantic import BaseModel
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.database import get_db
from app.models.accommodation import Accommodation, AccommodationType, Gender
from app.models.reading_room import ListingStatus
from app.models.booking import Booking
from app.schemas.accommodation import AccommodationResponse, AccommodationCreate, AccommodationUpdate
from app.models.user import User, UserRole
from app.deps import get_current_admin, get_current_user_optional, get_current_user

router = APIRouter(prefix="/accommodations", tags=["accommodations"])

from app.utils.geo import haversine_distance, sort_by_proximity
import json

@router.get("/", response_model=List[AccommodationResponse])
async def get_accommodations(
    location: Optional[str] = None, # Text search
    price_max: Optional[float] = None,
    gender: Optional[Gender] = None,
    type: Optional[AccommodationType] = None,
    lat: Optional[float] = None,
    long: Optional[float] = None,
    radius: Optional[float] = 5.0,
    include_unverified: bool = False,
    limit: int = 50,  # Default limit to prevent massive responses
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    query = select(Accommodation)
    
    show_unverified = False
    if include_unverified:
         if current_user and current_user.role in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
             show_unverified = True
    
    if not show_unverified:
        # Show LIVE accommodations OR accommodations owned by current user (any status)
        if current_user:
            query = query.where(
                (Accommodation.status == ListingStatus.LIVE) | 
                (Accommodation.owner_id == current_user.id)
            )
        else:
            query = query.where(Accommodation.status == ListingStatus.LIVE)
    else:
        # Super Admin View - HARDCODED RULE: Hide listings that haven't completed payment
        # Filter out DRAFT and PAYMENT_PENDING
        query = query.where(
            Accommodation.status.notin_([ListingStatus.DRAFT, ListingStatus.PAYMENT_PENDING])
        )
    
    if location:
        query = query.where(
            Accommodation.address.ilike(f"%{location}%") | 
            Accommodation.city.ilike(f"%{location}%") | 
            Accommodation.area.ilike(f"%{location}%")
        )
    if price_max:
        query = query.where(Accommodation.price <= price_max)
    if gender:
        query = query.where(Accommodation.gender == gender)
    if type:
        query = query.where(Accommodation.type == type)
    
    # Apply pagination
    query = query.offset(offset).limit(limit)
        
    result = await db.execute(query)
    accommodations = result.scalars().all()
    
    if lat is not None and long is not None:
        nearby = []
        for acc in accommodations:
            if acc.latitude and acc.longitude:
                dist = haversine_distance(lat, long, acc.latitude, acc.longitude)
                if dist <= radius:
                    setattr(acc, '_distance', dist)
                    nearby.append(acc)
        return sort_by_proximity(lat, long, nearby)

    return accommodations

@router.get("/my", response_model=List[AccommodationResponse])
async def get_my_accommodations(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all accommodations owned by the current user, regardless of status."""
    query = select(Accommodation).where(Accommodation.owner_id == current_user.id)
    result = await db.execute(query)
    return result.scalars().all()

@router.post("/", response_model=AccommodationResponse)
async def create_accommodation(
    accommodation: AccommodationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    new_acc = Accommodation(
        **accommodation.model_dump(),
        owner_id=current_user.id,
        status=ListingStatus.DRAFT,
        is_verified=False
    )
    db.add(new_acc)
    await db.commit()
    await db.refresh(new_acc)
    return new_acc

@router.get("/{acc_id}", response_model=AccommodationResponse)
async def get_accommodation(
    acc_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    result = await db.execute(select(Accommodation).where(Accommodation.id == acc_id))
    acc = result.scalars().first()
    if not acc:
        raise HTTPException(status_code=404, detail="Accommodation not found")
        
    is_public = acc.status == ListingStatus.LIVE
    is_owner = current_user and acc.owner_id == current_user.id
    is_admin = current_user and current_user.role in [UserRole.ADMIN, UserRole.SUPER_ADMIN]
    
    if not (is_public or is_owner or is_admin):
         raise HTTPException(status_code=403, detail="Not authorized")

    return acc

@router.put("/{acc_id}", response_model=AccommodationResponse)
async def update_accommodation(
    acc_id: str,
    updates: AccommodationUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    result = await db.execute(select(Accommodation).where(Accommodation.id == acc_id))
    acc = result.scalars().first()
    if not acc:
        raise HTTPException(status_code=404, detail="Accommodation not found")
    
    if acc.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    update_data = updates.model_dump(exclude_unset=True)
    
    # Security: Prevent unauthorized status changes
    if current_user.role != UserRole.SUPER_ADMIN:
        if "status" in update_data:
            del update_data["status"]
            
    for key, value in update_data.items():
        setattr(acc, key, value)
    
    await db.commit()
    await db.refresh(acc)
    return acc


@router.delete("/{acc_id}")
async def delete_accommodation(
    acc_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Delete an accommodation. Only owner can delete. Cannot delete if there are any bookings."""
    result = await db.execute(select(Accommodation).where(Accommodation.id == acc_id))
    acc = result.scalars().first()
    if not acc:
        raise HTTPException(status_code=404, detail="Accommodation not found")
    
    if acc.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to delete this accommodation")
    
    # Check for any bookings on this accommodation
    bookings_check = await db.execute(
        select(Booking).where(Booking.accommodation_id == acc_id)
    )
    existing_bookings = bookings_check.scalars().first()
    if existing_bookings:
        raise HTTPException(
            status_code=400, 
            detail="Cannot delete accommodation with existing bookings. Please contact support if you need to remove this listing."
        )
    
    await db.delete(acc)
    await db.commit()
    
    return {"message": "Accommodation deleted successfully"}


@router.put("/{acc_id}/submit-payment")
async def submit_accommodation_payment(
    acc_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    result = await db.execute(select(Accommodation).where(Accommodation.id == acc_id))
    acc = result.scalars().first()
    if not acc:
        raise HTTPException(status_code=404, detail="Accommodation not found")
    
    if acc.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    # VALIDATION
    errors = []
    if not acc.name: errors.append("Name")
    if not acc.address: errors.append("Address")
    if not acc.city: errors.append("City")
    # if not acc.state: errors.append("State")
    # if not acc.locality: errors.append("Locality")
    if not acc.contact_phone: errors.append("Phone")
    if not acc.type: errors.append("Type")
    if not acc.gender: errors.append("Gender")
    if not acc.price: errors.append("Price")
    
    # Image Validation
    valid_images = False
    if acc.images:
        try:
            imgs = json.loads(acc.images)
            if isinstance(imgs, list) and len(imgs) >= 4:
                valid_images = True
        except: pass
    
    if not valid_images:
        errors.append("Minimum 4 Correct Images")

    if errors:
        raise HTTPException(status_code=400, detail=f"Incomplete Details: {', '.join(errors)}")
        
    # HARDCODED RULE: Payment must be completed before verification
    if not acc.payment_id:
        # If no payment ID, restrict status to PAYMENT_PENDING
        acc.status = ListingStatus.PAYMENT_PENDING
        await db.commit()
        raise HTTPException(
            status_code=400, 
            detail="Payment not completed. Please complete payment to submit for verification."
        )
        
    acc.status = ListingStatus.VERIFICATION_PENDING
    await db.commit()
    return {"message": "Payment confirmed and listing submitted for verification"}

@router.put("/{acc_id}/verify", response_model=AccommodationResponse)
async def verify_accommodation(
    acc_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    result = await db.execute(select(Accommodation).where(Accommodation.id == acc_id))
    acc = result.scalars().first()
    if not acc:
        raise HTTPException(status_code=404, detail="Accommodation not found")
    
    acc.status = ListingStatus.LIVE
    acc.is_verified = True
    await db.commit()
    await db.refresh(acc)
    return acc

class RejectRequest(BaseModel):
    reason: str

@router.put("/{acc_id}/reject", response_model=AccommodationResponse)
async def reject_accommodation(
    acc_id: str,
    rejection: RejectRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    result = await db.execute(select(Accommodation).where(Accommodation.id == acc_id))
    acc = result.scalars().first()
    if not acc:
        raise HTTPException(status_code=404, detail="Accommodation not found")
    
    acc.status = ListingStatus.REJECTED
    acc.is_verified = False
    
    await db.commit()
    await db.refresh(acc)
    return acc
