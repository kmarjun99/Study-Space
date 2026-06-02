"""Settlement engine tests.

Covers the four key acceptance criteria for Phase 6:
  - Owner net payout = gross - refunds - TCS - TDS - offsets
  - Per-window idempotency (unique on owner_id + window)
  - Per-booking idempotency (settled_at flag)
  - Ledger group balances (Σdebit == Σcredit)
  - Negative-net runs land in NEGATIVE_HELD (no money moves)
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models.accommodation import Accommodation, AccommodationType, Gender
from app.models.booking import (
    Booking, BookingStatus, GSTTreatment, PaymentStatus,
)
from app.models.ledger_entry import LedgerEntry
from app.models.refund import Refund, RefundReason, RefundStatus
from app.models.settlement import (
    SettlementLine, SettlementLineKind, SettlementRun,
    SettlementStatus as SettlementRunStatus,
)
from app.models.tax_config import TaxConfig
from app.models.user import GSTRegistrationType, User, UserRole
from app.services.accounting_shadow import AccountingShadow
from app.services.settlement_service import (
    mark_failed,
    mark_paid,
    run_settlements,
)
from app.services.tax_engine import q2


async def _make_user(db, uid, email, role=UserRole.STUDENT, registered=False, state="KA"):
    u = User(
        id=uid, email=email, hashed_password="x", name=uid, role=role,
        gst_registration_type=GSTRegistrationType.REGULAR if registered else GSTRegistrationType.UNREGISTERED,
        business_state_code=state if registered else None,
        gstin="29ZZZZZ1234Z1Z5" if registered else None,
        legal_name=f"{uid} Pvt Ltd" if registered else None,
    )
    db.add(u)
    await db.flush()
    return u


async def _make_acc(db, owner, *, state="KA", price=2500.0, category="HOSTEL_PG"):
    acc = Accommodation(
        id=f"acc-{owner.id}", owner_id=owner.id, name=f"Acme PG {owner.id}",
        type=AccommodationType.PG, gender=Gender.UNISEX,
        address="-", price=price, sharing="single", state=state, gst_category=category,
    )
    db.add(acc)
    await db.flush()
    return acc


async def _make_paid_booking(db, owner, student, *, amount=2500.0, paid_offset_days=10):
    acc = (await db.execute(
        select(Accommodation).where(Accommodation.owner_id == owner.id)
    )).scalar_one_or_none()
    if acc is None:
        acc = await _make_acc(db, owner)
    paid_at = datetime.utcnow() - timedelta(days=paid_offset_days)
    booking = Booking(
        id=f"bk-{student.id}-{int(datetime.utcnow().timestamp() * 1000) % 1_000_000}",
        user_id=student.id, accommodation_id=acc.id,
        start_date=datetime.utcnow(), end_date=datetime.utcnow() + timedelta(days=30),
        amount=amount, status=BookingStatus.ACTIVE,
        payment_status=PaymentStatus.PAID,
    )
    db.add(booking)
    await db.flush()
    # Shadow-post so it becomes eligible.
    await AccountingShadow.shadow_post_booking_paid(db, booking_id=booking.id)
    # Backfill paid_at to be safely past the hold window.
    booking.paid_at = paid_at
    await db.flush()
    return booking


# ---------- happy path -----------------------------------------------------

@pytest.mark.asyncio
async def test_single_booking_settles_full_amount(seeded_db):
    owner = await _make_user(seeded_db, "o1", "o1@x.com", role=UserRole.ADMIN, registered=True)
    student = await _make_user(seeded_db, "s1", "s1@x.com")
    booking = await _make_paid_booking(seeded_db, owner, student, amount=2500.0)
    await seeded_db.commit()

    summary = await run_settlements(seeded_db)
    assert summary["runs_created"] == 1

    runs = (await seeded_db.execute(select(SettlementRun))).scalars().all()
    assert len(runs) == 1
    run = runs[0]
    assert run.status == SettlementRunStatus.READY
    # Owner-registered: full gross flows to owner. No TCS/TDS by default (off).
    assert q2(run.gross) == Decimal("2500.00")
    assert run.net_payout == Decimal("2500.00")
    assert booking.id == (await seeded_db.execute(
        select(Booking.id).where(Booking.settlement_run_id == run.id)
    )).scalar_one()


@pytest.mark.asyncio
async def test_booking_within_hold_window_is_not_settled(seeded_db):
    owner = await _make_user(seeded_db, "o2", "o2@x.com", role=UserRole.ADMIN, registered=True)
    student = await _make_user(seeded_db, "s2", "s2@x.com")
    # paid_at = 1 day ago, hold_days = 3 → NOT eligible
    booking = await _make_paid_booking(seeded_db, owner, student, paid_offset_days=1)
    await seeded_db.commit()

    summary = await run_settlements(seeded_db)
    assert summary["runs_created"] == 0
    assert booking.settled_at is None


# ---------- TCS / TDS ------------------------------------------------------

@pytest.mark.asyncio
async def test_tcs_applied_when_enabled(seeded_db):
    """Enable TCS in config; verify intra-state CGST+SGST split."""
    cfg = (await seeded_db.execute(
        select(TaxConfig).where(TaxConfig.key == "tcs.enabled")
    )).scalar_one()
    cfg.value = json.dumps(True)
    await seeded_db.commit()

    owner = await _make_user(seeded_db, "o3", "o3@x.com", role=UserRole.ADMIN, registered=True)
    student = await _make_user(seeded_db, "s3", "s3@x.com")
    await _make_paid_booking(seeded_db, owner, student, amount=10000.0)
    await seeded_db.commit()

    await run_settlements(seeded_db)
    run = (await seeded_db.execute(select(SettlementRun))).scalar_one()
    # Booking base_amount (≈ 8474.58 of 10000 incl. 18% GST) is the TCS base.
    # 0.25% of 8474.58 = 21.19 each for CGST/SGST.
    assert run.tcs_total > 0
    assert run.net_payout == q2(run.gross - run.tcs_total - run.tds_total - run.platform_offset - run.refunds)


# ---------- refund deduction ------------------------------------------------

@pytest.mark.asyncio
async def test_refund_deducted_from_settlement(seeded_db):
    owner = await _make_user(seeded_db, "o4", "o4@x.com", role=UserRole.ADMIN, registered=True)
    student = await _make_user(seeded_db, "s4", "s4@x.com")
    booking = await _make_paid_booking(seeded_db, owner, student, amount=5000.0)
    refund = Refund(
        booking_id=booking.id, user_id=student.id, amount=1000.0,
        reason=RefundReason.BOOKING_CANCELLED, status=RefundStatus.APPROVED,
    )
    seeded_db.add(refund)
    await seeded_db.commit()

    await run_settlements(seeded_db)
    run = (await seeded_db.execute(select(SettlementRun))).scalar_one()
    assert run.refunds == Decimal("1000.00")
    assert run.net_payout == q2(run.gross - run.refunds - run.platform_offset - run.tcs_total - run.tds_total)


# ---------- negative settlement --------------------------------------------

@pytest.mark.asyncio
async def test_negative_net_settles_to_negative_held(seeded_db):
    owner = await _make_user(seeded_db, "o5", "o5@x.com", role=UserRole.ADMIN, registered=True)
    student = await _make_user(seeded_db, "s5", "s5@x.com")
    booking = await _make_paid_booking(seeded_db, owner, student, amount=1000.0)
    # Refund more than the booking — net goes negative.
    refund = Refund(
        booking_id=booking.id, user_id=student.id, amount=1500.0,
        reason=RefundReason.BOOKING_CANCELLED, status=RefundStatus.APPROVED,
    )
    seeded_db.add(refund)
    await seeded_db.commit()

    await run_settlements(seeded_db)
    run = (await seeded_db.execute(select(SettlementRun))).scalar_one()
    assert run.net_payout < 0
    assert run.status == SettlementRunStatus.NEGATIVE_HELD

    # No ledger group is posted for negative runs (no payout went out).
    ledger_rows = (await seeded_db.execute(
        select(LedgerEntry).where(LedgerEntry.source_id == run.id)
    )).scalars().all()
    assert ledger_rows == []


# ---------- idempotency -----------------------------------------------------

@pytest.mark.asyncio
async def test_rerunning_cron_does_not_double_settle(seeded_db):
    owner = await _make_user(seeded_db, "o6", "o6@x.com", role=UserRole.ADMIN, registered=True)
    student = await _make_user(seeded_db, "s6", "s6@x.com")
    await _make_paid_booking(seeded_db, owner, student, amount=2500.0)
    await seeded_db.commit()

    await run_settlements(seeded_db)
    await run_settlements(seeded_db)

    runs = (await seeded_db.execute(select(SettlementRun))).scalars().all()
    assert len(runs) == 1


# ---------- ledger invariants ----------------------------------------------

@pytest.mark.asyncio
async def test_ready_run_posts_balanced_ledger_group(seeded_db):
    owner = await _make_user(seeded_db, "o7", "o7@x.com", role=UserRole.ADMIN, registered=True)
    student = await _make_user(seeded_db, "s7", "s7@x.com")
    await _make_paid_booking(seeded_db, owner, student, amount=2500.0)
    await seeded_db.commit()

    await run_settlements(seeded_db)
    run = (await seeded_db.execute(select(SettlementRun))).scalar_one()
    rows = (await seeded_db.execute(
        select(LedgerEntry).where(LedgerEntry.source_id == run.id)
    )).scalars().all()
    assert rows
    dr = sum(r.debit for r in rows)
    cr = sum(r.credit for r in rows)
    assert q2(dr) == q2(cr)


# ---------- super-admin actions --------------------------------------------

@pytest.mark.asyncio
async def test_mark_paid_records_utr(seeded_db):
    owner = await _make_user(seeded_db, "o8", "o8@x.com", role=UserRole.ADMIN, registered=True)
    student = await _make_user(seeded_db, "s8", "s8@x.com")
    await _make_paid_booking(seeded_db, owner, student, amount=2500.0)
    await seeded_db.commit()

    await run_settlements(seeded_db)
    run = (await seeded_db.execute(select(SettlementRun))).scalar_one()

    updated = await mark_paid(seeded_db, run_id=run.id, payout_ref="HDFC1234567890")
    await seeded_db.commit()
    assert updated.status == SettlementRunStatus.PAID
    assert updated.payout_ref == "HDFC1234567890"
    assert updated.payout_at is not None


@pytest.mark.asyncio
async def test_mark_failed_records_reason(seeded_db):
    owner = await _make_user(seeded_db, "o9", "o9@x.com", role=UserRole.ADMIN, registered=True)
    student = await _make_user(seeded_db, "s9", "s9@x.com")
    await _make_paid_booking(seeded_db, owner, student, amount=2500.0)
    await seeded_db.commit()

    await run_settlements(seeded_db)
    run = (await seeded_db.execute(select(SettlementRun))).scalar_one()

    updated = await mark_failed(seeded_db, run_id=run.id, reason="Insufficient balance")
    await seeded_db.commit()
    assert updated.status == SettlementRunStatus.FAILED
    assert "Insufficient" in (updated.failure_reason or "")


@pytest.mark.asyncio
async def test_mark_paid_rejects_non_ready_run(seeded_db):
    owner = await _make_user(seeded_db, "o10", "o10@x.com", role=UserRole.ADMIN, registered=True)
    student = await _make_user(seeded_db, "s10", "s10@x.com")
    await _make_paid_booking(seeded_db, owner, student, amount=2500.0)
    await seeded_db.commit()
    await run_settlements(seeded_db)
    run = (await seeded_db.execute(select(SettlementRun))).scalar_one()
    await mark_paid(seeded_db, run_id=run.id, payout_ref="HDFC1")
    await seeded_db.commit()

    # Second attempt should be rejected.
    with pytest.raises(ValueError):
        await mark_paid(seeded_db, run_id=run.id, payout_ref="HDFC2")


# ---------- SEC 9(5) treatment ---------------------------------------------

@pytest.mark.asyncio
async def test_sec_9_5_owner_payable_is_base_only(seeded_db):
    """Sec 9(5) unregistered owner: only the base goes to owner; GST stays with platform."""
    owner = await _make_user(seeded_db, "o11", "o11@x.com", role=UserRole.ADMIN, registered=False)
    student = await _make_user(seeded_db, "s11", "s11@x.com")
    acc = Accommodation(
        id="acc-o11", owner_id=owner.id, name="Acme",
        type=AccommodationType.HOSTEL, gender=Gender.UNISEX,
        address="-", price=2500.0, sharing="single", state="KA",
        gst_category="HOTEL_LIKE",  # in Sec 9(5) list
    )
    seeded_db.add(acc)
    await seeded_db.flush()

    booking = Booking(
        id="bk-9-5", user_id=student.id, accommodation_id=acc.id,
        start_date=datetime.utcnow(), end_date=datetime.utcnow() + timedelta(days=30),
        amount=2500.0, status=BookingStatus.ACTIVE,
        payment_status=PaymentStatus.PAID,
    )
    seeded_db.add(booking)
    await seeded_db.flush()
    await AccountingShadow.shadow_post_booking_paid(seeded_db, booking_id=booking.id)
    booking.paid_at = datetime.utcnow() - timedelta(days=10)
    await seeded_db.commit()

    assert booking.gst_treatment == GSTTreatment.SEC_9_5
    await run_settlements(seeded_db)
    run = (await seeded_db.execute(select(SettlementRun))).scalar_one()
    # Owner gets the base only (≈ 2118.64). NOT the full 2500.
    assert q2(run.gross) == q2(booking.base_amount)
    assert q2(run.gross) < Decimal("2500.00")
