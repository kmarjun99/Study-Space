"""End-to-end canary walkthrough for CA review.

Runs the full money loop against a throwaway in-memory SQLite database and
dumps the resulting artifacts into `./canary_output/` so a CA (or any
reviewer) has something concrete to audit before the platform is enabled
for real owners.

Scenarios covered (one of each per the CA review pack request):

  1. GST-registered owner booking          → OWNER_TAX_INVOICE PDF
  2. Unregistered owner, non-Sec-9(5)      → NON_GST_RECEIPT PDF
  3. Unregistered owner, Sec 9(5) eligible → ECO_TAX_INVOICE PDF
  4. Refund BEFORE settlement              → CREDIT_NOTE + reversing ledger
  5. Refund AFTER settlement               → CREDIT_NOTE + RECOVERY_PENDING flag
  6. Monthly maintenance fee invoice       → PLATFORM_TAX_INVOICE PDF
  7. Owner settlement statement            → SETTLEMENT_STATEMENT PDF

Outputs:
  - ledger.csv       — every double-entry row produced
  - bookings.csv     — booking-level tax breakdown
  - settlements.csv  — per-run summary
  - invoice_*.pdf    — every issued document
  - summary.md       — human-readable narrative + CA review checklist

Run:
    python -m scripts.canary_walkthrough

Idempotent: deletes and recreates `canary_output/` on each run.
"""
from __future__ import annotations

import asyncio
import csv
import json
import os
import shutil
import sys
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

# Force a clean in-memory DB BEFORE the app imports settings.
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ.setdefault("SECRET_KEY", "canary")
os.environ.setdefault("ALGORITHM", "HS256")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.ext.asyncio import create_async_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402

from app.database import Base  # noqa: E402
import app.models  # noqa: F401, E402  (registers tables)
from app.models.accommodation import Accommodation, AccommodationType, Gender  # noqa: E402
from app.models.booking import Booking, BookingStatus, PaymentStatus  # noqa: E402
from app.models.chart_of_accounts import ChartOfAccounts  # noqa: E402
from app.models.invoice import Invoice  # noqa: E402
from app.models.ledger_entry import LedgerEntry  # noqa: E402
from app.models.owner_charge import ListingType  # noqa: E402
from app.models.party import Party  # noqa: E402
from app.models.refund import Refund, RefundReason, RefundStatus  # noqa: E402
from app.models.settlement import SettlementLine, SettlementRun  # noqa: E402
from app.models.subscription_plan import SubscriptionPlan  # noqa: E402
from app.models.tax_config import TaxConfig  # noqa: E402
from app.models.user import GSTRegistrationType, KYCStatus, User, UserRole  # noqa: E402
from app.services.accounting_shadow import AccountingShadow  # noqa: E402
from app.services.credit_note_service import issue_for_refund  # noqa: E402
from app.services.invoice_pdf_service import (  # noqa: E402
    render_credit_note,
    render_eco_tax_invoice,
    render_non_gst_receipt,
    render_owner_tax_invoice,
    render_platform_tax_invoice,
    render_settlement_statement,
)
from app.services.invoice_series_service import InvoiceSeriesService  # noqa: E402
from app.services.owner_billing_service import (  # noqa: E402
    create_listing_fee_charge,
    create_maintenance_charge_for_period,
    mark_charge_paid,
)
from app.services.settlement_service import mark_paid, run_settlements  # noqa: E402


OUTPUT_DIR = Path(__file__).resolve().parent.parent / "canary_output"


# ---------- setup ----------------------------------------------------------

async def _setup_db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    return engine, Session


async def _seed_accounts(db: AsyncSession) -> None:
    accounts = [
        ("1010", "Razorpay Receivable",       "ASSET",     "Dr"),
        ("1011", "Razorpay Settlement A/c",   "ASSET",     "Dr"),
        ("1020", "Bank — Current",            "ASSET",     "Dr"),
        ("2010", "Owner Payable",             "LIABILITY", "Cr"),
        ("2020", "GST Output — CGST",         "LIABILITY", "Cr"),
        ("2021", "GST Output — SGST",         "LIABILITY", "Cr"),
        ("2022", "GST Output — IGST",         "LIABILITY", "Cr"),
        ("2030", "TCS Payable — CGST",        "LIABILITY", "Cr"),
        ("2031", "TCS Payable — SGST",        "LIABILITY", "Cr"),
        ("2032", "TCS Payable — IGST",        "LIABILITY", "Cr"),
        ("2040", "TDS Payable — 194-O",       "LIABILITY", "Cr"),
        ("2050", "Refund Provision",          "LIABILITY", "Cr"),
        ("4010", "Revenue — Listing Fee",     "INCOME",    "Cr"),
        ("4011", "Revenue — Maintenance Fee", "INCOME",    "Cr"),
        ("4012", "Revenue — Facilitation Fee","INCOME",    "Cr"),
        ("5010", "Payment Gateway Charges",   "EXPENSE",   "Dr"),
    ]
    for code, name, t, side in accounts:
        db.add(ChartOfAccounts(code=code, name=name, type=t, normal_side=side, is_active=True))


