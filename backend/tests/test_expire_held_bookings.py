"""Tests for the cabin-hold expiry job.

Pinned guarantees:
  - Expired holds are released; cabin returns to AVAILABLE.
  - HELD bookings past `expires_at` are marked EXPIRED.
  - Non-expired holds are untouched.
  - PAID / ACTIVE bookings are never accidentally expired.
  - OCCUPIED cabins (real bookings) are never touched even if they happen
    to have a stale hold marker.
"""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

from app.models.booking import Booking, BookingStatus, PaymentStatus
from app.models.reading_room import Cabin, CabinStatus, ReadingRoom
from app.models.user import User, UserRole
from app.services.scheduler import expire_held_bookings_once


async def _make_room_and_cabins(db) -> tuple[User, ReadingRoom, list[Cabin]]:
    owner = User(
        id="ohe", email="ohe@x.com", hashed_password="x", name="Owner",
        role=UserRole.ADMIN,
    )
    db.add(owner)
    await db.flush()
    room = ReadingRoom(
        id="rhe", owner_id=owner.id, name="Acme",
        address="-", state="KA",
    )
    db.add(room)
    await db.flush()
    cabins = [
        Cabin(id=f"c{i}", reading_room_id=room.id,
              number=str(i), floor=1, price=100.0,
              status=CabinStatus.AVAILABLE)
        for i in range(4)
    ]
    db.add_all(cabins)
    await db.flush()
    return owner, room, cabins


@pytest.mark.asyncio
async def test_expired_hold_is_released(seeded_db):
    _, _, cabins = await _make_room_and_cabins(seeded_db)
    user = User(id="uhe1", email="u1@x.com", hashed_password="x", name="U",
                role=UserRole.STUDENT)
    seeded_db.add(user)

    cabin = cabins[0]
    cabin.status = CabinStatus.RESERVED
    cabin.held_by_user_id = user.id
    cabin.hold_expires_at = (datetime.utcnow() - timedelta(minutes=5)).isoformat()
    await seeded_db.commit()

    summary = await expire_held_bookings_once(seeded_db)
    await seeded_db.commit()
    assert summary["released_holds"] == 1

    await seeded_db.refresh(cabin)
    assert cabin.held_by_user_id is None
    assert cabin.hold_expires_at is None
    assert cabin.status == CabinStatus.AVAILABLE


@pytest.mark.asyncio
async def test_non_expired_hold_is_untouched(seeded_db):
    _, _, cabins = await _make_room_and_cabins(seeded_db)
    user = User(id="uhe2", email="u2@x.com", hashed_password="x", name="U",
                role=UserRole.STUDENT)
    seeded_db.add(user)

    cabin = cabins[0]
    cabin.status = CabinStatus.RESERVED
    cabin.held_by_user_id = user.id
    future = (datetime.utcnow() + timedelta(minutes=5)).isoformat()
    cabin.hold_expires_at = future
    await seeded_db.commit()

    summary = await expire_held_bookings_once(seeded_db)
    await seeded_db.commit()
    assert summary["released_holds"] == 0

    await seeded_db.refresh(cabin)
    assert cabin.held_by_user_id == user.id
    assert cabin.hold_expires_at == future
    assert cabin.status == CabinStatus.RESERVED


@pytest.mark.asyncio
async def test_occupied_cabin_never_touched(seeded_db):
    """An OCCUPIED cabin must never flip to AVAILABLE, even if hold fields are stale."""
    _, _, cabins = await _make_room_and_cabins(seeded_db)
    user = User(id="uhe3", email="u3@x.com", hashed_password="x", name="U",
                role=UserRole.STUDENT)
    seeded_db.add(user)

    cabin = cabins[0]
    cabin.status = CabinStatus.OCCUPIED
    cabin.current_occupant_id = user.id
    cabin.held_by_user_id = user.id
    cabin.hold_expires_at = (datetime.utcnow() - timedelta(hours=1)).isoformat()
    await seeded_db.commit()

    await expire_held_bookings_once(seeded_db)
    await seeded_db.commit()

    await seeded_db.refresh(cabin)
    # Hold fields cleared, but status stays OCCUPIED
    assert cabin.status == CabinStatus.OCCUPIED
    assert cabin.current_occupant_id == user.id


@pytest.mark.asyncio
async def test_held_booking_past_expiry_becomes_expired(seeded_db):
    _, _, cabins = await _make_room_and_cabins(seeded_db)
    user = User(id="uhe4", email="u4@x.com", hashed_password="x", name="U",
                role=UserRole.STUDENT)
    seeded_db.add(user)
    booking = Booking(
        id="bhe-held", user_id=user.id, cabin_id=cabins[0].id,
        start_date=datetime.utcnow(), end_date=datetime.utcnow() + timedelta(days=1),
        amount=100.0,
        status=BookingStatus.HELD,
        expires_at=datetime.utcnow() - timedelta(minutes=10),
        payment_status=PaymentStatus.PENDING,
    )
    seeded_db.add(booking)
    await seeded_db.commit()

    summary = await expire_held_bookings_once(seeded_db)
    await seeded_db.commit()
    assert summary["expired_bookings"] >= 1

    await seeded_db.refresh(booking)
    assert booking.status == BookingStatus.EXPIRED


@pytest.mark.asyncio
async def test_active_paid_booking_never_expired(seeded_db):
    """The most important safety property — PAID/ACTIVE bookings are sacred."""
    _, _, cabins = await _make_room_and_cabins(seeded_db)
    user = User(id="uhe5", email="u5@x.com", hashed_password="x", name="U",
                role=UserRole.STUDENT)
    seeded_db.add(user)
    booking = Booking(
        id="bhe-active", user_id=user.id, cabin_id=cabins[0].id,
        start_date=datetime.utcnow(), end_date=datetime.utcnow() + timedelta(days=1),
        amount=100.0,
        status=BookingStatus.ACTIVE,
        # Deliberately set expires_at in the past — must not affect ACTIVE
        expires_at=datetime.utcnow() - timedelta(days=10),
        payment_status=PaymentStatus.PAID,
    )
    seeded_db.add(booking)
    await seeded_db.commit()

    await expire_held_bookings_once(seeded_db)
    await seeded_db.commit()

    await seeded_db.refresh(booking)
    assert booking.status == BookingStatus.ACTIVE
    assert booking.payment_status == PaymentStatus.PAID
