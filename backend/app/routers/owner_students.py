from __future__ import annotations

import secrets
from datetime import datetime, time
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_password_hash
from app.database import get_db
from app.deps import get_current_user
from app.models.booking import Booking, BookingStatus, PaymentStatus, SettlementStatus
from app.models.invoice import Invoice, InvoiceDocType
from app.models.notification import Notification
from app.models.payment_transaction import (
    PaymentGateway,
    PaymentMethod,
    PaymentTransaction,
    PaymentType,
)
from app.models.reading_room import Cabin, CabinStatus, ReadingRoom
from app.models.user import User, UserRole, VerificationStatus
from app.schemas.owner_students import (
    OwnerBookingRenewRequest,
    OwnerMarkPaidRequest,
    OwnerStudentActionResponse,
    OwnerStudentAssignmentCreate,
    OwnerStudentRow,
)
from app.services import otp_service
from app.services.booking_validator import booking_validator
from app.services.email_service import is_email_delivery_configured, send_otp_email
from app.services.invoice_series_service import InvoiceSeriesService
from app.services.renewal_service import apply_renewal_fields


router = APIRouter(prefix="/owner", tags=["owner-students"])


def _require_owner(user: User) -> None:
    if user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Owner/admin account required")


def _as_owner_row(
    *,
    student: User,
    booking: Optional[Booking],
    cabin: Optional[Cabin],
    room: Optional[ReadingRoom],
) -> OwnerStudentRow:
    payload = {
        "student_id": student.id,
        "name": student.name,
        "email": student.email,
        "phone": student.phone,
        "verification_status": student.verification_status.value if student.verification_status else "NOT_REQUIRED",
        "must_set_password": bool(student.must_set_password),
        "booking_id": booking.id if booking else None,
        "cabin_id": cabin.id if cabin else None,
        "cabin_number": cabin.number if cabin else None,
        "reading_room_id": room.id if room else None,
        "reading_room_name": room.name if room else None,
        "payment_status": booking.payment_status if booking else None,
        "booking_status": booking.status if booking else None,
        "amount": booking.amount if booking else None,
        "duration_type": booking.duration_type if booking else None,
        "created_at": booking.created_at if booking else None,
    }
    if booking:
        payload = apply_renewal_fields(payload, booking)
    return OwnerStudentRow(**payload)


async def _get_owned_room_and_cabin(
    db: AsyncSession,
    *,
    owner_id: str,
    reading_room_id: str,
    cabin_id: str,
) -> tuple[ReadingRoom, Cabin]:
    room = await db.get(ReadingRoom, reading_room_id)
    if not room or room.owner_id != owner_id:
        raise HTTPException(status_code=404, detail="Reading room not found")

    cabin = await db.get(Cabin, cabin_id)
    if not cabin or cabin.reading_room_id != room.id:
        raise HTTPException(status_code=404, detail="Cabin not found in this reading room")
    return room, cabin


async def _load_owned_booking(
    db: AsyncSession,
    *,
    owner_id: str,
    booking_id: str,
) -> tuple[Booking, Cabin, ReadingRoom, User]:
    result = await db.execute(
        select(Booking, Cabin, ReadingRoom, User)
        .join(Cabin, Booking.cabin_id == Cabin.id)
        .join(ReadingRoom, Cabin.reading_room_id == ReadingRoom.id)
        .join(User, Booking.user_id == User.id)
        .where(Booking.id == booking_id, ReadingRoom.owner_id == owner_id)
    )
    row = result.first()
    if not row:
        raise HTTPException(status_code=404, detail="Student booking not found")
    return row[0], row[1], row[2], row[3]


async def _create_manual_payment(
    db: AsyncSession,
    *,
    booking: Booking,
    amount: float,
    payment_type: PaymentType,
    reference: Optional[str],
    description: str,
) -> PaymentTransaction:
    payment = PaymentTransaction(
        booking_id=booking.id,
        user_id=booking.user_id,
        payment_type=payment_type,
        method=PaymentMethod.UPI,
        gateway=PaymentGateway.MANUAL,
        masked_reference=reference,
        amount=amount,
        gateway_transaction_id=reference,
        description=description,
    )
    db.add(payment)
    await db.flush()
    return payment


