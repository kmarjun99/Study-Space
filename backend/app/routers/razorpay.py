import logging
import traceback

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

from app.database import get_db
from app.models.booking import Booking, PaymentStatus
from app.models.boost_request import BoostRequest, BoostRequestStatus
from app.models.user import User, UserRole
from app.services.payment_service import payment_service
from app.deps import get_current_user

router = APIRouter(prefix="/razorpay", tags=["Razorpay Payments"])
_log = logging.getLogger("studyspace.razorpay")


class CreateOrderRequest(BaseModel):
    booking_id: str
    amount: float


class CreateBoostOrderRequest(BaseModel):
    boost_request_id: str
    amount: float


class CreateOrderResponse(BaseModel):
    order_id: str
    amount: int  # in paise
    currency: str
    razorpay_key_id: str
    is_demo: bool = False


class VerifyPaymentRequest(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str
    booking_id: Optional[str] = None  # Optional for flexibility


class RefundRequest(BaseModel):
    booking_id: str
    amount: Optional[float] = None
    reason: Optional[str] = None


@router.post("/create-order", response_model=CreateOrderResponse)
async def create_payment_order(
    request: CreateOrderRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Create a Razorpay order for a booking
    """
    # Verify booking exists and belongs to user
    result = await db.execute(
        select(Booking).where(
            Booking.id == request.booking_id,
            Booking.user_id == current_user.id
        )
    )
    booking = result.scalar_one_or_none()
    
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    
    if booking.payment_status == PaymentStatus.PAID:
        raise HTTPException(status_code=400, detail="Booking already paid")
    
    # Create Razorpay order
    order = payment_service.create_order(
        amount=request.amount,
        receipt=f"booking_{booking.id}",
        notes={
            "booking_id": booking.id,
            "user_id": current_user.id,
            "user_email": current_user.email or ""
        }
    )
    
    # Update booking with order ID (store in transaction_id temporarily)
    booking.transaction_id = order["id"]
    await db.commit()
    
    return CreateOrderResponse(
        order_id=order["id"],
        amount=order["amount"],
        currency=order["currency"],
        razorpay_key_id=payment_service.razorpay_key_id,
        is_demo=order.get("is_demo", False)
    )


@router.post("/create-boost-order", response_model=CreateOrderResponse)
async def create_boost_payment_order(
    request: CreateBoostOrderRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Create a Razorpay order for a boost request
    """
    # Verify boost request exists and belongs to user's venue
    result = await db.execute(
        select(BoostRequest).where(
            BoostRequest.id == request.boost_request_id,
            BoostRequest.owner_id == current_user.id
        )
    )
    boost_request = result.scalar_one_or_none()
    
    if not boost_request:
        raise HTTPException(status_code=404, detail="Boost request not found")
    
    if boost_request.status == BoostRequestStatus.PAID:
        raise HTTPException(status_code=400, detail="Boost request already paid")
    
    # Create Razorpay order
    order = payment_service.create_order(
        amount=request.amount,
        receipt=f"boost_{boost_request.id}",
        notes={
            "boost_request_id": boost_request.id,
            "venue_id": boost_request.venue_id,
            "owner_id": current_user.id,
            "owner_email": current_user.email or ""
        }
    )
    
    # Update boost request with order ID
    boost_request.payment_id = order["id"]
    await db.commit()
    
    return CreateOrderResponse(
        order_id=order["id"],
        amount=order["amount"],
        currency=order["currency"],
        razorpay_key_id=payment_service.razorpay_key_id,
        is_demo=order.get("is_demo", False)
    )


@router.post("/verify")
async def verify_payment(
    request: VerifyPaymentRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Verify Razorpay payment signature and update booking
    """
    try:
        return await _verify_payment_impl(request, current_user, db)
    except HTTPException:
        # Already a properly-shaped error (400/404) — let it propagate so
        # the client sees the original status + detail.
        raise
    except Exception as exc:
        # Unexpected 500. Without this wrapper, FastAPI logs the traceback
        # to stderr only and returns an opaque 500 with no body, leaving
        # the operator (and us) guessing about which line threw. Logging
        # + including the message in the detail trades a little
        # information leakage for actionable error messages — acceptable
        # because this endpoint is auth-gated.
        tb = traceback.format_exc()
        _log.error(
            "verify_payment failed booking_id=%s order_id=%s payment_id=%s\n%s",
            request.booking_id, request.razorpay_order_id,
            request.razorpay_payment_id, tb,
        )
        # Try to roll back any partial state so the next attempt isn't
        # stuck behind a half-committed transaction.
        try:
            await db.rollback()
        except Exception:
            pass
        raise HTTPException(
            status_code=500,
            detail=f"Payment verification failed: {type(exc).__name__}: {exc}",
        )


async def _verify_payment_impl(
    request: VerifyPaymentRequest,
    current_user: User,
    db: AsyncSession,
):
    # Verify signature
    is_valid = payment_service.verify_payment_signature(
        request.razorpay_order_id,
        request.razorpay_payment_id,
        request.razorpay_signature
    )
    
    if not is_valid:
        raise HTTPException(status_code=400, detail="Invalid payment signature")
    
    # Fetch payment details from Razorpay (skip in demo mode).
    #
    # SECURITY: is_demo is set SOLELY from the server-side
    # `payment_service.demo_mode` flag. The previous version also OR-ed in
    # `request.razorpay_payment_id.startswith("pay_demo_")` — a
    # client-controlled string. A malicious client in production could
    # send `pay_demo_<anything>` as the payment_id and skip the real
    # Razorpay fetch_payment call, which is the only way the server
    # cross-checks the amount + method against Razorpay's own records.
    # Together with the matching client-spoof in
    # payment_service.verify_payment_signature, a forged demo payment
    # could mark any booking as PAID for free.
    is_demo = payment_service.demo_mode
    if is_demo:
        # Create mock payment data for demo mode
        payment = {
            "id": request.razorpay_payment_id,
            "amount": 0,  # Will use booking amount
            "method": "upi",
            "status": "captured"
        }
    else:
        payment = payment_service.fetch_payment(request.razorpay_payment_id)
    
    # Validate booking_id is provided
    if not request.booking_id:
        raise HTTPException(status_code=400, detail="booking_id is required")
    
    # Update booking
    result = await db.execute(
        select(Booking).where(
            Booking.id == request.booking_id,
            Booking.user_id == current_user.id
        )
    )
    booking = result.scalar_one_or_none()
    
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    
    # Check if already paid to avoid duplicate payment records
    if booking.payment_status == PaymentStatus.PAID:
        # Use booking amount for demo mode, payment amount for real mode
        amount_rupees = booking.amount if is_demo else (payment["amount"] / 100)
        return {
            "success": True,
            "message": "Payment already verified",
            "booking_id": booking.id,
            "payment_id": request.razorpay_payment_id,
            "amount": amount_rupees
        }
    
    # Snapshot booking attributes to plain locals NOW, before any mutation
    # or commit. This is THE bug behind the persistent 500s when payments
    # were actually succeeding in the database:
    #
    #   After db.commit() SQLAlchemy expires every loaded attribute; the
    #   next read of `booking.amount` triggers a refresh-on-access. If any
    #   side-effect block (accounting shadow / campaign / recommendation /
    #   email) earlier in the request had its own flush fail, the session
    #   is in a "needs rollback" state. The refresh-on-access then throws
    #   sqlalche.me/e/20/7s2a INSIDE the line that just reads
    #   `booking.amount` at the bottom of this function — long after the
    #   booking has been successfully marked PAID + invoice issued. The
    #   exception escapes to the global handler as Internal Server Error,
    #   the frontend shows "Demo payment failed", the user thinks the
    #   payment failed — even though the database has a PAID row and a
    #   downloadable invoice.
    #
    # Caching primitives here means every read below this point is just
    # local-variable access, independent of session state.
    booking_id_str = booking.id
    booking_amount_val = float(booking.amount) if booking.amount is not None else 0.0
    booking_start_date_val = booking.start_date
    booking_end_date_val = booking.end_date
    booking_cabin_id_val = booking.cabin_id
    booking_accommodation_id_val = booking.accommodation_id

    # Update payment status
    booking.payment_status = PaymentStatus.PAID
    booking.transaction_id = request.razorpay_payment_id

    # If booking was HELD, confirm it now
    from app.models.booking import BookingStatus
    from app.models.reading_room import Cabin, CabinStatus

    # Look up the cabin BEFORE modifying anything on booking that would
    # auto-flush the booking changes. We were doing it the other way
    # around: setting booking.status = ACTIVE, then `await db.execute(
    # select(Cabin)...)`. SQLAlchemy's autoflush would push the pending
    # booking UPDATE first; if that flush failed (constraint / column /
    # enum issue), the session was poisoned and every subsequent
    # operation in this request threw the 7s2a error. Resolving the cabin
    # FIRST keeps autoflush from triggering during an unrelated query.
    cabin = None
    if booking.cabin_id:
        cabin_result = await db.execute(select(Cabin).where(Cabin.id == booking.cabin_id))
        cabin = cabin_result.scalar_one_or_none()

    if booking.status == BookingStatus.HELD:
        booking.status = BookingStatus.ACTIVE
        if cabin is not None:
            cabin.status = CabinStatus.OCCUPIED
            cabin.current_occupant_id = current_user.id
    
    # Stamp paid_at on the booking so settlement + the accounting shadow have
    # a definitive timestamp (the shadow used to set this itself, but doing it
    # here makes the booking row authoritative even if accounting.enabled is off).
    if getattr(booking, "paid_at", None) is None:
        booking.paid_at = datetime.utcnow()

    # Explicit flush of the booking + cabin updates BEFORE adding the
    # PaymentTransaction. If something in the booking/cabin update fails
    # (column missing, enum mismatch, constraint), this is where the
    # error surfaces — clearly attributable to "booking/cabin update",
    # not to "payment_transaction insert" further down. The error string
    # gets included in the 500 detail by the outer try/except.
    try:
        await db.flush()
    except Exception as flush_err:
        _log.exception(
            "verify_payment booking/cabin flush failed booking_id=%s",
            request.booking_id,
        )
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail=(
                f"Could not update booking status: {type(flush_err).__name__}: "
                f"{flush_err}"
            ),
        )

    # Create PaymentTransaction record for financial tracking
    from app.models.payment_transaction import PaymentTransaction, PaymentMethod, PaymentGateway, PaymentType

    # Determine payment method from Razorpay response
    payment_method = PaymentMethod.UPI  # Default
    if payment.get("method"):
        method_str = payment["method"].upper()
        if method_str == "CARD":
            payment_method = PaymentMethod.CARD
        elif method_str == "NETBANKING":
            payment_method = PaymentMethod.NET_BANKING
        elif method_str == "WALLET":
            payment_method = PaymentMethod.WALLET
    
    # Create payment transaction record
    # Use booking amount for demo mode, payment amount (in paise) for real mode
    amount_rupees = booking.amount if is_demo else (payment["amount"] / 100)
    
    payment_transaction = PaymentTransaction(
        booking_id=booking.id,
        user_id=current_user.id,
        payment_type=PaymentType.INITIAL,
        method=payment_method,
        gateway=PaymentGateway.RAZORPAY,
        amount=amount_rupees,
        gateway_transaction_id=request.razorpay_payment_id,
        description=f"Cabin booking payment",
        created_at=datetime.utcnow()
    )
    db.add(payment_transaction)

    # Critical commit — if this fails the booking IS NOT marked PAID, so the
    # client must know. Catch SQLAlchemy errors specifically so a constraint
    # violation surfaces with the constraint name in the response instead of
    # the generic "Internal Server Error" body emitted by the global handler.
    try:
        await db.commit()
    except Exception as commit_err:
        _log.exception(
            "verify_payment commit failed booking_id=%s",
            request.booking_id,
        )
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail=(
                f"Could not finalize booking: {type(commit_err).__name__}: "
                f"{commit_err}"
            ),
        )

    # db.refresh(booking) was removed — it's redundant (we just modified the
    # row and committed it; SQLAlchemy auto-expires attributes and reloads
    # them on next access). The previous explicit refresh added a network
    # round-trip and one more point of failure for no benefit.

    # The booking IS NOW PAID and committed. Everything below is a side-
    # effect: tax shadow, attribution, email. NONE of them are allowed to
    # affect the response — if any throws OR poisons the session, we
    # rollback that block's partial state and continue. The response below
    # is the definitive "payment verified" signal to the client.
    #
    # Each block needs its OWN db.rollback() inside except, because a
    # failed commit leaves the AsyncSession in a "needs rollback" state;
    # without an explicit rollback every subsequent db.execute() in the
    # NEXT block would also throw with "Can't reconnect until invalid
    # transaction is rolled back".

    # Accounting shadow — guarded internally by `accounting.enabled`.
    try:
        from app.services.accounting_shadow import AccountingShadow
        await AccountingShadow.shadow_post_booking_paid(db, booking_id=booking.id)
        await db.commit()
    except Exception as acc_err:
        _log.warning("[accounting_shadow] non-fatal: %s", acc_err)
        try: await db.rollback()
        except Exception: pass

    # Phase 4B — campaign attribution. Gated internally by `campaigns.enabled`.
    try:
        from app.services import campaign_service
        await campaign_service.attribute_booking(
            db, booking_id=booking.id, user_id=current_user.id,
        )
        await db.commit()
    except Exception as att_err:
        _log.warning("[campaign_attribution] non-fatal: %s", att_err)
        try: await db.rollback()
        except Exception: pass

    # Phase 4D — recommendation attribution. Gated internally.
    # Uses snapshotted IDs (booking_cabin_id_val / booking_accommodation_id_val)
    # so we never lazy-load expired booking attributes through a possibly-
    # poisoned session.
    try:
        from app.services import recommendation_attribution_service
        from app.models.reading_room import Cabin
        listing_id_for_attribution: str | None = None
        if booking_cabin_id_val:
            cab_row = await db.get(Cabin, booking_cabin_id_val)
            if cab_row is not None:
                listing_id_for_attribution = cab_row.reading_room_id
        elif booking_accommodation_id_val:
            listing_id_for_attribution = booking_accommodation_id_val
        if listing_id_for_attribution:
            await recommendation_attribution_service.attribute_booking(
                db,
                booking_id=booking_id_str,
                user_id=current_user.id,
                listing_id=listing_id_for_attribution,
            )
            await db.commit()
    except Exception as reco_err:
        _log.warning("[recommendation_attribution] non-fatal: %s", reco_err)
        try: await db.rollback()
        except Exception: pass

    # Send booking confirmation email — uses snapshotted booking fields for
    # the same lazy-load-safety reason as above.
    try:
        from app.services.email_service import send_booking_confirmation_email
        from app.models.reading_room import Cabin, ReadingRoom
        from app.models.accommodation import Accommodation

        venue_name = "Venue"
        venue_address = ""
        cabin_number = None
        booking_type = "booking"

        if booking_cabin_id_val:
            cabin_result = await db.execute(select(Cabin).where(Cabin.id == booking_cabin_id_val))
            cabin = cabin_result.scalar_one_or_none()
            if cabin:
                cabin_number = cabin.number
                room_result = await db.execute(select(ReadingRoom).where(ReadingRoom.id == cabin.reading_room_id))
                room = room_result.scalar_one_or_none()
                if room:
                    venue_name = room.name
                    venue_address = room.address or ""
            booking_type = "cabin"
        elif booking_accommodation_id_val:
            acc_result = await db.execute(select(Accommodation).where(Accommodation.id == booking_accommodation_id_val))
            accommodation = acc_result.scalar_one_or_none()
            if accommodation:
                venue_name = accommodation.name
                venue_address = accommodation.address or ""
            booking_type = "accommodation"

        await send_booking_confirmation_email(
            recipient_email=current_user.email,
            recipient_name=current_user.name,
            booking_details={
                "venue_name": venue_name,
                "booking_type": booking_type,
                "start_date": booking_start_date_val.strftime("%d %B %Y") if booking_start_date_val else "N/A",
                "end_date": booking_end_date_val.strftime("%d %B %Y") if booking_end_date_val else "N/A",
                "amount": f"{booking_amount_val:,.2f}",
                "transaction_id": request.razorpay_payment_id,
                "venue_address": venue_address,
                "cabin_number": cabin_number
            }
        )
    except Exception as email_error:
        _log.warning("Failed to send booking confirmation email: %s", email_error)
        try: await db.rollback()
        except Exception: pass

    # Use SNAPSHOTTED booking_amount_val and booking_id_str — never
    # `booking.amount` / `booking.id` directly. The booking instance's
    # attributes were expired by db.commit() above; any side-effect that
    # leaves the session in a "needs rollback" state turns the next
    # attribute access into a lazy-load that throws 7s2a, ESCAPES the
    # function entirely (no try/except wraps this line), and bubbles up
    # to the global exception handler as Internal Server Error. That was
    # the production bug: payment marked PAID + invoice issued, but this
    # final read failed with 7s2a so the client thought the payment
    # failed.
    amount_rupees = booking_amount_val if is_demo else (payment["amount"] / 100)

    return {
        "success": True,
        "message": "Payment verified successfully",
        "booking_id": booking_id_str,
        "payment_id": request.razorpay_payment_id,
        "amount": amount_rupees
    }


@router.post("/refund")
async def refund_payment(
    request: RefundRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Process refund for a booking.

    AUTHORIZATION (added as part of P1 security hardening):
      * Super-admin can refund ANY booking.
      * Venue owner can refund a booking ONLY for a cabin / accommodation
        they own. Ownership is checked against ReadingRoom.owner_id (via
        the cabin → room chain) or Accommodation.owner_id.
      * Regular students cannot refund here. Student-initiated refund
        REQUESTS go through /payments/admin/refunds where the request
        is queued for admin review — not via this endpoint.
      * Unauthenticated callers cannot reach this code at all (the
        get_current_user dependency rejects them with 401).

    Previously: ANY authenticated user could refund ANY booking. That was
    a critical data-integrity hole. The docstring claimed "Admin/Owner
    only" but the enforcement was missing.
    """
    # Verify booking exists
    result = await db.execute(
        select(Booking).where(Booking.id == request.booking_id)
    )
    booking = result.scalar_one_or_none()

    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    if booking.payment_status != PaymentStatus.PAID:
        raise HTTPException(status_code=400, detail="Booking is not paid")

    # Authorization: super-admin bypasses the ownership check.
    if current_user.role != UserRole.SUPER_ADMIN:
        # For non-super-admins, require venue ownership. Resolve the
        # owner_id via the booking's cabin/accommodation relationship.
        from app.models.reading_room import Cabin, ReadingRoom
        from app.models.accommodation import Accommodation
        venue_owner_id: Optional[str] = None
        if booking.cabin_id:
            cabin = (await db.execute(
                select(Cabin).where(Cabin.id == booking.cabin_id)
            )).scalar_one_or_none()
            if cabin is not None:
                room = (await db.execute(
                    select(ReadingRoom).where(ReadingRoom.id == cabin.reading_room_id)
                )).scalar_one_or_none()
                if room is not None:
                    venue_owner_id = room.owner_id
        elif booking.accommodation_id:
            acc = (await db.execute(
                select(Accommodation).where(Accommodation.id == booking.accommodation_id)
            )).scalar_one_or_none()
            if acc is not None:
                venue_owner_id = acc.owner_id

        if venue_owner_id is None or venue_owner_id != current_user.id:
            # 403 (not 404) — the booking exists; the caller just isn't
            # allowed to refund it. Returning 404 here would obscure a
            # legitimate "missing venue/cabin" data issue from operators.
            raise HTTPException(
                status_code=403,
                detail="Refund forbidden: not the venue owner. "
                       "Students must request refunds via the support flow.",
            )

    # Process refund
    refund = payment_service.refund_payment(
        payment_id=booking.transaction_id,
        amount=request.amount,
        notes={"reason": request.reason or "User requested refund"}
    )

    # Update booking status
    booking.payment_status = PaymentStatus.REFUNDED
    await db.commit()

    return {
        "success": True,
        "message": "Refund processed successfully",
        "refund_id": refund["id"],
        "amount": refund["amount"] / 100
    }


@router.get("/status/{booking_id}")
async def get_payment_status(
    booking_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get payment status for a booking
    """
    result = await db.execute(
        select(Booking).where(
            Booking.id == booking_id,
            Booking.user_id == current_user.id
        )
    )
    booking = result.scalar_one_or_none()
    
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    
    return {
        "booking_id": booking.id,
        "payment_status": booking.payment_status.value if booking.payment_status else "PENDING",
        "transaction_id": booking.transaction_id,
        "amount": booking.amount
    }
