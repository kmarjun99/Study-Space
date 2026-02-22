from typing import List, Annotated
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.database import get_db
from app.models.reading_room import ReadingRoom, Cabin, CabinStatus, ListingStatus
from app.models.city import CitySettings
from app.models.booking import Booking
from app.schemas.reading_room import ReadingRoomCreate, ReadingRoomResponse, CabinCreate, ReadingRoomUpdate
from app.models.user import User, UserRole
from app.deps import get_current_user, get_current_admin, get_current_user_optional
from pydantic import BaseModel
import json

router = APIRouter(prefix="/reading-rooms", tags=["reading-rooms"])

from app.utils.geo import haversine_distance, sort_by_proximity
from typing import Optional


@router.get("/", response_model=List[ReadingRoomResponse])
async def get_reading_rooms(
    lat: Optional[float] = None,
    long: Optional[float] = None,
    radius: Optional[float] = 5.0, # Default 5km radius
    include_unverified: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    query = select(ReadingRoom).order_by(ReadingRoom.is_sponsored.desc(), ReadingRoom.name)
    
    show_unverified = False
    if include_unverified:
         if current_user and current_user.role in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
             show_unverified = True
    

    if not show_unverified:
        # Show LIVE rooms OR rooms owned by current user
        if current_user:
             query = query.where((ReadingRoom.status == ListingStatus.LIVE) | (ReadingRoom.owner_id == current_user.id))
        else:
             query = query.where(ReadingRoom.status == ListingStatus.LIVE)
    else:
        # Admin View: Only show venues that have completed payment (VERIFICATION_PENDING or later)
        # Exclude DRAFT and PAYMENT_PENDING unless specific filtering options are added later
        # But if the admin IS the owner, they should see their drafts? 
        # For now, implementing strict requirement: Admin sees only PAID venues.
        query = query.where(ReadingRoom.status.notin_([ListingStatus.DRAFT, ListingStatus.PAYMENT_PENDING]))

    result = await db.execute(query)
    all_rooms = result.scalars().all()
    
    # Filter by City Status
    settings_res = await db.execute(select(CitySettings))
    city_map = {s.city_name.lower(): s.is_active for s in settings_res.scalars().all()}
    
    rooms = []
    for r in all_rooms:
        c_name = (r.city or "").strip().lower()
        if city_map.get(c_name, True):
            rooms.append(r)
    
    # Filter by Trust Status - hide FLAGGED and SUSPENDED venues from public listings
    # Owners and admins can still see their own flagged venues
    trust_filtered_rooms = []
    for room in rooms:
        trust_status = getattr(room, 'trust_status', 'CLEAR') or 'CLEAR'
        
        # Super Admins can see all
        if current_user and current_user.role == UserRole.SUPER_ADMIN:
            trust_filtered_rooms.append(room)
        # Owner can see their own venue regardless of trust status
        elif current_user and room.owner_id == current_user.id:
            trust_filtered_rooms.append(room)
        # Public users only see CLEAR or UNDER_REVIEW venues
        elif trust_status in ['CLEAR', 'UNDER_REVIEW']:
            trust_filtered_rooms.append(room)
        # FLAGGED and SUSPENDED venues are hidden from public
        # (they can still see UNDER_REVIEW as it means owner is working on it)
    
    rooms = trust_filtered_rooms

    if lat is not None and long is not None:
        nearby_rooms = []
        for room in rooms:
            if room.latitude and room.longitude:
                dist = haversine_distance(lat, long, room.latitude, room.longitude)
                if dist <= radius:
                    setattr(room, '_distance', dist)
                    nearby_rooms.append(room)
        return sort_by_proximity(lat, long, nearby_rooms)

    return rooms

from app.schemas.user import UserResponse

@router.get("/my-venues", response_model=List[ReadingRoomResponse])
async def get_my_venues(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all reading rooms owned by the current user."""
    query = (
        select(ReadingRoom)
        .where(ReadingRoom.owner_id == current_user.id)
        .order_by(ReadingRoom.name)
    )
    result = await db.execute(query)
    venues = result.scalars().all()
    return venues

@router.get("/my-students", response_model=List[UserResponse])
async def get_my_students(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    from app.models.booking import Booking
    
    # 1. Get Owner's Venues
    r_result = await db.execute(select(ReadingRoom.id).where(ReadingRoom.owner_id == current_user.id))
    room_ids = r_result.scalars().all()
    
    if not room_ids:
        return []

    # 2. Get Cabins
    c_result = await db.execute(select(Cabin.id).where(Cabin.reading_room_id.in_(room_ids)))
    cabin_ids = c_result.scalars().all()
    
    if not cabin_ids:
        return []

    # 3. Get Users for ALL bookings in these cabins
    query = (
        select(User)
        .join(Booking, Booking.user_id == User.id)
        .where(Booking.cabin_id.in_(cabin_ids))
        .distinct()
    )
    
    result = await db.execute(query)
    students = result.scalars().all()
    
    return students

@router.post("/", response_model=ReadingRoomResponse)
async def create_reading_room(
    room: ReadingRoomCreate, 
    db: AsyncSession = Depends(get_db), 
    current_user: User = Depends(get_current_admin)
):
    import traceback
    try:
        print(f"📝 Creating reading room for user: {current_user.email}")
        print(f"📝 Room data: {room.model_dump()}")
        
        normalized_city = (room.city or "").strip().title()
        if normalized_city:
            setting_res = await db.execute(select(CitySettings).where(CitySettings.city_name == normalized_city))
            setting = setting_res.scalars().first()
            if setting and not setting.is_active:
                 raise HTTPException(status_code=400, detail=f"Operations in {normalized_city} are currently paused.")

        new_room = ReadingRoom(
            **room.model_dump(),
            owner_id=current_user.id,
            status=ListingStatus.DRAFT,
            is_verified=False
        )
        new_room.city = normalized_city
        
        db.add(new_room)
        await db.commit()
        await db.refresh(new_room)
        print(f"✅ Room created with ID: {new_room.id}")
        return new_room
    except HTTPException:
        raise  # Re-raise HTTP exceptions as-is
    except Exception as e:
        print(f"❌ Error creating reading room: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to create reading room: {str(e)}")

class CabinBatchCreate(BaseModel):
    start_number: int
    end_number: int
    floor: int
    price: float
    amenities: str = ""

@router.post("/{room_id}/cabins/batch")
async def create_cabins_batch(
    room_id: str,
    batch: CabinBatchCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    result = await db.execute(select(ReadingRoom).where(ReadingRoom.id == room_id))
    room = result.scalars().first()
    if not room:
        raise HTTPException(status_code=404, detail="Reading room not found")
        
    if room.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    cabins = []
    for num in range(batch.start_number, batch.end_number + 1):
        cabin = Cabin(
            reading_room_id=room_id,
            number=str(num),
            floor=batch.floor,
            price=batch.price,
            amenities=batch.amenities,
            status=CabinStatus.AVAILABLE
        )
        cabins.append(cabin)
    
    db.add_all(cabins)
    await db.commit()
    return {"message": f"{len(cabins)} cabins created successfully"}

from app.schemas.reading_room import CabinResponse

@router.post("/{room_id}/cabins", response_model=CabinResponse)
async def create_cabin(
    room_id: str,
    cabin: CabinCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    result = await db.execute(select(ReadingRoom).where(ReadingRoom.id == room_id))
    room = result.scalars().first()
    if not room:
        raise HTTPException(status_code=404, detail="Reading room not found")
    
    if room.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    new_cabin = Cabin(
        reading_room_id=room_id,
        **cabin.model_dump()
    )
    db.add(new_cabin)
    await db.commit()
    await db.refresh(new_cabin)
    return new_cabin

@router.get("/{room_id}", response_model=ReadingRoomResponse)
async def get_reading_room(
    room_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    result = await db.execute(select(ReadingRoom).where(ReadingRoom.id == room_id))
    room = result.scalars().first()
    if not room:
        raise HTTPException(status_code=404, detail="Reading room not found")
        
    is_public = room.status == ListingStatus.LIVE
    is_owner = current_user and room.owner_id == current_user.id
    is_admin = current_user and current_user.role in [UserRole.ADMIN, UserRole.SUPER_ADMIN]
    
    if not (is_public or is_owner or is_admin):
         raise HTTPException(status_code=403, detail="Not authorized")

    return room

@router.get("/{room_id}/active-students")
async def get_active_students_count(
    room_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Get count of unique active students (users with active bookings) at this venue.
    Public endpoint - no authentication required.
    """
    from datetime import datetime, timezone
    from sqlalchemy import func, distinct
    from app.models.booking import BookingStatus
    
    # Get all cabins for this venue
    cabins_result = await db.execute(
        select(Cabin.id).where(Cabin.reading_room_id == room_id)
    )
    cabin_ids = [row[0] for row in cabins_result.fetchall()]
    
    if not cabin_ids:
        print(f"⚠️ No cabins found for venue {room_id}")
        return {"venue_id": room_id, "active_students": 0}
    
    print(f"✅ Found {len(cabin_ids)} cabins for venue {room_id}")
    
    # Count unique users with ACTIVE bookings that haven't expired
    # Use timezone-aware datetime for comparison
    now = datetime.now(timezone.utc).replace(tzinfo=None)  # Make it naive for DB comparison
    
    # Debug: Check all bookings for these cabins
    debug_result = await db.execute(
        select(Booking)
        .where(Booking.cabin_id.in_(cabin_ids))
    )
    all_bookings = debug_result.scalars().all()
    print(f"📊 Total bookings for venue: {len(all_bookings)}")
    for b in all_bookings:
        status_str = str(b.status) if hasattr(b.status, 'value') else b.status
        print(f"  📋 Booking {b.id[:8]}...: status={status_str}, user={b.user_id[:8]}..., end_date={b.end_date}, now={now}, active={b.end_date >= now if b.end_date else False}")
    
    # Try both enum and string comparison to handle different storage formats
    result = await db.execute(
        select(func.count(distinct(Booking.user_id)))
        .where(
            Booking.cabin_id.in_(cabin_ids),
            Booking.status == BookingStatus.ACTIVE.value,  # Compare as string value
            Booking.end_date >= now
        )
    )
    active_count = result.scalar() or 0
    
    print(f"✨ Active students count: {active_count}")
    
    return {
        "venue_id": room_id,
        "active_students": active_count
    }

@router.put("/{room_id}", response_model=ReadingRoomResponse)
async def update_reading_room(
    room_id: str,
    updates: ReadingRoomUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    result = await db.execute(select(ReadingRoom).where(ReadingRoom.id == room_id))
    room = result.scalars().first()
    if not room:
        raise HTTPException(status_code=404, detail="Reading room not found")
    
    if room.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    update_data = updates.model_dump(exclude_unset=True)
    
    # Security: Prevent unauthorized status changes
    # Only SUPER_ADMIN can change status freely (e.g. to LIVE)
    # Owners (ADMIN) cannot change status to LIVE directly
    if current_user.role != UserRole.SUPER_ADMIN:
        if "status" in update_data:
            # Optionally allow transition to DRAFT? 
            # For now, strict: Remove status from updates initiated by Owner
            del update_data["status"]
            
    for key, value in update_data.items():
        setattr(room, key, value)
    
    await db.commit()
    await db.refresh(room)
    return room


@router.delete("/{room_id}")
async def delete_reading_room(
    room_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Delete a reading room. Only owner can delete. Cannot delete if there are any bookings."""
    result = await db.execute(select(ReadingRoom).where(ReadingRoom.id == room_id))
    room = result.scalars().first()
    if not room:
        raise HTTPException(status_code=404, detail="Reading room not found")
    
    if room.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to delete this venue")
    
    # Check for any bookings on cabins in this reading room
    cabins = (await db.execute(select(Cabin).where(Cabin.reading_room_id == room_id))).scalars().all()
    cabin_ids = [c.id for c in cabins]
    
    if cabin_ids:
        bookings_check = await db.execute(
            select(Booking).where(Booking.cabin_id.in_(cabin_ids))
        )
        existing_bookings = bookings_check.scalars().first()
        if existing_bookings:
            raise HTTPException(
                status_code=400, 
                detail="Cannot delete reading room with existing bookings. Please contact support if you need to remove this listing."
            )
    
    # Delete associated cabins first
    for cabin in cabins:
        await db.delete(cabin)
    
    # Delete the reading room
    await db.delete(room)
    await db.commit()
    
    return {"message": "Reading room deleted successfully"}


@router.put("/{room_id}/submit-payment")
async def submit_payment(
    room_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    result = await db.execute(select(ReadingRoom).where(ReadingRoom.id == room_id))
    room = result.scalars().first()
    if not room:
        raise HTTPException(status_code=404, detail="Venue not found")
        
    if room.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    # VALIDATION
    errors = []
    if not room.name: errors.append("Name")
    if not room.address: errors.append("Address")
    # if not room.locality: errors.append("Locality") # Relaxing strictly slightly if migration issue? No, strict.
    if not room.city: errors.append("City")
    # if not room.state: errors.append("State")
    # if not room.pincode: errors.append("Pincode")
    if not room.contact_phone: errors.append("Phone")
    
    # Image Validation
    valid_images = False
    if room.images:
        try:
            imgs = json.loads(room.images)
            if isinstance(imgs, list) and len(imgs) >= 4:
                valid_images = True
        except: pass
    
    # Check for legacy single image_url if images not set (Migration support)
    # If no images list, fail.
    if not valid_images:
        errors.append("Minimum 4 Correct Images")

    if errors:
        raise HTTPException(status_code=400, detail=f"Incomplete Details: {', '.join(errors)}")

    # Update Status
    room.status = ListingStatus.VERIFICATION_PENDING
    await db.commit()
    return {"message": "Payment confirmed and listing submitted for verification"}

@router.put("/{room_id}/verify", response_model=ReadingRoomResponse)
async def verify_reading_room(
    room_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    result = await db.execute(select(ReadingRoom).where(ReadingRoom.id == room_id))
    room = result.scalars().first()
    if not room:
        raise HTTPException(status_code=404, detail="Reading room not found")
    
    # Update to LIVE
    room.status = ListingStatus.LIVE
    room.is_verified = True
    await db.commit()
    await db.refresh(room)
    return room

class RejectRequest(BaseModel):
    reason: str

@router.put("/{room_id}/reject", response_model=ReadingRoomResponse)
async def reject_reading_room(
    room_id: str,
    rejection: RejectRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    result = await db.execute(select(ReadingRoom).where(ReadingRoom.id == room_id))
    room = result.scalars().first()
    if not room:
        raise HTTPException(status_code=404, detail="Reading room not found")
    
    room.status = ListingStatus.REJECTED
    room.is_verified = False
    
    await db.commit()
    await db.refresh(room)
    return room
