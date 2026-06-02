from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.database import get_db
from app.models.booking import Booking, BookingStatus, PaymentStatus, SettlementStatus
from app.models.reading_room import Cabin, CabinStatus, ReadingRoom
from app.models.accommodation import Accommodation
from app.schemas.booking import BookingCreate, BookingResponse
from app.models.user import User
from app.deps import get_current_user, dev_only
from app.services.booking_validator import booking_validator, BookingDurationType
from datetime import datetime, timedelta, date

router = APIRouter(prefix="/bookings", tags=["bookings"])

@router.post("/hold", response_model=BookingResponse)
async def hold_booking(
    cabin_id: str = Query(..., description="ID of the cabin to book"),
    duration_type: str = Query(..., description="Booking duration type: 1_DAY, 1_WEEK, 1_MONTH, 3_MONTHS, 6_MONTHS"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Step 1: Hold a seat for 10 minutes with flexible duration support.
    Locks the cabin and creates a HELD booking.
    
    Supports: 1_DAY, 1_WEEK, 1_MONTH, 3_MONTHS, 6_MONTHS
    Price is fetched from reading room's custom duration_prices configuration.
    """
    print(f"[HOLD] ===== HOLD BOOKING ENDPOINT CALLED =====")
    print(f"[HOLD] Received parameters: cabin_id='{cabin_id}', duration_type='{duration_type}'")
    print(f"[HOLD] User: {current_user.id} ({current_user.email})")
    
    if not cabin_id:
        raise HTTPException(status_code=400, detail="Cabin ID required for hold")

    print(f"[HOLD] User attempting to book: cabin_id={cabin_id}, duration_type={duration_type}")

    # 1. Get Cabin and Reading Room
    cabin_result = await db.execute(select(Cabin).where(Cabin.id == cabin_id))
    cabin = cabin_result.scalars().first()
    if not cabin:
        raise HTTPException(status_code=404, detail="Cabin not found")
    
    print(f"[HOLD] Found cabin: {cabin.number}, room_id={cabin.reading_room_id}")
    
    # Get Reading Room to validate duration and get price
    room_result = await db.execute(
        select(ReadingRoom).where(ReadingRoom.id == cabin.reading_room_id)
    )
    reading_room = room_result.scalars().first()
    if not reading_room:
        raise HTTPException(status_code=404, detail="Reading room not found")
    
    print(f"[HOLD] Reading room: {reading_room.name}")
    print(f"[HOLD] Allowed durations (raw): {reading_room.allowed_booking_durations}")
    print(f"[HOLD] Duration prices (raw): {reading_room.duration_prices}")
    
    # 2. Validate duration is allowed for this venue
    try:
        await booking_validator.validate_duration_allowed(reading_room, duration_type)
        print(f"[HOLD] Duration {duration_type} is allowed")
    except HTTPException as e:
        print(f"[HOLD ERROR] Duration validation failed: {e.detail}")
        raise
    
    # 3. Validate owner has set custom price for this duration
    try:
        booking_validator.validate_custom_prices_set(reading_room, duration_type)
        print(f"[HOLD] Custom price validation passed")
    except HTTPException as e:
        print(f"[HOLD ERROR] Price validation failed: {e.detail}")
        raise
    
    # 4. Get custom price from reading room configuration
    amount = booking_validator.get_duration_price(reading_room, duration_type, cabin.price)
    print(f"[HOLD] Calculated amount: {amount}")
    
    # 5. Check cabin availability
    if cabin.status != CabinStatus.AVAILABLE:
        raise HTTPException(status_code=409, detail="Cabin is not available")
    
    # 6. Calculate dates based on duration
    start_date = datetime.utcnow()
    end_date = booking_validator.calculate_end_date(start_date, duration_type)
    
    # 7. Apply Lock
    cabin.status = CabinStatus.RESERVED
    
    # 8. Create HELD Booking
    start_date_naive = start_date.replace(tzinfo=None)
    end_date_naive = end_date.replace(tzinfo=None)
    expires_at = datetime.utcnow() + timedelta(minutes=10)
    
    new_booking = Booking(
        user_id=current_user.id,
        cabin_id=cabin_id,
        start_date=start_date_naive,
        end_date=end_date_naive,
        amount=amount,
        status=BookingStatus.HELD,
        expires_at=expires_at,
        duration_type=duration_type  # Store duration type
    )
    db.add(new_booking)
    await db.commit()
    await db.refresh(new_booking)
    
    # 9. Broadcast Update
    from app.core.socket_manager import broadcast_cabin_update
    await broadcast_cabin_update(cabin_id=cabin_id, status=cabin.status)
    
    return new_booking

@router.post("/{booking_id}/confirm", response_model=BookingResponse)
async def confirm_booking(
    booking_id: str,
    payment_id: str, # Mock payment ID
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Step 2: Confirm the held booking after payment.
    """
    result = await db.execute(select(Booking).where(Booking.id == booking_id))
    booking = result.scalars().first()
    
    if not booking or booking.status != BookingStatus.HELD:
        raise HTTPException(status_code=400, detail="Invalid booking or not in HELD state")
    
    if datetime.utcnow() > booking.expires_at:
        raise HTTPException(status_code=400, detail="Booking expired")

    # Update Booking
    booking.status = BookingStatus.ACTIVE
    booking.payment_status = "PAID"
    booking.transaction_id = payment_id
    
    # Update Cabin to OCCUPIED
    result_cabin = await db.execute(select(Cabin).where(Cabin.id == booking.cabin_id))
    cabin = result_cabin.scalars().first()
    if cabin:
        cabin.status = CabinStatus.OCCUPIED
        cabin.current_occupant_id = current_user.id
        
    await db.commit()
    await db.refresh(booking)
    
    # Broadcast
    from app.core.socket_manager import broadcast_cabin_update
    await broadcast_cabin_update(cabin_id=booking.cabin_id, status=cabin.status)
    
    return booking


@router.get("/{booking_id}")
async def get_booking_by_id(
    booking_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get a single booking by ID.
    Users can only access their own bookings unless they are admin/super_admin.
    """
    from app.models.user import UserRole
    
    result = await db.execute(select(Booking).where(Booking.id == booking_id))
    booking = result.scalars().first()
    
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    
    # Check ownership for non-admin users
    if current_user.role not in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
        if booking.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Not authorized to view this booking")
    
    # Get cabin details
    cabin_result = await db.execute(select(Cabin).where(Cabin.id == booking.cabin_id))
    cabin = cabin_result.scalar_one_or_none()
    
    return {
        "id": booking.id,
        "user_id": booking.user_id,
        "cabin_id": booking.cabin_id,
        "cabin_number": cabin.number if cabin else "N/A",
        "start_date": booking.start_date.isoformat() if booking.start_date else None,
        "end_date": booking.end_date.isoformat() if booking.end_date else None,
        "amount": booking.amount,
        "status": booking.status.value if booking.status else "ACTIVE",
        "payment_status": booking.payment_status.value if booking.payment_status else "PAID",
        "transaction_id": booking.transaction_id
    }


@router.get("/", response_model=List[BookingResponse])
async def get_my_bookings(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    from app.models.user import UserRole
    from app.models.reading_room import ReadingRoom
    
    if current_user.role in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
        result = await db.execute(select(Booking))
        bookings = result.scalars().all()
        
        # Enrich for Admin Console
        cabin_ids = {b.cabin_id for b in bookings if b.cabin_id}
        

        if cabin_ids:
             # Fetch Venue/Owner details via Cabin
             stmt = (
                 select(Cabin.id, Cabin.number.label("cabin_number"), ReadingRoom.name, ReadingRoom.owner_id, User.name.label("owner_name"))
                 .join(ReadingRoom, Cabin.reading_room_id == ReadingRoom.id)
                 .join(User, ReadingRoom.owner_id == User.id)
                 .where(Cabin.id.in_(cabin_ids))
             )
             res = await db.execute(stmt)
             cabin_map = {row.id: row for row in res}
             
             for b in bookings:
                 if b.cabin_id and b.cabin_id in cabin_map:
                     details = cabin_map[b.cabin_id]
                     b.venue_name = details.name
                     b.owner_name = details.owner_name
                     b.owner_id = details.owner_id
                     b.cabin_number = details.cabin_number
                     
        return bookings

    else:
        result = await db.execute(select(Booking).where(Booking.user_id == current_user.id))
        return result.scalars().all()

@router.post("/", response_model=BookingResponse)
async def create_booking(
    booking: BookingCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    DEPRECATED: Use /bookings/hold + payment verification flow instead.
    This endpoint is kept for backwards compatibility only.
    """
    # Logic for Cabin Booking
    if booking.cabin_id:
        raise HTTPException(
            status_code=400, 
            detail="Direct cabin booking is disabled. Please use the payment flow: /bookings/hold -> payment -> verification"
        )
        
    # Only allow direct booking for accommodations (no cabin bookings)
    if booking.accommodation_id:
        result = await db.execute(select(Cabin).where(Cabin.id == booking.cabin_id))
        cabin = result.scalars().first()
        if not cabin:
            raise HTTPException(status_code=404, detail="Cabin not found")
        
        if cabin.status != CabinStatus.AVAILABLE:
            raise HTTPException(status_code=400, detail="Cabin is not available")
        
        # Update Cabin Status
        cabin.status = CabinStatus.OCCUPIED
        cabin.current_occupant_id = current_user.id
        
        # Check and update Waitlist status to CONVERTED
        try:
            from app.models.waitlist import WaitlistEntry, WaitlistStatus
            wl_result = await db.execute(
                select(WaitlistEntry).where(
                    WaitlistEntry.user_id == current_user.id,
                    WaitlistEntry.reading_room_id == cabin.reading_room_id,
                    WaitlistEntry.status.in_([WaitlistStatus.ACTIVE, WaitlistStatus.NOTIFIED])
                )
            )
            wl_entry = wl_result.scalars().first()
            if wl_entry:
                wl_entry.status = WaitlistStatus.CONVERTED
        except Exception as e:
            print(f"Error updating waitlist status: {e}")
            # Do not fail booking if waitlist update fails
            pass
        

        # Create Booking
        # Convert timezone-aware datetimes to naive datetimes for PostgreSQL TIMESTAMP WITHOUT TIME ZONE
        start_date_naive = booking.start_date.replace(tzinfo=None) if booking.start_date.tzinfo else booking.start_date
        end_date_naive = booking.end_date.replace(tzinfo=None) if booking.end_date.tzinfo else booking.end_date
        
        new_booking = Booking(
            user_id=current_user.id,
            cabin_id=booking.cabin_id,
            accommodation_id=booking.accommodation_id or None,  # Ensure None if empty string
            start_date=start_date_naive,
            end_date=end_date_naive,
            amount=booking.amount,
            status=BookingStatus.ACTIVE,
            payment_status=PaymentStatus.PAID,
            transaction_id=booking.transaction_id,
            settlement_status=SettlementStatus.NOT_SETTLED
        )

        try:
            db.add(new_booking)
            await db.commit()
            await db.refresh(new_booking)

            # Accounting shadow: compute tax + post ledger group. Guarded
            # internally by `accounting.enabled` and never raises into the
            # caller. Mirrors the call in routers/razorpay.py and
            # routers/payments.py so every booking-paid path freezes the GST
            # split identically.
            try:
                from app.services.accounting_shadow import AccountingShadow
                await AccountingShadow.shadow_post_booking_paid(
                    db, booking_id=new_booking.id,
                )
                await db.commit()
            except Exception as acc_err:
                print(f"[accounting_shadow] non-fatal: {acc_err}")

            # Send booking confirmation email
            try:
                from app.services.email_service import send_booking_confirmation_email
                await send_booking_confirmation_email(
                    recipient_email=current_user.email,
                    recipient_name=current_user.name,
                    booking_details={
                        "venue_name": cabin.reading_room.name if hasattr(cabin, 'reading_room') else "Reading Room",
                        "booking_type": "cabin",
                        "start_date": start_date_naive.strftime("%d %B %Y"),
                        "end_date": end_date_naive.strftime("%d %B %Y"),
                        "amount": f"{booking.amount:,.2f}",
                        "transaction_id": booking.transaction_id,
                        "venue_address": cabin.reading_room.address if hasattr(cabin, 'reading_room') else "",
                        "cabin_number": cabin.number
                    }
                )
            except Exception as email_error:
                print(f"Failed to send booking confirmation email: {email_error}")

            # Broadcast Update
            from app.core.socket_manager import broadcast_cabin_update
            await broadcast_cabin_update(cabin_id=booking.cabin_id, status=cabin.status)
        except Exception as e:
            await db.rollback()
            raise HTTPException(status_code=500, detail=f"Booking transaction failed: {str(e)}")

        return new_booking

    # Logic for Accommodation Booking (Simplified)
    elif booking.accommodation_id:
        # Convert timezone-aware datetimes to naive datetimes for PostgreSQL TIMESTAMP WITHOUT TIME ZONE
        start_date_naive = booking.start_date.replace(tzinfo=None) if booking.start_date.tzinfo else booking.start_date
        end_date_naive = booking.end_date.replace(tzinfo=None) if booking.end_date.tzinfo else booking.end_date
        
        new_booking = Booking(
            user_id=current_user.id,
            accommodation_id=booking.accommodation_id,
            start_date=start_date_naive,
            end_date=end_date_naive,
            amount=booking.amount
        )
        db.add(new_booking)
        await db.commit()
        await db.refresh(new_booking)

        # Accounting shadow — same protection as the cabin branch above.
        try:
            from app.services.accounting_shadow import AccountingShadow
            await AccountingShadow.shadow_post_booking_paid(
                db, booking_id=new_booking.id,
            )
            await db.commit()
        except Exception as acc_err:
            print(f"[accounting_shadow] non-fatal: {acc_err}")

        # Send booking confirmation email
        try:
            from app.services.email_service import send_booking_confirmation_email
            result = await db.execute(select(Accommodation).where(Accommodation.id == booking.accommodation_id))
            accommodation = result.scalars().first()
            
            await send_booking_confirmation_email(
                recipient_email=current_user.email,
                recipient_name=current_user.name,
                booking_details={
                    "venue_name": accommodation.name if accommodation else "Accommodation",
                    "booking_type": "accommodation",
                    "start_date": start_date_naive.strftime("%d %B %Y"),
                    "end_date": end_date_naive.strftime("%d %B %Y"),
                    "amount": f"{booking.amount:,.2f}",
                    "transaction_id": booking.transaction_id or "N/A",
                    "venue_address": accommodation.address if accommodation else "",
                    "cabin_number": None
                }
            )
        except Exception as email_error:
            print(f"Failed to send booking confirmation email: {email_error}")
        
        return new_booking
    
    raise HTTPException(status_code=400, detail="Must specify cabin_id or accommodation_id")


@router.post("/extend-test", dependencies=[Depends(dev_only), Depends(get_current_user)])
async def extend_booking_test(
    booking_id: str,
    new_end_date: str,  # Accept as string to debug
    extension_amount: float,
    db: AsyncSession = Depends(get_db)
):
    """DEBUG: test extend endpoint.

    Previously this had NO authentication AND was reachable on
    production — anyone could extend any booking's end_date and add
    arbitrary money to its amount. Two layers added:
      * `dev_only` — 404 in production (override with ENABLE_DEV_BYPASS).
      * `get_current_user` — requires a valid JWT even in dev so a
        nightly cron / random crawler can't hit it accidentally.
    """
    try:
        # Parse the datetime from ISO string (handle Z timezone suffix)
        date_str = new_end_date.replace('Z', '+00:00')
        parsed_date = datetime.fromisoformat(date_str)
        
        result = await db.execute(select(Booking).where(Booking.id == booking_id))
        booking = result.scalars().first()
        
        if not booking:
            return {"error": "Booking not found", "booking_id": booking_id}
        
        old_date = booking.end_date
        # Convert to naive datetime if timezone-aware
        booking.end_date = parsed_date.replace(tzinfo=None) if parsed_date.tzinfo else parsed_date
        booking.amount = (booking.amount or 0) + extension_amount
        
        await db.commit()
        await db.refresh(booking)
        
        return {
            "success": True,
            "old_end_date": str(old_date),
            "new_end_date": str(booking.end_date),
            "booking_id": booking_id
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"error": str(e), "type": type(e).__name__}


@router.post("/extend")
async def extend_booking(
    booking_id: str,
    extension_duration_type: str = Query(..., description="Extension duration: 1_DAY, 1_WEEK, 1_MONTH, 3_MONTHS, 6_MONTHS"),
    payment_method: str = "UPI",
    transaction_id: str = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Extend an existing booking with duration type support.
    Extension duration must be enabled in the venue's configuration.
    Price is calculated from venue's custom duration_prices.
    """
    try:
        # Get existing booking
        result = await db.execute(select(Booking).where(Booking.id == booking_id))
        booking = result.scalars().first()
        if not booking:
            raise HTTPException(status_code=404, detail="Booking not found")
        
        if booking.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Not authorized")
        
        # Get reading room to validate extension duration and get price
        if not booking.cabin_id:
            raise HTTPException(status_code=400, detail="Extension only supported for cabin bookings")
        
        cabin_result = await db.execute(select(Cabin).where(Cabin.id == booking.cabin_id))
        cabin = cabin_result.scalars().first()
        if not cabin:
            raise HTTPException(status_code=404, detail="Cabin not found")
        
        room_result = await db.execute(
            select(ReadingRoom).where(ReadingRoom.id == cabin.reading_room_id)
        )
        reading_room = room_result.scalars().first()
        if not reading_room:
            raise HTTPException(status_code=404, detail="Reading room not found")
        
        # Validate extension duration is allowed
        await booking_validator.validate_duration_allowed(reading_room, extension_duration_type)
        
        # Validate owner has set price for this duration
        booking_validator.validate_custom_prices_set(reading_room, extension_duration_type)
        
        # Get extension price
        extension_amount = booking_validator.get_duration_price(reading_room, extension_duration_type, cabin.price)
        
        # Calculate new end date
        current_end_date = booking.end_date
        new_end_date = booking_validator.calculate_end_date(current_end_date, extension_duration_type)
        
        # Calculate days extended for reporting
        days_extended = (new_end_date - current_end_date).days
        
        # Update booking
        old_end_date_str = booking.end_date.strftime("%d %B %Y") if booking.end_date else ""
        booking.end_date = new_end_date.replace(tzinfo=None) if new_end_date.tzinfo else new_end_date
        booking.amount = (booking.amount or 0) + extension_amount
        
        await db.commit()
        await db.refresh(booking)
        
        # Send booking extension email
        try:
            from app.services.email_service import send_booking_extension_email
            
            await send_booking_extension_email(
                recipient_email=current_user.email,
                recipient_name=current_user.name,
                extension_details={
                    "venue_name": reading_room.name,
                    "old_end_date": old_end_date_str,
                    "new_end_date": booking.end_date.strftime("%d %B %Y"),
                    "extension_amount": f"{extension_amount:,.2f}",
                    "total_amount": f"{booking.amount:,.2f}",
                    "extension_duration": booking_validator.format_duration_label(extension_duration_type),
                    "days_extended": days_extended
                }
            )
        except Exception as email_error:
            print(f"Failed to send booking extension email: {email_error}")
        
        return {
            "message": "Booking extended successfully",
            "booking_id": booking_id,
            "old_end_date": old_end_date_str,
            "new_end_date": booking.end_date.strftime("%d %B %Y"),
            "extension_amount": extension_amount,
            "total_amount": booking.amount,
            "extension_duration_type": extension_duration_type,
            "days_extended": days_extended
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error in extend_booking: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Extension failed: {str(e)}")


@router.post("/{booking_id}/cancel")
async def cancel_booking(
    booking_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Cancel a booking (User action).
    Triggers waitlist if cabin becomes available.
    """
    result = await db.execute(select(Booking).where(Booking.id == booking_id))
    booking = result.scalars().first()
    
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
        
    if booking.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    if booking.status == BookingStatus.CANCELLED:
         raise HTTPException(status_code=400, detail="Booking already cancelled")

    # Update Booking
    booking.status = BookingStatus.CANCELLED
    
    # Update Cabin
    if booking.cabin_id:
        result_cabin = await db.execute(select(Cabin).where(Cabin.id == booking.cabin_id))
        cabin = result_cabin.scalars().first()
        if cabin:
            cabin.status = CabinStatus.AVAILABLE
            cabin.current_occupant_id = None
            await db.commit() # Commit cancellation first
            
            # TRIGGER WAITLIST
            from app.services.waitlist_service import waitlist_service
            await waitlist_service.check_waitlist_and_notify(cabin.id, db)

    await db.commit()
    return {"message": "Booking cancelled successfully", "status": "CANCELLED"}

