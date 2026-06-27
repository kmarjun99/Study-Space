from __future__ import annotations

from datetime import date, datetime, timedelta
from types import SimpleNamespace

import pytest
from fastapi import BackgroundTasks, HTTPException, Response
from sqlalchemy import select

from app.core.security import get_password_hash
from app.models.booking import Booking, BookingStatus, PaymentStatus
from app.models.booking_renewal import BookingRenewalReminder
from app.models.invoice import Invoice, InvoiceDocType
from app.models.notification import Notification
from app.models.payment_transaction import PaymentTransaction
from app.models.reading_room import Cabin, CabinStatus, ListingStatus, OperationalAccessOverride, ReadingRoom
from app.models.subscription_plan import SubscriptionPlan
from app.models.user import User, UserRole, VerificationStatus
from app.routers.auth import complete_owner_invite, login
from app.routers.bookings import get_my_bookings
from app.routers.otp import resend_otp, send_otp
from app.routers.owner_students import create_owner_student_assignment, mark_student_booking_paid, renew_student_booking
from app.schemas.otp import CompleteOwnerInviteRequest, OTPRequest
from app.schemas.owner_students import OwnerBookingRenewRequest, OwnerMarkPaidRequest, OwnerStudentAssignmentCreate
from app.services import otp_service
from app.services.renewal_service import RenewalStatus, process_renewal_reminders_once, renewal_info_for_booking


async def _seed_owner_room_cabin(db, *, cabin_status=CabinStatus.AVAILABLE):
    owner = User(
        email="owner-renewal@example.com",
        hashed_password=get_password_hash("Secret123!"),
        name="Owner",
        role=UserRole.ADMIN,
        verification_status=VerificationStatus.VERIFIED,
    )
    db.add(owner)
    await db.flush()
    room = ReadingRoom(
        owner_id=owner.id,
        name="Renewal Room",
        address="Main Road",
        contact_phone="9999999999",
        state="Kerala",
        price_start=1500,
        status=ListingStatus.LIVE,
        is_verified=True,
        operational_access_override=OperationalAccessOverride.FREE_GRANTED.value,
        operational_access_until=datetime(2030, 1, 1),
        allowed_booking_durations='["1_MONTH","3_MONTHS","6_MONTHS"]',
        duration_prices='{"1_MONTH":1500,"3_MONTHS":4200,"6_MONTHS":8000}',
    )
    db.add(room)
    await db.flush()
    cabin = Cabin(
        reading_room_id=room.id,
        number="10",
        floor=1,
        price=1500,
        status=cabin_status,
    )
    db.add(cabin)
    await db.commit()
    return owner, room, cabin


@pytest.mark.asyncio
async def test_renewal_status_window_priority():
    booking = Booking(
        user_id="student",
        cabin_id="cabin",
        start_date=datetime(2026, 1, 1),
        end_date=datetime(2026, 2, 1),
        amount=1500,
        status=BookingStatus.ACTIVE,
        payment_status=PaymentStatus.PAID,
    )

    assert renewal_info_for_booking(booking, today=date(2026, 1, 31)).renewal_status == RenewalStatus.ACTIVE
    due = renewal_info_for_booking(booking, today=date(2026, 2, 1))
    assert due.renewal_status == RenewalStatus.RENEWAL_DUE
    assert due.renewal_day == 1
    assert renewal_info_for_booking(booking, today=date(2026, 2, 5)).renewal_day == 5
    assert renewal_info_for_booking(booking, today=date(2026, 2, 6)).renewal_status == RenewalStatus.EXPIRED

    booking.payment_status = PaymentStatus.PENDING
    assert renewal_info_for_booking(booking, today=date(2026, 2, 6)).renewal_status == RenewalStatus.PAYMENT_PENDING


