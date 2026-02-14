from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List, Optional
from datetime import datetime, timedelta, timezone

from app.database import get_db
from app.models.review import Review
from app.models.booking import Booking, BookingStatus
from app.schemas.review import ReviewCreate, ReviewResponse
from app.deps import get_current_user
from app.models.user import User

router = APIRouter(prefix="/reviews", tags=["Reviews"])

# Review eligibility delay in hours
REVIEW_ELIGIBILITY_HOURS = 48


async def check_review_eligibility(
    user_id: str,
    reading_room_id: Optional[str],
    accommodation_id: Optional[str],
    db: AsyncSession
) -> dict:
    """
    Check if user is eligible to write a review.
    User must have a confirmed booking that started at least 48 hours ago.
    Returns: { eligible: bool, reason: str, hours_remaining: int | None, booking_id: str | None }
    """
    # Build query based on venue type
    query = select(Booking).where(
        Booking.user_id == user_id,
        Booking.status.in_([BookingStatus.ACTIVE, BookingStatus.EXPIRED])  # Only confirmed bookings
    )
    
    if reading_room_id:
        query = query.where(Booking.cabin_id.isnot(None))
        # We need to check if the cabin belongs to this reading room
        from app.models.reading_room import Cabin
        cabin_query = select(Cabin.id).where(Cabin.reading_room_id == reading_room_id)
        cabin_result = await db.execute(cabin_query)
        cabin_ids = [c for c in cabin_result.scalars().all()]
        if not cabin_ids:
            return {"eligible": False, "reason": "No cabins found for this venue", "hours_remaining": None, "booking_id": None}
        query = query.where(Booking.cabin_id.in_(cabin_ids))
    elif accommodation_id:
        query = query.where(Booking.accommodation_id == accommodation_id)
    else:
        return {"eligible": False, "reason": "No venue specified", "hours_remaining": None, "booking_id": None}
    
    # Get the earliest confirmed booking
    query = query.order_by(Booking.start_date.asc())
    result = await db.execute(query)
    booking = result.scalars().first()
    
    if not booking:
        return {"eligible": False, "reason": "No confirmed booking found for this venue", "hours_remaining": None, "booking_id": None}
    
    # Check 48-hour eligibility
    now = datetime.now(timezone.utc)
    booking_start = booking.start_date.replace(tzinfo=timezone.utc) if booking.start_date.tzinfo is None else booking.start_date
    eligible_at = booking_start + timedelta(hours=REVIEW_ELIGIBILITY_HOURS)
    
    if now < eligible_at:
        remaining = eligible_at - now
        hours_remaining = int(remaining.total_seconds() / 3600)
        return {
            "eligible": False, 
            "reason": f"You can write a review after {hours_remaining} hours",
            "hours_remaining": hours_remaining,
            "booking_id": booking.id,
            "eligible_at": eligible_at.isoformat()
        }
    
    return {"eligible": True, "reason": "Eligible to review", "hours_remaining": 0, "booking_id": booking.id}


@router.get("/eligibility")
async def check_review_eligibility_endpoint(
    reading_room_id: Optional[str] = None,
    accommodation_id: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Check if user is eligible to write a review for a venue.
    Returns eligibility status and hours remaining if not eligible.
    """
    eligibility = await check_review_eligibility(
        current_user.id, reading_room_id, accommodation_id, db
    )
    
    # Also check if user has already reviewed
    stmt = select(Review).where(Review.user_id == current_user.id)
    if reading_room_id:
        stmt = stmt.where(Review.reading_room_id == reading_room_id)
    if accommodation_id:
        stmt = stmt.where(Review.accommodation_id == accommodation_id)
    
    result = await db.execute(stmt)
    existing = result.scalars().first()
    
    if existing:
        return {
            "eligible": False,
            "reason": "You have already reviewed this venue",
            "hasReviewed": True,
            "review": {
                "id": existing.id,
                "rating": existing.rating,
                "comment": existing.comment
            }
        }
    
    return {**eligibility, "hasReviewed": False}


@router.get("/status")
async def check_review_status(
    reading_room_id: Optional[str] = None,
    accommodation_id: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    print(f"Checking review status for user {current_user.id}, RR: {reading_room_id}, Acc: {accommodation_id}")
    stmt = select(Review).where(
        Review.user_id == current_user.id,
        Review.reading_room_id == reading_room_id,
        Review.accommodation_id == accommodation_id
    )
    result = await db.execute(stmt)
    existing = result.scalars().first()
    print(f"Review status result: {existing}")
    
    if existing:
        return {
            "hasReviewed": True,
            "review": {
                "id": existing.id,
                "rating": existing.rating,
                "comment": existing.comment,
                "created_at": existing.created_at
            }
        }
    return {"hasReviewed": False, "review": None}

@router.post("/", response_model=ReviewResponse)
async def create_review(
    review: ReviewCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    print(f"Received review: {review.model_dump()}")
    
    # ========================================
    # 48-HOUR ELIGIBILITY CHECK (CRITICAL)
    # ========================================
    eligibility = await check_review_eligibility(
        current_user.id, review.reading_room_id, review.accommodation_id, db
    )
    
    if not eligibility["eligible"]:
        raise HTTPException(
            status_code=400,
            detail=eligibility["reason"]
        )
    
    # Check for existing review
    stmt = select(Review).where(
        Review.user_id == current_user.id,
        Review.reading_room_id == review.reading_room_id,
        Review.accommodation_id == review.accommodation_id
    )
    result = await db.execute(stmt)
    existing_review = result.scalars().first()
    
    if existing_review:
        raise HTTPException(
            status_code=400,
            detail="You have already reviewed this place."
        )

    try:
        new_review = Review(
            user_id=current_user.id,
            **review.model_dump()
        )
        db.add(new_review)
        await db.commit()
        await db.refresh(new_review)
        return new_review
    except Exception as e:
        print(f"Error creating review: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/", response_model=List[ReviewResponse])
async def get_reviews(
    reading_room_id: Optional[str] = None,
    accommodation_id: Optional[str] = None,
    user_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    query = select(Review)
    if reading_room_id:
        query = query.where(Review.reading_room_id == reading_room_id)
    if accommodation_id:
        query = query.where(Review.accommodation_id == accommodation_id)
    if user_id:
        query = query.where(Review.user_id == user_id)
        
    result = await db.execute(query)
    return result.scalars().all()

