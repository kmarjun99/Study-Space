"""Security regression tests for the P1 hardening pass.

Each test is independently runnable and self-documenting. They cover:

1. /razorpay/refund authorization — only super-admin OR the venue's owner
   can refund. Regular students (and any other non-owner authenticated
   user) get a 403.
2. dev_only dependency — returns 404 in production unless
   ENABLE_DEV_BYPASS is explicitly set true. Used to gate
   /payments/venue/dev-bypass and /bookings/extend-test.
3. payment_service.verify_payment_signature — the demo bypass is gated
   ONLY by the server-side `demo_mode` flag. A client-controlled
   "order_demo_*" / "order_fallback_*" prefix in a non-demo environment
   must NOT skip HMAC verification.

These do NOT spin up the full FastAPI app — they exercise the helpers
and route functions directly with hand-rolled dependency fakes. That
keeps the runtime fast and avoids brittleness across env config
changes.
"""
from __future__ import annotations

import importlib
import os
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch

import pytest
import pytest_asyncio
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.booking import Booking, BookingStatus, PaymentStatus, SettlementStatus
from app.models.reading_room import Cabin, CabinStatus, ReadingRoom
from app.models.user import User, UserRole
from app.routers.razorpay import RefundRequest, refund_payment
from app.services.payment_service import PaymentService


# ---------- helpers ---------------------------------------------------------