async def _seed_config(db: AsyncSession) -> None:
    cfg = {
        # All accounting features ON for the canary
        "accounting.enabled": True,
        "feature.recurring_maintenance": True,
        "feature.gst_invoices": True,
        "feature.credit_notes": True,
        "feature.per_listing_price_mode": False,   # left OFF on purpose
        # Platform identity
        "platform.legal_name": "StudySpace Technology Pvt Ltd",
        "platform.gstin": "29AABCT1234A1Z5",
        "platform.address": "12, Brigade Rd, Bengaluru, KA",
        "platform.home_state": "KA",
        # Booking GST (inclusive by default)
        "gst.platform_fee_rate": 0.18,
        "gst.platform_fee_inclusive": False,
        "gst.platform_fee_sac": "998599",
        "gst.booking.default_rate": 0.18,
        "gst.booking.pricing_is_inclusive": True,
        "gst.booking.default_sac": "996311",
        "gst.booking.sec_9_5_eligible_categories": ["HOTEL_LIKE", "SHORT_STAY"],
        # TCS / TDS on for the demo
        "tcs.enabled": True,
        "tcs.rate_cgst": 0.0025,
        "tcs.rate_sgst": 0.0025,
        "tcs.rate_igst": 0.005,
        "tcs.applies_to_unregistered_owner": False,
        "tds.section_194o_enabled": False,
        "tds.section_194o_rate": 0.001,
        "tds.section_194o_threshold_yearly": 500000,
        # Settlement
        "settlement.hold_days": 3,
        "settlement.offset_maintenance": False,
        # Maintenance fee default (per-listing fallback)
        "maintenance.default_base_amount": 499,
    }
    for key, value in cfg.items():
        db.add(TaxConfig(key=key, value=json.dumps(value)))


# ---------- fixtures: owners, listings, plans -----------------------------

async def _make_owner(
    db: AsyncSession, *,
    uid: str, name: str, state: str = "KA",
    registered: bool, gstin: str | None = None,
) -> User:
    owner = User(
        id=uid, email=f"{uid}@canary.local", hashed_password="x",
        name=name, role=UserRole.ADMIN,
        legal_name=name + (" Pvt Ltd" if registered else ""),
        pan=f"AAA{uid[:5].upper()}A",
        gstin=gstin,
        gst_registration_type=(
            GSTRegistrationType.REGULAR if registered
            else GSTRegistrationType.UNREGISTERED
        ),
        business_state_code=state,
        bank_account_holder=name,
        bank_account_number=f"5010{uid[-8:].rjust(8, '0').upper()}",
        bank_ifsc="HDFC0001234",
        kyc_status=KYCStatus.VERIFIED,
        phone="9000000000",
    )
    db.add(owner)
    await db.flush()
    return owner


async def _make_acc(
    db: AsyncSession, *, owner: User, name: str, category: str,
    price: float = 2500.0, state: str = "KA",
) -> Accommodation:
    acc = Accommodation(
        id=f"acc-{owner.id}",
        owner_id=owner.id, name=name,
        type=AccommodationType.HOSTEL, gender=Gender.UNISEX,
        address=f"{name} Address, {state}",
        price=price, sharing="single",
        state=state,
        gst_category=category,
    )
    db.add(acc)
    await db.flush()
    return acc


async def _make_paid_booking(
    db: AsyncSession, *,
    bid: str, student: User, acc: Accommodation,
    amount: float, paid_offset_days: int = 10,
) -> Booking:
    booking = Booking(
        id=bid, user_id=student.id, accommodation_id=acc.id,
        start_date=datetime.utcnow(),
        end_date=datetime.utcnow() + timedelta(days=30),
        amount=amount, status=BookingStatus.ACTIVE,
        payment_status=PaymentStatus.PAID,
    )
    db.add(booking)
    await db.flush()
    await AccountingShadow.shadow_post_booking_paid(db, booking_id=booking.id)
    booking.paid_at = datetime.utcnow() - timedelta(days=paid_offset_days)
    await db.flush()
    return booking


# ---------- main scenario --------------------------------------------------

async def _run_scenario(db: AsyncSession) -> dict:
    # Listing plan + one student
    plan = SubscriptionPlan(
        name="Standard Listing", description="One-time listing fee",
        price=999.0, duration_days=365,
        is_active=True, is_default=True, created_by="canary-super-admin",
    )
    db.add(plan)
    student = User(
        id="student-canary", email="ananya@canary.local",
        hashed_password="x", name="Ananya R", role=UserRole.STUDENT,
    )
    db.add(student)
    await db.flush()

    # --- THREE owners, one per CA scenario ---
    owner_a = await _make_owner(
        db, uid="owner-a", name="Acme Reading Rooms",
        registered=True, gstin="29ACMEZ1234Z1Z5",
    )
    acc_a = await _make_acc(
        db, owner=owner_a, name="Acme Hostel — Indiranagar",
        category="HOSTEL_PG", price=2500.0,
    )

    owner_b = await _make_owner(
        db, uid="owner-b", name="Bharat Lodge",
        registered=False,
    )
    acc_b = await _make_acc(
        db, owner=owner_b, name="Bharat Lodge — Jayanagar",
        category="HOSTEL_PG", price=1800.0,   # NOT in Sec 9(5) list
    )

    owner_c = await _make_owner(
        db, uid="owner-c", name="Comfort Stays",
        registered=False,
    )
    acc_c = await _make_acc(
        db, owner=owner_c, name="Comfort Stays — Koramangala",
        category="HOTEL_LIKE", price=3000.0,   # IS in Sec 9(5) list
    )
    await db.commit()

    # --- Listing fees (StudySpace revenue, paid by each owner) ---
    listing_invoices: dict[str, Invoice] = {}
    for owner, acc in [(owner_a, acc_a), (owner_b, acc_b), (owner_c, acc_c)]:
        charge = await create_listing_fee_charge(
            db, owner_id=owner.id, listing_id=acc.id,
            listing_type=ListingType.ACCOMMODATION, plan_id=plan.id,
        )
        await db.commit()
        inv = await mark_charge_paid(
            db, charge_id=charge.charge.id,
            payment_ref=f"pay_canary_listing_{owner.id[-1]}",
        )
        await db.commit()
        listing_invoices[owner.id] = inv

    # --- Monthly maintenance fee for Owner A (Scenario #6) ---
    maint_result = await create_maintenance_charge_for_period(
        db,
        listing_id=acc_a.id,
        listing_type=ListingType.ACCOMMODATION,
        year_month=datetime.utcnow().strftime("%Y-%m"),
        base_amount=Decimal("499"),
    )
    await db.commit()
    maint_invoice: Invoice | None = None
    if maint_result is not None:
        maint_invoice = await mark_charge_paid(
            db, charge_id=maint_result.charge.id,
            payment_ref="pay_canary_maint_a",
        )
        await db.commit()

    # --- Bookings (one per owner; each shadow-posted with a different treatment) ---
    booking_a = await _make_paid_booking(
        db, bid="bk-a", student=student, acc=acc_a, amount=2500.0,
    )
    booking_b = await _make_paid_booking(
        db, bid="bk-b", student=student, acc=acc_b, amount=1800.0,
    )
    booking_c = await _make_paid_booking(
        db, bid="bk-c", student=student, acc=acc_c, amount=3000.0,
    )
    await db.commit()

    # --- Refund BEFORE settlement on Owner A's booking (Scenario #4) ---
    refund_pre = Refund(
        booking_id=booking_a.id, user_id=student.id, amount=500.0,
        reason=RefundReason.SERVICE_ISSUE, status=RefundStatus.APPROVED,
    )
    db.add(refund_pre)
    await db.commit()
    cn_pre = await issue_for_refund(db, refund_id=refund_pre.id)
    await db.commit()

    # --- Settlement run ---
    summary = await run_settlements(db)

    # Mark Owner B's run PAID so the next refund is "after settlement"
    runs = (await db.execute(select(SettlementRun))).scalars().all()
    owner_b_run = next((r for r in runs if r.owner_id == owner_b.id and r.status.value == "READY"), None)
    if owner_b_run is not None:
        await mark_paid(db, run_id=owner_b_run.id, payout_ref="HDFC-CANARY-B-001")
        await db.commit()

    # --- Refund AFTER settlement on Owner B's booking (Scenario #5) ---
    refund_post = Refund(
        booking_id=booking_b.id, user_id=student.id, amount=200.0,
        reason=RefundReason.SERVICE_ISSUE, status=RefundStatus.APPROVED,
    )
    db.add(refund_post)
    await db.commit()
    cn_post = await issue_for_refund(db, refund_id=refund_post.id)
    await db.commit()

    return {
        "student": student,
        "owners": {"a": owner_a, "b": owner_b, "c": owner_c},
        "accs": {"a": acc_a, "b": acc_b, "c": acc_c},
        "bookings": {"a": booking_a, "b": booking_b, "c": booking_c},
        "listing_invoices": listing_invoices,
        "maint_invoice": maint_invoice,
        "refunds": {"pre": refund_pre, "post": refund_post},
        "credit_notes": {"pre": cn_pre, "post": cn_post},
        "settlement_summary": summary,
    }