@pytest.mark.asyncio
async def test_owner_can_create_offline_student_assignment_and_payment(seeded_db):
    owner, room, cabin = await _seed_owner_room_cabin(seeded_db)

    response = await create_owner_student_assignment(
        OwnerStudentAssignmentCreate(
            name="Offline Student",
            email="offline.student@example.com",
            phone="9999999999",
            reading_room_id=room.id,
            cabin_id=cabin.id,
            duration_type="1_MONTH",
            joining_date=date(2026, 6, 1),
            payment_status=PaymentStatus.PAID,
            payment_reference="cash-001",
        ),
        background_tasks=BackgroundTasks(),
        db=seeded_db,
        current_user=owner,
    )

    assert response.success is True
    assert response.student.email == "offline.student@example.com"
    assert response.student.renewal_status == RenewalStatus.ACTIVE

    student = await seeded_db.scalar(select(User).where(User.email == "offline.student@example.com"))
    assert student is not None
    assert student.role == UserRole.STUDENT
    assert student.must_set_password is True
    assert student.verification_status == VerificationStatus.PENDING

    await seeded_db.refresh(cabin)
    assert cabin.status == CabinStatus.OCCUPIED
    assert cabin.current_occupant_id == student.id

    booking = await seeded_db.scalar(select(Booking).where(Booking.user_id == student.id))
    assert booking.payment_status == PaymentStatus.PAID
    assert booking.booking_source == "OWNER_OFFLINE"

    txn = await seeded_db.scalar(select(PaymentTransaction).where(PaymentTransaction.booking_id == booking.id))
    assert txn is not None
    assert txn.gateway.value == "MANUAL"

    invoice = await seeded_db.scalar(select(Invoice).where(Invoice.booking_id == booking.id))
    assert invoice is not None
    assert invoice.invoice_number.startswith("SS/RCT/")
    assert invoice.doc_type == InvoiceDocType.NON_GST_RECEIPT
    assert invoice.user_id == student.id
    assert invoice.owner_id == owner.id
    assert invoice.cabin_id == cabin.id
    assert invoice.payment_id == txn.id
    assert invoice.payment_status == PaymentStatus.PAID.value
    assert invoice.payment_reference == "cash-001"
    assert invoice.joining_date == booking.start_date
    assert invoice.renewal_period_end == booking.end_date


@pytest.mark.asyncio
async def test_draft_room_cannot_create_offline_student_and_has_no_side_effects(seeded_db):
    owner, room, cabin = await _seed_owner_room_cabin(seeded_db)
    room.status = ListingStatus.DRAFT
    room.is_verified = False
    room.operational_access_override = OperationalAccessOverride.NONE.value
    room.operational_access_until = None
    await seeded_db.commit()

    with pytest.raises(HTTPException) as exc:
        await create_owner_student_assignment(
            OwnerStudentAssignmentCreate(
                name="Blocked Student",
                email="blocked.student@example.com",
                phone="9999999998",
                reading_room_id=room.id,
                cabin_id=cabin.id,
                duration_type="1_MONTH",
                joining_date=date(2026, 6, 1),
                payment_status=PaymentStatus.PAID,
                payment_reference="cash-blocked",
            ),
            background_tasks=BackgroundTasks(),
            db=seeded_db,
            current_user=owner,
        )

    assert exc.value.status_code == 403
    assert exc.value.detail["code"] == "VENUE_NOT_LIVE"
    assert await seeded_db.scalar(select(User).where(User.email == "blocked.student@example.com")) is None
    assert await seeded_db.scalar(select(Booking).where(Booking.transaction_id == "cash-blocked")) is None
    assert await seeded_db.scalar(select(Invoice).where(Invoice.payment_reference == "cash-blocked")) is None
    await seeded_db.refresh(cabin)
    assert cabin.status == CabinStatus.AVAILABLE
    assert cabin.current_occupant_id is None


