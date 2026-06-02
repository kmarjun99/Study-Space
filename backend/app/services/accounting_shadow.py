"""Accounting shadow layer.

Called from EVERY booking-payment-completion site AFTER the booking has been
marked PAID. Computes tax, freezes the snapshot, posts the ledger group, and
backfills `bookings.base_amount` / `gst_amount` / `gst_treatment`.

Guarantees:
  - Never raises into the caller. If anything goes wrong, the booking is
    still marked PAID (existing behavior) — we log a warning and move on.
    The integrity job will pick up the missing ledger group next morning.
  - No-op when `accounting.enabled = false` in tax_config. This is the
    master kill switch that protects the existing flow.
  - Idempotent: posting twice for the same booking is a no-op (the ledger
    service de-dupes by source_id).

Single call site convention: routers/payments/webhooks all call
`AccountingShadow.shadow_post_booking_paid(db, booking_id=...)` then commit.
The shadow logs structured warnings via `logging` so failures surface in
log aggregation rather than only stdout.
"""
from __future__ import annotations

import logging
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.accommodation import Accommodation
from app.models.booking import Booking, GSTTreatment, PaymentStatus
from app.models.reading_room import Cabin, ReadingRoom
from app.models.user import User
from app.services.ledger_service import Entry, LedgerService
from app.services.tax_engine import (
    accounting_enabled,
    compute_booking_tax,
    freeze_snapshot,
    load_active_config,
    q2,
    to_decimal,
)


_log = logging.getLogger("studyspace.accounting")


# Two-letter state code lookup. The platform stores full state names on
# listings (e.g. "Karnataka") but Indian GST place-of-supply is the 2-char
# state code. Until listings are normalized, we map here.
_INDIAN_STATE_CODES: dict[str, str] = {
    "andhra pradesh": "AP", "arunachal pradesh": "AR", "assam": "AS",
    "bihar": "BR", "chhattisgarh": "CT", "goa": "GA", "gujarat": "GJ",
    "haryana": "HR", "himachal pradesh": "HP", "jharkhand": "JH",
    "karnataka": "KA", "kerala": "KL", "madhya pradesh": "MP",
    "maharashtra": "MH", "manipur": "MN", "meghalaya": "ML",
    "mizoram": "MZ", "nagaland": "NL", "odisha": "OR", "orissa": "OR",
    "punjab": "PB", "rajasthan": "RJ", "sikkim": "SK", "tamil nadu": "TN",
    "telangana": "TG", "tripura": "TR", "uttar pradesh": "UP",
    "uttarakhand": "UT", "west bengal": "WB",
    "andaman and nicobar islands": "AN", "chandigarh": "CH",
    "dadra and nagar haveli and daman and diu": "DN", "delhi": "DL",
    "jammu and kashmir": "JK", "ladakh": "LA", "lakshadweep": "LD",
    "puducherry": "PY",
}


def _to_state_code(raw: Optional[str]) -> Optional[str]:
    """Normalize a state value to the canonical 2-char GST code.

    Accepts already-2-char codes (returned uppercased), full names from the
    canonical lookup above, or None. Returns None when no confident mapping
    is possible — better to skip GST split than to insert garbage that fails
    the DB's `VARCHAR(2)` length check and rolls back the shadow."""
    if not raw:
        return None
    raw = raw.strip()
    if len(raw) == 2:
        return raw.upper()
    return _INDIAN_STATE_CODES.get(raw.lower())


# Account codes (match seed_chart_of_accounts.py)
ACC_RAZORPAY_RECEIVABLE = "1010"
ACC_OWNER_PAYABLE = "2010"
ACC_GST_OUT_CGST = "2020"
ACC_GST_OUT_SGST = "2021"
ACC_GST_OUT_IGST = "2022"