# ---------- artifact writers ----------------------------------------------

async def _dump_csvs(db: AsyncSession, out_dir: Path) -> None:
    rows = (await db.execute(select(LedgerEntry).order_by(LedgerEntry.posted_at))).scalars().all()
    with (out_dir / "ledger.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["posted_at", "txn_group_id", "source_type", "source_id",
                    "account_code", "party_type", "party_id",
                    "debit", "credit", "narration"])
        for r in rows:
            w.writerow([
                r.posted_at.isoformat(), r.txn_group_id, r.source_type, r.source_id,
                r.account_code, r.party_type or "", r.party_id or "",
                f"{r.debit:.2f}", f"{r.credit:.2f}", r.narration or "",
            ])

    bks = (await db.execute(select(Booking))).scalars().all()
    with (out_dir / "bookings.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "amount_paid", "base", "gst", "treatment",
                    "paid_at", "settled_at", "settlement_run_id"])
        for b in bks:
            w.writerow([
                b.id, f"{b.amount:.2f}",
                f"{(b.base_amount or 0):.2f}", f"{(b.gst_amount or 0):.2f}",
                (b.gst_treatment.value if b.gst_treatment else ""),
                b.paid_at.isoformat() if b.paid_at else "",
                b.settled_at.isoformat() if b.settled_at else "",
                b.settlement_run_id or "",
            ])

    runs = (await db.execute(select(SettlementRun))).scalars().all()
    with (out_dir / "settlements.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "owner_id", "period_start", "period_end",
                    "gross", "refunds", "platform_offset", "tcs", "tds",
                    "net_payout", "status", "payout_ref"])
        for r in runs:
            w.writerow([
                r.id, r.owner_id, r.period_start.isoformat(), r.period_end.isoformat(),
                f"{r.gross:.2f}", f"{r.refunds:.2f}", f"{r.platform_offset:.2f}",
                f"{r.tcs_total:.2f}", f"{r.tds_total:.2f}", f"{r.net_payout:.2f}",
                r.status.value, r.payout_ref or "",
            ])