@pytest.mark.asyncio
async def test_live_verified_room_with_active_paid_plan_can_create_offline_student(seeded_db):
    owner, room, cabin = await _seed_owner_room_cabin(seeded_db)
    plan = SubscriptionPlan(
        name="Monthly",
        description="Test plan",
        price=999,
        duration_days=30,
        is_active=True,
        created_by="super-admin",
    )
    seeded_db.add(plan)
    await seeded_db.flush()
    room.operational_access_override = OperationalAccessOverride.NONE.value
    room.operational_access_until = None
    room.subscription_plan_id = plan.id
    room.payment_date = datetime.utcnow()
    await seeded_db.commit()

    response = await create_owner_student_assignment(
        OwnerStudentAssignmentCreate(
            name="Paid Plan Student",
            email="paid.plan.student@example.com",
            phone="9999999997",
            reading_room_id=room.id,
            cabin_id=cabin.id,
            duration_type="1_MONTH",
            joining_date=date(2026, 6, 1),
            payment_status=PaymentStatus.PENDING,
            send_invite=False,
        ),
        background_tasks=BackgroundTasks(),
        db=seeded_db,
        current_user=owner,
    )

    assert response.success is True
    assert response.student.email == "paid.plan.student@example.com"
    assert response.student.payment_status == PaymentStatus.PENDING


@pytest.mark.asyncio
async def test_admin_blocked_room_cannot_resend_or_renew_but_release_is_allowed(seeded_db):
    from app.routers.owner_students import release_student_cabin, resend_owner_student_invite

    owner, room, cabin = await _seed_owner_room_cabin(seeded_db)
    student = User(
        email="assigned.student@example.com",
        hashed_password=get_password_hash("Secret123!"),
        name="Assigned Student",
        role=UserRole.STUDENT,
        verification_status=VerificationStatus.PENDING,
        must_set_password=True,
    )
    seeded_db.add(student)
    await seeded_db.flush()
    booking = Booking(
        user_id=student.id,
        cabin_id=cabin.id,
        start_date=datetime(2026, 6, 1),
        end_date=datetime(2026, 7, 1),
        amount=1500,
        status=BookingStatus.ACTIVE,
        payment_status=PaymentStatus.PENDING,
        duration_type="1_MONTH",
    )
    cabin.status = CabinStatus.OCCUPIED
    cabin.current_occupant_id = student.id
    seeded_db.add(booking)
    await seeded_db.commit()

    room.operational_access_override = OperationalAccessOverride.BLOCKED.value
    await seeded_db.commit()

    with pytest.raises(HTTPException) as renew_exc:
        await renew_student_booking(
            booking.id,
            OwnerBookingRenewRequest(duration_type="1_MONTH", payment_status=PaymentStatus.PENDING),
            db=seeded_db,
            current_user=owner,
        )
    assert renew_exc.value.status_code == 403
    assert renew_exc.value.detail["code"] == "ADMIN_BLOCKED"

    with pytest.raises(HTTPException) as invite_exc:
        await resend_owner_student_invite(
            student.id,
            background_tasks=BackgroundTasks(),
            db=seeded_db,
            current_user=owner,
        )
    assert invite_exc.value.status_code == 403

    released = await release_student_cabin(booking.id, db=seeded_db, current_user=owner)
    assert released.success is True
    await seeded_db.refresh(cabin)
    assert cabin.status == CabinStatus.AVAILABLE


@pytest.mark.asyncio
async def test_student_booking_list_is_enriched_with_venue_details(seeded_db):
    owner, room, cabin = await _seed_owner_room_cabin(seeded_db)
    student = User(
        email="booking.student@example.com",
        hashed_password=get_password_hash("Secret123!"),
        name="Booking Student",
        role=UserRole.STUDENT,
        verification_status=VerificationStatus.VERIFIED,
    )
    seeded_db.add(student)
    await seeded_db.flush()
    booking = Booking(
        user_id=student.id,
        cabin_id=cabin.id,
        start_date=datetime(2026, 6, 1),
        end_date=datetime(2026, 7, 1),
        amount=1500,
        status=BookingStatus.ACTIVE,
        payment_status=PaymentStatus.PAID,
        duration_type="1_MONTH",
    )
    seeded_db.add(booking)
    await seeded_db.commit()

    rows = await get_my_bookings(db=seeded_db, current_user=student)
    payload = rows[0]
    assert payload["venue_name"] == room.name
    assert payload["venue_address"] == room.address
    assert payload["venue_contact_phone"] == room.contact_phone
    assert payload["owner_id"] == owner.id
    assert payload["cabin_number"] == cabin.number