class AccountingShadow:
    """Static facade. Stateless."""

    @staticmethod
    async def shadow_post_booking_paid(
        db: AsyncSession, *, booking_id: str,
    ) -> Optional[str]:
        """Compute tax + post ledger for a freshly-paid booking.

        Returns the txn_group_id on success, None when skipped.
        Never raises into the caller.
        """
        try:
            return await _shadow_impl(db, booking_id)
        except Exception:  # pragma: no cover -- defensive
            # CRITICAL: roll back the session BEFORE returning. If the shadow
            # threw during a flush — which happens when the new accounting
            # tables aren't migrated yet, a chart_of_accounts code is missing,
            # a tax_snapshot insert violates a constraint, etc. — SQLAlchemy
            # marks the session as "needs rollback". WITHOUT this explicit
            # rollback, the caller's next `await db.commit()` throws
            # PendingRollbackError ("This Session's transaction has been
            # rolled back due to a previous exception" — sqlalche.me/e/20/7s2a).
            # That escapes the caller's try/except and bubbles to the global
            # handler as a 500, even though the BOOKING is already committed
            # by the caller. End result the user sees: payment IS PAID in the
            # DB and has an invoice, but the response says 500 and the
            # frontend shows "payment failed". This single rollback fixes that.
            try:
                await db.rollback()
            except Exception:
                pass  # Best-effort — if rollback itself fails, can't recover
            _log.exception(
                "Shadow posting failed for booking %s — booking remains PAID, "
                "ledger group missing (integrity job will flag).",
                booking_id,
            )
            return None


async def _shadow_impl(db: AsyncSession, booking_id: str) -> Optional[str]:
    config = await load_active_config(db)
    if not accounting_enabled(config):
        return None

    # SELECT FOR UPDATE serializes concurrent callers (client /verify and
    # the asynchronous webhook both reaching this point at once would
    # otherwise both see `gst_treatment IS NULL` and both post a duplicate
    # ledger group). Postgres only; the SQLite dev dialect ignores the lock
    # hint silently which is fine because SQLite is single-writer.
    dialect = db.bind.dialect.name if db.bind is not None else "sqlite"
    if dialect == "postgresql":
        booking = (await db.execute(
            select(Booking).where(Booking.id == booking_id).with_for_update()
        )).scalar_one_or_none()
    else:
        booking = await db.get(Booking, booking_id)
    if booking is None:
        return None
    if booking.payment_status != PaymentStatus.PAID:
        # Only shadow PAID bookings — refunds/holds are not money events here.
        return None
    if booking.gst_treatment is not None and booking.gst_treatment != GSTTreatment.NOT_COMPUTED:
        # Already shadowed (under the row lock this is the canonical signal
        # that another caller completed first).
        return None

    # Resolve owner + listing context
    (owner, place_of_supply_state_raw, listing_gst_category,
     listing_rate_override, listing_price_mode) = \
        await _resolve_booking_context(db, booking)

    # The bookings.place_of_supply_state column is VARCHAR(2) — listings
    # store the full state name ("Karnataka") so we must map before write,
    # otherwise Postgres raises a length-check error inside the shadow's
    # try/except and the booking silently misses its GST split.
    place_of_supply_state = _to_state_code(place_of_supply_state_raw)

    snap = await freeze_snapshot(db, config)
    tax = compute_booking_tax(
        gross=to_decimal(booking.amount),
        owner=owner,
        listing_gst_category=listing_gst_category,
        listing_gst_rate_override=listing_rate_override,
        listing_price_display_mode=listing_price_mode,
        place_of_supply_state=place_of_supply_state,
        config=config,
        snapshot_id=snap.id,
    )

    # Backfill the booking row with the tax breakdown
    booking.base_amount = tax.base
    booking.gst_amount = tax.gst.total
    booking.gst_rate_applied = tax.rate_applied
    booking.gst_treatment = tax.treatment
    booking.place_of_supply_state = place_of_supply_state
    booking.frozen_tax_snapshot_id = snap.id
    # Settlement engine reads paid_at to know the T+N eligibility window.
    if booking.paid_at is None:
        booking.paid_at = datetime.utcnow()

    # Build ledger entries depending on treatment
    entries = _entries_for(booking, owner, tax)
    if not entries:
        # No money to post (gross was zero?). Don't fail.
        return None

    txn_group = await LedgerService.post_entries(
        db,
        txn_group_id=None,
        source_type="BOOKING",
        source_id=booking.id,
        entries=entries,
        narration=f"Booking {booking.id} payment ({tax.treatment.value})",
    )
    return txn_group