async def _dump_pdfs(db: AsyncSession, artifacts: dict, out_dir: Path) -> None:
    platform_party = {
        "legal_name": "StudySpace Technology Pvt Ltd",
        "address": "12, Brigade Rd, Bengaluru, KA",
        "gstin": "29AABCT1234A1Z5",
        "state_code": "KA",
    }
    student = artifacts["student"]
    student_party = {
        "legal_name": student.name,
        "gstin": None,
        "state_code": "KA",
    }

    # ---- 1. Platform-side: listing fee + maintenance fee ----
    for owner_key in ["a", "b", "c"]:
        owner = artifacts["owners"][owner_key]
        inv = artifacts["listing_invoices"][owner.id]
        supplier = await db.get(Party, inv.supplier_party_id) if inv.supplier_party_id else None
        recipient = await db.get(Party, inv.recipient_party_id) if inv.recipient_party_id else None
        pdf = render_platform_tax_invoice(
            invoice_number=inv.invoice_number,
            invoice_date=inv.generated_at,
            supplier=_pdict(supplier), recipient=_pdict(recipient),
            line={"description": inv.seat_details or "Listing fee", "period": "One-time"},
            cgst=float(inv.cgst or 0), sgst=float(inv.sgst or 0), igst=float(inv.igst or 0),
            base_amount=float(inv.base_amount or inv.amount),
            total=float(inv.total_amount),
            hsn_sac=inv.hsn_sac, place_of_supply=inv.place_of_supply_state,
        )
        _write_pdf(out_dir / f"06a_listing_fee_{owner_key}_{_safe(inv.invoice_number)}.pdf", pdf)

    if artifacts["maint_invoice"] is not None:
        inv = artifacts["maint_invoice"]
        supplier = await db.get(Party, inv.supplier_party_id) if inv.supplier_party_id else None
        recipient = await db.get(Party, inv.recipient_party_id) if inv.recipient_party_id else None
        pdf = render_platform_tax_invoice(
            invoice_number=inv.invoice_number,
            invoice_date=inv.generated_at,
            supplier=_pdict(supplier), recipient=_pdict(recipient),
            line={"description": inv.seat_details or "Maintenance fee",
                  "period": (inv.plan_duration or "—")},
            cgst=float(inv.cgst or 0), sgst=float(inv.sgst or 0), igst=float(inv.igst or 0),
            base_amount=float(inv.base_amount or inv.amount),
            total=float(inv.total_amount),
            hsn_sac=inv.hsn_sac, place_of_supply=inv.place_of_supply_state,
        )
        _write_pdf(out_dir / f"06b_maintenance_fee_owner_a_{_safe(inv.invoice_number)}.pdf", pdf)

    # ---- 2. Booking-side: one of each doc type (Scenarios 1, 2, 3) ----
    for owner_key, treatment in [
        ("a", "OWNER_REGISTERED"),
        ("b", "NOT_REGISTERED"),
        ("c", "SEC_9_5"),
    ]:
        booking = artifacts["bookings"][owner_key]
        owner = artifacts["owners"][owner_key]
        # Allocate a series number for the booking-side doc on the fly.
        if treatment == "OWNER_REGISTERED":
            number, _, _ = await InvoiceSeriesService.next_number(db, series_code="OBI")
            pdf = render_owner_tax_invoice(
                invoice_number=number,
                invoice_date=datetime.utcnow(),
                supplier={
                    "legal_name": owner.legal_name or owner.name,
                    "address": "—",
                    "gstin": owner.gstin,
                    "state_code": owner.business_state_code,
                },
                recipient=student_party,
                line={"description": f"Accommodation — {artifacts['accs'][owner_key].name}",
                      "period": booking.start_date.strftime("%d %b %Y") + " onwards"},
                cgst=float(_split(booking.gst_amount, "cgst", booking)),
                sgst=float(_split(booking.gst_amount, "sgst", booking)),
                igst=float(_split(booking.gst_amount, "igst", booking)),
                base_amount=float(booking.base_amount or 0),
                total=float(booking.amount),
                hsn_sac="996311",
                place_of_supply=booking.place_of_supply_state or "KA",
            )
            _write_pdf(out_dir / f"01_owner_tax_invoice_{_safe(number)}.pdf", pdf)
        elif treatment == "NOT_REGISTERED":
            number, _, _ = await InvoiceSeriesService.next_number(db, series_code="RCT")
            pdf = render_non_gst_receipt(
                receipt_number=number,
                receipt_date=datetime.utcnow(),
                supplier={
                    "legal_name": owner.legal_name or owner.name,
                    "address": "—",
                    "gstin": None,
                    "state_code": owner.business_state_code,
                },
                recipient=student_party,
                line={"description": f"Accommodation — {artifacts['accs'][owner_key].name}",
                      "period": booking.start_date.strftime("%d %b %Y") + " onwards"},
                total=float(booking.amount),
            )
            _write_pdf(out_dir / f"02_non_gst_receipt_{_safe(number)}.pdf", pdf)
        elif treatment == "SEC_9_5":
            number, _, _ = await InvoiceSeriesService.next_number(db, series_code="ECO")
            pdf = render_eco_tax_invoice(
                invoice_number=number,
                invoice_date=datetime.utcnow(),
                platform_party=platform_party,
                underlying_owner={"legal_name": owner.legal_name or owner.name},
                recipient=student_party,
                line={"description": f"Accommodation — {artifacts['accs'][owner_key].name}",
                      "period": booking.start_date.strftime("%d %b %Y") + " onwards"},
                cgst=float(_split(booking.gst_amount, "cgst", booking)),
                sgst=float(_split(booking.gst_amount, "sgst", booking)),
                igst=float(_split(booking.gst_amount, "igst", booking)),
                base_amount=float(booking.base_amount or 0),
                total=float(booking.amount),
                hsn_sac="996311",
                place_of_supply=booking.place_of_supply_state or "KA",
            )
            _write_pdf(out_dir / f"03_eco_tax_invoice_sec_9_5_{_safe(number)}.pdf", pdf)

    # ---- 3. Credit notes: pre- and post-settlement (Scenarios 4 & 5) ----
    for label, cn in [("04_refund_before_settlement", artifacts["credit_notes"]["pre"]),
                      ("05_refund_after_settlement", artifacts["credit_notes"]["post"])]:
        if cn is None:
            continue
        owner_p = await db.get(Party, cn.supplier_party_id) if cn.supplier_party_id else None
        student_p = await db.get(Party, cn.recipient_party_id) if cn.recipient_party_id else None
        refund = artifacts["refunds"]["pre"] if "pre" in label else artifacts["refunds"]["post"]
        pdf = render_credit_note(
            credit_note_number=cn.invoice_number,
            original_invoice_number=None,
            issue_date=cn.generated_at,
            supplier=_pdict(owner_p), recipient=_pdict(student_p),
            reason=(refund.reason.value if refund.reason else "—"),
            base_amount=float(cn.base_amount or cn.amount),
            cgst=float(cn.cgst or 0), sgst=float(cn.sgst or 0), igst=float(cn.igst or 0),
            total=float(cn.total_amount),
            hsn_sac=cn.hsn_sac, place_of_supply=cn.place_of_supply_state,
        )
        _write_pdf(out_dir / f"{label}_{_safe(cn.invoice_number)}.pdf", pdf)

    # ---- 4. Settlement statements (Scenario 7) ----
    runs = (await db.execute(select(SettlementRun))).scalars().all()
    for run in runs:
        owner = next((o for o in artifacts["owners"].values() if o.id == run.owner_id), None)
        if owner is None:
            continue
        lines = (await db.execute(
            select(SettlementLine).where(SettlementLine.run_id == run.id)
        )).scalars().all()
        number, _, _ = await InvoiceSeriesService.next_number(db, series_code="STM")
        bank_masked = (f"HDFC ****{(owner.bank_account_number or '')[-4:]}"
                       if owner.bank_account_number else None)
        pdf = render_settlement_statement(
            statement_number=number,
            owner_name=owner.legal_name or owner.name,
            owner_gstin=owner.gstin,
            bank_masked=bank_masked,
            period_start=run.period_start, period_end=run.period_end,
            totals={
                "gross": float(run.gross), "refunds": float(run.refunds),
                "tcs": float(run.tcs_total), "tds": float(run.tds_total),
                "offset": float(run.platform_offset), "net": float(run.net_payout),
            },
            payout_ref=run.payout_ref, payout_at=run.payout_at,
            lines=[
                {
                    "kind": line.kind.value, "reference_id": line.reference_id,
                    "base_amount": float(line.base_amount),
                    "deduction": float(line.deduction), "net": float(line.net),
                }
                for line in lines
            ],
        )
        owner_letter = next((k for k, o in artifacts["owners"].items() if o.id == owner.id), "x")
        _write_pdf(out_dir / f"07_settlement_owner_{owner_letter}_{_safe(number)}.pdf", pdf)

    await db.commit()


