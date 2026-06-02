"""Credit note service tests.

Three contract claims:
  1. Flag off => no credit note issued. The existing refund flow keeps working.
  2. Flag on + approved refund => CREDIT_NOTE doc issued with sequential
     SS/CN/{FY}/{NNNNNN} number; ledger group balances; idempotent on re-call.
  3. The reversing ledger entries exactly mirror the original shadow posting
     (proportionally if refund < booking amount).
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models.accommodation import Accommodation, AccommodationType, Gender
from app.models.booking import Booking, BookingStatus, PaymentStatus
from app.models.invoice import Invoice, InvoiceDocType
from app.models.ledger_entry import LedgerEntry
from app.models.refund import Refund, RefundReason, RefundStatus
from app.models.tax_config import TaxConfig
from app.models.user import GSTRegistrationType, User, UserRole
from app.services.accounting_shadow import AccountingShadow
from app.services.credit_note_service import issue_for_refund
from app.services.tax_engine import q2


async def _set_flag(db, key, value):
    row = (await db.execute(
        select(TaxConfig).where(TaxConfig.key == key)
    )).scalar_one_or_none()
    if row is None:
        db.add(TaxConfig(key=key, value=json.dumps(value)))
    else:
        row.value = json.dumps(value)
    await db.commit()


async def _arrange(seeded_db, *, refund_amount: float, booking_amount: float = 2500.0):
    owner = User(
        id="ocn", email="ocn@x.com", hashed_password="x", name="Owner",
        role=UserRole.ADMIN, legal_name="Owner Pvt Ltd",
        gst_registration_type=GSTRegistrationType.REGULAR,
        gstin="29ZZZZZ1234Z1Z5", business_state_code="KA",
    )
    student = User(id="scn", email="scn@x.com", hashed_password="x", name="Student", role=UserRole.STUDENT)
    seeded_db.add_all([owner, student])
    await seeded_db.flush()

    acc = Accommodation(
        id="acn", owner_id=owner.id, name="Acme",
        type=AccommodationType.PG, gender=Gender.UNISEX,
        address="-", price=booking_amount, sharing="single", state="KA",
        gst_category="HOSTEL_PG",
    )
    seeded_db.add(acc)

    booking = Booking(
        id="bcn", user_id=student.id, accommodation_id=acc.id,
        start_date=datetime.utcnow(), end_date=datetime.utcnow() + timedelta(days=30),
        amount=booking_amount, status=BookingStatus.ACTIVE,
        payment_status=PaymentStatus.PAID,
    )
    seeded_db.add(booking)
    await seeded_db.flush()
    await AccountingShadow.shadow_post_booking_paid(seeded_db, booking_id=booking.id)
    booking.paid_at = datetime.utcnow() - timedelta(days=1)
    await seeded_db.commit()

    refund = Refund(
        booking_id=booking.id, user_id=student.id, amount=refund_amount,
        reason=RefundReason.SERVICE_ISSUE, status=RefundStatus.APPROVED,
    )
    seeded_db.add(refund)
    await seeded_db.commit()
    return owner, student, booking, refund


@pytest.mark.asyncio
async def test_flag_off_no_credit_note(seeded_db):
    """`feature.credit_notes` default false => issue_for_refund is a no-op."""
    _, _, _, refund = await _arrange(seeded_db, refund_amount=500.0)
    cn = await issue_for_refund(seeded_db, refund_id=refund.id)
    assert cn is None

    # No CREDIT_NOTE rows in invoices
    rows = (await seeded_db.execute(
        select(Invoice).where(Invoice.doc_type == InvoiceDocType.CREDIT_NOTE)
    )).scalars().all()
    assert rows == []


@pytest.mark.asyncio
async def test_flag_on_issues_credit_note_with_series_number(seeded_db):
    await _set_flag(seeded_db, "feature.credit_notes", True)
    _, _, _, refund = await _arrange(seeded_db, refund_amount=500.0)

    cn = await issue_for_refund(seeded_db, refund_id=refund.id)
    await seeded_db.commit()
    assert cn is not None
    assert cn.doc_type == InvoiceDocType.CREDIT_NOTE
    assert cn.series_code == "CN"
    assert cn.fiscal_year is not None
    assert cn.sequence_no == 1
    assert cn.invoice_number.startswith("SS/CN/")


@pytest.mark.asyncio
async def test_reversing_ledger_balances(seeded_db):
    await _set_flag(seeded_db, "feature.credit_notes", True)
    _, _, _, refund = await _arrange(seeded_db, refund_amount=500.0)

    cn = await issue_for_refund(seeded_db, refund_id=refund.id)
    await seeded_db.commit()
    assert cn is not None

    rows = (await seeded_db.execute(
        select(LedgerEntry).where(LedgerEntry.source_id == cn.id)
    )).scalars().all()
    assert rows
    dr = sum(r.debit for r in rows)
    cr = sum(r.credit for r in rows)
    assert q2(dr) == q2(cr) == Decimal("500.00")


@pytest.mark.asyncio
async def test_partial_refund_proportional_reversal(seeded_db):
    """Refund of ₹500 against a ₹2,500 booking reverses 20% of base + GST."""
    await _set_flag(seeded_db, "feature.credit_notes", True)
    _, _, booking, refund = await _arrange(
        seeded_db, refund_amount=500.0, booking_amount=2500.0,
    )

    cn = await issue_for_refund(seeded_db, refund_id=refund.id)
    await seeded_db.commit()
    assert cn is not None
    # The amounts reversed should sum to exactly the refund amount.
    assert q2(Decimal(str(cn.amount)) + Decimal(str(cn.tax_amount))) == Decimal("500.00")
    # And the proportional GST reversed is ~20% of the original booking GST.
    booking_gst = q2(booking.gst_amount)
    cn_gst = q2(Decimal(str(cn.tax_amount)))
    # 20% of 381.36 = 76.27 (give or take rounding)
    assert abs(cn_gst - q2(booking_gst * Decimal("0.2"))) <= Decimal("0.05")


@pytest.mark.asyncio
async def test_issue_for_refund_is_idempotent(seeded_db):
    """Re-running on the same refund returns the existing credit note."""
    await _set_flag(seeded_db, "feature.credit_notes", True)
    _, _, _, refund = await _arrange(seeded_db, refund_amount=500.0)

    cn1 = await issue_for_refund(seeded_db, refund_id=refund.id)
    await seeded_db.commit()
    cn2 = await issue_for_refund(seeded_db, refund_id=refund.id)
    await seeded_db.commit()
    assert cn1.id == cn2.id

    # Exactly one CREDIT_NOTE row exists
    count = len((await seeded_db.execute(
        select(Invoice).where(Invoice.doc_type == InvoiceDocType.CREDIT_NOTE)
    )).scalars().all())
    assert count == 1
