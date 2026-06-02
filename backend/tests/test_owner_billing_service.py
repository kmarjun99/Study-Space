"""Tests for owner_billing_service production paths.

Closes the test-coverage gap for:
  - generate_maintenance_charges_for_today idempotency (cron re-run safety)
  - mark_charge_paid: ledger entries posted + balanced + invoice issued
  - dunning_step state machine (DUE → OVERDUE → SUSPENDED → HIDDEN)
  - reactivate_listing_after_payment when last unpaid charge clears
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models.accommodation import Accommodation, AccommodationType, Gender
from app.models.invoice import Invoice, InvoiceDocType
from app.models.ledger_entry import LedgerEntry
from app.models.owner_charge import (
    ListingType, OwnerCharge, OwnerChargeStatus, OwnerChargeType,
)
from app.models.reading_room import ListingStatus, MaintenanceStatus, ReadingRoom
from app.models.subscription_plan import SubscriptionPlan
from app.models.tax_config import TaxConfig
from app.models.user import GSTRegistrationType, KYCStatus, User, UserRole
from app.services.owner_billing_service import (
    create_listing_fee_charge,
    create_maintenance_charge_for_period,
    dunning_step,
    generate_maintenance_charges_for_today,
    mark_charge_paid,
    reactivate_listing_after_payment,
)
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


async def _make_owner(db, *, uid: str = "ob-owner", state: str = "KA",
                      registered: bool = True) -> User:
    owner = User(
        id=uid, email=f"{uid}@x.com", hashed_password="x", name="Owner",
        role=UserRole.ADMIN, legal_name="Owner Pvt Ltd",
        gst_registration_type=(GSTRegistrationType.REGULAR if registered
                               else GSTRegistrationType.UNREGISTERED),
        business_state_code=state,
        gstin="29ZZZZZ1234Z1Z5" if registered else None,
        kyc_status=KYCStatus.VERIFIED,
    )
    db.add(owner)
    await db.flush()
    return owner


async def _make_accommodation(
    db, *, owner: User, listing_id: str = "ob-acc",
    anchor_day: int = 1, status: ListingStatus = ListingStatus.LIVE,
) -> Accommodation:
    acc = Accommodation(
        id=listing_id, owner_id=owner.id, name="Acme",
        type=AccommodationType.PG, gender=Gender.UNISEX,
        address="-", price=2500.0, sharing="single", state="KA",
        status=status, billing_anchor_day=anchor_day,
        maintenance_status=MaintenanceStatus.CURRENT,
    )
    db.add(acc)
    await db.flush()
    return acc


async def _make_plan(db) -> SubscriptionPlan:
    plan = SubscriptionPlan(
        name="Standard", description="Standard listing",
        price=999.0, duration_days=365,
        is_active=True, is_default=True, created_by="canary",
    )
    db.add(plan)
    await db.flush()
    return plan


# ============== generate_maintenance_charges_for_today ==============

@pytest.mark.asyncio
async def test_maintenance_cron_creates_one_charge_per_live_listing(seeded_db):
    await _set(seeded_db, "feature.recurring_maintenance", True)
    await _set(seeded_db, "maintenance.default_base_amount", 499)

    owner = await _make_owner(seeded_db)
    today = datetime.utcnow()
    await _make_accommodation(seeded_db, owner=owner,
                              listing_id="lst-1", anchor_day=today.day)
    await _make_accommodation(seeded_db, owner=owner,
                              listing_id="lst-2", anchor_day=today.day)
    # Decoy: anchor_day doesn't match today
    other_day = 28 if today.day != 28 else 1
    await _make_accommodation(seeded_db, owner=owner,
                              listing_id="lst-3", anchor_day=other_day)
    await seeded_db.commit()

    summary = await generate_maintenance_charges_for_today(seeded_db, today=today)
    assert summary["created"] == 2

    charges = (await seeded_db.execute(
        select(OwnerCharge).where(
            OwnerCharge.charge_type == OwnerChargeType.MAINTENANCE_FEE
        )
    )).scalars().all()
    assert len(charges) == 2


@pytest.mark.asyncio
async def test_maintenance_cron_re_run_is_idempotent(seeded_db):
    """Re-running same-period cron creates ZERO additional rows.

    This is the cron idempotency contract — must hold even if the unique
    constraint is what's protecting us. We assert at the *service* level.
    """
    await _set(seeded_db, "feature.recurring_maintenance", True)
    await _set(seeded_db, "maintenance.default_base_amount", 499)

    owner = await _make_owner(seeded_db)
    today = datetime.utcnow()
    await _make_accommodation(seeded_db, owner=owner,
                              listing_id="lst-idem", anchor_day=today.day)
    await seeded_db.commit()

    s1 = await generate_maintenance_charges_for_today(seeded_db, today=today)
    s2 = await generate_maintenance_charges_for_today(seeded_db, today=today)
    s3 = await generate_maintenance_charges_for_today(seeded_db, today=today)

    assert s1["created"] == 1
    assert s2["created"] == 0
    assert s3["created"] == 0

    count = len((await seeded_db.execute(
        select(OwnerCharge).where(
            OwnerCharge.charge_type == OwnerChargeType.MAINTENANCE_FEE
        )
    )).scalars().all())
    assert count == 1


@pytest.mark.asyncio
async def test_maintenance_cron_skipped_when_flag_off(seeded_db):
    """Recurring billing must respect the master kill switch."""
    await _set(seeded_db, "feature.recurring_maintenance", False)
    await _set(seeded_db, "maintenance.default_base_amount", 499)

    owner = await _make_owner(seeded_db)
    today = datetime.utcnow()
    await _make_accommodation(seeded_db, owner=owner,
                              listing_id="lst-off", anchor_day=today.day)
    await seeded_db.commit()

    summary = await generate_maintenance_charges_for_today(seeded_db, today=today)
    assert "skipped" in summary
    count = len((await seeded_db.execute(
        select(OwnerCharge)
    )).scalars().all())
    assert count == 0


# ============== mark_charge_paid ==============

@pytest.mark.asyncio
async def test_mark_charge_paid_issues_invoice_and_balanced_ledger(seeded_db):
    owner = await _make_owner(seeded_db)
    acc = await _make_accommodation(seeded_db, owner=owner)
    plan = await _make_plan(seeded_db)

    result = await create_listing_fee_charge(
        seeded_db,
        owner_id=owner.id, listing_id=acc.id,
        listing_type=ListingType.ACCOMMODATION, plan_id=plan.id,
    )
    await seeded_db.commit()

    invoice = await mark_charge_paid(
        seeded_db, charge_id=result.charge.id, payment_ref="pay_test_001",
    )
    await seeded_db.commit()

    # Charge is now PAID
    await seeded_db.refresh(result.charge)
    assert result.charge.status == OwnerChargeStatus.PAID
    assert result.charge.razorpay_payment_id == "pay_test_001"
    assert result.charge.invoice_id == invoice.id

    # Invoice has the right doc_type + series number
    assert invoice.doc_type == InvoiceDocType.PLATFORM_TAX_INVOICE
    assert invoice.series_code == "PLF"
    assert invoice.sequence_no == 1
    assert invoice.invoice_number.startswith("SS/PLF/")

    # Ledger group balances
    rows = (await seeded_db.execute(
        select(LedgerEntry).where(LedgerEntry.source_id == result.charge.id)
    )).scalars().all()
    assert rows
    dr = sum(r.debit for r in rows)
    cr = sum(r.credit for r in rows)
    assert q2(dr) == q2(cr) == q2(to_decimal(result.charge.total_amount))

    # Revenue is recognized (Listing Fee account 4010 credited)
    revenue_codes = {r.account_code for r in rows if r.credit > 0}
    assert "4010" in revenue_codes


@pytest.mark.asyncio
async def test_mark_charge_paid_is_idempotent(seeded_db):
    """Second call returns the same invoice; no duplicate ledger group."""
    owner = await _make_owner(seeded_db)
    acc = await _make_accommodation(seeded_db, owner=owner)
    plan = await _make_plan(seeded_db)
    result = await create_listing_fee_charge(
        seeded_db,
        owner_id=owner.id, listing_id=acc.id,
        listing_type=ListingType.ACCOMMODATION, plan_id=plan.id,
    )
    await seeded_db.commit()

    inv1 = await mark_charge_paid(
        seeded_db, charge_id=result.charge.id, payment_ref="pay_001",
    )
    await seeded_db.commit()
    inv2 = await mark_charge_paid(
        seeded_db, charge_id=result.charge.id, payment_ref="pay_002",
    )
    await seeded_db.commit()
    assert inv1.id == inv2.id

    # Only one ledger group for this charge
    groups = {r.txn_group_id for r in (await seeded_db.execute(
        select(LedgerEntry).where(LedgerEntry.source_id == result.charge.id)
    )).scalars().all()}
    assert len(groups) == 1


# ============== dunning_step ==============

@pytest.mark.asyncio
async def test_dunning_dimmed_at_T_plus_7(seeded_db):
    owner = await _make_owner(seeded_db)
    acc = await _make_accommodation(seeded_db, owner=owner)
    charge = await create_maintenance_charge_for_period(
        seeded_db,
        listing_id=acc.id, listing_type=ListingType.ACCOMMODATION,
        year_month="2026-01", base_amount=Decimal("499"),
    )
    await seeded_db.commit()
    # Backdate due_date so days_overdue ~ 8
    charge.charge.due_date = datetime.utcnow() - timedelta(days=8)
    await seeded_db.commit()

    status = await dunning_step(seeded_db, charge_id=charge.charge.id)
    await seeded_db.commit()
    assert "dimmed" in status or "T+8" in status

    await seeded_db.refresh(acc)
    assert q2(to_decimal(acc.visibility_score)) == Decimal("0.50")
    assert acc.maintenance_status == MaintenanceStatus.OVERDUE


@pytest.mark.asyncio
async def test_dunning_suspended_at_T_plus_10(seeded_db):
    owner = await _make_owner(seeded_db)
    acc = await _make_accommodation(seeded_db, owner=owner)
    charge = await create_maintenance_charge_for_period(
        seeded_db,
        listing_id=acc.id, listing_type=ListingType.ACCOMMODATION,
        year_month="2026-02", base_amount=Decimal("499"),
    )
    await seeded_db.commit()
    charge.charge.due_date = datetime.utcnow() - timedelta(days=11)
    await seeded_db.commit()

    status = await dunning_step(seeded_db, charge_id=charge.charge.id)
    await seeded_db.commit()
    assert "suspended" in status

    await seeded_db.refresh(acc)
    assert acc.maintenance_status == MaintenanceStatus.SUSPENDED_FOR_NONPAYMENT


@pytest.mark.asyncio
async def test_dunning_hidden_at_T_plus_15(seeded_db):
    owner = await _make_owner(seeded_db)
    acc = await _make_accommodation(seeded_db, owner=owner)
    charge = await create_maintenance_charge_for_period(
        seeded_db,
        listing_id=acc.id, listing_type=ListingType.ACCOMMODATION,
        year_month="2026-03", base_amount=Decimal("499"),
    )
    await seeded_db.commit()
    charge.charge.due_date = datetime.utcnow() - timedelta(days=16)
    await seeded_db.commit()

    status = await dunning_step(seeded_db, charge_id=charge.charge.id)
    await seeded_db.commit()
    assert "hidden" in status

    await seeded_db.refresh(acc)
    assert q2(to_decimal(acc.visibility_score)) == Decimal("0")


@pytest.mark.asyncio
async def test_dunning_no_op_when_not_due(seeded_db):
    owner = await _make_owner(seeded_db)
    acc = await _make_accommodation(seeded_db, owner=owner)
    charge = await create_maintenance_charge_for_period(
        seeded_db,
        listing_id=acc.id, listing_type=ListingType.ACCOMMODATION,
        year_month="2026-04", base_amount=Decimal("499"),
    )
    await seeded_db.commit()
    # Future due date
    charge.charge.due_date = datetime.utcnow() + timedelta(days=3)
    await seeded_db.commit()

    status = await dunning_step(seeded_db, charge_id=charge.charge.id)
    assert "not-yet-due" in status


# ============== reactivate_listing_after_payment ==============

@pytest.mark.asyncio
async def test_reactivate_clears_listing_state_when_no_unpaid_charges(seeded_db):
    owner = await _make_owner(seeded_db)
    acc = await _make_accommodation(seeded_db, owner=owner)
    # Pretend the listing was suspended
    acc.maintenance_status = MaintenanceStatus.SUSPENDED_FOR_NONPAYMENT
    acc.visibility_score = Decimal("0.25")
    await seeded_db.commit()

    await reactivate_listing_after_payment(
        seeded_db, listing_id=acc.id, listing_type=ListingType.ACCOMMODATION,
    )
    await seeded_db.commit()
    await seeded_db.refresh(acc)
    assert acc.maintenance_status == MaintenanceStatus.CURRENT
    assert q2(to_decimal(acc.visibility_score)) == Decimal("1.000")


@pytest.mark.asyncio
async def test_reactivate_noop_when_other_charges_still_due(seeded_db):
    """If another OwnerCharge is still DUE/OVERDUE, listing stays suspended."""
    owner = await _make_owner(seeded_db)
    acc = await _make_accommodation(seeded_db, owner=owner)
    acc.maintenance_status = MaintenanceStatus.SUSPENDED_FOR_NONPAYMENT
    acc.visibility_score = Decimal("0.25")

    # Add an outstanding charge so reactivate must NOT clear
    db_charge = await create_maintenance_charge_for_period(
        seeded_db,
        listing_id=acc.id, listing_type=ListingType.ACCOMMODATION,
        year_month="2026-05", base_amount=Decimal("499"),
    )
    assert db_charge.charge.status == OwnerChargeStatus.DUE
    await seeded_db.commit()

    await reactivate_listing_after_payment(
        seeded_db, listing_id=acc.id, listing_type=ListingType.ACCOMMODATION,
    )
    await seeded_db.commit()
    await seeded_db.refresh(acc)
    # State should NOT have been reset because db_charge is still DUE
    assert acc.maintenance_status == MaintenanceStatus.SUSPENDED_FOR_NONPAYMENT
    assert q2(to_decimal(acc.visibility_score)) == Decimal("0.25")
