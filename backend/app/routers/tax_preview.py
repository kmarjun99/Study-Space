"""Public-ish tax preview endpoint.

The frontend uses this to show "you'll pay ₹X, of which ₹Y is GST" before
the student actually pays. Crucially:

  - This NEVER writes to the database. It is a pure pricing query.
  - It reports the *mode currently in effect* for the listing, including
    whether the per-listing flag is honoured. The UI shows this transparently
    so an owner can see exactly what the student will see.
  - When `feature.per_listing_price_mode` is off, GST_EXTRA listings still
    preview as if they were GST_INCLUDED — matching the actual booking math.
    This pins the contract: the preview never lies.
"""
from __future__ import annotations

from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user_optional
from app.models.accommodation import Accommodation
from app.models.reading_room import ReadingRoom
from app.models.user import User
from app.services.tax_engine import (
    cfg_get,
    compute_booking_gross,
    compute_booking_tax,
    freeze_snapshot,
    load_active_config,
    resolve_pricing_inclusive,
    to_decimal,
)


router = APIRouter(prefix="/tax", tags=["Tax Preview"])


class PreviewRequest(BaseModel):
    listing_type: Literal["reading-room", "accommodation"]
    listing_id: str
    # Price as the student sees it on the listing page
    displayed_price: float
    place_of_supply_state: Optional[str] = None


class PreviewResponse(BaseModel):
    # The amount the student will actually be charged at checkout
    payable_amount: float
    # Reverse-calculated split
    base_amount: float
    gst_amount: float
    cgst: float
    sgst: float
    igst: float
    gst_rate_applied: float
    # Treatment label (OWNER_REGISTERED / SEC_9_5 / NOT_REGISTERED / EXEMPT)
    treatment: str
    # Mode actually used by the engine for THIS call
    effective_mode: Literal["GST_INCLUDED", "GST_EXTRA"]
    # What the listing has set, if anything
    listing_mode: Optional[str]
    # Whether the per-listing override is live (i.e., the feature flag is on)
    per_listing_flag_on: bool
    # Human-readable note explaining the resolution
    notes: list[str]


def _is_pdf(_):  # placeholder for symmetry; preview doesn't render PDFs.
    return False


@router.post("/preview-booking", response_model=PreviewResponse)
async def preview_booking(
    body: PreviewRequest,
    _user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    """Compute the GST breakdown the student would see, without writing anything."""
    if body.displayed_price < 0:
        raise HTTPException(status_code=400, detail="displayed_price must be >= 0")

    listing, owner, listing_state = await _load_listing(db, body.listing_type, body.listing_id)
    if listing is None:
        raise HTTPException(status_code=404, detail="Listing not found")

    config = await load_active_config(db)
    snap = await freeze_snapshot(db, config)
    # Don't commit the snapshot — preview is read-only. Rollback at the end.

    listing_mode = (listing.price_display_mode.value
                    if listing.price_display_mode else None)
    flag_on = bool(cfg_get(config, "feature.per_listing_price_mode", False))

    # Step 1: compute what the student is actually charged. With the flag off
    # this is always the displayed_price (the existing behavior). With the
    # flag on + GST_EXTRA, this multiplies by (1 + rate).
    payable = compute_booking_gross(
        displayed_price=body.displayed_price,
        listing_gst_rate_override=listing.gst_rate_override,
        listing_price_display_mode=listing_mode,
        config=config,
    )

    # Step 2: split `payable` into base + GST. By now `payable` is ALWAYS the
    # gross-inclusive amount (compute_booking_gross has already done any
    # add-on math). We must therefore reverse-calc; passing the listing mode
    # again would re-apply the add-on and double-count GST.
    tax = compute_booking_tax(
        gross=payable,
        owner=owner,
        listing_gst_category=listing.gst_category,
        listing_gst_rate_override=(to_decimal(listing.gst_rate_override)
                                   if listing.gst_rate_override is not None else None),
        place_of_supply_state=body.place_of_supply_state or listing_state,
        config=config,
        snapshot_id=snap.id,
        inclusive_override=True,
    )

    effective_inclusive = resolve_pricing_inclusive(
        listing_price_display_mode=listing_mode, config=config,
    )
    effective_mode = "GST_INCLUDED" if effective_inclusive else "GST_EXTRA"

    notes: list[str] = []
    if listing_mode and not flag_on:
        notes.append(
            f"Listing is set to {listing_mode} but the platform flag "
            "`feature.per_listing_price_mode` is OFF — preview uses global default."
        )
    if not listing_mode:
        notes.append("No per-listing mode set; using platform default.")
    if tax.treatment == "NOT_REGISTERED":
        notes.append("Owner is not GST-registered — no GST is collected by the platform.")

    # Roll back the snapshot insert so preview leaves zero trace.
    await db.rollback()

    return PreviewResponse(
        payable_amount=float(payable),
        base_amount=float(tax.base),
        gst_amount=float(tax.gst.total),
        cgst=float(tax.gst.cgst),
        sgst=float(tax.gst.sgst),
        igst=float(tax.gst.igst),
        gst_rate_applied=float(tax.rate_applied),
        treatment=tax.treatment.value,
        effective_mode=effective_mode,
        listing_mode=listing_mode,
        per_listing_flag_on=flag_on,
        notes=notes,
    )


async def _load_listing(
    db: AsyncSession, listing_type: str, listing_id: str,
):
    """Returns (listing, owner_user, listing_state)."""
    if listing_type == "reading-room":
        listing = await db.get(ReadingRoom, listing_id)
        if listing is None:
            return None, None, None
        owner = await db.get(User, listing.owner_id)
        return listing, owner, listing.state
    if listing_type == "accommodation":
        listing = await db.get(Accommodation, listing_id)
        if listing is None:
            return None, None, None
        owner = await db.get(User, listing.owner_id)
        return listing, owner, listing.state
    raise HTTPException(status_code=400, detail="listing_type must be reading-room or accommodation")
