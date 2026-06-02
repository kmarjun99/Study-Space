"""Tests for the archive bundler used by --archive on the validator CLI.

Three claims:
  1. Each collector returns (None, None) gracefully when its source is missing.
  2. `build_archive_bundle` always produces a valid zip with a manifest, even
     when individual collectors return nothing.
  3. When the DB has a paid booking + credit note + settlement run, the bundle
     contains the corresponding files with the expected naming.
"""
from __future__ import annotations

import io
import json
import zipfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import select

from app.models.accommodation import Accommodation, AccommodationType, Gender
from app.models.booking import Booking, BookingStatus, PaymentStatus
from app.models.refund import Refund, RefundReason, RefundStatus
from app.models.settlement import SettlementRun
from app.models.tax_config import TaxConfig
from app.models.user import GSTRegistrationType, KYCStatus, User, UserRole
from app.services.accounting_shadow import AccountingShadow
from app.services.canary_archive import (
    build_archive_bundle,
    collect_booking_invoice_pdf,
    collect_credit_note_pdf,
    collect_ledger_csv,
    collect_settlement_pdf,
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


async def _make_booking(db, *, amount=2500.0, paid_days_ago=10):
    owner = User(
        id="oarc", email="oarc@x.com", hashed_password="x", name="Owner",
        role=UserRole.ADMIN, legal_name="Owner Pvt Ltd",
        gst_registration_type=GSTRegistrationType.REGULAR,
        gstin="29ZZZZZ1234Z1Z5", business_state_code="KA",
        bank_account_number="50101234567890", bank_ifsc="HDFC0001234",
        kyc_status=KYCStatus.VERIFIED,
    )
    student = User(
        id="sarc", email="sarc@x.com", hashed_password="x", name="Student",
        role=UserRole.STUDENT,
    )
    db.add_all([owner, student])
    await db.flush()
    acc = Accommodation(
        id="aarc", owner_id=owner.id, name="Acme",
        type=AccommodationType.PG, gender=Gender.UNISEX,
        address="-", price=amount, sharing="single", state="KA",
        gst_category="HOSTEL_PG",
    )
    db.add(acc)
    await db.flush()
    b = Booking(
        id="barc", user_id=student.id, accommodation_id=acc.id,
        start_date=datetime.utcnow(), end_date=datetime.utcnow() + timedelta(days=30),
        amount=amount, status=BookingStatus.ACTIVE,
        payment_status=PaymentStatus.PAID,
    )
    db.add(b)
    await db.flush()
    await AccountingShadow.shadow_post_booking_paid(db, booking_id=b.id)
    b.paid_at = datetime.utcnow() - timedelta(days=paid_days_ago)
    await db.commit()
    return owner, student, acc, b


# ---------- individual collectors -----------------------------------------

@pytest.mark.asyncio
async def test_collect_booking_invoice_returns_none_when_no_invoice(seeded_db):
    _, _, _, b = await _make_booking(seeded_db)
    fname, data = await collect_booking_invoice_pdf(seeded_db, booking_id=b.id)
    assert fname is None and data is None


@pytest.mark.asyncio
async def test_collect_credit_note_returns_none_when_no_refund(seeded_db):
    _, _, _, b = await _make_booking(seeded_db)
    fname, data = await collect_credit_note_pdf(seeded_db, booking_id=b.id)
    assert fname is None and data is None


@pytest.mark.asyncio
async def test_collect_settlement_returns_none_for_missing_run(seeded_db):
    fname, data = await collect_settlement_pdf(seeded_db, run_id="nope")
    assert fname is None and data is None


@pytest.mark.asyncio
async def test_collect_ledger_csv_always_returns_something(seeded_db):
    _, _, _, b = await _make_booking(seeded_db)
    fname, data = await collect_ledger_csv(seeded_db, booking_id=b.id)
    assert fname == "ledger.csv"
    text = data.decode("utf-8")
    assert "txn_group_id" in text
    assert b.id in text   # booking-related ledger rows are included


@pytest.mark.asyncio
async def test_collect_credit_note_renders_after_approval(seeded_db):
    await _set_flag(seeded_db, "feature.credit_notes", True)
    _, student, _, b = await _make_booking(seeded_db, amount=2500.0)
    refund = Refund(
        booking_id=b.id, user_id=student.id, amount=500.0,
        reason=RefundReason.SERVICE_ISSUE, status=RefundStatus.APPROVED,
    )
    seeded_db.add(refund)
    await seeded_db.commit()
    await issue_for_refund(seeded_db, refund_id=refund.id)
    await seeded_db.commit()

    fname, data = await collect_credit_note_pdf(seeded_db, booking_id=b.id)
    assert fname is not None and fname.endswith(".pdf")
    assert data is not None and data[:5] == b"%PDF-"


@pytest.mark.asyncio
async def test_collect_settlement_pdf_after_run(seeded_db):
    _, _, _, b = await _make_booking(seeded_db)
    await run_settlements(seeded_db)
    b2 = (await seeded_db.execute(
        select(Booking).where(Booking.id == b.id)
    )).scalar_one()
    fname, data = await collect_settlement_pdf(seeded_db, run_id=b2.settlement_run_id)
    assert fname is not None and fname.endswith(".pdf")
    assert data[:5] == b"%PDF-"


# ---------- bundle entrypoint ---------------------------------------------

@pytest.mark.asyncio
async def test_bundle_always_contains_manifest(seeded_db, tmp_path):
    """Even with nothing to bundle (no booking), we still get a usable zip."""
    name, data = await build_archive_bundle(
        seeded_db,
        listing_id="abcd1234-no-data",
        booking_id=None,
        settlement_run_id=None,
        validation_json_path=None,
    )
    assert name.startswith("staging_canary_abcd1234")
    z = zipfile.ZipFile(io.BytesIO(data))
    names = z.namelist()
    assert "manifest.txt" in names
    manifest = z.read("manifest.txt").decode("utf-8")
    assert "missing : booking invoice + credit note + ledger (no booking)" in manifest
    assert "missing : settlement PDF (no settlement run yet)" in manifest


@pytest.mark.asyncio
async def test_full_bundle_after_complete_flow(seeded_db, tmp_path):
    await _set_flag(seeded_db, "feature.credit_notes", True)
    _, student, _, b = await _make_booking(seeded_db, amount=2500.0)

    # Refund + credit note
    refund = Refund(
        booking_id=b.id, user_id=student.id, amount=500.0,
        reason=RefundReason.SERVICE_ISSUE, status=RefundStatus.APPROVED,
    )
    seeded_db.add(refund)
    await seeded_db.commit()
    await issue_for_refund(seeded_db, refund_id=refund.id)
    await seeded_db.commit()

    # Settlement
    await run_settlements(seeded_db)
    b2 = (await seeded_db.execute(
        select(Booking).where(Booking.id == b.id)
    )).scalar_one()

    # Pretend the validator wrote a JSON log
    validation_path = tmp_path / "validation_test.json"
    validation_path.write_text('{"results": []}')

    name, data = await build_archive_bundle(
        seeded_db,
        listing_id="abcd1234-listing",
        booking_id=b.id,
        settlement_run_id=b2.settlement_run_id,
        validation_json_path=validation_path,
    )
    z = zipfile.ZipFile(io.BytesIO(data))
    names = z.namelist()

    # Validation JSON, ledger, credit note, settlement PDF, manifest — all 5
    assert "validation_test.json" in names
    assert "ledger.csv" in names
    assert any(n.startswith("credit_note_") and n.endswith(".pdf") for n in names)
    assert any(n.startswith("settlement_") and n.endswith(".pdf") for n in names)
    assert "manifest.txt" in names

    # Manifest records what was included
    manifest = z.read("manifest.txt").decode("utf-8")
    assert "validation_test.json" in manifest
    assert "ledger.csv" in manifest
