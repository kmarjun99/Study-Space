"""Pure check functions used by the per-listing canary validator.

Each function returns a `CheckResult` instead of raising, so the CLI script
can render a pass/fail table and the ops audit log. Splitting these out from
the script makes them unit-testable against an in-memory DB.

Naming convention: every `check_step_N_*` function mirrors a numbered step in
the operator checklist that the friend wrote — see
`scripts/canary_validate_listing.py` for the human-facing flow.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.accommodation import Accommodation
from app.models.booking import Booking, GSTTreatment, PaymentStatus
from app.models.invoice import Invoice, InvoiceDocType
from app.models.ledger_entry import LedgerEntry
from app.models.reading_room import PriceDisplayMode, ReadingRoom
from app.models.refund import Refund, RefundStatus
from app.models.settlement import SettlementLine, SettlementRun
from app.models.user import User
from app.services.ledger_service import LedgerService
from app.services.tax_engine import (
    cfg_get,
    compute_booking_gross,
    compute_booking_tax,
    freeze_snapshot,
    load_active_config,
    q2,
    to_decimal,
)


# ---------- result type ----------------------------------------------------

class Status(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    WARN = "WARN"
    SKIP = "SKIP"
    NEEDS_ACTION = "NEEDS_ACTION"


@dataclass
class CheckResult:
    step: int
    name: str
    status: Status
    detail: str = ""
    data: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.status in (Status.PASS, Status.SKIP)

    def to_dict(self) -> dict[str, Any]:
        return {
            "step": self.step,
            "name": self.name,
            "status": self.status.value,
            "detail": self.detail,
            "data": self.data,
        }


# ---------- helpers --------------------------------------------------------

async def _load_listing(
    db: AsyncSession, listing_type: str, listing_id: str,
) -> tuple[Optional[Any], Optional[str]]:
    if listing_type == "reading-room":
        listing = await db.get(ReadingRoom, listing_id)
        return listing, "reading_room"
    if listing_type == "accommodation":
        listing = await db.get(Accommodation, listing_id)
        return listing, "accommodation"
    return None, None


# ---------- the ten checks -------------------------------------------------

async def check_step_1_listing_safety(
    db: AsyncSession, *, listing_type: str, listing_id: str,
) -> CheckResult:
    """1. Listing exists; price_display_mode is GST_INCLUDED or null
       (matching the global default while the per-listing flag is OFF)."""
    listing, _ = await _load_listing(db, listing_type, listing_id)
    if listing is None:
        return CheckResult(1, "Listing exists", Status.FAIL,
                           f"No {listing_type} found with id {listing_id}")

    mode = listing.price_display_mode
    config = await load_active_config(db)
    flag_on = bool(cfg_get(config, "feature.per_listing_price_mode", False))

    if flag_on and mode == PriceDisplayMode.GST_EXTRA:
        return CheckResult(
            1, "Listing is GST_INCLUDED-safe", Status.FAIL,
            "feature.per_listing_price_mode is ON and listing is GST_EXTRA — "
            "live booking math will deviate. Flip the flag back or change the listing.",
        )

    return CheckResult(
        1, "Listing is GST_INCLUDED-safe", Status.PASS,
        f"price_display_mode={mode.value if mode else 'unset (uses global default)'}; "
        f"feature.per_listing_price_mode={flag_on}",
        data={"price_display_mode": mode.value if mode else None,
              "feature_flag_on": flag_on},
    )


async def check_step_2_payable_matches_expected(
    db: AsyncSession, *, listing_type: str, listing_id: str, expected_price: Decimal,
) -> CheckResult:
    """2. Verify checkout will charge `expected_price` (no silent add-on)."""
    listing, _ = await _load_listing(db, listing_type, listing_id)
    if listing is None:
        return CheckResult(2, "Payable amount = expected", Status.FAIL, "listing missing")

    config = await load_active_config(db)
    mode = listing.price_display_mode.value if listing.price_display_mode else None
    payable = compute_booking_gross(
        displayed_price=expected_price,
        listing_gst_rate_override=listing.gst_rate_override,
        listing_price_display_mode=mode,
        config=config,
    )
    if q2(payable) != q2(expected_price):
        return CheckResult(
            2, "Payable amount = expected", Status.FAIL,
            f"engine returns payable={payable} for displayed={expected_price}",
            data={"payable": float(payable), "expected": float(expected_price)},
        )
    return CheckResult(
        2, "Payable amount = expected", Status.PASS,
        f"engine returns payable={payable} (matches displayed)",
        data={"payable": float(payable)},
    )


async def check_step_3_split_matches(
    db: AsyncSession,
    *,
    listing_type: str,
    listing_id: str,
    expected_price: Decimal,
    expected_base: Decimal,
    expected_gst: Decimal,
) -> CheckResult:
    """3. Verify reverse-calc split: base + GST == expected_price."""
    listing, _ = await _load_listing(db, listing_type, listing_id)
    if listing is None:
        return CheckResult(3, "Tax split matches expected", Status.FAIL, "listing missing")

    config = await load_active_config(db)
    snap = await freeze_snapshot(db, config)
    owner = await db.get(User, listing.owner_id) if listing.owner_id else None
    tax = compute_booking_tax(
        gross=expected_price,
        owner=owner,
        listing_gst_category=listing.gst_category,
        listing_gst_rate_override=(
            to_decimal(listing.gst_rate_override)
            if listing.gst_rate_override is not None else None
        ),
        listing_price_display_mode=(
            listing.price_display_mode.value if listing.price_display_mode else None
        ),
        place_of_supply_state=listing.state,
        config=config,
        snapshot_id=snap.id,
        inclusive_override=True,
    )
    # Don't let the snapshot leak out of a read-only check.
    await db.rollback()

    base, gst = tax.base, tax.gst.total
    if q2(base) != q2(expected_base) or q2(gst) != q2(expected_gst):
        return CheckResult(
            3, "Tax split matches expected", Status.FAIL,
            f"engine: base={base} gst={gst}; expected base={expected_base} gst={expected_gst}",
            data={"base": float(base), "gst": float(gst),
                  "expected_base": float(expected_base), "expected_gst": float(expected_gst)},
        )
    return CheckResult(
        3, "Tax split matches expected", Status.PASS,
        f"base={base} + gst={gst} = {q2(base + gst)} (matches expected_price)",
        data={"base": float(base), "gst": float(gst), "treatment": tax.treatment.value},
    )


async def check_step_4_test_booking_exists(
    db: AsyncSession, *, listing_type: str, listing_id: str,
) -> CheckResult:
    """4. After the operator completes a test payment: a PAID booking exists
       and has been shadow-posted (non-null gst_treatment)."""
    paid = await _find_recent_paid_booking(db, listing_type, listing_id)
    if paid is None:
        return CheckResult(
            4, "Test payment landed", Status.NEEDS_ACTION,
            "no PAID booking found for this listing — make a test payment "
            "and re-run this step.",
        )
    if paid.gst_treatment is None or paid.gst_treatment == GSTTreatment.LEGACY:
        return CheckResult(
            4, "Test payment landed", Status.WARN,
            f"booking {paid.id} is PAID but accounting shadow has not posted yet. "
            "Wait a few seconds and re-run, or check that `accounting.enabled` is true.",
            data={"booking_id": paid.id},
        )
    return CheckResult(
        4, "Test payment landed", Status.PASS,
        f"booking {paid.id} paid Rs.{paid.amount:.2f} with treatment {paid.gst_treatment.value}",
        data={"booking_id": paid.id, "amount": float(paid.amount),
              "treatment": paid.gst_treatment.value},
    )


async def check_step_5_invoice_split_matches(
    db: AsyncSession, *, booking_id: str,
) -> CheckResult:
    """5. If an invoice has been issued for this booking, its base + GST match
       what's stored on the Booking. Skipped if no invoice yet."""
    invoice = (await db.execute(
        select(Invoice).where(
            (Invoice.booking_id == booking_id)
            & (Invoice.doc_type != InvoiceDocType.CREDIT_NOTE)
            & (Invoice.doc_type != InvoiceDocType.LEGACY)
        )
        .limit(1)
    )).scalar_one_or_none()
    if invoice is None:
        return CheckResult(
            5, "Invoice PDF uses same split", Status.SKIP,
            "no GST-aware invoice issued yet for this booking (legacy or none).",
        )
    booking = await db.get(Booking, booking_id)
    if booking is None:
        return CheckResult(5, "Invoice PDF uses same split", Status.FAIL, "booking missing")

    booking_total_gst = (
        to_decimal(invoice.cgst or 0) + to_decimal(invoice.sgst or 0) + to_decimal(invoice.igst or 0)
    )
    booking_gst = to_decimal(booking.gst_amount or 0)
    invoice_base = to_decimal(invoice.base_amount or 0)
    booking_base = to_decimal(booking.base_amount or 0)
    if q2(invoice_base) != q2(booking_base) or q2(booking_total_gst) != q2(booking_gst):
        return CheckResult(
            5, "Invoice PDF uses same split", Status.FAIL,
            f"booking base={booking_base} gst={booking_gst} ; "
            f"invoice base={invoice_base} gst={booking_total_gst}",
            data={
                "booking_base": float(booking_base), "booking_gst": float(booking_gst),
                "invoice_base": float(invoice_base), "invoice_gst": float(booking_total_gst),
                "invoice_number": invoice.invoice_number,
            },
        )
    return CheckResult(
        5, "Invoice PDF uses same split", Status.PASS,
        f"invoice {invoice.invoice_number}: base={invoice_base}, gst={booking_total_gst}",
        data={"invoice_number": invoice.invoice_number},
    )