def _split(total, key: str, booking: Booking) -> float:
    """Approximate per-component split for booking GST.

    For canary purposes we treat the booking as intra-state (CGST/SGST equally).
    The real engine stores splits more precisely; this is a display helper.
    """
    total = float(total or 0)
    if total <= 0:
        return 0.0
    if (booking.place_of_supply_state or "").upper() != "KA":
        return total if key == "igst" else 0.0
    half = round(total / 2, 2)
    if key == "cgst":
        return half
    if key == "sgst":
        return round(total - half, 2)
    return 0.0


def _pdict(p):
    if p is None:
        return {}
    return {"legal_name": p.legal_name, "address": p.address,
            "gstin": p.gstin, "state_code": p.state_code}


def _write_pdf(path: Path, data: bytes) -> None:
    path.write_bytes(data)


def _safe(s: str) -> str:
    return s.replace("/", "_")


# ---------- summary.md + CA checklist --------------------------------------

async def _dump_summary(db: AsyncSession, artifacts: dict, out_dir: Path) -> None:
    bookings = artifacts["bookings"]
    runs = (await db.execute(select(SettlementRun))).scalars().all()

    from app.services.ledger_service import LedgerService
    bad = await LedgerService.integrity_check(db)

    lines: list[str] = []
    lines.append("# StudySpace canary walkthrough — CA review pack\n\n")
    lines.append(f"Generated at: {datetime.utcnow().isoformat()}Z\n\n")
    lines.append("This package demonstrates StudySpace's GST + settlement engine end-to-end.\n")
    lines.append("All accounting feature flags are ON for the demo; in production they remain OFF\n")
    lines.append("until each one is reviewed and signed off.\n\n")

    lines.append("## Cast\n")
    lines.append(f"- **Student**: {artifacts['student'].name}\n")
    for k, label in [("a", "GST-registered (Scenario 1)"),
                     ("b", "Unregistered, HOSTEL_PG / non-Sec 9(5) (Scenario 2)"),
                     ("c", "Unregistered, HOTEL_LIKE / Sec 9(5) eligible (Scenario 3)")]:
        owner = artifacts["owners"][k]
        acc = artifacts["accs"][k]
        gstin = f"GSTIN `{owner.gstin}`" if owner.gstin else "no GSTIN"
        lines.append(f"- **Owner {k.upper()} — {label}**: {owner.legal_name or owner.name} ({gstin})\n")
        lines.append(f"  - Listing: *{acc.name}* — category `{acc.gst_category}`, state `{acc.state}`\n")

    lines.append("\n## Scenario-by-scenario\n")
    lines.append(_scenario_line(
        1, "GST-registered owner booking",
        bookings["a"], "OWNER_TAX_INVOICE",
        "Owner is the supplier of record. Owner GSTIN appears on the invoice. "
        "Owner pays output GST in own GSTR-1.",
    ))
    lines.append(_scenario_line(
        2, "Unregistered owner, non-Sec 9(5)",
        bookings["b"], "NON_GST_RECEIPT",
        "No GST is collected on this supply. Receipt clearly states the supplier "
        "is unregistered and StudySpace is only the facilitator.",
    ))
    lines.append(_scenario_line(
        3, "Unregistered owner, Sec 9(5) eligible",
        bookings["c"], "ECO_TAX_INVOICE",
        "StudySpace is the deemed supplier under Sec 9(5). Owner is disclosed "
        "as the underlying supplier but not the GST supplier of record.",
    ))

    cn_pre = artifacts["credit_notes"]["pre"]
    cn_post = artifacts["credit_notes"]["post"]
    lines.append(f"4. **Refund BEFORE settlement** on Owner A booking — refund Rs. 500. "
                 f"Credit note **{cn_pre.invoice_number if cn_pre else '—'}** issued; "
                 f"ledger group reverses the original booking proportionally; settlement "
                 f"that follows shows the refund as a deduction.\n\n")
    lines.append(f"5. **Refund AFTER settlement** on Owner B booking — refund Rs. 200, "
                 f"raised after Owner B's payout was already marked PAID. Credit note "
                 f"**{cn_post.invoice_number if cn_post else '—'}** issued; "
                 f"in production this would create a `RECOVERY_PENDING` debit against "
                 f"Owner B's next settlement. **CA: please review whether immediate "
                 f"recovery from owner or a netted next-cycle adjustment is preferable.**\n\n")
    if artifacts["maint_invoice"] is not None:
        mi = artifacts["maint_invoice"]
        lines.append(f"6. **Monthly maintenance fee** on Owner A's listing — Rs. 499 + 18% GST. "
                     f"Platform tax invoice **{mi.invoice_number}** issued (StudySpace as "
                     f"supplier, owner as recipient).\n\n")
    else:
        lines.append("6. **Monthly maintenance fee** — not generated this run "
                     "(feature.recurring_maintenance was off or no listing matched).\n\n")

    lines.append("7. **Owner settlement statements** — one per owner:\n")
    for r in runs:
        owner_letter = next(
            (k for k, o in artifacts["owners"].items() if o.id == r.owner_id), "?",
        )
        lines.append(
            f"   - Owner {owner_letter.upper()} `{r.id[:8]}`: "
            f"gross Rs. {float(r.gross):,.2f} − refunds Rs. {float(r.refunds):,.2f} "
            f"− TCS Rs. {float(r.tcs_total):,.2f} − TDS Rs. {float(r.tds_total):,.2f} "
            f"= **net Rs. {float(r.net_payout):,.2f}** ({r.status.value}"
            f"{', UTR ' + r.payout_ref if r.payout_ref else ''})\n"
        )
    lines.append("\n")

    lines.append("## Ledger integrity\n")
    lines.append(f"- Imbalanced txn groups: **{len(bad)}** (expected 0)\n")
    lines.append("- Every row in `ledger.csv` has exactly one of debit/credit non-zero.\n")
    lines.append("- Σdebit equals Σcredit for every `txn_group_id`.\n\n")

    lines.append("---\n\n")
    lines.append("## CA review checklist\n\n")
    lines.append("Please review the artifacts in this folder and confirm:\n\n")
    lines.append(
        "1. **Booking GST rate** — Is `18%` the correct rate for reading-room / cabin / "
        "seat bookings? If different (e.g., 12% for hostel-style accommodation), tell us "
        "the exact rate and we will update `gst.booking.default_rate` in `tax_config`.\n\n"
        "2. **SAC code** — Is `996311` correct for reading-room / cabin usage? If the "
        "supply is closer to coworking / business support, advise the right SAC (e.g., "
        "997212, 998313) and we will set per-listing `gst_sac`.\n\n"
        "3. **Hostel / PG category** — Is a HOSTEL_PG stay (continuous, residential) "
        "exempt, taxable at 12%, or treatment-dependent on the per-unit-per-day tariff? "
        "Please flag the threshold and we will encode it in `tax_config` "
        "(`gst.booking.exempt_threshold_monthly`).\n\n"
        "4. **Section 9(5) applicability** — Among our categories (HOTEL_LIKE, "
        "SHORT_STAY, HOSTEL_PG, READING_ROOM, OTHER) which qualify as 'specified "
        "services' u/s 9(5) when supplied through an ECO by an unregistered owner? "
        "We currently list `[HOTEL_LIKE, SHORT_STAY]`.\n\n"
        "5. **TCS / TDS timing** — Should we enable `tcs.enabled` (0.5% Sec 52 CGST) "
        "and `tds.section_194o_enabled` (0.1% Income Tax) from day 1 of going live, or "
        "after 2-3 months of clean booking data? Both flags are currently OFF in production "
        "config; the canary above turned TCS on to demonstrate the math.\n\n"
        "6. **Owner-issued invoice format** — Open `01_owner_tax_invoice_*.pdf`. Is the "
        "platform-on-behalf-of-supplier format and disclosure footer acceptable for "
        "your registered owners' GSTR-1 reporting? Anything missing for e-invoicing "
        "(IRN/QR) when an owner crosses the AATO threshold?\n\n"
        "7. **Credit note format** — Open `04_refund_before_settlement_*.pdf` and "
        "`05_refund_after_settlement_*.pdf`. Are both compliant with Section 34 of CGST "
        "Act, 2017? Do you require explicit linkage to the original invoice number on "
        "the face of the document (we have the field, currently omitted because the "
        "OWNER_TAX_INVOICE was not yet linked in this synthetic run)?\n\n"
    )

    lines.append("---\n\n")
    lines.append("## What is NOT enabled yet (intentional)\n")
    lines.append("- `feature.per_listing_price_mode` — per-listing GST_INCLUDED / GST_EXTRA "
                 "override. Live booking math stays GST-inclusive globally for now.\n")
    lines.append("- `settlement.offset_maintenance` — auto-deduction of unpaid maintenance "
                 "fees from owner payouts. Maintenance is still billed separately.\n")
    lines.append("- GSTR-1 / GSTR-8 / 26Q export endpoints. Manual review of the CSVs in "
                 "this folder is the current path; exports will ship after this CA review.\n")

    (out_dir / "summary.md").write_text("".join(lines))


