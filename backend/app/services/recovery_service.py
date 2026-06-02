"""Recovery flow for refunds approved AFTER the booking was settled.

When a refund hits a booking whose payout has already gone to the owner,
the platform needs to recover that money. Two paths:

  1. **Auto-deduct from next settlement**: a `RECOVERY` OwnerCharge is created
     against the owner. The settlement engine picks it up on its next run
     (via the existing maintenance-offset hook, repurposed for recovery).

  2. **Manual recovery (flagged)**: if the next settlement run can't fully
     cover the recovery (owner has no upcoming payouts), the OwnerCharge
     stays `DUE`/`OVERDUE` and super-admin sees it on the KYC/finance dash.

Idempotency: re-detecting the same refund must not create a second recovery
charge. We use `period_key = f"REFUND-{refund_id}"` (a non-monthly value) so
the OwnerCharge unique constraint `(owner_id, charge_type, period_key, listing_id)`
gives us free deduplication.

Credit-note ledger postings continue to be handled by `credit_note_service`;
this module only creates the OwnerCharge debit. Together they keep books
balanced: the credit note reverses the original owner-payable; the recovery
charge re-asserts what's owed back.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.accommodation import Accommodation
from app.models.booking import Booking
from app.models.owner_charge import (
    ListingType,
    OwnerCharge,
    OwnerChargeStatus,
    OwnerChargeType,
)
from app.models.reading_room import Cabin, ReadingRoom
from app.models.refund import Refund, RefundStatus
from app.services.tax_engine import q2, to_decimal


# How the period_key tags recovery charges so they don't collide with monthly billing.
RECOVERY_PERIOD_PREFIX = "REFUND-"


async def _resolve_listing_for_booking(
    db: AsyncSession, booking: Booking,
) -> tuple[Optional[str], Optional[ListingType], Optional[str]]:
    """Returns (owner_id, listing_type, listing_id) for a booking, or all-None."""
    if booking.cabin_id:
        cabin = await db.get(Cabin, booking.cabin_id)
        if cabin is None:
            return None, None, None
        room = await db.get(ReadingRoom, cabin.reading_room_id)
        if room is None:
            return None, None, None
        return room.owner_id, ListingType.READING_ROOM, room.id
    if booking.accommodation_id:
        acc = await db.get(Accommodation, booking.accommodation_id)
        if acc is None:
            return None, None, None
        return acc.owner_id, ListingType.ACCOMMODATION, acc.id
    return None, None, None


def is_recovery_eligible(booking: Booking) -> bool:
    """A booking is recovery-eligible iff it was already settled when the
    refund hit it. Pre-settlement refunds reverse cleanly via credit_note
    only — no separate recovery charge needed."""
    return booking.settled_at is not None


async def create_recovery_charge_for_refund(
    db: AsyncSession, *, refund_id: str,
) -> Optional[OwnerCharge]:
    """Create a `RECOVERY` OwnerCharge if the underlying booking was settled
    before the refund. Idempotent on the refund_id.

    Returns the OwnerCharge (existing or newly created), or None if the
    booking isn't recovery-eligible (pre-settlement) or context is missing.
    """
    refund = await db.get(Refund, refund_id)
    if refund is None:
        return None
    if refund.status not in (RefundStatus.APPROVED, RefundStatus.PROCESSED):
        return None

    booking = await db.get(Booking, refund.booking_id)
    if booking is None or not is_recovery_eligible(booking):
        return None

    owner_id, listing_type, listing_id = await _resolve_listing_for_booking(db, booking)
    if owner_id is None:
        return None

    period_key = f"{RECOVERY_PERIOD_PREFIX}{refund.id}"

    # Service-level idempotency check first (SQLite-friendly).
    existing = (await db.execute(
        select(OwnerCharge).where(
            (OwnerCharge.owner_id == owner_id)
            & (OwnerCharge.charge_type == OwnerChargeType.RECOVERY)
            & (OwnerCharge.period_key == period_key)
            & (OwnerCharge.listing_id == listing_id)
        )
    )).scalar_one_or_none()
    if existing is not None:
        return existing

    amount = q2(to_decimal(refund.amount))
    charge = OwnerCharge(
        owner_id=owner_id,
        listing_id=listing_id,
        listing_type=listing_type,
        charge_type=OwnerChargeType.RECOVERY,
        period_key=period_key,
        base_amount=amount,
        gst_amount=Decimal("0"),       # recovery isn't a fresh supply
        total_amount=amount,
        gst_rate_applied=None,
        status=OwnerChargeStatus.DUE,
        # Recovery is due immediately; next settlement run will pick it up
        # via the maintenance-offset hook (settlement.offset_maintenance).
        due_date=datetime.utcnow() + timedelta(days=0),
    )
    db.add(charge)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        # Race: re-fetch
        existing = (await db.execute(
            select(OwnerCharge).where(
                (OwnerCharge.owner_id == owner_id)
                & (OwnerCharge.charge_type == OwnerChargeType.RECOVERY)
                & (OwnerCharge.period_key == period_key)
                & (OwnerCharge.listing_id == listing_id)
            )
        )).scalar_one()
        return existing
    return charge


async def scan_and_create_recovery_charges(db: AsyncSession) -> dict:
    """Cron-friendly entry-point. Walks recently-approved refunds whose
    bookings were already settled and creates recovery charges for any that
    don't yet have one.

    Called once at the top of every settlement run so the run can immediately
    pick up the recovery as a deduction (or hold the payout if insufficient).
    """
    rows = (await db.execute(
        select(Refund).where(
            Refund.status.in_([RefundStatus.APPROVED, RefundStatus.PROCESSED])
        )
    )).scalars().all()

    created = 0
    skipped = 0
    for refund in rows:
        charge = await create_recovery_charge_for_refund(db, refund_id=refund.id)
        if charge is not None and charge.created_at is not None:
            # `created_at` defaults at insert; this check approximates "new this scan".
            # The unique constraint guarantees no duplicates either way.
            pass
        # Count via a separate exists check would be over-engineering — the
        # unique-key shape means re-running this scan is safe regardless.
        if charge is None:
            skipped += 1
        else:
            created += 1
    await db.commit()
    return {"recovery_charges_created_or_existing": created, "skipped": skipped}


async def get_outstanding_recoveries_for_owner(
    db: AsyncSession, *, owner_id: str,
) -> list[OwnerCharge]:
    """Pending RECOVERY charges (DUE / OVERDUE / FAILED) for one owner.

    Surface this on the super-admin finance dashboard so manual recovery is
    possible when a negative settlement holds.
    """
    rows = (await db.execute(
        select(OwnerCharge).where(
            (OwnerCharge.owner_id == owner_id)
            & (OwnerCharge.charge_type == OwnerChargeType.RECOVERY)
            & (OwnerCharge.status.in_([
                OwnerChargeStatus.DUE,
                OwnerChargeStatus.OVERDUE,
                OwnerChargeStatus.FAILED,
            ]))
        )
    )).scalars().all()
    return list(rows)
