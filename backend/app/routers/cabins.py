from typing import List, Annotated, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.database import get_db
from app.models.reading_room import Cabin, CabinStatus
from app.schemas.reading_room import CabinResponse, CabinUpdate
from app.models.user import User
from app.deps import get_current_user, get_current_admin
from pydantic import BaseModel
from datetime import datetime, timedelta, timezone

router = APIRouter(prefix="/cabins", tags=["cabins"])

# Hold duration in minutes
HOLD_DURATION_MINUTES = 5

@router.get("/", response_model=List[CabinResponse])
async def get_cabins(
    reading_room_id: str = None, 
    status: CabinStatus = None, 
    db: AsyncSession = Depends(get_db)
):
    query = select(Cabin)
    if reading_room_id:
        query = query.where(Cabin.reading_room_id == reading_room_id)
    if status:
        query = query.where(Cabin.status == status)
    
    result = await db.execute(query)
    return result.scalars().all()


class BulkUpdateSchema(BaseModel):
    cabin_ids: List[str]
    status: CabinStatus = None
    price: float = None

@router.patch("/bulk")
async def bulk_update_cabins(
    payload: BulkUpdateSchema,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    # Fetch cabins
    query = select(Cabin).where(Cabin.id.in_(payload.cabin_ids))
    result = await db.execute(query)
    cabins = result.scalars().all()
    
    for cabin in cabins:
        if payload.status:
            cabin.status = payload.status
        if payload.price:
            cabin.price = payload.price
    
    await db.commit()

    # Broadcast updates
    if payload.status:
        from app.core.socket_manager import broadcast_cabin_update
        for cabin in cabins:
            await broadcast_cabin_update(cabin_id=cabin.id, status=cabin.status)


@router.put("/{cabin_id}", response_model=CabinResponse)
async def update_cabin(
    cabin_id: str,
    updates: CabinUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Fetch cabin
    result = await db.execute(select(Cabin).where(Cabin.id == cabin_id))
    cabin = result.scalars().first()
    if not cabin:
        raise HTTPException(status_code=404, detail="Cabin not found")
        
    # Verify ownership
    from app.models.reading_room import ReadingRoom
    rr_result = await db.execute(select(ReadingRoom).where(ReadingRoom.id == cabin.reading_room_id))
    room = rr_result.scalars().first()
    if not room or room.owner_id != current_user.id:
         raise HTTPException(status_code=403, detail="Not authorized")

    if not room or room.owner_id != current_user.id:
         raise HTTPException(status_code=403, detail="Not authorized")

    # Capture old status
    old_status = cabin.status

    # Update fields
    update_data = updates.dict(exclude_unset=True)
    for key, value in update_data.items():
        if key == 'amenities' and isinstance(value, list):
             setattr(cabin, key, ','.join(value))
        else:
             setattr(cabin, key, value)
    
    await db.commit()
    await db.refresh(cabin)
    
    # Broadcast REAL-TIME update
    from app.core.socket_manager import broadcast_cabin_update
    # We broadcast status and any other changed fields
    broadcast_data = {}
    if updates.price is not None:
        broadcast_data['price'] = updates.price
    if updates.amenities:
        broadcast_data['amenities'] = updates.amenities 

    # Trigger Waitlist if status changed to AVAILABLE
    if old_status != CabinStatus.AVAILABLE and cabin.status == CabinStatus.AVAILABLE:
        from app.services.waitlist_service import waitlist_service
        await waitlist_service.check_waitlist_and_notify(cabin.id, db)

    await broadcast_cabin_update(cabin_id=cabin.id, status=cabin.status, **broadcast_data)
        
    return cabin

class BulkDeleteSchema(BaseModel):
    cabin_ids: List[str]



@router.post("/bulk-delete")
async def bulk_delete_cabins(
    payload: BulkDeleteSchema,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Fetch cabins with their Reading Rooms to check ownership
    query = select(Cabin).where(Cabin.id.in_(payload.cabin_ids))
    result = await db.execute(query)
    cabins = result.scalars().all()

    if not cabins:
        return {"message": "No cabins found to delete"}

    # Validation: 1. Ownership 2. Status
    from app.models.reading_room import ReadingRoom
    
    # We need to fetch ReadingRoom separately or use join, 
    # but for simplicity let's check ownership by fetching the room for the first cabin 
    # (assuming bulk action is usually within one room). 
    # A safer, more robust way is to check each cabin.
    
    for cabin in cabins:
        # Check if cabin is occupied
        if cabin.status == CabinStatus.OCCUPIED:
            raise HTTPException(
                status_code=400, 
                detail=f"Cabin {cabin.number} is occupied and cannot be deleted."
            )
        
        # Verify ownership
        # Efficiency note: This N+1 query is bad for large batches, but safe for critical actions.
        # Optimized approach: fetch distinct reading_room_ids and check ownership of those.
        rr_result = await db.execute(select(ReadingRoom).where(ReadingRoom.id == cabin.reading_room_id))
        room = rr_result.scalars().first()
        if not room or room.owner_id != current_user.id:
             raise HTTPException(
                status_code=403, 
                detail=f"You do not have permission to delete cabin {cabin.number}"
            )
        
        await db.delete(cabin)
        
    await db.commit()
    return {"message": f"{len(cabins)} cabins deleted successfully"}


# ============================================
# SEAT HOLD SYSTEM (BookMyShow-Style)
# ============================================

class HoldResponse(BaseModel):
    cabin_id: str
    held_by_user_id: str
    hold_expires_at: str
    remaining_seconds: int
    message: str

def is_hold_expired(hold_expires_at: Optional[str]) -> bool:
    """Check if a hold has expired"""
    if not hold_expires_at:
        return True
    try:
        expires = datetime.fromisoformat(hold_expires_at.replace('Z', '+00:00'))
        return datetime.now(timezone.utc) >= expires
    except:
        return True


@router.post("/{cabin_id}/hold")
async def acquire_seat_hold(
    cabin_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Acquire a temporary hold on a seat.
    - First user to call gets priority for 5 minutes
    - Prevents others from booking the same seat
    - Hold auto-expires if not converted to booking
    """
    # Fetch cabin
    result = await db.execute(select(Cabin).where(Cabin.id == cabin_id))
    cabin = result.scalars().first()
    
    if not cabin:
        raise HTTPException(status_code=404, detail="Cabin not found")
    
    # Check if cabin is bookable
    if cabin.status == CabinStatus.OCCUPIED:
        raise HTTPException(status_code=400, detail="Seat is already booked")
    
    if cabin.status == CabinStatus.MAINTENANCE:
        raise HTTPException(status_code=400, detail="Seat is under maintenance")
    
    # Check if already held by someone else (and not expired)
    if cabin.held_by_user_id and not is_hold_expired(cabin.hold_expires_at):
        if cabin.held_by_user_id != current_user.id:
            raise HTTPException(
                status_code=409, 
                detail="Seat is temporarily held by another user"
            )
        # User already holds this seat - extend the hold
    
    # Set the hold
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=HOLD_DURATION_MINUTES)
    cabin.held_by_user_id = current_user.id
    cabin.hold_expires_at = expires_at.isoformat()
    
    await db.commit()
    await db.refresh(cabin)
    
    # Broadcast hold update via WebSocket
    from app.core.socket_manager import broadcast_cabin_update
    await broadcast_cabin_update(
        cabin_id=cabin.id,
        status=str(cabin.status.value),
        held_by_user_id=cabin.held_by_user_id,
        hold_expires_at=cabin.hold_expires_at
    )
    
    remaining = int((expires_at - datetime.now(timezone.utc)).total_seconds())
    
    return {
        "cabin_id": cabin.id,
        "held_by_user_id": cabin.held_by_user_id,
        "hold_expires_at": cabin.hold_expires_at,
        "remaining_seconds": remaining,
        "message": f"Seat held for {HOLD_DURATION_MINUTES} minutes"
    }


@router.delete("/{cabin_id}/hold")
async def release_seat_hold(
    cabin_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Release a seat hold.
    - Only the user who holds the seat can release it
    - Called when user navigates away or cancels selection
    """
    # Fetch cabin
    result = await db.execute(select(Cabin).where(Cabin.id == cabin_id))
    cabin = result.scalars().first()
    
    if not cabin:
        raise HTTPException(status_code=404, detail="Cabin not found")
    
    # Check if user holds this seat
    if cabin.held_by_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="You do not hold this seat")
    
    # Release the hold
    cabin.held_by_user_id = None
    cabin.hold_expires_at = None
    
    await db.commit()
    
    # Broadcast release via WebSocket
    from app.core.socket_manager import broadcast_cabin_update
    await broadcast_cabin_update(
        cabin_id=cabin.id,
        status=str(cabin.status.value),
        held_by_user_id=None,
        hold_expires_at=None
    )
    
    # Check waitlist for next person!
    from app.services.waitlist_service import waitlist_service
    await waitlist_service.check_waitlist_and_notify(cabin.id, db)

    return {"message": "Seat hold released", "cabin_id": cabin.id}


@router.get("/{cabin_id}/hold-status")
async def get_hold_status(
    cabin_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get the current hold status of a seat.
    """
    result = await db.execute(select(Cabin).where(Cabin.id == cabin_id))
    cabin = result.scalars().first()
    
    if not cabin:
        raise HTTPException(status_code=404, detail="Cabin not found")
    
    is_held = cabin.held_by_user_id and not is_hold_expired(cabin.hold_expires_at)
    is_mine = cabin.held_by_user_id == current_user.id if is_held else False
    
    remaining = 0
    if is_held and cabin.hold_expires_at:
        try:
            expires = datetime.fromisoformat(cabin.hold_expires_at.replace('Z', '+00:00'))
            remaining = max(0, int((expires - datetime.now(timezone.utc)).total_seconds()))
        except:
            pass
    
    return {
        "cabin_id": cabin.id,
        "is_held": is_held,
        "held_by_me": is_mine,
        "held_by_user_id": cabin.held_by_user_id if is_held else None,
        "hold_expires_at": cabin.hold_expires_at if is_held else None,
        "remaining_seconds": remaining
    }

