from __future__ import annotations

import base64

import pytest
from fastapi import HTTPException

from app.models.reading_room import ReadingRoom
from app.models.user import User, UserRole
from app.routers.reading_rooms import get_reading_room_preview_image


async def _seed_room(db, *, image_source: str):
    owner = User(
        email="image-owner@example.com",
        hashed_password="not-used",
        name="Image Owner",
        role=UserRole.ADMIN,
    )
    outsider = User(
        email="image-outsider@example.com",
        hashed_password="not-used",
        name="Image Outsider",
        role=UserRole.ADMIN,
    )
    db.add_all([owner, outsider])
    await db.flush()

    room = ReadingRoom(
        owner_id=owner.id,
        name="Image Test Room",
        address="Test Address",
        images=f'["{image_source}"]',
    )
    db.add(room)
    await db.commit()
    return owner, outsider, room


@pytest.mark.asyncio
async def test_owner_can_fetch_inline_preview_without_summary_blob(db):
    image_bytes = b"small-webp-preview"
    source = "data:image/webp;base64," + base64.b64encode(image_bytes).decode()
    owner, _, room = await _seed_room(db, image_source=source)

    response = await get_reading_room_preview_image(room.id, db, owner)

    assert response.body == image_bytes
    assert response.media_type == "image/webp"
    assert response.headers["cache-control"] == "private, max-age=300"


@pytest.mark.asyncio
async def test_non_owner_cannot_fetch_draft_preview(db):
    source = "data:image/png;base64," + base64.b64encode(b"png-preview").decode()
    _, outsider, room = await _seed_room(db, image_source=source)

    with pytest.raises(HTTPException) as exc_info:
        await get_reading_room_preview_image(room.id, db, outsider)

    assert exc_info.value.status_code == 403
