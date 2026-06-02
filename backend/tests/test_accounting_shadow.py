"""End-to-end shadow posting from a paid booking.

Proves:
  - Accounting is a no-op when `accounting.enabled=false` (existing flow safe).
  - A paid booking yields one balanced ledger group when enabled.
  - Booking row gets `base_amount`, `gst_amount`, `gst_treatment` populated.
"""
from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal

import pytest

from app.models.accommodation import Accommodation, AccommodationType, Gender
from app.models.booking import Booking, BookingStatus, GSTTreatment, PaymentStatus
from app.models.ledger_entry import LedgerEntry
from app.models.tax_config import TaxConfig
from app.models.user import GSTRegistrationType, User, UserRole
from app.services.accounting_shadow import AccountingShadow
from app.services.tax_engine import q2


async def _make_owner(db, *, registered=True, state="KA") -> User:
    owner = User(
        id="owner-1", email="owner@x.com", hashed_password="x",
        name="Acme PG", role=UserRole.ADMIN, legal_name="Acme PG Pvt Ltd",
        gst_registration_type=GSTRegistrationType.REGULAR if registered else GSTRegistrationType.UNREGISTERED,
        gstin="29AAACL1234C1Z5" if registered else None,
        business_state_code=state,
    )
    db.add(owner)
    student = User(
        id="stu-1", email="s@x.com", hashed_password="x", name="S", role=UserRole.STUDENT,
    )
    db.add(student)
    await db.flush()
    return owner


async def _make_accommodation_booking(db, owner, *, amount=2500.0, state="KA",
                                      category="HOSTEL_PG") -> Booking:
    acc = Accommodation(
        id="acc-1", owner_id=owner.id, name="Acme PG",
        type=AccommodationType.PG, gender=Gender.UNISEX,
        address="-", price=amount, sharing="single", state=state, gst_category=category,
    )
    db.add(acc)
    booking = Booking(
        id="bk-1", user_id="stu-1", accommodation_id=acc.id,
        start_date=datetime.utcnow(), end_date=datetime.utcnow(),
        amount=amount, status=BookingStatus.ACTIVE,
        payment_status=PaymentStatus.PAID,
    )
    db.add(booking)
    await db.flush()
    return booking


@pytest.mark.asyncio
async def test_shadow_noop_when_disabled(seeded_db):
    # Override the enabled flag
    cfg = (await seeded_db.execute(
        __import__("sqlalchemy").select(TaxConfig).where(TaxConfig.key == "accounting.enabled")
    )).scalar_one()
    cfg.value = json.dumps(False)
    await seeded_db.commit()

    owner = await _make_owner(seeded_db)
    booking = await _make_accommodation_booking(seeded_db, owner)
    await seeded_db.commit()

    result = await AccountingShadow.shadow_post_booking_paid(seeded_db, booking_id=booking.id)
    assert result is None
    await seeded_db.refresh(booking)
    assert booking.gst_treatment is None  # untouched


@pytest.mark.asyncio
async def test_shadow_owner_registered_intra_state(seeded_db):
    owner = await _make_owner(seeded_db, registered=True, state="KA")
    booking = await _make_accommodation_booking(seeded_db, owner, amount=2500.0, state="KA")
    await seeded_db.commit()

    txn = await AccountingShadow.shadow_post_booking_paid(seeded_db, booking_id=booking.id)
    await seeded_db.commit()
    assert txn is not None

    await seeded_db.refresh(booking)
    assert booking.gst_treatment == GSTTreatment.OWNER_REGISTERED
    assert q2(booking.base_amount + booking.gst_amount) == Decimal("2500.00")

    from sqlalchemy import select
    rows = (await seeded_db.execute(
        select(LedgerEntry).where(LedgerEntry.source_id == booking.id)
    )).scalars().all()

    dr = sum(r.debit for r in rows)
    cr = sum(r.credit for r in rows)
    assert q2(dr) == q2(cr)
    # 4xxx revenue accounts must NEVER be credited from a BOOKING source.
    revenue_codes = {"4010", "4011", "4012"}
    assert not any(r.account_code in revenue_codes for r in rows)


@pytest.mark.asyncio
async def test_shadow_is_idempotent(seeded_db):
    owner = await _make_owner(seeded_db)
    booking = await _make_accommodation_booking(seeded_db, owner)
    await seeded_db.commit()

    txn1 = await AccountingShadow.shadow_post_booking_paid(seeded_db, booking_id=booking.id)
    await seeded_db.commit()
    txn2 = await AccountingShadow.shadow_post_booking_paid(seeded_db, booking_id=booking.id)
    await seeded_db.commit()
    assert txn1 == txn2 or txn2 is None  # already-shadowed -> short-circuit
