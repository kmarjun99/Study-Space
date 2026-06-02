from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.database import get_db
from app.models.waitlist import WaitlistEntry, WaitlistStatus
from app.models.reading_room import Cabin, CabinStatus
from app.schemas.waitlist import WaitlistEntryCreate, WaitlistEntryResponse
from app.models.user import User
from app.deps import get_current_user

router = APIRouter(prefix="/waitlist", tags=["waitlist"])

@router.post("/", response_model=WaitlistEntryResponse)
async def join_waitlist(
    entry: WaitlistEntryCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Check if cabin is occupied OR reserved
    result = await db.execute(select(Cabin).where(Cabin.id == entry.cabin_id))
    cabin = result.scalars().first()
    if not cabin:
        raise HTTPException(status_code=404, detail="Cabin not found")
        
    if cabin.status == CabinStatus.AVAILABLE:
        raise HTTPException(status_code=400, detail="Cabin is available, you can book it directly")

    # Check if user has an ACTIVE booking for this cabin
    from app.models.booking import Booking, BookingStatus, PaymentStatus
    from datetime import datetime
    
    current_time = datetime.utcnow()
    
    active_booking = await db.execute(select(Booking).where(
        (Booking.user_id == current_user.id) &
        (Booking.cabin_id == entry.cabin_id) &
        (Booking.status == BookingStatus.ACTIVE) &
        (Booking.end_date > current_time)
    ))
    
    if active_booking.scalars().first():
        raise HTTPException(status_code=400, detail="You already have an active booking for this cabin")

    # Check if already in waitlist (ACTIVE or NOTIFIED)
    existing = await db.execute(select(WaitlistEntry).where(
        (WaitlistEntry.user_id == current_user.id) & 
        (WaitlistEntry.cabin_id == entry.cabin_id) &
        (WaitlistEntry.status.in_([WaitlistStatus.ACTIVE, WaitlistStatus.NOTIFIED]))
    ))
    if existing.scalars().first():
        raise HTTPException(status_code=400, detail="You are already on the waitlist for this cabin")

    # Get reading room for owner_id
    from app.models.reading_room import ReadingRoom
    rr_result = await db.execute(select(ReadingRoom).where(ReadingRoom.id == entry.reading_room_id))
    reading_room = rr_result.scalars().first()

    new_entry = WaitlistEntry(
        user_id=current_user.id,
        cabin_id=entry.cabin_id,
        reading_room_id=entry.reading_room_id,
        owner_id=reading_room.owner_id if reading_room else None,
        status=WaitlistStatus.ACTIVE
    )
    db.add(new_entry)
    await db.commit()
    await db.refresh(new_entry)
    return new_entry

@router.get("/my-waitlists", response_model=List[WaitlistEntryResponse])
async def get_my_waitlists(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    from app.models.reading_room import ReadingRoom
    from sqlalchemy import func
    
    # Join with ReadingRoom and Cabin to get details
    query = (
        select(WaitlistEntry, ReadingRoom, Cabin)
        .join(ReadingRoom, WaitlistEntry.reading_room_id == ReadingRoom.id)
        .join(Cabin, WaitlistEntry.cabin_id == Cabin.id)
        .where(
            WaitlistEntry.user_id == current_user.id,
            WaitlistEntry.status.in_([WaitlistStatus.ACTIVE, WaitlistStatus.NOTIFIED])
        )
        .order_by(WaitlistEntry.created_at.desc())
    )
    
    result = await db.execute(query)
    rows = result.all()
    
    response = []
    for entry, room, cabin in rows:
        # Convert to Pydantic model
        entry_data = WaitlistEntryResponse.model_validate(entry)
        
        # Enrich
        entry_data.venue_name = room.name
        entry_data.venue_address = f"{room.address}" + (f", {room.city}" if room.city else "")
        entry_data.cabin_number = cabin.number
        
        # Calculate Priority (simulated for now, or actual count)
        if entry.status == WaitlistStatus.ACTIVE:
             # Count entries for this cabin created before this entry
            position_query = select(func.count()).select_from(WaitlistEntry).where(
                WaitlistEntry.cabin_id == entry.cabin_id,
                WaitlistEntry.status.in_([WaitlistStatus.ACTIVE, WaitlistStatus.NOTIFIED]),
                WaitlistEntry.created_at < entry.created_at
            )
            pos_result = await db.execute(position_query)
            # Position is count + 1
            entry_data.priority_position = pos_result.scalar() + 1
        
        response.append(entry_data)
        
    return response

@router.get("/venue/{venue_id}")
async def get_venue_waitlist(
    venue_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Verify ownership of the venue
    from app.models.reading_room import ReadingRoom
    r_result = await db.execute(select(ReadingRoom).where(ReadingRoom.id == venue_id))
    venue = r_result.scalars().first()
    if not venue:
        raise HTTPException(status_code=404, detail="Venue not found")
        
    if venue.owner_id != current_user.id and current_user.role != "SUPER_ADMIN":
         raise HTTPException(status_code=403, detail="Not authorized")

    # Fetch waitlists
    # Fetch waitlists with enriched data using JOINs
    query = (
        select(WaitlistEntry, User, Cabin)
        .join(User, WaitlistEntry.user_id == User.id)
        .join(Cabin, WaitlistEntry.cabin_id == Cabin.id)
        .where(
            WaitlistEntry.reading_room_id == venue_id,
            WaitlistEntry.status.in_([WaitlistStatus.ACTIVE, WaitlistStatus.NOTIFIED])
        )
        .order_by(WaitlistEntry.created_at.asc()) # FIFO order
    )
    
    result = await db.execute(query)
    rows = result.all()
    
    response = []
    for entry, user, cabin in rows:
        # Convert to Pydantic model
        entry_data = WaitlistEntryResponse.model_validate(entry)
        
        # Enrich with User and Cabin details
        entry_data.user_name = user.name
        entry_data.user_email = user.email
        entry_data.cabin_number = cabin.number
        
        response.append(entry_data)

    return response

@router.post("/{entry_id}/cancel")
async def cancel_waitlist(
    entry_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(select(WaitlistEntry).where(WaitlistEntry.id == entry_id))
    entry = result.scalars().first()
    if not entry:
        raise HTTPException(status_code=404, detail="Waitlist entry not found")
        
    if entry.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
        
    entry.status = WaitlistStatus.CANCELLED
    
    # If user was NOTIFIED and holding the cabin, release the hold!
    if entry.status == WaitlistStatus.NOTIFIED:
        # Import service to trigger next person
        from app.services.waitlist_service import waitlist_service
        # Check if cabin is still held by this user
        c_result = await db.execute(select(Cabin).where(Cabin.id == entry.cabin_id))
        cabin = c_result.scalars().first()
        if cabin and cabin.held_by_user_id == current_user.id:
            cabin.status = CabinStatus.AVAILABLE # Reset to available first
            cabin.held_by_user_id = None
            await db.commit()
            # Trigger next person immediately
            await waitlist_service.check_waitlist_and_notify(cabin.id, db)
    
    await db.commit()
    return {"message": "Waitlist entry cancelled"}
