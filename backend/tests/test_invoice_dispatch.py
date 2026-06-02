"""Tests for student-side invoice doc_type dispatch.

Targets the new `_render_for_doc_type` dispatcher in routers/invoices.py.
Each doc_type maps to a specific renderer; legacy/unknown types fall back to
the existing free-form template so no existing download breaks.

We test the dispatcher directly (not the HTTP layer) because the auth chain
uses Python-3.10 syntax our local venv (3.9) can't import.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from io import BytesIO

import pytest

from app.models.accommodation import Accommodation, AccommodationType, Gender
from app.models.booking import Booking, BookingStatus, PaymentStatus
from app.models.invoice import Invoice, InvoiceDocType
from app.models.party import Party
from app.models.user import User, UserRole
from app.routers.invoices import _render_for_doc_type


def _is_pdf(data) -> bool:
    if isinstance(data, BytesIO):
        data.seek(0)
        head = data.read(5)
        data.seek(0)
        return head == b"%PDF-"
    return isinstance(data, (bytes, bytearray)) and data[:5] == b"%PDF-"


async def _make(seeded_db, *, doc_type, with_parties=True):
    owner = User(
        id=f"o-{doc_type.value}", email=f"o-{doc_type.value}@x.com",
        hashed_password="x", name="Owner", role=UserRole.ADMIN,
    )
    student = User(
        id=f"s-{doc_type.value}", email=f"s-{doc_type.value}@x.com",
        hashed_password="x", name="Student", role=UserRole.STUDENT,
    )
    seeded_db.add_all([owner, student])
    await seeded_db.flush()
    acc = Accommodation(
        id=f"a-{doc_type.value}", owner_id=owner.id, name="Acme",
        type=AccommodationType.PG, gender=Gender.UNISEX,
        address="-", price=2500.0, sharing="single", state="KA",
    )
    seeded_db.add(acc)
    await seeded_db.flush()

    booking = Booking(
        id=f"b-{doc_type.value}", user_id=student.id, accommodation_id=acc.id,
        start_date=datetime.utcnow(), end_date=datetime.utcnow() + timedelta(days=30),
        amount=2500.0, status=BookingStatus.ACTIVE,
        payment_status=PaymentStatus.PAID,
    )
    seeded_db.add(booking)
    await seeded_db.flush()

    supplier_id = None
    recipient_id = None
    if with_parties:
        supplier = Party(party_type="OWNER", legal_name="Owner Pvt Ltd",
                         gstin="29ZZZ1234Z1Z5", state_code="KA")
        recipient = Party(party_type="STUDENT", legal_name="Student",
                          state_code="KA")
        seeded_db.add_all([supplier, recipient])
        await seeded_db.flush()
        supplier_id = supplier.id
        recipient_id = recipient.id

    inv = Invoice(
        invoice_number=f"SS/X/26-27/{doc_type.value[:3]}",
        booking_id=booking.id, user_id=student.id,
        amount=2118.64, tax_amount=381.36, total_amount=2500.0,
        venue_name=acc.name,
        doc_type=doc_type,
        cgst=190.68, sgst=190.68, igst=0,
        base_amount=2118.64,
        hsn_sac="996311", place_of_supply_state="KA",
        supplier_party_id=supplier_id, recipient_party_id=recipient_id,
    )
    seeded_db.add(inv)
    await seeded_db.commit()
    return inv, booking


def _legacy_data(inv: Invoice) -> dict:
    return {
        "invoice_number": inv.invoice_number,
        "invoice_date": inv.generated_at.strftime("%d %B %Y"),
        "booking_id": inv.booking_id,
        "user_name": "Student", "user_email": "s@x.com",
        "venue_name": inv.venue_name, "venue_address": "-",
        "seat_details": "-", "plan_duration": "1 Month",
        "start_date": "01 Jun 2026", "end_date": "30 Jun 2026",
        "amount": inv.amount, "tax_amount": inv.tax_amount,
        "total_amount": inv.total_amount,
        "payment_method": "UPI", "transaction_id": "txn_001",
    }


# ---------- Each doc_type renders to a PDF ----------

@pytest.mark.asyncio
async def test_owner_tax_invoice_renders(seeded_db):
    inv, booking = await _make(seeded_db, doc_type=InvoiceDocType.OWNER_TAX_INVOICE)
    out = await _render_for_doc_type(
        seeded_db, inv, booking, InvoiceDocType.OWNER_TAX_INVOICE,
        _legacy_data(inv),
    )
    assert _is_pdf(out)


@pytest.mark.asyncio
async def test_eco_tax_invoice_renders(seeded_db):
    inv, booking = await _make(seeded_db, doc_type=InvoiceDocType.ECO_TAX_INVOICE)
    out = await _render_for_doc_type(
        seeded_db, inv, booking, InvoiceDocType.ECO_TAX_INVOICE,
        _legacy_data(inv),
    )
    assert _is_pdf(out)


@pytest.mark.asyncio
async def test_non_gst_receipt_renders(seeded_db):
    inv, booking = await _make(
        seeded_db, doc_type=InvoiceDocType.NON_GST_RECEIPT, with_parties=True,
    )
    out = await _render_for_doc_type(
        seeded_db, inv, booking, InvoiceDocType.NON_GST_RECEIPT,
        _legacy_data(inv),
    )
    assert _is_pdf(out)


@pytest.mark.asyncio
async def test_legacy_falls_back_to_existing_renderer(seeded_db):
    """No party data, no GST split — must still produce a PDF via the
    legacy renderer. The friend's #1 acceptance: existing downloads don't break."""
    inv, booking = await _make(
        seeded_db, doc_type=InvoiceDocType.LEGACY, with_parties=False,
    )
    out = await _render_for_doc_type(
        seeded_db, inv, booking, InvoiceDocType.LEGACY, _legacy_data(inv),
    )
    assert _is_pdf(out)


@pytest.mark.asyncio
async def test_credit_note_doc_type_falls_back(seeded_db):
    """CREDIT_NOTE is downloaded via its own endpoint; if a student hits the
    booking endpoint and the row happens to be a credit note, fall back
    rather than crash."""
    inv, booking = await _make(seeded_db, doc_type=InvoiceDocType.CREDIT_NOTE)
    out = await _render_for_doc_type(
        seeded_db, inv, booking, InvoiceDocType.CREDIT_NOTE, _legacy_data(inv),
    )
    assert _is_pdf(out)


@pytest.mark.asyncio
async def test_owner_invoice_with_no_parties_still_renders(seeded_db):
    """Defensive: if party FKs aren't set, the dispatcher passes empty dicts
    to the renderer. Test that we still get a PDF instead of a 500."""
    inv, booking = await _make(
        seeded_db, doc_type=InvoiceDocType.OWNER_TAX_INVOICE, with_parties=False,
    )
    out = await _render_for_doc_type(
        seeded_db, inv, booking, InvoiceDocType.OWNER_TAX_INVOICE,
        _legacy_data(inv),
    )
    assert _is_pdf(out)