async def _mk_user(db: AsyncSession, *, role: UserRole, suffix: str) -> User:
    user = User(
        email=f"user.{suffix}@example.com",
        hashed_password="x",
        name=f"User {suffix}",
        role=role,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def _mk_reading_room(db: AsyncSession, owner: User) -> ReadingRoom:
    room = ReadingRoom(
        name="Test Reading Room",
        owner_id=owner.id,
        address="x",
        city="Bengaluru",
        state="Karnataka",
        latitude=12.97,
        longitude=77.59,
    )
    db.add(room)
    await db.commit()
    await db.refresh(room)
    return room


async def _mk_cabin(db: AsyncSession, room: ReadingRoom) -> Cabin:
    cabin = Cabin(
        reading_room_id=room.id,
        number="C-1",
        floor=1,
        price=1000.0,
        status=CabinStatus.AVAILABLE,
    )
    db.add(cabin)
    await db.commit()
    await db.refresh(cabin)
    return cabin


async def _mk_paid_booking(
    db: AsyncSession, *, student: User, cabin: Cabin
) -> Booking:
    booking = Booking(
        user_id=student.id,
        cabin_id=cabin.id,
        start_date=datetime(2026, 6, 1),
        end_date=datetime(2026, 7, 1),
        amount=4000.0,
        status=BookingStatus.ACTIVE,
        payment_status=PaymentStatus.PAID,
        transaction_id="pay_for_refund_test",
        settlement_status=SettlementStatus.NOT_SETTLED,
    )
    db.add(booking)
    await db.commit()
    await db.refresh(booking)
    return booking


# ---------- /razorpay/refund authorization ---------------------------------


@pytest_asyncio.fixture
async def refund_fixtures(db: AsyncSession):
    """Set up: a venue owner, a different owner, a student, a super
    admin, a reading room owned by `owner_a`, a cabin in it, and a paid
    booking made by `student` on that cabin."""
    owner_a = await _mk_user(db, role=UserRole.ADMIN, suffix="owner-a")
    owner_b = await _mk_user(db, role=UserRole.ADMIN, suffix="owner-b")
    student = await _mk_user(db, role=UserRole.STUDENT, suffix="student")
    super_admin = await _mk_user(db, role=UserRole.SUPER_ADMIN, suffix="super")
    room = await _mk_reading_room(db, owner_a)
    cabin = await _mk_cabin(db, room)
    booking = await _mk_paid_booking(db, student=student, cabin=cabin)
    return SimpleNamespace(
        owner_a=owner_a,
        owner_b=owner_b,
        student=student,
        super_admin=super_admin,
        room=room,
        cabin=cabin,
        booking=booking,
    )


def _fake_refund_payment(payment_id, amount=None, notes=None):
    """Stand-in for payment_service.refund_payment so tests don't hit
    Razorpay. Returns the canonical shape the route expects."""
    return {"id": "rfnd_test_abc", "amount": int((amount or 4000.0) * 100)}


@pytest.mark.asyncio
async def test_refund_blocked_for_student(refund_fixtures, db):
    """A regular student CANNOT call /razorpay/refund — even on their
    own booking. The refund flow for students goes through the support
    ticket queue, not this admin endpoint."""
    req = RefundRequest(booking_id=refund_fixtures.booking.id, amount=4000.0)
    with patch(
        "app.routers.razorpay.payment_service.refund_payment",
        side_effect=AssertionError("must not be called"),
    ):
        with pytest.raises(HTTPException) as exc_info:
            await refund_payment(
                request=req,
                current_user=refund_fixtures.student,
                db=db,
            )
    assert exc_info.value.status_code == 403, (
        "Student must be rejected with 403, not silently allowed"
    )


@pytest.mark.asyncio
async def test_refund_blocked_for_other_owner(refund_fixtures, db):
    """Owner B cannot refund a booking on Owner A's venue. Cross-owner
    refunds were the original critical hole — any authenticated owner
    could refund any booking before this hardening pass."""
    req = RefundRequest(booking_id=refund_fixtures.booking.id, amount=4000.0)
    with patch(
        "app.routers.razorpay.payment_service.refund_payment",
        side_effect=AssertionError("must not be called"),
    ):
        with pytest.raises(HTTPException) as exc_info:
            await refund_payment(
                request=req,
                current_user=refund_fixtures.owner_b,
                db=db,
            )
    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_refund_allowed_for_venue_owner(refund_fixtures, db):
    """Owner A can refund a booking on a cabin in Owner A's reading
    room. Confirms the authorized path still works after locking the
    others down."""
    req = RefundRequest(booking_id=refund_fixtures.booking.id, amount=4000.0)
    with patch(
        "app.routers.razorpay.payment_service.refund_payment",
        wraps=_fake_refund_payment,
    ):
        result = await refund_payment(
            request=req,
            current_user=refund_fixtures.owner_a,
            db=db,
        )
    assert result["success"] is True


@pytest.mark.asyncio
async def test_refund_allowed_for_super_admin(refund_fixtures, db):
    """Super-admin bypasses the ownership check — they can refund any
    booking. This is the operational lever for handling disputes the
    venue owner won't resolve."""
    req = RefundRequest(booking_id=refund_fixtures.booking.id, amount=4000.0)
    with patch(
        "app.routers.razorpay.payment_service.refund_payment",
        wraps=_fake_refund_payment,
    ):
        result = await refund_payment(
            request=req,
            current_user=refund_fixtures.super_admin,
            db=db,
        )
    assert result["success"] is True


# ---------- dev_only dependency --------------------------------------------


def _reload_deps_with_env(**env_overrides):
    """Reload app.core.config + app.deps after overriding env so the
    `dev_only` gate reads the new ENVIRONMENT / ENABLE_DEV_BYPASS."""
    import app.core.config as config_mod
    import app.deps as deps_mod
    for k in ("ENVIRONMENT", "ENABLE_DEV_BYPASS"):
        os.environ.pop(k, None)
    for k, v in env_overrides.items():
        os.environ[k] = v
    importlib.reload(config_mod)
    importlib.reload(deps_mod)
    return deps_mod


def test_dev_only_blocks_in_production():
    """In production with no override, dev_only raises 404 — callers
    can't even tell the route exists."""
    deps = _reload_deps_with_env(ENVIRONMENT="production")
    with pytest.raises(HTTPException) as exc_info:
        deps.dev_only()
    assert exc_info.value.status_code == 404


def test_dev_only_allows_in_development():
    """In development the gate is a no-op (returns None implicitly)."""
    deps = _reload_deps_with_env(ENVIRONMENT="development")
    # Must NOT raise. The dependency returns None on success.
    assert deps.dev_only() is None


def test_dev_only_allows_with_explicit_override():
    """ENABLE_DEV_BYPASS=true on a non-dev env is the explicit opt-in
    for staging diagnostics. Anything else stays 404."""
    deps = _reload_deps_with_env(
        ENVIRONMENT="production", ENABLE_DEV_BYPASS="true",
    )
    assert deps.dev_only() is None


def test_dev_only_ignores_truthy_non_true_values():
    """Tighten the override — only the literal string "true" (any case)
    opens the gate. "1", "yes", "on" stay closed so the flag has a
    single canonical form."""
    deps = _reload_deps_with_env(
        ENVIRONMENT="production", ENABLE_DEV_BYPASS="1",
    )
    with pytest.raises(HTTPException) as exc_info:
        deps.dev_only()
    assert exc_info.value.status_code == 404


# ---------- payment signature bypass ---------------------------------------


def _real_mode_service() -> PaymentService:
    """Build a PaymentService that thinks it has real Razorpay creds —
    so demo_mode is False. We don't need the Razorpay client itself for
    the verify_payment_signature unit tests; only the demo flag and the
    secret matter."""
    with patch.dict(
        os.environ,
        {
            "RAZORPAY_KEY_ID": "rzp_live_FAKE",
            "RAZORPAY_KEY_SECRET": "secret_FAKE",
            "PAYMENT_DEMO_MODE": "false",
        },
        clear=False,
    ):
        # Patch the Razorpay client constructor so we don't make HTTP
        # calls during the test. We only need verify_payment_signature
        # to think it's NOT in demo mode.
        with patch("razorpay.Client") as MockClient:
            MockClient.return_value = object()
            svc = PaymentService()
    # Sanity — the test setup is meaningless if the service decided to
    # fall back to demo mode anyway.
    assert svc.demo_mode is False
    return svc


def test_signature_bypass_blocked_via_order_demo_prefix():
    """Critical security regression. A client in production cannot
    spoof `order_demo_<anything>` as razorpay_order_id and skip HMAC
    verification. Previous code returned True for any order_id with
    that prefix; this test pins the new behavior."""
    svc = _real_mode_service()
    result = svc.verify_payment_signature(
        razorpay_order_id="order_demo_forged_id",
        razorpay_payment_id="pay_demo_forged_id",
        razorpay_signature="not_a_valid_signature",
    )
    assert result is False, (
        "verify_payment_signature MUST reject forged demo-prefix order "
        "IDs in production. Returning True was a critical revenue-loss "
        "vulnerability."
    )


def test_signature_bypass_blocked_via_order_fallback_prefix():
    """Same as above but for the `order_fallback_*` prefix that the
    old payment_service.create_order returned on Razorpay outages.
    Belt and braces — even though the silent fallback is also gone now,
    the verify path independently rejects forged fallback IDs."""
    svc = _real_mode_service()
    result = svc.verify_payment_signature(
        razorpay_order_id="order_fallback_forged_id",
        razorpay_payment_id="pay_real_id",
        razorpay_signature="not_a_valid_signature",
    )
    assert result is False


def test_signature_accepted_when_server_is_in_demo_mode():
    """Demo mode is now SOLELY a server-side flag (PAYMENT_DEMO_MODE or
    missing credentials). When set, signature verification is skipped
    intentionally — that's expected behavior for local dev / canary
    runs. Test confirms the demo path still works for legitimate dev."""
    with patch.dict(
        os.environ,
        {
            "RAZORPAY_KEY_ID": "",
            "RAZORPAY_KEY_SECRET": "",
            "PAYMENT_DEMO_MODE": "true",
        },
        clear=False,
    ):
        svc = PaymentService()
    assert svc.demo_mode is True
    # In demo mode, signature is auto-accepted regardless of value.
    assert svc.verify_payment_signature(
        razorpay_order_id="order_anything",
        razorpay_payment_id="pay_anything",
        razorpay_signature="whatever",
    ) is True


def test_real_mode_create_order_failure_fails_loudly():
    """The previous silent fallback to `order_fallback_*` is gone. When
    Razorpay client fails in real mode, create_order raises HTTP 502 so
    the user sees a real error instead of a phantom-success demo order
    that would have been auto-verified by the (now closed) signature
    bypass."""
    svc = _real_mode_service()
    # Stub the razorpay client to raise on order.create.
    svc.client = SimpleNamespace(
        order=SimpleNamespace(
            create=lambda data: (_ for _ in ()).throw(
                RuntimeError("simulated Razorpay outage")
            )
        )
    )
    with pytest.raises(HTTPException) as exc_info:
        svc.create_order(amount=4000.0, currency="INR", receipt="r1")
    assert exc_info.value.status_code == 502
    assert "temporarily unavailable" in exc_info.value.detail.lower()
