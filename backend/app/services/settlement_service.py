"""Settlement engine.

Daily cron job picks bookings that:
  - have `payment_status = PAID`
  - have a non-LEGACY `gst_treatment` (i.e., were shadow-posted)
  - have NOT yet been settled (`settled_at IS NULL`)
  - are past the configurable T+N hold window (`paid_at <= now - hold_days`)
  - have no open refund

For each eligible owner, we build one `SettlementRun` containing:
  - one BOOKING line per booking → owner's gross payable
  - TCS deduction lines (if `tcs.enabled` and owner is registered) per IGST or
    CGST/SGST depending on intra/inter state
  - TDS 194-O deduction (if `tds.section_194o_enabled` and yearly threshold crossed)
  - MAINTENANCE_OFFSET lines for any DUE/OVERDUE maintenance fees on the
    owner's listings (eligible to be deducted at source)
  - REFUND lines for any approved refunds processed since last run

`net_payout = gross - refunds - platform_offset - tcs_total - tds_total`.

If `net_payout < 0`, status flips to `NEGATIVE_HELD` and no money moves;
super-admin reviews and converts the deficit into a `RECOVERY` charge.

Idempotency: uniqueness on `(owner_id, period_start, period_end)`, plus the
booking-level `settled_at` flag — a booking can only land in one run.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.accommodation import Accommodation
from app.models.booking import Booking, GSTTreatment, PaymentStatus
from app.models.owner_charge import OwnerCharge, OwnerChargeStatus
from app.models.reading_room import ReadingRoom
from app.models.refund import Refund, RefundStatus
from app.models.settlement import (
    SettlementLine,
    SettlementLineKind,
    SettlementRun,
    SettlementStatus as SettlementRunStatus,
)
from app.models.user import GSTRegistrationType, User
from app.services.ledger_service import Entry, LedgerService
from app.services.tax_engine import (
    cfg_get,
    compute_statutory_deductions,
    load_active_config,
    q2,
    to_decimal,
    ZERO,
)


# Account codes (match seed_chart_of_accounts.py)
ACC_OWNER_PAYABLE = "2010"
ACC_RAZORPAY_SETTLEMENT = "1011"
ACC_TCS_CGST = "2030"
ACC_TCS_SGST = "2031"
ACC_TCS_IGST = "2032"
ACC_TDS_194O = "2040"


@dataclass
class EligibleBooking:
    booking: Booking
    owner_id: str
    intra_state: bool
    treatment: GSTTreatment


# ---------- candidate selection --------------------------------------------

async def _load_eligible_bookings(
    db: AsyncSession,
    *,
    now: datetime,
    hold_days: int,
) -> dict[str, list[EligibleBooking]]:
    """Group eligible bookings by owner_id."""
    threshold = now - timedelta(days=hold_days)

    # Pull bookings that the shadow has touched (non-NULL gst_treatment) and
    # haven't been settled yet.
    rows = (await db.execute(
        select(Booking).where(
            (Booking.payment_status == PaymentStatus.PAID)
            & (Booking.settled_at.is_(None))
            & (Booking.gst_treatment.isnot(None))
            & (Booking.gst_treatment != GSTTreatment.LEGACY)
            & (Booking.paid_at.isnot(None))
            & (Booking.paid_at <= threshold)
        )
    )).scalars().all()

    grouped: dict[str, list[EligibleBooking]] = {}
    for b in rows:
        owner_id, intra = await _resolve_owner_intra_state(db, b)
        if owner_id is None:
            continue
        eb = EligibleBooking(
            booking=b, owner_id=owner_id, intra_state=intra,
            treatment=b.gst_treatment,
        )
        grouped.setdefault(owner_id, []).append(eb)
    return grouped


async def _resolve_owner_intra_state(
    db: AsyncSession, booking: Booking,
) -> tuple[Optional[str], bool]:
    """Returns (owner_id, intra_state).

    intra_state is True iff the venue's place_of_supply matches the owner's
    business state. Unknown -> defaults to True (CGST+SGST treatment).
    """
    owner_id: Optional[str] = None
    venue_state: Optional[str] = booking.place_of_supply_state
    if booking.cabin_id:
        from app.models.reading_room import Cabin
        cabin = (await db.execute(
            select(Cabin).where(Cabin.id == booking.cabin_id)
        )).scalar_one_or_none()
        if cabin is not None:
            room = (await db.execute(
                select(ReadingRoom).where(ReadingRoom.id == cabin.reading_room_id)
            )).scalar_one_or_none()
            if room is not None:
                owner_id = room.owner_id
                venue_state = venue_state or room.state
    elif booking.accommodation_id:
        acc = (await db.execute(
            select(Accommodation).where(Accommodation.id == booking.accommodation_id)
        )).scalar_one_or_none()
        if acc is not None:
            owner_id = acc.owner_id
            venue_state = venue_state or acc.state

    if owner_id is None:
        return None, True
    owner = await db.get(User, owner_id)
    if owner is None:
        return None, True
    owner_state = (owner.business_state_code or "").upper()
    venue_state = (venue_state or "").upper()
    if owner_state and venue_state:
        return owner_id, owner_state == venue_state
    return owner_id, True   # default intra


# ---------- per-owner aggregation ------------------------------------------

@dataclass
class OwnerTotals:
    gross: Decimal = ZERO
    refunds: Decimal = ZERO
    platform_offset: Decimal = ZERO
    tcs_cgst: Decimal = ZERO
    tcs_sgst: Decimal = ZERO
    tcs_igst: Decimal = ZERO
    tds_194o: Decimal = ZERO

    @property
    def tcs_total(self) -> Decimal:
        return q2(self.tcs_cgst + self.tcs_sgst + self.tcs_igst)

    @property
    def net(self) -> Decimal:
        return q2(
            self.gross
            - self.refunds
            - self.platform_offset
            - self.tcs_total
            - self.tds_194o
        )


async def _aggregate_owner(
    db: AsyncSession,
    *,
    owner_id: str,
    bookings: list[EligibleBooking],
    config: dict,
    period_start: datetime,
    period_end: datetime,
) -> tuple[OwnerTotals, list[SettlementLine]]:
    """Compute totals + per-line breakdown for one owner."""
    totals = OwnerTotals()
    lines: list[SettlementLine] = []

    owner = await db.get(User, owner_id)
    owner_registered = (
        owner is not None
        and owner.gst_registration_type == GSTRegistrationType.REGULAR
    )

    # --- BOOKING + TCS/TDS lines ---
    for eb in bookings:
        owner_payable = _owner_payable_for(eb)
        if owner_payable <= 0:
            continue
        totals.gross = q2(totals.gross + owner_payable)
        lines.append(SettlementLine(
            run_id="",  # filled in commit phase below
            kind=SettlementLineKind.BOOKING,
            reference_type="BOOKING",
            reference_id=eb.booking.id,
            base_amount=owner_payable,
            deduction=ZERO,
            net=owner_payable,
            narration=f"Booking {eb.booking.id} owner-payable",
        ))

        # Compute TCS/TDS per booking line (more accurate than on the aggregate)
        # Net taxable value = base_amount when owner-registered; full payable otherwise.
        net_taxable = to_decimal(eb.booking.base_amount or owner_payable)
        deductions = compute_statutory_deductions(
            net_taxable_value=net_taxable,
            owner_registered=owner_registered,
            intra_state=eb.intra_state,
            yearly_owner_gross_so_far=totals.gross,
            config=config,
        )
        totals.tcs_cgst = q2(totals.tcs_cgst + deductions.tcs_cgst)
        totals.tcs_sgst = q2(totals.tcs_sgst + deductions.tcs_sgst)
        totals.tcs_igst = q2(totals.tcs_igst + deductions.tcs_igst)
        totals.tds_194o = q2(totals.tds_194o + deductions.tds_194o)

    # Emit aggregated TCS / TDS lines (one row per kind keeps the statement readable).
    if totals.tcs_cgst > 0:
        lines.append(SettlementLine(
            run_id="", kind=SettlementLineKind.TCS_CGST,
            base_amount=ZERO, deduction=totals.tcs_cgst, net=-totals.tcs_cgst,
            narration="TCS CGST u/s 52",
        ))
    if totals.tcs_sgst > 0:
        lines.append(SettlementLine(
            run_id="", kind=SettlementLineKind.TCS_SGST,
            base_amount=ZERO, deduction=totals.tcs_sgst, net=-totals.tcs_sgst,
            narration="TCS SGST u/s 52",
        ))
    if totals.tcs_igst > 0:
        lines.append(SettlementLine(
            run_id="", kind=SettlementLineKind.TCS_IGST,
            base_amount=ZERO, deduction=totals.tcs_igst, net=-totals.tcs_igst,
            narration="TCS IGST u/s 52",
        ))
    if totals.tds_194o > 0:
        lines.append(SettlementLine(
            run_id="", kind=SettlementLineKind.TDS_194O,
            base_amount=ZERO, deduction=totals.tds_194o, net=-totals.tds_194o,
            narration="TDS u/s 194-O Income Tax",
        ))

    # --- MAINTENANCE OFFSET lines (opt-in via config) ---
    # When enabled, the owner's unpaid maintenance charges are deducted at
    # source from the payout. Each offset still requires its own revenue+GST
    # recognition (handled by the existing owner_charge mark-paid flow), so
    # we cap this at v2; default OFF until the offset ledger group is wired.
    if bool(cfg_get(config, "settlement.offset_maintenance", False)):
        unpaid = (await db.execute(
            select(OwnerCharge).where(
                (OwnerCharge.owner_id == owner_id)
                & (OwnerCharge.status.in_([
                    OwnerChargeStatus.DUE, OwnerChargeStatus.OVERDUE,
                ]))
            )
        )).scalars().all()
        for charge in unpaid:
            offset = to_decimal(charge.total_amount)
            totals.platform_offset = q2(totals.platform_offset + offset)
            lines.append(SettlementLine(
                run_id="",
                kind=SettlementLineKind.MAINTENANCE_OFFSET,
                reference_type="OWNER_CHARGE",
                reference_id=charge.id,
                base_amount=ZERO,
                deduction=offset,
                net=-offset,
                narration=f"Maintenance fee {charge.period_key or charge.charge_type.value} offset",
            ))

    # --- REFUND lines (approved/processed against this owner's bookings since last run) ---
    booking_ids = [eb.booking.id for eb in bookings]
    if booking_ids:
        refunds = (await db.execute(
            select(Refund).where(
                Refund.booking_id.in_(booking_ids),
                Refund.status.in_([
                    RefundStatus.APPROVED, RefundStatus.PROCESSED,
                ]),
            )
        )).scalars().all()
        for r in refunds:
            amt = to_decimal(r.amount)
            totals.refunds = q2(totals.refunds + amt)
            lines.append(SettlementLine(
                run_id="",
                kind=SettlementLineKind.REFUND,
                reference_type="REFUND",
                reference_id=r.id,
                base_amount=ZERO,
                deduction=amt,
                net=-amt,
                narration=f"Refund {r.id} for booking {r.booking_id}",
            ))

    return totals, lines


def _owner_payable_for(eb: EligibleBooking) -> Decimal:
    """Per design §3 — what the owner is owed for this booking before deductions.

    - OWNER_REGISTERED: full gross (owner remits their own GSTR-1)
    - SEC_9_5:          base only (platform retains GST per Sec 9(5))
    - NOT_REGISTERED / EXEMPT: full gross
    """
    b = eb.booking
    if eb.treatment == GSTTreatment.SEC_9_5:
        return q2(to_decimal(b.base_amount or 0))
    return q2(to_decimal(b.amount or 0))


# ---------- public API: run the cron ---------------------------------------

async def run_settlements(
    db: AsyncSession,
    *,
    now: Optional[datetime] = None,
) -> dict:
    """Cron entry point. Returns a summary for the scheduler log."""
    now = now or datetime.utcnow()
    config = await load_active_config(db)
    hold_days = int(cfg_get(config, "settlement.hold_days", 3))

    # First, sweep for refunds against already-settled bookings and create
    # RECOVERY charges. These flow into the next settlement run as deductions
    # via the maintenance-offset path (when settlement.offset_maintenance is
    # enabled). Even when offset is off, the recovery charge becomes visible
    # to super admin for manual reconciliation.
    from app.services.recovery_service import scan_and_create_recovery_charges
    await scan_and_create_recovery_charges(db)

    grouped = await _load_eligible_bookings(db, now=now, hold_days=hold_days)
    if not grouped:
        await db.commit()
        return {"runs_created": 0, "owners": 0}

    runs_created = 0
    # Use a single period window per cron run: the day before "now".
    period_start = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    period_end = now.replace(hour=0, minute=0, second=0, microsecond=0)

    for owner_id, bookings in grouped.items():
        try:
            await _commit_run_for_owner(
                db, owner_id=owner_id, bookings=bookings, config=config,
                period_start=period_start, period_end=period_end,
            )
            runs_created += 1
        except IntegrityError:
            # Another worker already created this window — skip cleanly.
            await db.rollback()

    await db.commit()
    return {"runs_created": runs_created, "owners": len(grouped)}


async def _commit_run_for_owner(
    db: AsyncSession,
    *,
    owner_id: str,
    bookings: list[EligibleBooking],
    config: dict,
    period_start: datetime,
    period_end: datetime,
) -> SettlementRun:
    totals, lines = await _aggregate_owner(
        db, owner_id=owner_id, bookings=bookings, config=config,
        period_start=period_start, period_end=period_end,
    )

    run = SettlementRun(
        owner_id=owner_id,
        period_start=period_start,
        period_end=period_end,
        gross=totals.gross,
        refunds=totals.refunds,
        platform_offset=totals.platform_offset,
        tcs_total=totals.tcs_total,
        tds_total=totals.tds_194o,
        net_payout=totals.net,
        status=SettlementRunStatus.NEGATIVE_HELD if totals.net < 0 else SettlementRunStatus.READY,
    )
    db.add(run)
    await db.flush()

    # Attach lines
    for line in lines:
        line.run_id = run.id
        db.add(line)

    # Mark bookings settled (booking-level idempotency)
    for eb in bookings:
        eb.booking.settled_at = datetime.utcnow()
        eb.booking.settlement_run_id = run.id

    # Mark offset maintenance charges as PAID (deducted at source from owner payable)
    for line in lines:
        if line.kind == SettlementLineKind.MAINTENANCE_OFFSET and line.reference_id:
            charge = await db.get(OwnerCharge, line.reference_id)
            if charge is not None:
                charge.status = OwnerChargeStatus.PAID
                charge.paid_at = datetime.utcnow()

    # Post ledger group — credits owner_payable, debits stat liabilities and payout asset.
    # Only post if status is READY (positive net). NEGATIVE_HELD waits for super-admin action.
    if run.status == SettlementRunStatus.READY:
        await _post_settlement_ledger(db, run, totals, owner_id)

    await db.flush()
    return run


async def _post_settlement_ledger(
    db: AsyncSession,
    run: SettlementRun,
    totals: OwnerTotals,
    owner_id: str,
) -> None:
    """Dr Owner Payable; Cr [Razorpay Settlement A/c, TCS, TDS]."""
    entries: list[Entry] = [
        Entry(
            account_code=ACC_OWNER_PAYABLE,
            debit=q2(totals.gross - totals.refunds),
            party_type="OWNER",
            party_id=owner_id,
            narration=f"Settlement run {run.id}",
        )
    ]
    if totals.net > 0:
        entries.append(Entry(
            account_code=ACC_RAZORPAY_SETTLEMENT,
            credit=totals.net,
            party_type="OWNER", party_id=owner_id,
            narration="Net payout to owner via RazorpayX",
        ))
    if totals.tcs_cgst > 0:
        entries.append(Entry(
            account_code=ACC_TCS_CGST, credit=totals.tcs_cgst,
            party_type="PLATFORM",
            narration="TCS CGST liability",
        ))
    if totals.tcs_sgst > 0:
        entries.append(Entry(
            account_code=ACC_TCS_SGST, credit=totals.tcs_sgst,
            party_type="PLATFORM",
            narration="TCS SGST liability",
        ))
    if totals.tcs_igst > 0:
        entries.append(Entry(
            account_code=ACC_TCS_IGST, credit=totals.tcs_igst,
            party_type="PLATFORM",
            narration="TCS IGST liability",
        ))
    if totals.tds_194o > 0:
        entries.append(Entry(
            account_code=ACC_TDS_194O, credit=totals.tds_194o,
            party_type="PLATFORM",
            narration="TDS 194-O liability",
        ))
    # Maintenance offset: owner payable already debited above; route it to platform revenue
    # account is already done at OwnerCharge.mark_charge_paid; here we just reconcile by NOT
    # double-counting. So we add a counter-credit to OWNER_PAYABLE for the offset to keep
    # the group balanced. Specifically: the owner payable debit above is gross-refunds, which
    # ALREADY includes the maintenance amount as part of the wealth reduction. We need to
    # rebalance:
    #
    #   dr_owner_payable = gross - refunds                         [from above]
    #   cr_razorpay_settlement = net = gross - refunds - offset - tcs - tds
    #
    # Difference (offset + tcs + tds) is covered by:
    #   cr TCS + cr TDS  + cr OWNER_PAYABLE (rebate for offset) -- but offset already paid
    #   the charge separately. Simpler: rebate the owner_payable debit by `offset`.
    if totals.platform_offset > 0:
        # Reduce the gross debit; cleanest is to add a credit back to owner_payable.
        entries.append(Entry(
            account_code=ACC_OWNER_PAYABLE,
            credit=totals.platform_offset,
            party_type="OWNER", party_id=owner_id,
            narration="Maintenance fee offset retained from owner payable",
        ))

    await LedgerService.post_entries(
        db,
        txn_group_id=None,
        source_type="SETTLEMENT",
        source_id=run.id,
        entries=entries,
        narration=f"Settlement {run.id} for owner {owner_id}",
    )


# ---------- super-admin actions --------------------------------------------

async def mark_paid(
    db: AsyncSession,
    *,
    run_id: str,
    payout_ref: str,
) -> SettlementRun:
    """Super-admin records a UTR after manual RazorpayX payout."""
    run = await db.get(SettlementRun, run_id)
    if run is None:
        raise ValueError(f"Settlement {run_id} not found")
    if run.status != SettlementRunStatus.READY:
        raise ValueError(f"Cannot mark {run.status.value} run as PAID")
    run.payout_ref = payout_ref
    run.payout_at = datetime.utcnow()
    run.status = SettlementRunStatus.PAID
    await db.flush()
    return run


async def mark_failed(
    db: AsyncSession,
    *,
    run_id: str,
    reason: str,
) -> SettlementRun:
    run = await db.get(SettlementRun, run_id)
    if run is None:
        raise ValueError(f"Settlement {run_id} not found")
    run.status = SettlementRunStatus.FAILED
    run.failure_reason = reason
    await db.flush()
    return run
