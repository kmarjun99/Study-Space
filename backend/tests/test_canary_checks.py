"""Tests for the per-listing canary check functions.

These prove that each check returns the expected Status given a known DB
state. The CLI script is a thin wrapper around these — once these pass we
trust the wrapper.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models.accommodation import Accommodation, AccommodationType, Gender
from app.models.booking import Booking, BookingStatus, PaymentStatus
from app.models.reading_room import PriceDisplayMode
from app.models.refund import Refund, RefundReason, RefundStatus
from app.models.tax_config import TaxConfig
from app.models.user import GSTRegistrationType, User, UserRole
from app.services.accounting_shadow import AccountingShadow
from app.services.canary_checks import (
    Status,
    check_ledger_integrity,
    check_step_1_listing_safety,
    check_step_10_safety_flag_off,
    check_step_2_payable_matches_expected,
    check_step_3_split_matches,
    check_step_4_test_booking_exists,
    check_step_5_invoice_split_matches,
    check_step_6_ledger_owner_payable,
    check_step_7_settlement_was_created,
    check_step_8_statement_matches_ledger,
    check_step_9_partial_refund_credit_note,
)
from app.services.credit_note_service import issue_for_refund
from app.services.settlement_service import run_settlements


async def _set_flag(db, key, value):
    row = (await db.execute(
        select(TaxConfig).where(TaxConfig.key == key)
    )).scalar_one_or_none()
    if row is None:
        db.add(TaxConfig(key=key, value=json.dumps(value)))
    else:
        row.value = json.dumps(value)
    await db.commit()


async def _arrange(seeded_db, *, registered=True, price_mode=None, price=2500.0):
    owner = User(
        id="ocan", email="ocan@x.com", hashed_password="x", name="Owner",
        role=UserRole.ADMIN, legal_name="Owner Pvt Ltd",
        gst_registration_type=(
            GSTRegistrationType.REGULAR if registered else GSTRegistrationType.UNREGISTERED
        ),
        business_state_code="KA",
        gstin="29ZZZZZ1234Z1Z5" if registered else None,
    )
    student = User(
        id="scan", email="scan@x.com", hashed_password="x", name="Student",
        role=UserRole.STUDENT,
    )
    seeded_db.add_all([owner, student])
    await seeded_db.flush()
    acc = Accommodation(
        id="acan", owner_id=owner.id, name="Acme",
        type=AccommodationType.PG, gender=Gender.UNISEX,
        address="-", price=price, sharing="single", state="KA",
        gst_category="HOSTEL_PG",
        price_display_mode=(PriceDisplayMode(price_mode) if price_mode else None),
    )
    seeded_db.add(acc)
    await seeded_db.commit()
    return owner, student, acc


async def _make_paid_booking(seeded_db, student, acc, *, amount=2500.0, paid_days_ago=10):
    b = Booking(
        id="bcan", user_id=student.id, accommodation_id=acc.id,
        start_date=datetime.utcnow(), end_date=datetime.utcnow() + timedelta(days=30),
        amount=amount, status=BookingStatus.ACTIVE,
        payment_status=PaymentStatus.PAID,
    )
    seeded_db.add(b)
    await seeded_db.flush()
    await AccountingShadow.shadow_post_booking_paid(seeded_db, booking_id=b.id)
    b.paid_at = datetime.utcnow() - timedelta(days=paid_days_ago)
    await seeded_db.commit()
    return b


# ---------- Step 1 ---------------------------------------------------------

@pytest.mark.asyncio
async def test_step_1_passes_when_listing_safe(seeded_db):
    _, _, acc = await _arrange(seeded_db)
    r = await check_step_1_listing_safety(
        seeded_db, listing_type="accommodation", listing_id=acc.id,
    )
    assert r.status == Status.PASS


@pytest.mark.asyncio
async def test_step_1_fails_when_extra_with_flag_on(seeded_db):
    """The whole point of the safety net: GST_EXTRA + flag on = unsafe state."""
    await _set_flag(seeded_db, "feature.per_listing_price_mode", True)
    _, _, acc = await _arrange(seeded_db, price_mode="GST_EXTRA")
    r = await check_step_1_listing_safety(
        seeded_db, listing_type="accommodation", listing_id=acc.id,
    )
    assert r.status == Status.FAIL


@pytest.mark.asyncio
async def test_step_1_fails_when_listing_missing(seeded_db):
    r = await check_step_1_listing_safety(
        seeded_db, listing_type="accommodation", listing_id="nope",
    )
    assert r.status == Status.FAIL


# ---------- Step 2 ---------------------------------------------------------

@pytest.mark.asyncio
async def test_step_2_payable_equals_displayed_with_flag_off(seeded_db):
    _, _, acc = await _arrange(seeded_db, price_mode="GST_EXTRA")
    r = await check_step_2_payable_matches_expected(
        seeded_db, listing_type="accommodation", listing_id=acc.id,
        expected_price=Decimal("2500"),
    )
    assert r.status == Status.PASS


# ---------- Step 3 ---------------------------------------------------------

@pytest.mark.asyncio
async def test_step_3_split_2500_at_18pct(seeded_db):
    _, _, acc = await _arrange(seeded_db)
    r = await check_step_3_split_matches(
        seeded_db, listing_type="accommodation", listing_id=acc.id,
        expected_price=Decimal("2500"),
        expected_base=Decimal("2118.64"),
        expected_gst=Decimal("381.36"),
    )
    assert r.status == Status.PASS


@pytest.mark.asyncio
async def test_step_3_fails_on_wrong_split(seeded_db):
    _, _, acc = await _arrange(seeded_db)
    r = await check_step_3_split_matches(
        seeded_db, listing_type="accommodation", listing_id=acc.id,
        expected_price=Decimal("2500"),
        expected_base=Decimal("2100.00"),  # wrong on purpose
        expected_gst=Decimal("400.00"),
    )
    assert r.status == Status.FAIL


# ---------- Step 4 ---------------------------------------------------------

@pytest.mark.asyncio
async def test_step_4_needs_action_when_no_booking(seeded_db):
    _, _, acc = await _arrange(seeded_db)
    r = await check_step_4_test_booking_exists(
        seeded_db, listing_type="accommodation", listing_id=acc.id,
    )
    assert r.status == Status.NEEDS_ACTION


@pytest.mark.asyncio
async def test_step_4_passes_when_paid_booking_shadowed(seeded_db):
    _, student, acc = await _arrange(seeded_db)
    await _make_paid_booking(seeded_db, student, acc)
    r = await check_step_4_test_booking_exists(
        seeded_db, listing_type="accommodation", listing_id=acc.id,
    )
    assert r.status == Status.PASS
    assert "booking_id" in r.data


# ---------- Step 5 ---------------------------------------------------------

@pytest.mark.asyncio
async def test_step_5_skips_when_no_invoice(seeded_db):
    _, student, acc = await _arrange(seeded_db)
    b = await _make_paid_booking(seeded_db, student, acc)
    r = await check_step_5_invoice_split_matches(seeded_db, booking_id=b.id)
    assert r.status == Status.SKIP


# ---------- Step 6 ---------------------------------------------------------

@pytest.mark.asyncio
async def test_step_6_ledger_owner_payable_full_gross(seeded_db):
    """OWNER_REGISTERED: owner-payable in the ledger == booking gross."""
    _, student, acc = await _arrange(seeded_db, registered=True)
    b = await _make_paid_booking(seeded_db, student, acc, amount=2500.0)
    r = await check_step_6_ledger_owner_payable(seeded_db, booking_id=b.id)
    assert r.status == Status.PASS
    assert r.data["owner_payable"] == 2500.0


# ---------- Step 7 ---------------------------------------------------------

@pytest.mark.asyncio
async def test_step_7_needs_action_before_settlement(seeded_db):
    _, student, acc = await _arrange(seeded_db)
    b = await _make_paid_booking(seeded_db, student, acc)
    r = await check_step_7_settlement_was_created(seeded_db, booking_id=b.id)
    assert r.status == Status.NEEDS_ACTION


@pytest.mark.asyncio
async def test_step_7_passes_after_settlement(seeded_db):
    _, student, acc = await _arrange(seeded_db)
    await _make_paid_booking(seeded_db, student, acc)
    await run_settlements(seeded_db)
    # Re-fetch booking with fresh state
    b = (await seeded_db.execute(
        select(Booking).where(Booking.id == "bcan")
    )).scalar_one()
    r = await check_step_7_settlement_was_created(seeded_db, booking_id=b.id)
    assert r.status == Status.PASS
    assert "run_id" in r.data


# ---------- Step 8 ---------------------------------------------------------

@pytest.mark.asyncio
async def test_step_8_matches_after_settlement(seeded_db):
    _, student, acc = await _arrange(seeded_db)
    await _make_paid_booking(seeded_db, student, acc)
    await run_settlements(seeded_db)
    b = (await seeded_db.execute(
        select(Booking).where(Booking.id == "bcan")
    )).scalar_one()
    r = await check_step_8_statement_matches_ledger(seeded_db, run_id=b.settlement_run_id)
    assert r.status == Status.PASS


# ---------- Step 9 ---------------------------------------------------------

@pytest.mark.asyncio
async def test_step_9_needs_action_when_no_refund(seeded_db):
    _, student, acc = await _arrange(seeded_db)
    b = await _make_paid_booking(seeded_db, student, acc)
    r = await check_step_9_partial_refund_credit_note(seeded_db, booking_id=b.id)
    assert r.status == Status.NEEDS_ACTION


@pytest.mark.asyncio
async def test_step_9_passes_with_proportional_credit_note(seeded_db):
    """Refund of 20% of booking → credit note reverses ~20% of GST."""
    await _set_flag(seeded_db, "feature.credit_notes", True)
    _, student, acc = await _arrange(seeded_db, registered=True)
    b = await _make_paid_booking(seeded_db, student, acc, amount=2500.0)
    refund = Refund(
        booking_id=b.id, user_id=student.id, amount=500.0,
        reason=RefundReason.SERVICE_ISSUE, status=RefundStatus.APPROVED,
    )
    seeded_db.add(refund)
    await seeded_db.commit()
    cn = await issue_for_refund(seeded_db, refund_id=refund.id)
    await seeded_db.commit()
    assert cn is not None

    r = await check_step_9_partial_refund_credit_note(seeded_db, booking_id=b.id)
    assert r.status == Status.PASS
    # 20% of 381.36 = 76.27 ≈ what should be reversed
    assert 70 <= r.data["gst_reversed"] <= 82


# ---------- Step 10 -------------------------------------------------------

@pytest.mark.asyncio
async def test_step_10_passes_with_flag_off(seeded_db):
    r = await check_step_10_safety_flag_off(seeded_db)
    assert r.status == Status.PASS


@pytest.mark.asyncio
async def test_step_10_fails_with_flag_on(seeded_db):
    await _set_flag(seeded_db, "feature.per_listing_price_mode", True)
    r = await check_step_10_safety_flag_off(seeded_db)
    assert r.status == Status.FAIL


# ---------- Bonus: integrity check ----------------------------------------

@pytest.mark.asyncio
async def test_ledger_integrity_passes_on_balanced_db(seeded_db):
    _, student, acc = await _arrange(seeded_db)
    await _make_paid_booking(seeded_db, student, acc)
    r = await check_ledger_integrity(seeded_db)
    assert r.status == Status.PASS
