from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from enum import Enum
from typing import Optional
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.booking import Booking, BookingStatus, PaymentStatus
from app.models.booking_renewal import BookingRenewalReminder
from app.models.notification import Notification
from app.models.reading_room import Cabin, ReadingRoom
from app.models.user import User
from app.services.email_service import _send_email
from app.services.owner_operational_access import evaluate_reading_room_operational_access


IST = ZoneInfo("Asia/Kolkata")
RENEWAL_WINDOW_DAYS = 5


class RenewalStatus(str, Enum):
    ACTIVE = "ACTIVE"
    RENEWAL_DUE = "RENEWAL_DUE"
    EXPIRED = "EXPIRED"
    PAYMENT_PENDING = "PAYMENT_PENDING"


@dataclass(frozen=True)
class RenewalInfo:
    joining_date: date
    expiry_date: date
    renewal_window_start: date
    renewal_window_end: date
    renewal_status: RenewalStatus
    renewal_day: Optional[int]

    def as_dict(self) -> dict:
        return {
            "joining_date": self.joining_date.isoformat(),
            "expiry_date": self.expiry_date.isoformat(),
            "renewal_window_start": self.renewal_window_start.isoformat(),
            "renewal_window_end": self.renewal_window_end.isoformat(),
            "renewal_status": self.renewal_status.value,
            "renewal_day": self.renewal_day,
        }


def _as_ist_date(value: datetime | date) -> date:
    if isinstance(value, datetime):
        dt = value
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(IST).date()
    return value


def today_ist() -> date:
    return datetime.now(IST).date()


def renewal_info_for_booking(booking: Booking, *, today: Optional[date] = None) -> RenewalInfo:
    current = today or today_ist()
    joining = _as_ist_date(booking.start_date)
    expiry = _as_ist_date(booking.end_date)
    window_start = expiry
    window_end = expiry + timedelta(days=RENEWAL_WINDOW_DAYS - 1)

    if booking.payment_status == PaymentStatus.PENDING:
        status = RenewalStatus.PAYMENT_PENDING
    elif booking.status == BookingStatus.EXPIRED or current > window_end:
        status = RenewalStatus.EXPIRED
    elif window_start <= current <= window_end:
        status = RenewalStatus.RENEWAL_DUE
    else:
        status = RenewalStatus.ACTIVE

    renewal_day = None
    if window_start <= current <= window_end:
        renewal_day = (current - window_start).days + 1

    return RenewalInfo(
        joining_date=joining,
        expiry_date=expiry,
        renewal_window_start=window_start,
        renewal_window_end=window_end,
        renewal_status=status,
        renewal_day=renewal_day,
    )


def apply_renewal_fields(payload: dict, booking: Booking, *, today: Optional[date] = None) -> dict:
    info = renewal_info_for_booking(booking, today=today)
    payload.update(info.as_dict())
    return payload


def ist_day_bounds(day: date) -> tuple[datetime, datetime]:
    start = datetime.combine(day, time.min, tzinfo=IST).astimezone(timezone.utc).replace(tzinfo=None)
    end = datetime.combine(day, time.max, tzinfo=IST).astimezone(timezone.utc).replace(tzinfo=None)
    return start, end


async def process_renewal_reminders_once(db: AsyncSession, *, today: Optional[date] = None) -> dict:
    """Create renewal reminders and mark stale bookings expired.

    Caller owns commit/rollback.
    """
    current = today or today_ist()
    active_bookings = (await db.execute(
        select(Booking)
        .where(
            Booking.cabin_id.isnot(None),
            Booking.status == BookingStatus.ACTIVE,
        )
    )).scalars().all()

    created = 0
    expired = 0
    emailed = 0

    for booking in active_bookings:
        cabin = await db.get(Cabin, booking.cabin_id)
        room = await db.get(ReadingRoom, cabin.reading_room_id) if cabin else None
        if not room:
            continue
        access = await evaluate_reading_room_operational_access(db, room)
        if not access.can_operate:
            continue

        info = renewal_info_for_booking(booking, today=current)

        # Display priority shows PAYMENT_PENDING before EXPIRED, but the
        # durable booking state must still age out after the grace window.
        if current > info.renewal_window_end or booking.status == BookingStatus.EXPIRED:
            booking.status = BookingStatus.EXPIRED
            expired += 1
            continue

        if info.renewal_status != RenewalStatus.RENEWAL_DUE or info.renewal_day is None:
            continue

        exists = await db.scalar(
            select(BookingRenewalReminder.id).where(
                BookingRenewalReminder.booking_id == booking.id,
                BookingRenewalReminder.renewal_due_date == info.expiry_date,
                BookingRenewalReminder.reminder_day == info.renewal_day,
            )
        )
        if exists:
            continue

        student = await db.get(User, booking.user_id)
        if not student:
            continue

        title = "Cabin renewal due"
        message = (
            f"Your cabin {cabin.number if cabin else ''} at "
            f"{room.name if room else 'your reading room'} is due for renewal. "
            f"Renew by {info.renewal_window_end.strftime('%d %b %Y')} to keep your seat active."
        )
        notification = Notification(
            user_id=student.id,
            title=title,
            message=message,
            type="warning",
        )
        db.add(notification)
        await db.flush()

        channel = "IN_APP"
        if info.renewal_day in {1, RENEWAL_WINDOW_DAYS} and student.email:
            html = (
                f"<p>Hello {student.name},</p>"
                f"<p>Your cabin renewal is due for "
                f"<strong>{room.name if room else 'your reading room'}</strong>.</p>"
                f"<p>Cabin: <strong>{cabin.number if cabin else 'N/A'}</strong><br>"
                f"Renewal window: {info.renewal_window_start.strftime('%d %b %Y')} - "
                f"{info.renewal_window_end.strftime('%d %b %Y')}</p>"
                "<p>Please renew or contact your reading room owner to avoid interruption.</p>"
            )
            if await _send_email(student.email, "Cabin renewal reminder - mySpace", html):
                emailed += 1
                channel = "IN_APP_EMAIL"

        db.add(BookingRenewalReminder(
            booking_id=booking.id,
            user_id=student.id,
            owner_id=room.owner_id if room else None,
            cabin_id=booking.cabin_id,
            renewal_due_date=info.expiry_date,
            reminder_day=info.renewal_day,
            channel=channel,
            notification_id=notification.id,
        ))
        created += 1

    return {"created": created, "expired": expired, "emailed": emailed}
