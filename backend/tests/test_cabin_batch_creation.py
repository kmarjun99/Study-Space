from __future__ import annotations

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select

from app.models.reading_room import Cabin, ReadingRoom
from app.models.user import User, UserRole
from app.routers.reading_rooms import (
    CabinBatchCreate,
    create_cabin,
    create_cabins_batch,
)
from app.schemas.reading_room import CabinCreate


async def _seed_owner_and_room(db):
    owner = User(
        email="cabin-owner@example.com",
        hashed_password="not-used",
        name="Cabin Owner",
        role=UserRole.ADMIN,
    )
    db.add(owner)
    await db.flush()

    room = ReadingRoom(
        owner_id=owner.id,
        name="Batch Test Room",
        address="Test Address",
        price_start=1500,
    )
    db.add(room)
    await db.commit()
    return owner, room


def _batch(start: int, end: int) -> CabinBatchCreate:
    return CabinBatchCreate(
        cabins=[
            CabinCreate(
                number=str(number),
                floor=1,
                amenities=["WiFi", "AC"],
                zone="FRONT",
            )
            for number in range(start, end + 1)
        ]
    )


@pytest.mark.asyncio
async def test_batch_creation_continues_after_first_twenty(db):
    owner, room = await _seed_owner_and_room(db)

    first_batch = await create_cabins_batch(room.id, _batch(1, 20), db, owner)
    second_batch = await create_cabins_batch(room.id, _batch(21, 40), db, owner)

    assert len(first_batch) == 20
    assert len(second_batch) == 20
    assert second_batch[0].number == "21"
    assert second_batch[-1].number == "40"
    assert all(cabin.price == 1500 for cabin in second_batch)

    count = await db.scalar(
        select(func.count(Cabin.id)).where(Cabin.reading_room_id == room.id)
    )
    assert count == 40


@pytest.mark.asyncio
async def test_batch_creation_rejects_existing_numbers_without_partial_insert(db):
    owner, room = await _seed_owner_and_room(db)
    await create_cabins_batch(room.id, _batch(1, 20), db, owner)

    with pytest.raises(HTTPException) as exc_info:
        await create_cabins_batch(room.id, _batch(20, 25), db, owner)

    assert exc_info.value.status_code == 409
    assert "20" in exc_info.value.detail

    numbers = (
        await db.execute(
            select(Cabin.number)
            .where(Cabin.reading_room_id == room.id)
            .order_by(Cabin.number)
        )
    ).scalars().all()
    assert len(numbers) == 20
    assert "21" not in numbers


def test_batch_payload_rejects_duplicate_numbers():
    with pytest.raises(ValueError, match="Duplicate cabin numbers"):
        CabinBatchCreate(
            cabins=[
                CabinCreate(number="21", floor=1),
                CabinCreate(number="21", floor=2),
            ]
        )


@pytest.mark.asyncio
async def test_single_creation_returns_conflict_for_existing_number(db):
    owner, room = await _seed_owner_and_room(db)
    await create_cabin(
        room.id,
        CabinCreate(number="1", floor=1),
        db,
        owner,
    )

    with pytest.raises(HTTPException) as exc_info:
        await create_cabin(
            room.id,
            CabinCreate(number=" 1 ", floor=2),
            db,
            owner,
        )

    assert exc_info.value.status_code == 409