async def _notify_student(db: AsyncSession, *, user_id: str, title: str, message: str, kind: str = "info") -> None:
    db.add(Notification(user_id=user_id, title=title, message=message, type=kind))


async def _create_or_update_offline_invoice(
    db: AsyncSession,
    *,
    booking: Booking,
    room: ReadingRoom,
    cabin: Cabin,
    owner_id: str,
    payment_transaction: Optional[PaymentTransaction],
    payment_reference: Optional[str],
) -> Invoice:
    invoice = await db.scalar(select(Invoice).where(Invoice.booking_id == booking.id))
    if invoice is None:
        invoice_number, fiscal_year, sequence_no = await InvoiceSeriesService.next_number(db, series_code="RCT")
        invoice = Invoice(
            invoice_number=invoice_number,
            booking_id=booking.id,
            user_id=booking.user_id,
            owner_id=owner_id,
            cabin_id=cabin.id,
            amount=booking.amount or 0,
            tax_amount=0.0,
            total_amount=booking.amount or 0,
            venue_name=room.name,
            venue_address=room.address,
            seat_details=f"Cabin {cabin.number}, Floor {cabin.floor}",
            plan_duration=booking_validator.format_duration_label(booking.duration_type or "1_MONTH"),
            duration_type=booking.duration_type,
            start_date=booking.start_date,
            end_date=booking.end_date,
            joining_date=booking.start_date,
            renewal_period_start=booking.start_date,
            renewal_period_end=booking.end_date,
            due_date=booking.start_date,
            doc_type=InvoiceDocType.NON_GST_RECEIPT,
            series_code="RCT",
            fiscal_year=fiscal_year,
            sequence_no=sequence_no,
            base_amount=booking.amount or 0,
            cgst=0,
            sgst=0,
            igst=0,
            cess=0,
        )
        db.add(invoice)

    invoice.payment_id = payment_transaction.id if payment_transaction else invoice.payment_id
    invoice.payment_status = booking.payment_status.value if hasattr(booking.payment_status, "value") else str(booking.payment_status)
    invoice.payment_reference = payment_reference or invoice.payment_reference
    invoice.amount = booking.amount or invoice.amount or 0
    invoice.total_amount = booking.amount or invoice.total_amount or 0
    invoice.owner_id = owner_id
    invoice.cabin_id = cabin.id
    invoice.duration_type = booking.duration_type
    invoice.plan_duration = booking_validator.format_duration_label(booking.duration_type or "1_MONTH")
    invoice.start_date = booking.start_date
    invoice.end_date = booking.end_date
    invoice.joining_date = booking.start_date
    invoice.renewal_period_start = booking.start_date
    invoice.renewal_period_end = booking.end_date
    invoice.due_date = booking.start_date
    await db.flush()
    return invoice