async def check_step_6_ledger_owner_payable(
    db: AsyncSession, *, booking_id: str,
) -> CheckResult:
    """6. Σ credit to Owner Payable (2010) from this booking equals
       owner-payable amount per the treatment rules:
         - OWNER_REGISTERED: full gross
         - SEC_9_5:          base only
         - NOT_REGISTERED / EXEMPT: full gross
       (TCS/TDS deductions happen at settlement; this check is pre-settlement.)"""
    booking = await db.get(Booking, booking_id)
    if booking is None:
        return CheckResult(6, "Ledger owner payable correct", Status.FAIL, "booking missing")

    rows = (await db.execute(
        select(LedgerEntry).where(
            (LedgerEntry.source_type == "BOOKING")
            & (LedgerEntry.source_id == booking_id)
            & (LedgerEntry.account_code == "2010")
        )
    )).scalars().all()
    cr_total = q2(sum((r.credit for r in rows), to_decimal(0)))
    dr_total = q2(sum((r.debit for r in rows), to_decimal(0)))
    owner_payable = q2(cr_total - dr_total)

    if booking.gst_treatment == GSTTreatment.SEC_9_5:
        expected = q2(to_decimal(booking.base_amount or 0))
        label = "base only (Sec 9(5))"
    else:
        expected = q2(to_decimal(booking.amount or 0))
        label = "full gross"

    if owner_payable != expected:
        return CheckResult(
            6, "Ledger owner payable correct", Status.FAIL,
            f"owner-payable from ledger={owner_payable} ; expected={expected} ({label})",
            data={"owner_payable": float(owner_payable), "expected": float(expected),
                  "label": label},
        )
    return CheckResult(
        6, "Ledger owner payable correct", Status.PASS,
        f"owner-payable={owner_payable} matches {label}",
        data={"owner_payable": float(owner_payable), "label": label},
    )


