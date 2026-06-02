"""Per-listing billing configuration.

Owner-side endpoints to edit the new accounting columns on a listing:
  - `gst_category`        (HOTEL_LIKE / SHORT_STAY / HOSTEL_PG / READING_ROOM / OTHER)
  - `gst_rate_override`   (per-listing rate; null = use config default)
  - `gst_sac`             (SAC code for the supply)
  - `price_display_mode`  (GST_INCLUDED / GST_EXTRA — informational until
                           `feature.per_listing_price_mode` is on)
  - `billing_anchor_day`  (1-28; which day of the month the maintenance
                           charge is created)

Kept in a dedicated router so the existing /reading-rooms and /accommodations
PUT endpoints (which use full-object update bodies) stay untouched.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_admin
from app.models.accommodation import Accommodation
from app.models.reading_room import PriceDisplayMode, ReadingRoom
from app.models.user import User, UserRole


router = APIRouter(prefix="/owner/listings", tags=["Owner Listing Billing"])


VALID_GST_CATEGORIES = {
    "HOTEL_LIKE", "SHORT_STAY", "HOSTEL_PG", "READING_ROOM", "OTHER",
}


class BillingConfigUpdate(BaseModel):
    """Partial update — only fields actually sent are touched."""
    gst_category: Optional[str] = Field(
        None, description="One of HOTEL_LIKE / SHORT_STAY / HOSTEL_PG / READING_ROOM / OTHER",
    )
    gst_rate_override: Optional[float] = Field(
        None, ge=0, le=1,
        description="0–1 (e.g., 0.18 = 18%). Null clears the override.",
    )
    gst_sac: Optional[str] = Field(None, max_length=10)
    price_display_mode: Optional[Literal["GST_INCLUDED", "GST_EXTRA"]] = None
    billing_anchor_day: Optional[int] = Field(None, ge=1, le=28)
    # Per-field "explicit clear" signals (because Pydantic can't tell apart
    # "field not sent" from "field sent as null"). The router clears a column
    # only when the matching `clear_*` flag is true.
    clear_gst_rate_override: bool = False
    clear_gst_category: bool = False
    clear_price_display_mode: bool = False


class BillingConfigOut(BaseModel):
    listing_type: str
    listing_id: str
    gst_category: Optional[str]
    gst_rate_override: Optional[float]
    gst_sac: Optional[str]
    price_display_mode: Optional[str]
    billing_anchor_day: Optional[int]
    maintenance_status: Optional[str]


def _to_out(listing_type: str, obj) -> BillingConfigOut:
    return BillingConfigOut(
        listing_type=listing_type,
        listing_id=obj.id,
        gst_category=obj.gst_category,
        gst_rate_override=float(obj.gst_rate_override) if obj.gst_rate_override is not None else None,
        gst_sac=obj.gst_sac,
        price_display_mode=(obj.price_display_mode.value if obj.price_display_mode else None),
        billing_anchor_day=obj.billing_anchor_day,
        maintenance_status=(obj.maintenance_status.value if obj.maintenance_status else None),
    )


async def _load(db: AsyncSession, listing_type: str, listing_id: str):
    if listing_type == "reading-room":
        return await db.get(ReadingRoom, listing_id)
    if listing_type == "accommodation":
        return await db.get(Accommodation, listing_id)
    raise HTTPException(status_code=400, detail="listing_type must be reading-room or accommodation")


def _check_owner(obj, current_user: User) -> None:
    if obj is None:
        raise HTTPException(status_code=404, detail="Listing not found")
    if obj.owner_id != current_user.id and current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=403, detail="Forbidden")


@router.get("/{listing_type}/{listing_id}/billing-config", response_model=BillingConfigOut)
async def get_billing_config(
    listing_type: str,
    listing_id: str,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    obj = await _load(db, listing_type, listing_id)
    _check_owner(obj, current_user)
    return _to_out(listing_type, obj)


@router.patch("/{listing_type}/{listing_id}/billing-config", response_model=BillingConfigOut)
async def update_billing_config(
    listing_type: str,
    listing_id: str,
    body: BillingConfigUpdate,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Partial update of accounting columns on a single listing.

    Only fields sent in the body are touched. To explicitly null a field, set
    the matching `clear_*` boolean to true.
    """
    obj = await _load(db, listing_type, listing_id)
    _check_owner(obj, current_user)

    if body.gst_category is not None:
        if body.gst_category not in VALID_GST_CATEGORIES:
            raise HTTPException(
                status_code=400,
                detail=f"gst_category must be one of {sorted(VALID_GST_CATEGORIES)}",
            )
        obj.gst_category = body.gst_category
    elif body.clear_gst_category:
        obj.gst_category = None

    if body.gst_rate_override is not None:
        obj.gst_rate_override = Decimal(str(body.gst_rate_override))
    elif body.clear_gst_rate_override:
        obj.gst_rate_override = None

    if body.gst_sac is not None:
        obj.gst_sac = body.gst_sac or None

    if body.price_display_mode is not None:
        obj.price_display_mode = PriceDisplayMode(body.price_display_mode)
    elif body.clear_price_display_mode:
        obj.price_display_mode = None

    if body.billing_anchor_day is not None:
        obj.billing_anchor_day = body.billing_anchor_day

    await db.commit()
    await db.refresh(obj)
    return _to_out(listing_type, obj)