@pytest.mark.asyncio
async def test_owner_rejects_occupied_cabin_for_different_student(seeded_db):
    owner, room, cabin = await _seed_owner_room_cabin(seeded_db, cabin_status=CabinStatus.OCCUPIED)
    existing = User(email="existing@example.com", hashed_password="x", name="Existing", role=UserRole.STUDENT)
    seeded_db.add(existing)
    await seeded_db.flush()
    cabin.current_occupant_id = existing.id
    await seeded_db.commit()

    with pytest.raises(Exception) as exc:
        await create_owner_student_assignment(
            OwnerStudentAssignmentCreate(
                name="Other Student",
                email="other.student@example.com",
                reading_room_id=room.id,
                cabin_id=cabin.id,
                duration_type="1_MONTH",
                joining_date=date(2026, 6, 1),
            ),
            background_tasks=BackgroundTasks(),
            db=seeded_db,
            current_user=owner,
        )

    assert getattr(exc.value, "status_code", None) == 409


@pytest.mark.asyncio
async def test_owner_invite_blocks_login_until_completed(seeded_db):
    user = User(
        email="invitee@example.com",
        hashed_password=get_password_hash("TempSecret123!"),
        name="Invitee",
        role=UserRole.STUDENT,
        verification_status=VerificationStatus.PENDING,
        must_set_password=True,
    )
    seeded_db.add(user)
    await seeded_db.commit()

    form = SimpleNamespace(username=user.email, password="TempSecret123!")
    with pytest.raises(Exception) as exc:
        await login(form, Response(), SimpleNamespace(headers={}), seeded_db)
    assert getattr(exc.value, "status_code", None) == 403

    otp_code, _ = await otp_service.create_otp(
        db=seeded_db,
        email=user.email,
        phone=None,
        otp_type="owner_invite",
        background_tasks=BackgroundTasks(),
    )

    token = await complete_owner_invite(
        CompleteOwnerInviteRequest(email=user.email, otp_code=otp_code, new_password="NewSecret123!"),
        Response(),
        SimpleNamespace(headers={}),
        seeded_db,
    )
    assert token["access_token"]
    await seeded_db.refresh(user)
    assert user.must_set_password is False
    assert user.verification_status == VerificationStatus.VERIFIED
    assert user.email_verified_at is not None


@pytest.mark.asyncio
async def test_public_otp_routes_do_not_mint_owner_invites(seeded_db):
    request = OTPRequest(email="invite-public-block@example.com", otp_type="owner_invite")

    with pytest.raises(Exception) as send_exc:
        await send_otp(request, BackgroundTasks(), seeded_db)
    assert getattr(send_exc.value, "status_code", None) == 403

    with pytest.raises(Exception) as resend_exc:
        await resend_otp(request, BackgroundTasks(), seeded_db)
    assert getattr(resend_exc.value, "status_code", None) == 403


