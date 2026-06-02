"""Recovery service tests.

Covers the refund-after-settlement RECOVERY flow end-to-end:
  - Pre-settlement refund creates NO recovery charge (credit note alone is enough)
  - Post-settlement refund creates exactly one RECOVERY OwnerCharge
  - Repeated calls / re-runs are idempotent on refund_id
  - REQUESTED / REJECTED refunds are skipped
  - get_outstanding_recoveries_for_owner only surfaces unpaid recoveries
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models.accommodation import Accommodation, AccommodationType, Gender
from app.models.booking import Booking, BookingStatus, GSTTreatment, PaymentStatus
from app.models.owner_charge import OwnerCharge, OwnerChargeStatus, OwnerChargeType
from app.models.refund import Refund, RefundReason, RefundStatus
from app.models.settlement import SettlementRun, SettlementStatus
from app.models.tax_config import TaxConfig
from app.models.user import GSTRegistrationType, User, UserRole
from app.services.accounting_shadow import AccountingShadow
from app.services.recovery_service import (
    create_recovery_charge_for_refund,
    get_outstanding_recoveries_for_owner,
    is_recovery_eligible,
    scan_and_create_recovery_charges,
)
from app.services.settlement_service import run_settlements
from app.services.tax_engine import q2, to_decimal


async def _set(db, key, value):
    row = (await db.execute(
        select(TaxConfig).where(TaxConfig.key == key)
    )).scalar_one_or_none()
    if row is None:
        db.add(TaxConfig(key=key, value=json.dumps(value)))
    else:
        row.value = json.dumps(value)
    await db.commit()


async def _arrange(seeded_db, *, refund_amount: float, post_settlement: bool):
    """Create owner + student + booking + refund. If post_settlement=True,
    settle the booking first so the refund creates a recovery charge."""
    owner = User(
        id="orec", email="orec@x.com", hashed_password="x", name="Owner",
        role=UserRole.ADMIN, legal_name="Owner Pvt Ltd",
        gst_registration_type=GSTRegistrationType.REGULAR,
        gstin="29ZZZZZ1234Z1Z5", business_state_code="KA",
    )
    student = User(
        id="srec", email="srec@x.com", hashed_password="x", name="Student",
        role=UserRole.STUDENT,
    )
    seeded_db.add_all([owner, student])
    await seeded_db.flush()
    acc = Accommodation(
        id="arec", owner_id=owner.id, name="Acme",
        type=AccommodationType.PG, gender=Gender.UNISEX,
        address="-", price=2500.0, sharing="single", state="KA",
        gst_category="HOSTEL_PG",
    )
    seeded_db.add(acc)
    await seeded_db.flush()
    booking = Booking(
        id="brec", user_id=student.id, accommodation_id=acc.id,
        start_date=datetime.utcnow(), end_date=datetime.utcnow() + timedelta(days=30),
        amount=2500.0, status=BookingStatus.ACTIVE,
        payment_status=PaymentStatus.PAID,
    )
    seeded_db.add(booking)
    await seeded_db.flush()
    await AccountingShadow.shadow_post_booking_paid(seeded_db, booking_id=booking.id)
    booking.paid_at = datetime.utcnow() - timedelta(days=10)
    await seeded_db.commit()

    if post_settlement:
        await run_settlements(seeded_db)
        # Booking should now have settled_at set
        await seeded_db.refresh(booking)
        assert booking.settled_at is not None

    refund = Refund(
        booking_id=booking.id, user_id=student.id, amount=refund_amount,
        reason=RefundReason.SERVICE_ISSUE, status=RefundStatus.APPROVED,
    )
    seeded_db.add(refund)
    await seeded_db.commit()
    return owner, student, booking, refund


# ---------- eligibility -----------------------------------------------------

@pytest.mark.asyncio
async def test_pre_settlement_booking_not_recovery_eligible(seeded_db):
    _, _, booking, _ = await _arrange(seeded_db, refund_amount=500.0,
                                      post_settlement=False)
    assert is_recovery_eligible(booking) is False


@pytest.mark.asyncio
async def test_post_settlement_booking_is_recovery_eligible(seeded_db):
    _, _, booking, _ = await _arrange(seeded_db, refund_amount=500.0,
                                      post_settlement=True)
    assert is_recovery_eligible(booking) is True


# ---------- create_recovery_charge_for_refund -----------------------------

@pytest.mark.asyncio
async def test_pre_settlement_refund_creates_no_recovery_charge(seeded_db):
    """If the credit note ran before settlement, refund reverses cleanly."""
    _, _, _, refund = await _arrange(seeded_db, refund_amount=500.0,
                                     post_settlement=False)
    charge = await create_recovery_charge_for_refund(seeded_db, refund_id=refund.id)
    assert charge is None

    rows = (await seeded_db.execute(
        select(OwnerCharge).where(
            OwnerCharge.charge_type == OwnerChargeType.RECOVERY
        )
    )).scalars().all()
    assert rows == []


@pytest.mark.asyncio
async def test_post_settlement_refund_creates_recovery_charge(seeded_db):
    owner, _, _, refund = await _arrange(seeded_db, refund_amount=500.0,
                                         post_settlement=True)
    charge = await create_recovery_charge_for_refund(seeded_db, refund_id=refund.id)
    await seeded_db.commit()
    assert charge is not None
    assert charge.charge_type == OwnerChargeType.RECOVERY
    assert charge.owner_id == owner.id
    assert q2(to_decimal(charge.total_amount)) == Decimal("500.00")
    assert charge.gst_amount == 0      # recovery is not a fresh supply
    assert charge.status == OwnerChargeStatus.DUE
    assert charge.period_key.startswith("REFUND-")


@pytest.mark.asyncio
async def test_recovery_creation_is_idempotent(seeded_db):
    """Two calls for the same refund return the same OwnerCharge id."""
    _, _, _, refund = await _arrange(seeded_db, refund_amount=500.0,
                                     post_settlement=True)
    c1 = await create_recovery_charge_for_refund(seeded_db, refund_id=refund.id)
    await seeded_db.commit()
    c2 = await create_recovery_charge_for_refund(seeded_db, refund_id=refund.id)
    await seeded_db.commit()
    assert c1.id == c2.id

    # Exactly one RECOVERY row exists
    rows = (await seeded_db.execute(
        select(OwnerCharge).where(
            OwnerCharge.charge_type == OwnerChargeType.RECOVERY
        )
    )).scalars().all()
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_requested_refund_does_not_create_recovery(seeded_db):
    """Only APPROVED / PROCESSED refunds count."""
    _, _, booking, _ = await _arrange(seeded_db, refund_amount=500.0,
                                      post_settlement=True)
    requested_refund = Refund(
        booking_id=booking.id, user_id=booking.user_id, amount=300.0,
        reason=RefundReason.SERVICE_ISSUE, status=RefundStatus.REQUESTED,
    )
    seeded_db.add(requested_refund)
    await seeded_db.commit()
    charge = await create_recovery_charge_for_refund(
        seeded_db, refund_id=requested_refund.id,
    )
    assert charge is None


@pytest.mark.asyncio
async def test_rejected_refund_does_not_create_recovery(seeded_db):
    _, _, booking, _ = await _arrange(seeded_db, refund_amount=500.0,
                                      post_settlement=True)
    rejected = Refund(
        booking_id=booking.id, user_id=booking.user_id, amount=300.0,
        reason=RefundReason.SERVICE_ISSUE, status=RefundStatus.REJECTED,
    )
    seeded_db.add(rejected)
    await seeded_db.commit()
    charge = await create_recovery_charge_for_refund(seeded_db, refund_id=rejected.id)
    assert charge is None


# ---------- scan_and_create_recovery_charges -----------------------------

@pytest.mark.asyncio
async def test_scan_processes_only_post_settlement_refunds(seeded_db):
    _, _, _, refund_post = await _arrange(
        seeded_db, refund_amount=500.0, post_settlement=True,
    )
    # Create a second booking + pre-settlement refund (decoy)
    student = await seeded_db.get(User, "srec")
    acc = await seeded_db.get(Accommodation, "arec")
    pre_booking = Booking(
        id="brec2", user_id=student.id, accommodation_id=acc.id,
        start_date=datetime.utcnow(), end_date=datetime.utcnow() + timedelta(days=30),
        amount=1000.0, status=BookingStatus.ACTIVE,
        payment_status=PaymentStatus.PAID,
    )
    seeded_db.add(pre_booking)
    await seeded_db.flush()
    await AccountingShadow.shadow_post_booking_paid(seeded_db, booking_id=pre_booking.id)
    # Do NOT settle this one
    pre_refund = Refund(
        booking_id=pre_booking.id, user_id=student.id, amount=200.0,
        reason=RefundReason.SERVICE_ISSUE, status=RefundStatus.APPROVED,
    )
    seeded_db.add(pre_refund)
    await seeded_db.commit()

    await scan_and_create_recovery_charges(seeded_db)
    recoveries = (await seeded_db.execute(
        select(OwnerCharge).where(
            OwnerCharge.charge_type == OwnerChargeType.RECOVERY
        )
    )).scalars().all()
    # Only the post-settlement refund yielded a recovery
    assert len(recoveries) == 1
    assert recoveries[0].period_key == f"REFUND-{refund_post.id}"


# ---------- super-admin visibility ---------------------------------------

@pytest.mark.asyncio
async def test_outstanding_recoveries_lists_only_unpaid(seeded_db):
    owner, _, _, refund = await _arrange(
        seeded_db, refund_amount=500.0, post_settlement=True,
    )
    await create_recovery_charge_for_refund(seeded_db, refund_id=refund.id)
    await seeded_db.commit()

    rows = await get_outstanding_recoveries_for_owner(seeded_db, owner_id=owner.id)
    assert len(rows) == 1

    # Marking it PAID should remove it from outstanding
    rows[0].status = OwnerChargeStatus.PAID
    await seeded_db.commit()
    rows2 = await get_outstanding_recoveries_for_owner(seeded_db, owner_id=owner.id)
    assert rows2 == []


# ---------- integration: settlement_run triggers recovery scan -----------

@pytest.mark.asyncio
async def test_run_settlements_creates_recovery_for_already_settled_refund(seeded_db):
    """The settlement cron itself sweeps for recovery charges before
    aggregating. A post-settlement refund created between runs gets caught."""
    owner, student, booking, _ = await _arrange(
        seeded_db, refund_amount=200.0, post_settlement=True,
    )
    # The refund from _arrange is APPROVED. Run settlement again; it should
    # scan and create a recovery charge for it (booking already settled).
    summary = await run_settlements(seeded_db)
    assert "runs_created" in summary

    recoveries = (await seeded_db.execute(
        select(OwnerCharge).where(
            (OwnerCharge.owner_id == owner.id)
            & (OwnerCharge.charge_type == OwnerChargeType.RECOVERY)
        )
    )).scalars().all()
    assert len(recoveries) == 1
    assert q2(to_decimal(recoveries[0].total_amount)) == Decimal("200.00")