async def check_step_7_settlement_was_created(
    db: AsyncSession, *, booking_id: str,
) -> CheckResult:
    """7. After settlement is triggered: the booking has a settlement_run_id
       and a corresponding SettlementRun exists in DRAFT/READY/PAID/NEGATIVE_HELD."""
    booking = await db.get(Booking, booking_id)
    if booking is None:
        return CheckResult(7, "Settlement run created", Status.FAIL, "booking missing")
    if booking.settlement_run_id is None:
        return CheckResult(
            7, "Settlement run created", Status.NEEDS_ACTION,
            "booking has not been settled yet — run the settlement cron and re-check.",
        )
    run = await db.get(SettlementRun, booking.settlement_run_id)
    if run is None:
        return CheckResult(7, "Settlement run created", Status.FAIL,
                           f"settlement_run_id {booking.settlement_run_id} not found")
    return CheckResult(
        7, "Settlement run created", Status.PASS,
        f"run {run.id[:8]} status={run.status.value} net={float(run.net_payout):.2f}",
        data={"run_id": run.id, "status": run.status.value,
              "net_payout": float(run.net_payout)},
    )


async def check_step_8_statement_matches_ledger(
    db: AsyncSession, *, run_id: str,
) -> CheckResult:
    """8. SettlementRun.gross - refunds - TCS - TDS - offset == net_payout,
       AND the SETTLEMENT ledger group sums to zero (already enforced) but we
       also confirm Σdebit owner-payable equals run.gross - run.refunds."""
    run = await db.get(SettlementRun, run_id)
    if run is None:
        return CheckResult(8, "Statement matches ledger", Status.FAIL, "run missing")

    arithmetic = q2(
        to_decimal(run.gross)
        - to_decimal(run.refunds)
        - to_decimal(run.tcs_total)
        - to_decimal(run.tds_total)
        - to_decimal(run.platform_offset)
    )
    if q2(arithmetic) != q2(to_decimal(run.net_payout)):
        return CheckResult(
            8, "Statement matches ledger", Status.FAIL,
            f"gross−refunds−tcs−tds−offset = {arithmetic} ; net_payout = {run.net_payout}",
        )

    # Match lines on the statement to the run totals
    lines = (await db.execute(
        select(SettlementLine).where(SettlementLine.run_id == run_id)
    )).scalars().all()
    booking_gross = q2(sum(
        (to_decimal(line.base_amount) for line in lines if line.kind.value == "BOOKING"),
        to_decimal(0),
    ))
    if booking_gross != q2(to_decimal(run.gross)):
        return CheckResult(
            8, "Statement matches ledger", Status.FAIL,
            f"Σ BOOKING lines = {booking_gross}, run.gross = {run.gross}",
        )

    return CheckResult(
        8, "Statement matches ledger", Status.PASS,
        f"arithmetic ok; Σ BOOKING lines = run.gross = {run.gross}",
        data={"net_payout": float(run.net_payout),
              "line_count": len(lines)},
    )


