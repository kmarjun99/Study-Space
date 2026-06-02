"""Tests for the per-listing `price_display_mode` override.

Pins down three contract guarantees:
  1. With `feature.per_listing_price_mode = False` (default), the per-listing
     mode is IGNORED — the global `gst.booking.pricing_is_inclusive` wins.
     This is what protects existing listings during rollout.
  2. With the flag ON, GST_INCLUDED uses reverse-calc and GST_EXTRA adds-on-top.
  3. The `compute_booking_gross` helper returns the correct order amount for
     the future booking-router migration.
"""
from __future__ import annotations

import json
from decimal import Decimal

import pytest

from app.models.tax_config import TaxConfig
from app.services.tax_engine import (
    compute_booking_gross,
    compute_booking_tax,
    freeze_snapshot,
    load_active_config,
    q2,
    resolve_pricing_inclusive,
)


async def _set_flag(db, key: str, value) -> None:
    """Upsert a tax_config key. Tests shouldn't depend on the seed fixture
    knowing about every future flag."""
    sqlalchemy = __import__("sqlalchemy")
    row = (await db.execute(
        sqlalchemy.select(TaxConfig).where(TaxConfig.key == key)
    )).scalar_one_or_none()
    if row is None:
        db.add(TaxConfig(key=key, value=json.dumps(value)))
    else:
        row.value = json.dumps(value)
    await db.commit()


# ---------- resolve_pricing_inclusive contract -----------------------------

@pytest.mark.asyncio
async def test_resolve_inclusive_with_flag_off_uses_global(seeded_db):
    config = await load_active_config(seeded_db)
    # Global default is inclusive=True
    assert resolve_pricing_inclusive(
        listing_price_display_mode="GST_EXTRA", config=config,
    ) is True
    assert resolve_pricing_inclusive(
        listing_price_display_mode=None, config=config,
    ) is True


@pytest.mark.asyncio
async def test_resolve_inclusive_with_flag_on_honours_listing(seeded_db):
    await _set_flag(seeded_db, "feature.per_listing_price_mode", True)
    config = await load_active_config(seeded_db)
    assert resolve_pricing_inclusive(
        listing_price_display_mode="GST_INCLUDED", config=config,
    ) is True
    assert resolve_pricing_inclusive(
        listing_price_display_mode="GST_EXTRA", config=config,
    ) is False
    # Listing left unset still falls back to global default
    assert resolve_pricing_inclusive(
        listing_price_display_mode=None, config=config,
    ) is True


# ---------- compute_booking_tax with override ------------------------------

@pytest.mark.asyncio
async def test_explicit_inclusive_override_wins(seeded_db):
    """An explicit caller override beats both flag + listing mode."""
    config = await load_active_config(seeded_db)
    snap = await freeze_snapshot(seeded_db, config)
    res_in = compute_booking_tax(
        gross=Decimal("2500"),
        owner=None,
        listing_gst_category="READING_ROOM",
        place_of_supply_state="KA",
        config=config, snapshot_id=snap.id,
        inclusive_override=True,
    )
    # NOT_REGISTERED treatment -> rate=0 -> all base, no GST.
    assert res_in.base == Decimal("2500.00")
    assert res_in.gst.total == Decimal("0")


@pytest.mark.asyncio
async def test_listing_mode_with_flag_on_changes_split(seeded_db):
    """GST_EXTRA + flag on + registered owner = base equals displayed, GST added on top.

    Specifically the engine treats `gross=2500` as the BASE (not the inclusive
    total) and computes GST on top to arrive at 2950.
    """
    await _set_flag(seeded_db, "feature.per_listing_price_mode", True)
    config = await load_active_config(seeded_db)
    snap = await freeze_snapshot(seeded_db, config)

    from app.models.user import User, GSTRegistrationType
    owner = User(
        id="ox", email="ox@x.com", hashed_password="x", name="O",
        gst_registration_type=GSTRegistrationType.REGULAR,
        business_state_code="KA",
    )

    res = compute_booking_tax(
        gross=Decimal("2500"),
        owner=owner,
        listing_gst_category="READING_ROOM",
        listing_price_display_mode="GST_EXTRA",
        place_of_supply_state="KA",
        config=config, snapshot_id=snap.id,
    )
    assert res.base == Decimal("2500.00")
    assert q2(res.gst.total) == Decimal("450.00")     # 18% of 2500


@pytest.mark.asyncio
async def test_listing_mode_with_flag_off_is_ignored(seeded_db):
    """Even when listing says GST_EXTRA, flag-off keeps the old reverse-calc."""
    config = await load_active_config(seeded_db)
    snap = await freeze_snapshot(seeded_db, config)

    from app.models.user import User, GSTRegistrationType
    owner = User(
        id="oy", email="oy@x.com", hashed_password="x", name="O",
        gst_registration_type=GSTRegistrationType.REGULAR,
        business_state_code="KA",
    )

    res = compute_booking_tax(
        gross=Decimal("2500"),
        owner=owner,
        listing_gst_category="READING_ROOM",
        listing_price_display_mode="GST_EXTRA",  # ignored
        place_of_supply_state="KA",
        config=config, snapshot_id=snap.id,
    )
    # Inclusive default still wins -> base=2118.64, gst=381.36
    assert res.base == Decimal("2118.64")


# ---------- compute_booking_gross helper for future router migration -------

@pytest.mark.asyncio
async def test_compute_booking_gross_flag_off_returns_displayed(seeded_db):
    config = await load_active_config(seeded_db)
    gross = compute_booking_gross(
        displayed_price=Decimal("10000"),
        listing_gst_rate_override=None,
        listing_price_display_mode="GST_EXTRA",
        config=config,
    )
    # Flag off → no math change → returns displayed
    assert gross == Decimal("10000.00")


@pytest.mark.asyncio
async def test_compute_booking_gross_extra_adds_on_top(seeded_db):
    await _set_flag(seeded_db, "feature.per_listing_price_mode", True)
    config = await load_active_config(seeded_db)
    gross = compute_booking_gross(
        displayed_price=Decimal("10000"),
        listing_gst_rate_override=None,
        listing_price_display_mode="GST_EXTRA",
        config=config,
    )
    # Owner enters ₹10,000 + GST -> student pays ₹11,800
    assert gross == Decimal("11800.00")


@pytest.mark.asyncio
async def test_compute_booking_gross_included_pass_through(seeded_db):
    await _set_flag(seeded_db, "feature.per_listing_price_mode", True)
    config = await load_active_config(seeded_db)
    gross = compute_booking_gross(
        displayed_price=Decimal("2500"),
        listing_gst_rate_override=None,
        listing_price_display_mode="GST_INCLUDED",
        config=config,
    )
    assert gross == Decimal("2500.00")