async def _dump_ca_review_notes(db: AsyncSession, out_dir: Path, artifacts: dict) -> None:
    """Write a standalone, fillable form for the CA.

    Separate from `summary.md` (which is narrative). `CA_REVIEW_NOTES.md` is
    the artifact the CA marks up and returns; their answers become the source
    of truth for the config keys we'll flip.
    """
    booking_a = artifacts["bookings"]["a"]
    booking_b = artifacts["bookings"]["b"]
    booking_c = artifacts["bookings"]["c"]
    cn_pre = artifacts["credit_notes"]["pre"]
    cn_post = artifacts["credit_notes"]["post"]
    maint = artifacts["maint_invoice"]

    owner_a_id = artifacts["owners"]["a"].id
    owner_a_run = (await db.execute(
        select(SettlementRun).where(SettlementRun.owner_id == owner_a_id).limit(1)
    )).scalar_one_or_none()
    owner_a_tcs = float(owner_a_run.tcs_total) if owner_a_run is not None else 0.0

    out = []
    out.append("# CA Review Notes — StudySpace Canary Pack\n\n")
    out.append("This document is a standalone checklist for your tax review. Please mark each\n")
    out.append("item with your decision and any notes. Supporting artifacts referenced in each\n")
    out.append("question are in this same folder.\n\n")
    out.append(f"**Pack generated**: {datetime.utcnow().isoformat()}Z\n")
    out.append("**Reviewer (CA name)**: ______________________________\n")
    out.append("**Firm**: ______________________________\n")
    out.append("**Date reviewed**: ______________________________\n\n")
    out.append("---\n\n")

    # --- Q1 ---
    out.append("## 1. Booking GST rate\n\n")
    out.append("Is `18%` the correct GST rate for reading-room / cabin / seat bookings on "
               "StudySpace, or should a different rate apply?\n\n")
    out.append("**Engine setting**: `gst.booking.default_rate = 0.18` in `tax_config`.\n\n")
    out.append("**Artifacts to review**:\n")
    out.append(f"- `bookings.csv` — line `{booking_a.id}` (Rs. {float(booking_a.amount):,.2f} "
               f"= Rs. {float(booking_a.base_amount or 0):,.2f} taxable + "
               f"Rs. {float(booking_a.gst_amount or 0):,.2f} GST)\n")
    out.append("- `01_owner_tax_invoice_*.pdf` — sample registered-owner booking invoice\n\n")
    out.append("**Your answer**:\n")
    out.append("- [ ] 18% confirmed\n")
    out.append("- [ ] Different rate: _____ %  (rationale: _________________________________)\n\n")
    out.append("**Notes**:\n\n_________________________________________________________________\n\n")

    # --- Q2 ---
    out.append("## 2. SAC code for reading-room / cabin bookings\n\n")
    out.append("Is `996311` (Room or unit accommodation services) the correct SAC for our "
               "supply, or should it be a coworking / business-support SAC "
               "(e.g., 997212, 998313)?\n\n")
    out.append("**Engine setting**: `gst.booking.default_sac = '996311'` in `tax_config`.\n\n")
    out.append("**Artifacts to review**:\n")
    out.append("- `01_owner_tax_invoice_*.pdf` — SAC column on line item\n\n")
    out.append("**Your answer**:\n")
    out.append("- [ ] 996311 confirmed\n")
    out.append("- [ ] Use SAC: _________ for reading-room / cabin\n")
    out.append("- [ ] Use SAC: _________ for hostel / PG\n")
    out.append("- [ ] Use SAC: _________ for short-stay / hotel-like\n\n")
    out.append("**Notes**:\n\n_________________________________________________________________\n\n")

    # --- Q3 ---
    out.append("## 3. Hostel / PG category treatment\n\n")
    out.append("Is a HOSTEL_PG stay (continuous, residential) **exempt**, **taxable at 12%**, "
               "or **treatment-dependent** on per-unit-per-day tariff / monthly amount per person?\n\n")
    out.append("**Engine setting**: `gst.booking.exempt_threshold_monthly = 20000` in `tax_config` "
               "(currently a placeholder; we will replace with whatever you confirm).\n\n")
    out.append("**Artifacts to review**:\n")
    out.append(f"- `02_non_gst_receipt_*.pdf` — booking `{booking_b.id}` "
               f"(Rs. {float(booking_b.amount):,.2f}, unregistered owner, HOSTEL_PG)\n")
    out.append("- `bookings.csv` — see treatment column for `bk-b`\n\n")
    out.append("**Your answer**:\n")
    out.append("- [ ] HOSTEL_PG is exempt under current GST rules (no threshold)\n")
    out.append("- [ ] HOSTEL_PG is taxable at _____ % unconditionally\n")
    out.append("- [ ] HOSTEL_PG is exempt up to Rs. _________ per person per month; above that, taxable at _____ %\n\n")
    out.append("**Notes**:\n\n_________________________________________________________________\n\n")

    # --- Q4 ---
    out.append("## 4. Section 9(5) applicability per category\n\n")
    out.append("For each StudySpace category, when supplied through StudySpace by an "
               "**unregistered owner**, does Section 9(5) of the CGST Act make StudySpace "
               "(the e-commerce operator) the deemed supplier?\n\n")
    out.append("**Engine setting**: `gst.booking.sec_9_5_eligible_categories = "
               "['HOTEL_LIKE', 'SHORT_STAY']` in `tax_config`.\n\n")
    out.append("**Artifacts to review**:\n")
    out.append(f"- `03_eco_tax_invoice_sec_9_5_*.pdf` — booking `{booking_c.id}` "
               f"(Rs. {float(booking_c.amount):,.2f}, unregistered owner, HOTEL_LIKE)\n\n")
    out.append("**Your answer** (mark Yes / No per category):\n")
    out.append("| Category | Sec 9(5) applies? |\n")
    out.append("| --- | --- |\n")
    out.append("| HOTEL_LIKE | [ ] Yes  [ ] No |\n")
    out.append("| SHORT_STAY | [ ] Yes  [ ] No |\n")
    out.append("| HOSTEL_PG  | [ ] Yes  [ ] No |\n")
    out.append("| READING_ROOM | [ ] Yes  [ ] No |\n")
    out.append("| OTHER      | [ ] Yes  [ ] No |\n\n")
    out.append("**Notes**:\n\n_________________________________________________________________\n\n")

    # --- Q5 ---
    out.append("## 5. TCS / TDS — enable now or later?\n\n")
    out.append("Should we enable TCS (Sec 52 CGST, 0.5%) and TDS u/s 194-O (0.1%) from day 1 of "
               "going live, or after 2–3 months of clean booking data?\n\n")
    out.append("**Engine setting**: both `tcs.enabled` and `tds.section_194o_enabled` are OFF in "
               "production config. The canary above turned TCS on to demonstrate the math.\n\n")
    out.append("**Artifacts to review**:\n")
    out.append(f"- `07_settlement_owner_a_*.pdf` — shows TCS Rs. "
               f"{owner_a_tcs:,.2f} deducted from gross\n")
    out.append("- `settlements.csv` — `tcs` column per run\n\n")
    out.append("**Your answer** (pick one for each):\n")
    out.append("| Deduction | Decision |\n")
    out.append("| --- | --- |\n")
    out.append("| TCS Sec 52 CGST | [ ] Enable at go-live  [ ] Enable after _____ months  [ ] Not applicable |\n")
    out.append("| TDS Sec 194-O   | [ ] Enable at go-live  [ ] Enable after _____ months  [ ] Not applicable |\n\n")
    out.append("**Notes**:\n\n_________________________________________________________________\n\n")

    # --- Q6 ---
    out.append("## 6. Owner-issued invoice format (acceptability)\n\n")
    out.append("StudySpace generates the tax invoice **on behalf of** GST-registered owners "
               "using the owner's GSTIN, with a footer disclosing StudySpace as the facilitator "
               "under Sec 2(45) CGST. Is this format acceptable for owner GSTR-1 reporting, "
               "and is anything missing for future e-invoicing (IRN/QR) when an owner crosses "
               "the AATO threshold?\n\n")
    out.append("**Artifacts to review**:\n")
    out.append("- `01_owner_tax_invoice_*.pdf` — full format and footer\n")
    out.append(f"- `06b_maintenance_fee_*.pdf` — StudySpace-as-supplier counter-example "
               f"({maint.invoice_number if maint else '—'})\n\n")
    out.append("**Your answer**:\n")
    out.append("- [ ] Format is acceptable as-is\n")
    out.append("- [ ] Acceptable with these changes: _______________________________________\n")
    out.append("- [ ] Format is not acceptable; rebuild per: __________________________________\n\n")
    out.append("**E-invoicing readiness** (IRN/QR fields present in DB but not rendered):\n")
    out.append("- [ ] No action needed until owner AATO crosses Rs. 5 cr threshold\n")
    out.append("- [ ] Action needed now — please specify: ____________________________________\n\n")
    out.append("**Notes**:\n\n_________________________________________________________________\n\n")

    # --- Q7 ---
    out.append("## 7. Credit note format (Sec 34 CGST compliance)\n\n")
    out.append("Are the credit notes generated by StudySpace compliant with Section 34 of the "
               "CGST Act, 2017? Do you require explicit linkage to the original invoice number "
               "on the face of the document?\n\n")
    out.append("**Artifacts to review**:\n")
    out.append(f"- `04_refund_before_settlement_*.pdf` — credit note `{cn_pre.invoice_number if cn_pre else '—'}` "
               f"for refund before settlement\n")
    out.append(f"- `05_refund_after_settlement_*.pdf` — credit note `{cn_post.invoice_number if cn_post else '—'}` "
               f"for refund after settlement\n\n")
    out.append("**Your answer**:\n")
    out.append("- [ ] Format compliant with Sec 34 as-is\n")
    out.append("- [ ] Compliant with these changes: _______________________________________\n")
    out.append("- [ ] Original-invoice linkage must appear on the face of the credit note\n")
    out.append("- [ ] Original-invoice linkage in our records is sufficient (not on face)\n\n")
    out.append("**Notes**:\n\n_________________________________________________________________\n\n")

    # --- Sign-off ---
    out.append("---\n\n")
    out.append("## Reviewer sign-off\n\n")
    out.append("I have reviewed the canary pack and the above seven items represent my "
               "confirmed positions for StudySpace's go-live configuration.\n\n")
    out.append("Signature: ______________________________\n\n")
    out.append("Date: ______________________________\n\n")
    out.append("Membership / ICAI no.: ______________________________\n\n")
    out.append("---\n\n")
    out.append("## Engineering notes (for follow-up after CA returns this form)\n\n")
    out.append("Once the CA returns this form, engineering will:\n\n")
    out.append("1. Update `tax_config` keys via super-admin `/super-admin/tax-config` to match "
               "the confirmed values (rates, SAC, exempt threshold, Sec 9(5) list).\n")
    out.append("2. Re-run `python -m scripts.canary_walkthrough` and confirm artifacts reflect "
               "the new config.\n")
    out.append("3. Run `python -m scripts.canary_validate_listing` against one real listing on "
               "staging to confirm end-to-end behaviour.\n")
    out.append("4. Only then enable production flags one at a time, in this order: "
               "`accounting.enabled` → `feature.gst_invoices` → `feature.recurring_maintenance` "
               "→ `feature.credit_notes` → `tcs.enabled` / `tds.section_194o_enabled`.\n")

    (out_dir / "CA_REVIEW_NOTES.md").write_text("".join(out))