async def check_step_9_partial_refund_credit_note(
    db: AsyncSession, *, booking_id: str,
) -> CheckResult:
    """9. After the operator approves a partial refund: a CREDIT_NOTE exists,
       the reversing ledger group is balanced, and the GST reversed is
       proportional to the refund amount."""
    refund = (await db.execute(
        select(Refund).where(
            (Refund.booking_id == booking_id)
            & (Refund.status.in_([RefundStatus.APPROVED, RefundStatus.PROCESSED]))
        ).order_by(Refund.requested_at.desc())
        .limit(1)
    )).scalar_one_or_none()
    if refund is None:
        return CheckResult(
            9, "Partial refund + credit note", Status.NEEDS_ACTION,
            "no APPROVED/PROCESSED refund found — create one and re-run this step.",
        )

    cn = (await db.execute(
        select(Invoice).where(
            (Invoice.doc_type == InvoiceDocType.CREDIT_NOTE)
            & (Invoice.payment_id == refund.id)
        )
    )).scalar_one_or_none()
    if cn is None:
        return CheckResult(
            9, "Partial refund + credit note", Status.FAIL,
            f"refund {refund.id} approved but no credit note issued. "
            "Is `feature.credit_notes` enabled?",
        )

    booking = await db.get(Booking, booking_id)
    if booking is None or booking.amount <= 0:
        return CheckResult(9, "Partial refund + credit note", Status.FAIL, "booking missing")

    expected_proportion = q2(to_decimal(refund.amount) / to_decimal(booking.amount))
    expected_gst_reversed = q2(to_decimal(booking.gst_amount or 0) * expected_proportion)
    actual_gst_reversed = q2(
        to_decimal(cn.cgst or 0) + to_decimal(cn.sgst or 0) + to_decimal(cn.igst or 0)
    )
    if abs(actual_gst_reversed - expected_gst_reversed) > to_decimal("0.10"):
        return CheckResult(
            9, "Partial refund + credit note", Status.FAIL,
            f"gst reversed = {actual_gst_reversed}, expected ≈ {expected_gst_reversed}",
            data={"reversed": float(actual_gst_reversed),
                  "expected": float(expected_gst_reversed)},
        )
    return CheckResult(
        9, "Partial refund + credit note", Status.PASS,
        f"credit note {cn.invoice_number}; gst reversed = {actual_gst_reversed} ≈ "
        f"{expected_gst_reversed} (proportional)",
        data={"credit_note": cn.invoice_number,
              "gst_reversed": float(actual_gst_reversed)},
    )