@router.get("/students", response_model=list[OwnerStudentRow])
async def list_owner_students(
    renewal_status: Optional[str] = Query(default=None),
    payment_status: Optional[PaymentStatus] = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_owner(current_user)
    result = await db.execute(
        select(User, Booking, Cabin, ReadingRoom)
        .join(Booking, Booking.user_id == User.id)
        .join(Cabin, Booking.cabin_id == Cabin.id)
        .join(ReadingRoom, Cabin.reading_room_id == ReadingRoom.id)
        .where(ReadingRoom.owner_id == current_user.id)
        .order_by(desc(Booking.created_at))
    )

    seen: set[str] = set()
    rows: list[OwnerStudentRow] = []
    for student, booking, cabin, room in result.all():
        if student.id in seen:
            continue
        seen.add(student.id)
        row = _as_owner_row(student=student, booking=booking, cabin=cabin, room=room)
        if renewal_status and row.renewal_status and row.renewal_status.value != renewal_status:
            continue
        if payment_status and row.payment_status != payment_status:
            continue
        rows.append(row)

    return rows


@router.post("/students", response_model=OwnerStudentActionResponse)
async def create_owner_student_assignment(
    request: OwnerStudentAssignmentCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_owner(current_user)
    room, cabin = await _get_owned_room_and_cabin(
        db,
        owner_id=current_user.id,
        reading_room_id=request.reading_room_id,
        cabin_id=request.cabin_id,
    )

    await booking_validator.validate_duration_allowed(room, request.duration_type)
    booking_validator.validate_custom_prices_set(room, request.duration_type)

    existing_user = await db.scalar(select(User).where(User.email == request.email))
    if existing_user and existing_user.role != UserRole.STUDENT:
        raise HTTPException(status_code=409, detail="This email belongs to a non-student account")

    student = existing_user
    if student is None:
        student = User(
            email=request.email,
            hashed_password=get_password_hash(secrets.token_urlsafe(32)),
            name=request.name.strip(),
            role=UserRole.STUDENT,
            phone=request.phone,
            verification_status=VerificationStatus.PENDING,
            created_by_owner_id=current_user.id,
            must_set_password=True,
        )
        db.add(student)
        await db.flush()
    else:
        student.name = request.name.strip() or student.name
        student.phone = request.phone or student.phone
        if not student.email_verified_at:
            student.verification_status = VerificationStatus.PENDING
            student.must_set_password = True

    if cabin.status not in (CabinStatus.AVAILABLE, CabinStatus.RESERVED) and cabin.current_occupant_id != student.id:
        raise HTTPException(status_code=409, detail="Cabin is already assigned to another student")

    active_other = await db.scalar(
        select(Booking.id)
        .where(
            Booking.cabin_id == cabin.id,
            Booking.status.in_([BookingStatus.ACTIVE, BookingStatus.HELD]),
            Booking.user_id != student.id,
        )
    )
    if active_other:
        raise HTTPException(status_code=409, detail="Cabin already has an active assignment")

    joining_dt = datetime.combine(request.joining_date, time.min)
    expiry_dt = booking_validator.calculate_end_date(joining_dt, request.duration_type)
    amount = request.amount
    if amount is None:
        amount = booking_validator.get_duration_price(room, request.duration_type, cabin.price)

    booking = Booking(
        user_id=student.id,
        cabin_id=cabin.id,
        start_date=joining_dt,
        end_date=expiry_dt,
        amount=amount,
        status=BookingStatus.ACTIVE,
        payment_status=request.payment_status,
        transaction_id=request.payment_reference,
        settlement_status=SettlementStatus.NOT_SETTLED,
        duration_type=request.duration_type,
        booking_source="OWNER_OFFLINE",
        assigned_by_owner_id=current_user.id,
        paid_at=datetime.utcnow() if request.payment_status == PaymentStatus.PAID else None,
    )
    cabin.status = CabinStatus.OCCUPIED
    cabin.current_occupant_id = student.id
    cabin.held_by_user_id = None
    cabin.hold_expires_at = None
    db.add(booking)
    await db.flush()

    payment_transaction: Optional[PaymentTransaction] = None
    if request.payment_status == PaymentStatus.PAID:
        payment_transaction = await _create_manual_payment(
            db,
            booking=booking,
            amount=amount,
            payment_type=PaymentType.INITIAL,
            reference=request.payment_reference,
            description="Owner-created offline student assignment",
        )

    await _create_or_update_offline_invoice(
        db,
        booking=booking,
        room=room,
        cabin=cabin,
        owner_id=current_user.id,
        payment_transaction=payment_transaction,
        payment_reference=request.payment_reference,
    )

    await _notify_student(
        db,
        user_id=student.id,
        title="Cabin assigned",
        message=f"You have been assigned cabin {cabin.number} at {room.name}.",
        kind="success",
    )

    invite_message = "Invite not sent"
    if request.send_invite:
        otp_code, _ = await otp_service.create_otp(
            db=db,
            email=student.email,
            phone=student.phone,
            otp_type="owner_invite",
            expires_in_minutes=60 * 24,
            background_tasks=None,
            send_email=False,
        )
        if is_email_delivery_configured():
            email_sent = await send_otp_email(student.email, student.name, otp_code, "owner_invite")
            invite_message = (
                f"Invite email sent to {student.email}"
                if email_sent
                else f"Invite code generated, but email delivery failed for {student.email}. Check SMTP/SendGrid credentials."
            )
        else:
            invite_message = "Invite code generated, but email delivery is not configured on this server"
    await db.commit()
    await db.refresh(booking)

    if request.payment_status == PaymentStatus.PAID:
        try:
            from app.services.accounting_shadow import AccountingShadow

            await AccountingShadow.shadow_post_booking_paid(db, booking_id=booking.id)
            await db.commit()
            await db.refresh(booking)
        except Exception as acc_err:
            print(f"[owner_students accounting_shadow] non-fatal: {acc_err}")

    return OwnerStudentActionResponse(
        success=True,
        message=f"Student assigned and invoice generated. {invite_message}.",
        student=_as_owner_row(student=student, booking=booking, cabin=cabin, room=room),
    )


@router.post("/student-bookings/{booking_id}/renew", response_model=OwnerStudentActionResponse)
async def renew_student_booking(
    booking_id: str,
    request: OwnerBookingRenewRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_owner(current_user)
    booking, cabin, room, student = await _load_owned_booking(db, owner_id=current_user.id, booking_id=booking_id)
    duration_type = request.duration_type or booking.duration_type or "1_MONTH"
    await booking_validator.validate_duration_allowed(room, duration_type)
    booking_validator.validate_custom_prices_set(room, duration_type)

    amount = request.amount
    if amount is None:
        amount = booking_validator.get_duration_price(room, duration_type, cabin.price)

    old_end = booking.end_date
    anchor = booking.end_date if booking.end_date and booking.end_date > datetime.utcnow() else datetime.utcnow()
    booking.end_date = booking_validator.calculate_end_date(anchor, duration_type)
    booking.amount = (booking.amount or 0) + amount
    booking.duration_type = duration_type
    booking.status = BookingStatus.ACTIVE
    booking.payment_status = request.payment_status
    booking.transaction_id = request.payment_reference or booking.transaction_id
    booking.booking_source = booking.booking_source or "OWNER_OFFLINE"
    booking.assigned_by_owner_id = current_user.id
    payment_transaction: Optional[PaymentTransaction] = None
    if request.payment_status == PaymentStatus.PAID:
        booking.paid_at = booking.paid_at or datetime.utcnow()
        payment_transaction = await _create_manual_payment(
            db,
            booking=booking,
            amount=amount,
            payment_type=PaymentType.EXTENSION,
            reference=request.payment_reference,
            description=f"Owner renewal from {old_end:%d %b %Y} to {booking.end_date:%d %b %Y}",
        )

    cabin.status = CabinStatus.OCCUPIED
    cabin.current_occupant_id = student.id
    await _create_or_update_offline_invoice(
        db,
        booking=booking,
        room=room,
        cabin=cabin,
        owner_id=current_user.id,
        payment_transaction=payment_transaction,
        payment_reference=request.payment_reference,
    )
    await _notify_student(
        db,
        user_id=student.id,
        title="Cabin renewed",
        message=f"Your cabin {cabin.number} at {room.name} is renewed until {booking.end_date:%d %b %Y}.",
        kind="success",
    )
    await db.commit()
    await db.refresh(booking)

    return OwnerStudentActionResponse(
        success=True,
        message="Student booking renewed",
        student=_as_owner_row(student=student, booking=booking, cabin=cabin, room=room),
    )


@router.post("/student-bookings/{booking_id}/mark-paid", response_model=OwnerStudentActionResponse)
async def mark_student_booking_paid(
    booking_id: str,
    request: OwnerMarkPaidRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_owner(current_user)
    booking, cabin, room, student = await _load_owned_booking(db, owner_id=current_user.id, booking_id=booking_id)
    amount = request.amount if request.amount is not None else booking.amount
    booking.payment_status = PaymentStatus.PAID
    booking.paid_at = booking.paid_at or datetime.utcnow()
    booking.transaction_id = request.payment_reference or booking.transaction_id
    payment_transaction = await _create_manual_payment(
        db,
        booking=booking,
        amount=amount,
        payment_type=PaymentType.INITIAL,
        reference=request.payment_reference,
        description="Owner marked offline payment as paid",
    )
    await _create_or_update_offline_invoice(
        db,
        booking=booking,
        room=room,
        cabin=cabin,
        owner_id=current_user.id,
        payment_transaction=payment_transaction,
        payment_reference=request.payment_reference,
    )
    await _notify_student(
        db,
        user_id=student.id,
        title="Payment received",
        message=f"Payment for cabin {cabin.number} at {room.name} has been marked as received.",
        kind="success",
    )
    await db.commit()
    await db.refresh(booking)

    try:
        from app.services.accounting_shadow import AccountingShadow

        await AccountingShadow.shadow_post_booking_paid(db, booking_id=booking.id)
        await db.commit()
        await db.refresh(booking)
    except Exception as acc_err:
        print(f"[owner_students accounting_shadow] non-fatal: {acc_err}")

    return OwnerStudentActionResponse(
        success=True,
        message="Payment marked as paid",
        student=_as_owner_row(student=student, booking=booking, cabin=cabin, room=room),
    )


@router.post("/student-bookings/{booking_id}/release", response_model=OwnerStudentActionResponse)
async def release_student_cabin(
    booking_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_owner(current_user)
    booking, cabin, room, student = await _load_owned_booking(db, owner_id=current_user.id, booking_id=booking_id)
    booking.status = BookingStatus.CANCELLED
    if cabin.current_occupant_id == student.id:
        cabin.status = CabinStatus.AVAILABLE
        cabin.current_occupant_id = None
        cabin.held_by_user_id = None
        cabin.hold_expires_at = None
    await _notify_student(
        db,
        user_id=student.id,
        title="Cabin released",
        message=f"Your cabin {cabin.number} at {room.name} has been released by the owner.",
        kind="warning",
    )
    await db.commit()
    await db.refresh(booking)

    return OwnerStudentActionResponse(
        success=True,
        message="Cabin released",
        student=_as_owner_row(student=student, booking=booking, cabin=cabin, room=room),
    )


@router.post("/students/{student_id}/resend-invite", response_model=OwnerStudentActionResponse)
async def resend_owner_student_invite(
    student_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_owner(current_user)
    result = await db.execute(
        select(User, Booking, Cabin, ReadingRoom)
        .join(Booking, Booking.user_id == User.id)
        .join(Cabin, Booking.cabin_id == Cabin.id)
        .join(ReadingRoom, Cabin.reading_room_id == ReadingRoom.id)
        .where(User.id == student_id, ReadingRoom.owner_id == current_user.id)
        .order_by(desc(Booking.created_at))
    )
    row = result.first()
    if not row:
        raise HTTPException(status_code=404, detail="Student not found")
    student, booking, cabin, room = row
    otp_code, _ = await otp_service.create_otp(
        db=db,
        email=student.email,
        phone=student.phone,
        otp_type="owner_invite",
        expires_in_minutes=60 * 24,
        background_tasks=None,
        send_email=False,
    )
    if is_email_delivery_configured():
        email_sent = await send_otp_email(student.email, student.name, otp_code, "owner_invite")
        message = (
            f"Invite email resent to {student.email}"
            if email_sent
            else f"Invite code regenerated, but email delivery failed for {student.email}. Check SMTP/SendGrid credentials."
        )
    else:
        message = "Invite code regenerated, but email delivery is not configured on this server"
    return OwnerStudentActionResponse(
        success=True,
        message=message,
        student=_as_owner_row(student=student, booking=booking, cabin=cabin, room=room),
    )