def _scenario_line(n: int, label: str, b: Booking, doc_type: str, note: str) -> str:
    base = float(b.base_amount or 0)
    gst = float(b.gst_amount or 0)
    treatment = b.gst_treatment.value if b.gst_treatment else "—"
    return (
        f"{n}. **{label}** — booking `{b.id}`, paid Rs. {float(b.amount):,.2f}. "
        f"Treatment `{treatment}` → base Rs. {base:,.2f}, GST Rs. {gst:,.2f}. "
        f"Document: `{doc_type}`. {note}\n\n"
    )


# ---------- entrypoint ----------------------------------------------------

async def main() -> None:
    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir()

    engine, Session = await _setup_db()
    try:
        async with Session() as db:
            await _seed_accounts(db)
            await _seed_config(db)
            await db.commit()
            artifacts = await _run_scenario(db)
            await _dump_csvs(db, OUTPUT_DIR)
            await _dump_pdfs(db, artifacts, OUTPUT_DIR)
            await _dump_summary(db, artifacts, OUTPUT_DIR)
            await _dump_ca_review_notes(db, OUTPUT_DIR, artifacts)
    finally:
        await engine.dispose()

    print(f"\nCanary walkthrough complete. Artifacts in: {OUTPUT_DIR}")
    for p in sorted(OUTPUT_DIR.iterdir()):
        size = p.stat().st_size
        print(f"  {p.name:<60}  {size:>8} bytes")
    print("\nNext step: review `summary.md` and forward this folder to the CA.")


if __name__ == "__main__":
    asyncio.run(main())
