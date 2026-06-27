from http.cookies import SimpleCookie
from types import SimpleNamespace
from datetime import timedelta

import pytest
from fastapi import Response
from sqlalchemy import select

from app.core.config import settings
from app.core.security import get_password_hash, create_access_token
from app.deps import get_current_user
from app.models.auth_session import RefreshSession
from app.models.user import User, UserRole
from app.routers.auth import (
    REFRESH_COOKIE_NAME,
    _issue_session,
    refresh_session,
    logout,
)


def _cookie_value(response: Response, name: str) -> str:
    raw = response.headers.get("set-cookie")
    cookie = SimpleCookie()
    cookie.load(raw)
    return cookie[name].value


@pytest.mark.asyncio
async def test_issue_refresh_and_logout_revokes_backend_session(db):
    user = User(
        email="owner@example.com",
        hashed_password=get_password_hash("Secret123!"),
        name="Owner",
        role=UserRole.ADMIN,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    response = Response()
    request = SimpleNamespace(headers={"user-agent": "pytest"})

    token_payload = await _issue_session(
        user=user,
        db=db,
        response=response,
        request=request,
        has_active_waitlist=False,
    )

    assert token_payload["access_token"]
    assert token_payload["access_token_expires_at"]
    assert token_payload["refresh_token_expires_at"]
    assert "httponly" in response.headers["set-cookie"].lower()

    refresh_cookie = _cookie_value(response, REFRESH_COOKIE_NAME)
    session = (await db.execute(select(RefreshSession))).scalars().one()
    assert session.user_id == user.id
    assert session.revoked_at is None

    refresh_response = Response()
    refreshed = await refresh_session(
        response=refresh_response,
        request=request,
        refresh_token=refresh_cookie,
        db=db,
    )

    assert refreshed["access_token"]
    assert refreshed["email"] == user.email
    rotated_cookie = _cookie_value(refresh_response, REFRESH_COOKIE_NAME)
    assert rotated_cookie != refresh_cookie

    await db.refresh(session)
    assert session.last_used_at is not None

    logout_response = Response()
    await logout(response=logout_response, refresh_token=rotated_cookie, db=db)
    await db.refresh(session)
    assert session.revoked_at is not None
    assert f"{REFRESH_COOKIE_NAME}=" in logout_response.headers["set-cookie"]


@pytest.mark.asyncio
async def test_expired_access_token_cannot_access_protected_dependency(db):
    user = User(
        email="student@example.com",
        hashed_password=get_password_hash("Secret123!"),
        name="Student",
        role=UserRole.STUDENT,
    )
    db.add(user)
    await db.commit()

    expired = create_access_token(subject=user.email, expires_delta=timedelta(seconds=-1))

    with pytest.raises(Exception) as exc:
        await get_current_user(expired, db)

    assert getattr(exc.value, "status_code", None) == 401
    assert "Token rejected" in getattr(exc.value, "detail", "")
