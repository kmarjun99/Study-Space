"""Tests for the tax-preview endpoint.

The preview must be the single source of truth for what a student will see
at checkout. These tests pin down three contracts:

  1. The preview never writes anything (no rows in `tax_snapshots`).
  2. With the per-listing flag OFF, GST_EXTRA listings preview as if they
     were GST_INCLUDED — matching the actual booking math.
  3. When `place_of_supply_state` differs from the supplier state, the engine
     returns IGST instead of CGST/SGST.

We bypass the FastAPI HTTP layer and call the service-level functions
directly through a constructed PreviewRequest, because the project's app
auth chain uses Python 3.10 syntax our test venv (3.9) doesn't run.
"""
from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models.accommodation import Accommodation, AccommodationType, Gender
from app.models.reading_room import PriceDisplayMode
from app.models.tax_config import TaxConfig
from app.models.tax_snapshot import TaxSnapshot
from app.models.user import GSTRegistrationType, User, UserRole
from app.routers.tax_preview import PreviewRequest, preview_booking
from app.services.tax_engine import q2


async def _set_flag(db, key, value):
    row = (await db.execute(
        select(TaxConfig).where(TaxConfig.key == key)
    )).scalar_one_or_none()
    if row is None:
        db.add(TaxConfig(key=key, value=json.dumps(value)))
    else:
        row.value = json.dumps(value)
    await db.commit()


async def _make_acc_owner(seeded_db, *, registered=True, state="KA", price_mode=None):
    owner = User(
        id="oprv", email="oprv@x.com", hashed_password="x", name="Owner",
        role=UserRole.ADMIN, legal_name="Owner Pvt Ltd",
        gst_registration_type=(
            GSTRegistrationType.REGULAR if registered else GSTRegistrationType.UNREGISTERED
        ),
        business_state_code=state if registered else None,
        gstin="29ZZZZZ1234Z1Z5" if registered else None,
    )
    seeded_db.add(owner)
    acc = Accommodation(
        id="aprv", owner_id=owner.id, name="Acme",
        type=AccommodationType.PG, gender=Gender.UNISEX,
        address="-", price=2500.0, sharing="single", state=state,
        gst_category="HOSTEL_PG",
        price_display_mode=PriceDisplayMode(price_mode) if price_mode else None,
    )
    seeded_db.add(acc)
    await seeded_db.commit()
    return owner, acc


# ---------- contract: never writes ----------------------------------------

@pytest.mark.asyncio
async def test_preview_does_not_persist_snapshot(seeded_db):
    """Preview is read-only — no tax_snapshots row should leak."""
    _, acc = await _make_acc_owner(seeded_db, registered=True)

    snaps_before = len((await seeded_db.execute(select(TaxSnapshot))).scalars().all())
    await preview_booking(
        body=PreviewRequest(
            listing_type="accommodation",
            listing_id=acc.id,
            displayed_price=2500.0,
        ),
        _user=None,
        db=seeded_db,
    )
    snaps_after = len((await seeded_db.execute(select(TaxSnapshot))).scalars().all())
    assert snaps_before == snaps_after


# ---------- contract: never lies about effective mode ----------------------

@pytest.mark.asyncio
async def test_gst_extra_listing_with_flag_off_previews_as_inclusive(seeded_db):
    """The owner chose GST_EXTRA but the platform flag is OFF.

    The preview MUST reflect what will actually happen (inclusive math) and
    surface a note explaining the divergence — never silently apply the
    listing's preference.
    """
    _, acc = await _make_acc_owner(seeded_db, registered=True, price_mode="GST_EXTRA")

    out = await preview_booking(
        body=PreviewRequest(
            listing_type="accommodation",
            listing_id=acc.id,
            displayed_price=2500.0,
        ),
        _user=None,
        db=seeded_db,
    )
    assert out.effective_mode == "GST_INCLUDED"
    assert out.listing_mode == "GST_EXTRA"
    assert out.per_listing_flag_on is False
    assert any("OFF" in n for n in out.notes)
    # And the math is the inclusive split (2500 -> 2118.64 + 381.36)
    assert q2(Decimal(str(out.base_amount))) == Decimal("2118.64")
    assert q2(Decimal(str(out.gst_amount))) == Decimal("381.36")
    assert q2(Decimal(str(out.payable_amount))) == Decimal("2500.00")


@pytest.mark.asyncio
async def test_gst_extra_listing_with_flag_on_changes_payable(seeded_db):
    """With the flag ON, GST_EXTRA: payable = displayed_price * (1 + rate)."""
    await _set_flag(seeded_db, "feature.per_listing_price_mode", True)
    _, acc = await _make_acc_owner(seeded_db, registered=True, price_mode="GST_EXTRA")

    out = await preview_booking(
        body=PreviewRequest(
            listing_type="accommodation",
            listing_id=acc.id,
            displayed_price=2500.0,
        ),
        _user=None,
        db=seeded_db,
    )
    assert out.effective_mode == "GST_EXTRA"
    assert q2(Decimal(str(out.payable_amount))) == Decimal("2950.00")
    assert q2(Decimal(str(out.base_amount))) == Decimal("2500.00")
    assert q2(Decimal(str(out.gst_amount))) == Decimal("450.00")


# ---------- contract: state split -----------------------------------------

@pytest.mark.asyncio
async def test_inter_state_supply_returns_igst(seeded_db):
    _, acc = await _make_acc_owner(seeded_db, registered=True, state="KA")
    out = await preview_booking(
        body=PreviewRequest(
            listing_type="accommodation",
            listing_id=acc.id,
            displayed_price=2500.0,
            place_of_supply_state="MH",
        ),
        _user=None,
        db=seeded_db,
    )
    assert out.igst > 0
    assert out.cgst == 0 and out.sgst == 0


@pytest.mark.asyncio
async def test_unregistered_owner_no_gst(seeded_db):
    _, acc = await _make_acc_owner(seeded_db, registered=False)
    out = await preview_booking(
        body=PreviewRequest(
            listing_type="accommodation",
            listing_id=acc.id,
            displayed_price=2500.0,
        ),
        _user=None,
        db=seeded_db,
    )
    # NOT_REGISTERED + category not in Sec 9(5) -> no GST collected by platform
    assert out.treatment in ("NOT_REGISTERED", "EXEMPT")
    assert out.gst_amount == 0
    assert q2(Decimal(str(out.payable_amount))) == Decimal("2500.00")


@pytest.mark.asyncio
async def test_missing_listing_404(seeded_db):
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc:
        await preview_booking(
            body=PreviewRequest(
                listing_type="accommodation",
                listing_id="nope",
                displayed_price=2500.0,
            ),
            _user=None,
            db=seeded_db,
        )
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_negative_price_rejected(seeded_db):
    from fastapi import HTTPException
    _, acc = await _make_acc_owner(seeded_db, registered=True)
    with pytest.raises(HTTPException) as exc:
        await preview_booking(
            body=PreviewRequest(
                listing_type="accommodation",
                listing_id=acc.id,
                displayed_price=-100,
            ),
            _user=None,
            db=seeded_db,
        )
    assert exc.value.status_code == 400
