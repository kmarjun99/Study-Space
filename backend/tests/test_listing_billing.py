"""Per-listing billing-config endpoint tests.

Pins down:
  - PATCH applies only the fields you send (partial update).
  - `clear_*` flags explicitly null a column.
  - Validation: rejects invalid gst_category, out-of-range rates / anchor_days.
  - Owner-only authorization is enforced via _check_owner (HTTPException 403/404).
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from app.models.accommodation import Accommodation, AccommodationType, Gender
from app.models.reading_room import PriceDisplayMode
from app.models.user import GSTRegistrationType, User, UserRole
from app.routers.listing_billing import (
    BillingConfigUpdate,
    get_billing_config,
    update_billing_config,
)


async def _make(seeded_db, owner_id="ob1"):
    owner = User(
        id=owner_id, email=f"{owner_id}@x.com", hashed_password="x",
        name="Owner", role=UserRole.ADMIN,
        gst_registration_type=GSTRegistrationType.REGULAR,
        business_state_code="KA",
    )
    seeded_db.add(owner)
    acc = Accommodation(
        id=f"{owner_id}-acc", owner_id=owner.id, name="Acme",
        type=AccommodationType.PG, gender=Gender.UNISEX,
        address="-", price=2500.0, sharing="single", state="KA",
    )
    seeded_db.add(acc)
    await seeded_db.commit()
    return owner, acc


@pytest.mark.asyncio
async def test_partial_update_only_touches_sent_fields(seeded_db):
    owner, acc = await _make(seeded_db)
    # Seed both gst_category and billing_anchor_day so we can prove the other
    # one is left alone.
    acc.gst_category = "HOSTEL_PG"
    acc.billing_anchor_day = 15
    await seeded_db.commit()

    out = await update_billing_config(
        listing_type="accommodation",
        listing_id=acc.id,
        body=BillingConfigUpdate(gst_sac="996311"),
        current_user=owner,
        db=seeded_db,
    )
    assert out.gst_sac == "996311"
    assert out.gst_category == "HOSTEL_PG"   # untouched
    assert out.billing_anchor_day == 15       # untouched


@pytest.mark.asyncio
async def test_clear_flag_nulls_a_field(seeded_db):
    owner, acc = await _make(seeded_db)
    acc.price_display_mode = PriceDisplayMode.GST_EXTRA
    await seeded_db.commit()

    out = await update_billing_config(
        listing_type="accommodation",
        listing_id=acc.id,
        body=BillingConfigUpdate(clear_price_display_mode=True),
        current_user=owner,
        db=seeded_db,
    )
    assert out.price_display_mode is None


@pytest.mark.asyncio
async def test_invalid_category_rejected(seeded_db):
    from fastapi import HTTPException
    owner, acc = await _make(seeded_db)
    with pytest.raises(HTTPException) as exc:
        await update_billing_config(
            listing_type="accommodation",
            listing_id=acc.id,
            body=BillingConfigUpdate(gst_category="NOT_A_CATEGORY"),
            current_user=owner,
            db=seeded_db,
        )
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_rate_override_persists_as_numeric(seeded_db):
    owner, acc = await _make(seeded_db)
    out = await update_billing_config(
        listing_type="accommodation",
        listing_id=acc.id,
        body=BillingConfigUpdate(gst_rate_override=0.12),
        current_user=owner,
        db=seeded_db,
    )
    assert out.gst_rate_override == 0.12
    await seeded_db.refresh(acc)
    # Stored as Decimal in the DB (precision preserved)
    assert Decimal(str(acc.gst_rate_override)) == Decimal("0.12")


@pytest.mark.asyncio
async def test_other_owner_cannot_edit(seeded_db):
    from fastapi import HTTPException
    owner, acc = await _make(seeded_db, owner_id="ob_real")
    intruder = User(
        id="ob_bad", email="bad@x.com", hashed_password="x",
        name="Intruder", role=UserRole.ADMIN,
    )
    seeded_db.add(intruder)
    await seeded_db.commit()

    with pytest.raises(HTTPException) as exc:
        await update_billing_config(
            listing_type="accommodation",
            listing_id=acc.id,
            body=BillingConfigUpdate(gst_sac="996311"),
            current_user=intruder,
            db=seeded_db,
        )
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_unknown_listing_type_rejected(seeded_db):
    from fastapi import HTTPException
    owner, _ = await _make(seeded_db)
    with pytest.raises(HTTPException) as exc:
        await get_billing_config(
            listing_type="hostel",   # not a valid slug
            listing_id="x",
            current_user=owner,
            db=seeded_db,
        )
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_get_after_set_roundtrip(seeded_db):
    owner, acc = await _make(seeded_db)
    await update_billing_config(
        listing_type="accommodation",
        listing_id=acc.id,
        body=BillingConfigUpdate(
            gst_category="HOSTEL_PG",
            gst_sac="996311",
            price_display_mode="GST_EXTRA",
            billing_anchor_day=5,
        ),
        current_user=owner,
        db=seeded_db,
    )
    out = await get_billing_config(
        listing_type="accommodation",
        listing_id=acc.id,
        current_user=owner,
        db=seeded_db,
    )
    assert out.gst_category == "HOSTEL_PG"
    assert out.gst_sac == "996311"
    assert out.price_display_mode == "GST_EXTRA"
    assert out.billing_anchor_day == 5