def _entries_for(
    booking: Booking, owner: Optional[User], tax,
) -> list[Entry]:
    """Ledger entries for the four GST treatments.

    See design doc §3 for the worked postings.
    """
    gross = q2(to_decimal(booking.amount))
    if gross <= 0:
        return []

    entries: list[Entry] = [
        Entry(
            account_code=ACC_RAZORPAY_RECEIVABLE,
            debit=gross,
            party_type="STUDENT",
            party_id=booking.user_id,
            narration="Razorpay receipt — student booking",
        )
    ]

    owner_id = owner.id if owner is not None else None

    if tax.treatment == GSTTreatment.OWNER_REGISTERED:
        # Owner is the supplier; the full gross is owed to the owner.
        # GST in the gross is the owner's liability (handled in their own GSTR-1).
        entries.append(Entry(
            account_code=ACC_OWNER_PAYABLE, credit=gross,
            party_type="OWNER", party_id=owner_id,
            narration="Owner payable — registered owner-issued invoice",
        ))
        return entries

    if tax.treatment == GSTTreatment.SEC_9_5:
        # Platform is deemed supplier — base goes to owner, GST is platform liability.
        entries.append(Entry(
            account_code=ACC_OWNER_PAYABLE, credit=tax.base,
            party_type="OWNER", party_id=owner_id,
            narration="Owner payable — Sec 9(5) (net of GST owed by platform)",
        ))
        if tax.gst.cgst > 0:
            entries.append(Entry(
                account_code=ACC_GST_OUT_CGST, credit=tax.gst.cgst,
                party_type="PLATFORM",
                narration="Output CGST — Sec 9(5) deemed supplier",
            ))
        if tax.gst.sgst > 0:
            entries.append(Entry(
                account_code=ACC_GST_OUT_SGST, credit=tax.gst.sgst,
                party_type="PLATFORM",
                narration="Output SGST — Sec 9(5) deemed supplier",
            ))
        if tax.gst.igst > 0:
            entries.append(Entry(
                account_code=ACC_GST_OUT_IGST, credit=tax.gst.igst,
                party_type="PLATFORM",
                narration="Output IGST — Sec 9(5) deemed supplier",
            ))
        return entries

    # NOT_REGISTERED or EXEMPT: no GST owed by platform; whole amount to owner.
    entries.append(Entry(
        account_code=ACC_OWNER_PAYABLE, credit=gross,
        party_type="OWNER", party_id=owner_id,
        narration=f"Owner payable — {tax.treatment.value}",
    ))
    return entries


async def _resolve_booking_context(
    db: AsyncSession, booking: Booking,
) -> tuple[
    Optional[User], Optional[str], Optional[str], Optional[Decimal], Optional[str],
]:
    """Pull (owner, place_of_supply_state, listing_gst_category, rate_override,
    price_display_mode)."""
    owner: Optional[User] = None
    place_state: Optional[str] = None
    category: Optional[str] = None
    rate_override: Optional[Decimal] = None
    price_mode: Optional[str] = None

    if booking.cabin_id:
        cabin = (await db.execute(
            select(Cabin).where(Cabin.id == booking.cabin_id)
        )).scalar_one_or_none()
        if cabin is not None:
            room = (await db.execute(
                select(ReadingRoom).where(ReadingRoom.id == cabin.reading_room_id)
            )).scalar_one_or_none()
            if room is not None:
                place_state = room.state
                category = room.gst_category
                rate_override = (
                    to_decimal(room.gst_rate_override)
                    if room.gst_rate_override is not None else None
                )
                price_mode = room.price_display_mode.value if room.price_display_mode else None
                owner = (await db.execute(
                    select(User).where(User.id == room.owner_id)
                )).scalar_one_or_none()
    elif booking.accommodation_id:
        acc = (await db.execute(
            select(Accommodation).where(Accommodation.id == booking.accommodation_id)
        )).scalar_one_or_none()
        if acc is not None:
            place_state = acc.state
            category = acc.gst_category
            rate_override = (
                to_decimal(acc.gst_rate_override)
                if acc.gst_rate_override is not None else None
            )
            price_mode = acc.price_display_mode.value if acc.price_display_mode else None
            owner = (await db.execute(
                select(User).where(User.id == acc.owner_id)
            )).scalar_one_or_none()

    return owner, place_state, category, rate_override, price_mode