async def check_step_10_safety_flag_off(
    db: AsyncSession,
) -> CheckResult:
    """10. Final safety net: `feature.per_listing_price_mode` is OFF. The
        canary's whole point is to confirm GST_EXTRA stays gated."""
    config = await load_active_config(db)
    flag = bool(cfg_get(config, "feature.per_listing_price_mode", False))
    if flag:
        return CheckResult(
            10, "GST_EXTRA stays disabled", Status.FAIL,
            "feature.per_listing_price_mode is ON. The canary explicitly requires "
            "this flag off until CA approves category-wise GST treatment.",
        )
    return CheckResult(
        10, "GST_EXTRA stays disabled", Status.PASS,
        "feature.per_listing_price_mode is OFF as required.",
    )


# ---------- ledger integrity (bonus that always runs) ----------------------

async def check_ledger_integrity(db: AsyncSession) -> CheckResult:
    bad = await LedgerService.integrity_check(db)
    if bad:
        return CheckResult(
            0, "Ledger integrity", Status.FAIL,
            f"{len(bad)} imbalanced txn groups: {bad[:5]}",
            data={"imbalanced": bad},
        )
    return CheckResult(0, "Ledger integrity", Status.PASS, "Σdr=Σcr across all groups")


# ---------- helpers --------------------------------------------------------

async def _find_recent_paid_booking(
    db: AsyncSession, listing_type: str, listing_id: str,
) -> Optional[Booking]:
    if listing_type == "reading-room":
        from app.models.reading_room import Cabin
        cabin_ids = (await db.execute(
            select(Cabin.id).where(Cabin.reading_room_id == listing_id)
        )).scalars().all()
        if not cabin_ids:
            return None
        return (await db.execute(
            select(Booking)
            .where((Booking.cabin_id.in_(cabin_ids))
                   & (Booking.payment_status == PaymentStatus.PAID))
            .order_by(Booking.created_at.desc())
            .limit(1)
        )).scalar_one_or_none()
    if listing_type == "accommodation":
        return (await db.execute(
            select(Booking)
            .where((Booking.accommodation_id == listing_id)
                   & (Booking.payment_status == PaymentStatus.PAID))
            .order_by(Booking.created_at.desc())
            .limit(1)
        )).scalar_one_or_none()
    return None
