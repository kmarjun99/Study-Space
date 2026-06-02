"""Credit-note issuance + ledger reversal for approved refunds.

When a refund is APPROVED (super-admin action), this service:
  1. Allocates a fresh CN/{FY}/NNNNNN sequential number
  2. Creates an `Invoice` row with `doc_type=CREDIT_NOTE` referencing the
     original booking invoice (if any)
  3. Posts a *reversing* ledger group: Dr Owner Payable / Cr Razorpay Receivable
     (with proportional GST output reversal for SEC_9_5 bookings)

Idempotent via `LedgerService` source-id check: re-approving a refund (or
running the migration twice) cannot produce two credit notes for the same
refund.

Feature-flagged behind `feature.credit_notes` so existing refund flow keeps
working bit-for-bit until super admin opts in.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.accommodation import Accommodation
from app.models.booking import Booking, GSTTreatment
from app.models.invoice import Invoice, InvoiceDocType
from app.models.party import Party
from app.models.reading_room import Cabin, ReadingRoom
from app.models.refund import Refund
from app.models.user import User
from app.services.invoice_series_service import InvoiceSeriesService
from app.services.ledger_service import Entry, LedgerService
from app.services.tax_engine import (
    cfg_get,
    load_active_config,
    q2,
    split_gst_by_state,
    to_decimal,
)


SERIES_CREDIT_NOTE = "CN"

ACC_RAZORPAY_RECEIVABLE = "1010"
ACC_OWNER_PAYABLE = "2010"
ACC_GST_OUT_CGST = "2020"
ACC_GST_OUT_SGST = "2021"
ACC_GST_OUT_IGST = "2022"


async def credit_notes_enabled(db: AsyncSession) -> bool:
    config = await load_active_config(db)
    return bool(cfg_get(config, "feature.credit_notes", False))


async def issue_for_refund(
    db: AsyncSession, *, refund_id: str,
) -> Optional[Invoice]:
    """Create the CREDIT_NOTE doc + post reversing ledger for one refund.

    Returns the Invoice row on success, None if:
      - feature flag is off
      - refund not found
      - booking not found (e.g., legacy)
      - already issued (idempotent short-circuit)
    """
    if not await credit_notes_enabled(db):
        return None

    refund = await db.get(Refund, refund_id)
    if refund is None:
        return None

    # Idempotent: short-circuit if a CN already exists for this refund.
    existing = (await db.execute(
        select(Invoice).where(
            (Invoice.doc_type == InvoiceDocType.CREDIT_NOTE)
            & (Invoice.payment_id == refund.id)
        )
    )).scalar_one_or_none()
    if existing is not None:
        return existing

    booking = await db.get(Booking, refund.booking_id)
    if booking is None:
        return None

    # Resolve venue/owner/student context — same shape as accounting_shadow.
    owner, venue_name, venue_state, place_state = await _resolve_context(db, booking)

    # Owner-party + student-party snapshots
    owner_party = await _owner_party(db, owner) if owner else None
    student_party = await _student_party(db, booking.user_id)

    # Proportional reversal of the original booking tax breakdown
    refund_amt = to_decimal(refund.amount)
    orig_gross = to_decimal(booking.amount or 0)
    if orig_gross <= 0:
        proportion = Decimal("0")
    else:
        proportion = (refund_amt / orig_gross).quantize(Decimal("0.000001"))

    base_reversed = q2(to_decimal(booking.base_amount or 0) * proportion)
    gst_reversed = q2(to_decimal(booking.gst_amount or 0) * proportion)
    if base_reversed + gst_reversed != refund_amt:
        # Pin remainder onto base so reversed total exactly matches refund amount.
        base_reversed = q2(refund_amt - gst_reversed)

    gst_split = split_gst_by_state(
        gst_reversed,
        supplier_state=(owner.business_state_code if owner else None),
        recipient_state=place_state,
    )

    # Allocate doc number
    invoice_no, fy, seq = await InvoiceSeriesService.next_number(
        db, series_code=SERIES_CREDIT_NOTE,
    )

    cn = Invoice(
        invoice_number=invoice_no,
        booking_id=booking.id,
        user_id=booking.user_id,
        payment_id=refund.id,  # repurpose this FK to link CN -> refund
        amount=float(base_reversed),
        tax_amount=float(gst_reversed),
        total_amount=float(refund_amt),
        venue_name=venue_name or "—",
        venue_address=None,
        seat_details=f"Refund of booking {booking.id[:8]}",
        plan_duration=booking.duration_type,
        doc_type=InvoiceDocType.CREDIT_NOTE,
        series_code=SERIES_CREDIT_NOTE,
        fiscal_year=fy,
        sequence_no=seq,
        supplier_party_id=owner_party.id if owner_party else None,
        recipient_party_id=student_party.id if student_party else None,
        place_of_supply_state=place_state,
        cgst=gst_split.cgst,
        sgst=gst_split.sgst,
        igst=gst_split.igst,
        cess=to_decimal(0),
        base_amount=base_reversed,
    )
    db.add(cn)
    await db.flush()

    # Reversing ledger group — mirror of the original shadow posting.
    # For OWNER_REGISTERED: Dr Owner Payable / Cr Razorpay Receivable (gross).
    # For SEC_9_5:         Dr Owner Payable (base) + Dr GST Output / Cr Razorpay.
    entries: list[Entry] = []
    if booking.gst_treatment == GSTTreatment.SEC_9_5:
        if owner_party:
            entries.append(Entry(
                account_code=ACC_OWNER_PAYABLE, debit=base_reversed,
                party_type="OWNER", party_id=booking.user_id,
                narration="Owner payable reversed (Sec 9(5))",
            ))
        if gst_split.cgst > 0:
            entries.append(Entry(
                account_code=ACC_GST_OUT_CGST, debit=gst_split.cgst,
                party_type="PLATFORM",
                narration="Output CGST reversed (Sec 9(5) credit note)",
            ))
        if gst_split.sgst > 0:
            entries.append(Entry(
                account_code=ACC_GST_OUT_SGST, debit=gst_split.sgst,
                party_type="PLATFORM",
                narration="Output SGST reversed (Sec 9(5) credit note)",
            ))
        if gst_split.igst > 0:
            entries.append(Entry(
                account_code=ACC_GST_OUT_IGST, debit=gst_split.igst,
                party_type="PLATFORM",
                narration="Output IGST reversed (Sec 9(5) credit note)",
            ))
    else:
        # Treatments where the whole gross is owner-payable
        entries.append(Entry(
            account_code=ACC_OWNER_PAYABLE, debit=refund_amt,
            party_type="OWNER",
            party_id=owner.id if owner else None,
            narration="Owner payable reversed",
        ))

    entries.append(Entry(
        account_code=ACC_RAZORPAY_RECEIVABLE, credit=refund_amt,
        party_type="STUDENT", party_id=booking.user_id,
        narration=f"Credit note {invoice_no} — refund to student",
    ))

    await LedgerService.post_entries(
        db,
        txn_group_id=None,
        source_type="CREDIT_NOTE",
        source_id=cn.id,
        entries=entries,
        narration=f"Credit note {invoice_no} for refund {refund.id}",
    )

    return cn


# ---------- helpers --------------------------------------------------------

async def _resolve_context(
    db: AsyncSession, booking: Booking,
) -> tuple[Optional[User], Optional[str], Optional[str], Optional[str]]:
    """Returns (owner, venue_name, venue_state, place_of_supply_state)."""
    if booking.cabin_id:
        cabin = (await db.execute(
            select(Cabin).where(Cabin.id == booking.cabin_id)
        )).scalar_one_or_none()
        if cabin is not None:
            room = (await db.execute(
                select(ReadingRoom).where(ReadingRoom.id == cabin.reading_room_id)
            )).scalar_one_or_none()
            if room is not None:
                owner = (await db.execute(
                    select(User).where(User.id == room.owner_id)
                )).scalar_one_or_none()
                return owner, room.name, room.state, booking.place_of_supply_state or room.state
    elif booking.accommodation_id:
        acc = (await db.execute(
            select(Accommodation).where(Accommodation.id == booking.accommodation_id)
        )).scalar_one_or_none()
        if acc is not None:
            owner = (await db.execute(
                select(User).where(User.id == acc.owner_id)
            )).scalar_one_or_none()
            return owner, acc.name, acc.state, booking.place_of_supply_state or acc.state
    return None, None, None, None


async def _owner_party(db: AsyncSession, owner: User) -> Party:
    party = Party(
        party_type="OWNER", party_ref_id=owner.id,
        legal_name=owner.legal_name or owner.name,
        gstin=owner.gstin, pan=owner.pan,
        state_code=owner.business_state_code,
        contact_email=owner.email, contact_phone=owner.phone,
    )
    db.add(party)
    await db.flush()
    return party


async def _student_party(db: AsyncSession, user_id: str) -> Optional[Party]:
    student = await db.get(User, user_id)
    if student is None:
        return None
    party = Party(
        party_type="STUDENT", party_ref_id=student.id,
        legal_name=student.name or student.email,
        contact_email=student.email,
        contact_phone=student.phone,
    )
    db.add(party)
    await db.flush()
    return party