@pytest.mark.asyncio
async def test_renewal_reminder_job_is_idempotent_and_expires_after_window(seeded_db):
    owner, room, cabin = await _seed_owner_room_cabin(seeded_db, cabin_status=CabinStatus.OCCUPIED)
    student = User(email="due@example.com", hashed_password="x", name="Due", role=UserRole.STUDENT)
    seeded_db.add(student)
    await seeded_db.flush()
    cabin.current_occupant_id = student.id
    booking = Booking(
        user_id=student.id,
        cabin_id=cabin.id,
        start_date=datetime(2026, 1, 1),
        end_date=datetime(2026, 2, 1),
        amount=1500,
        status=BookingStatus.ACTIVE,
        payment_status=PaymentStatus.PAID,
    )
    seeded_db.add(booking)
    await seeded_db.commit()

    first = await process_renewal_reminders_once(seeded_db, today=date(2026, 2, 2))
    await seeded_db.commit()
    second = await process_renewal_reminders_once(seeded_db, today=date(2026, 2, 2))
    await seeded_db.commit()

    assert first["created"] == 1
    assert second["created"] == 0
    assert await seeded_db.scalar(select(BookingRenewalReminder.id).where(BookingRenewalReminder.booking_id == booking.id))
    assert await seeded_db.scalar(select(Notification.id).where(Notification.user_id == student.id))

    expired = await process_renewal_reminders_once(seeded_db, today=date(2026, 2, 6))
    await seeded_db.commit()
    await seeded_db.refresh(booking)
    await seeded_db.refresh(cabin)
    assert expired["expired"] == 1
    assert booking.status == BookingStatus.EXPIRED
    assert cabin.status == CabinStatus.OCCUPIED
    assert cabin.current_occupant_id == student.id


@pytest.mark.asyncio
async def test_renewal_job_expires_pending_payment_after_window(seeded_db):
    _, _, cabin = await _seed_owner_room_cabin(seeded_db, cabin_status=CabinStatus.OCCUPIED)
    student = User(email="pending-due@example.com", hashed_password="x", name="Pending", role=UserRole.STUDENT)
    seeded_db.add(student)
    await seeded_db.flush()
    cabin.current_occupant_id = student.id
    booking = Booking(
        user_id=student.id,
        cabin_id=cabin.id,
        start_date=datetime(2026, 1, 1),
        end_date=datetime(2026, 2, 1),
        amount=1500,
        status=BookingStatus.ACTIVE,
        payment_status=PaymentStatus.PENDING,
    )
    seeded_db.add(booking)
    await seeded_db.commit()

    summary = await process_renewal_reminders_once(seeded_db, today=date(2026, 2, 6))
    await seeded_db.commit()
    await seeded_db.refresh(booking)
    await seeded_db.refresh(cabin)

    assert summary["expired"] == 1
    assert booking.status == BookingStatus.EXPIRED
    assert cabin.status == CabinStatus.OCCUPIED
    assert cabin.current_occupant_id == student.id


@pytest.mark.asyncio
async def test_owner_renew_and_mark_paid_update_booking(seeded_db):
    owner, room, cabin = await _seed_owner_room_cabin(seeded_db, cabin_status=CabinStatus.OCCUPIED)
    student = User(email="renew-me@example.com", hashed_password="x", name="Renew Me", role=UserRole.STUDENT)
    seeded_db.add(student)
    await seeded_db.flush()
    cabin.current_occupant_id = student.id
    booking = Booking(
        user_id=student.id,
        cabin_id=cabin.id,
        start_date=datetime.utcnow() - timedelta(days=40),
        end_date=datetime.utcnow() - timedelta(days=5),
        amount=1500,
        status=BookingStatus.EXPIRED,
        payment_status=PaymentStatus.PENDING,
        duration_type="1_MONTH",
    )
    seeded_db.add(booking)
    await seeded_db.commit()

    renewed = await renew_student_booking(
        booking.id,
        OwnerBookingRenewRequest(duration_type="1_MONTH", payment_status=PaymentStatus.PENDING),
        db=seeded_db,
        current_user=owner,
    )
    assert renewed.student.booking_status == BookingStatus.ACTIVE
    assert renewed.student.payment_status == PaymentStatus.PENDING

    paid = await mark_student_booking_paid(
        booking.id,
        OwnerMarkPaidRequest(payment_reference="upi-123"),
        db=seeded_db,
        current_user=owner,
    )
    assert paid.student.payment_status == PaymentStatus.PAID
    txn = await seeded_db.scalar(select(PaymentTransaction).where(PaymentTransaction.booking_id == booking.id))
    assert txn is not None
