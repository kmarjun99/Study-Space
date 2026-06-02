"""Tax engine unit tests.

These tests exercise pure functions and DB-backed config loading. They prove
the two business-critical claims:
  1. compute_inclusive_split(2500, 18%) == (2118.64, 381.36).
  2. base + gst always equals gross at 2 decimal places for any input.
"""
from __future__ import annotations

import random
from decimal import Decimal

import pytest

from app.services.tax_engine import (
    accounting_enabled,
    compute_booking_tax,
    compute_inclusive_split,
    compute_platform_fee_tax,
    freeze_snapshot,
    load_active_config,
    q2,
    split_gst_by_state,
)


def test_inclusive_split_2500_at_18pct():
    """Worked example from the business rules."""
    split = compute_inclusive_split(2500, Decimal("0.18"))
    assert split.base == Decimal("2118.64")
    assert split.gst == Decimal("381.36")
    assert q2(split.base + split.gst) == Decimal("2500.00")


def test_inclusive_split_zero_rate_pass_through():
    split = compute_inclusive_split(1000, 0)
    assert split.base == Decimal("1000.00")
    assert split.gst == Decimal("0.00")


def test_inclusive_split_zero_gross():
    split = compute_inclusive_split(0, Decimal("0.18"))
    assert split.base == Decimal("0")
    assert split.gst == Decimal("0")


def test_inclusive_split_sum_invariant_random():
    """For any random (gross, rate), base + gst must equal gross at 2dp."""
    random.seed(42)
    for _ in range(2000):
        gross = round(random.uniform(1, 100_000), 2)
        rate = Decimal(str(random.choice([0.05, 0.12, 0.18, 0.28])))
        split = compute_inclusive_split(gross, rate)
        assert q2(split.base + split.gst) == q2(gross), (
            f"sum mismatch: gross={gross} rate={rate} "
            f"base={split.base} gst={split.gst}"
        )


def test_split_gst_by_state_intra():
    amt = split_gst_by_state(Decimal("100.00"), "KA", "KA")
    assert amt.cgst == Decimal("50.00")
    assert amt.sgst == Decimal("50.00")
    assert amt.igst == Decimal("0")


def test_split_gst_by_state_odd_paise_lands_on_sgst():
    """If GST total is 0.01 odd, the residue stays on SGST so CGST+SGST = total exactly."""
    amt = split_gst_by_state(Decimal("0.03"), "KA", "KA")
    assert amt.cgst == Decimal("0.02")
    assert amt.sgst == Decimal("0.01")
    assert q2(amt.cgst + amt.sgst) == Decimal("0.03")


def test_split_gst_by_state_inter():
    amt = split_gst_by_state(Decimal("180.00"), "KA", "MH")
    assert amt.cgst == 0
    assert amt.sgst == 0
    assert amt.igst == Decimal("180.00")


def test_split_gst_by_state_unknown_recipient_defaults_to_igst():
    amt = split_gst_by_state(Decimal("180.00"), "KA", None)
    assert amt.igst == Decimal("180.00")


@pytest.mark.asyncio
async def test_load_active_config_parses_json(seeded_db):
    config = await load_active_config(seeded_db)
    assert config["accounting.enabled"] is True
    assert config["gst.booking.default_rate"] == 0.18
    assert config["platform.home_state"] == "KA"
    assert isinstance(config["gst.booking.sec_9_5_eligible_categories"], list)


@pytest.mark.asyncio
async def test_freeze_snapshot_returns_persisted_id(seeded_db):
    config = await load_active_config(seeded_db)
    snap = await freeze_snapshot(seeded_db, config)
    assert snap.id
    assert "platform.home_state" in snap.payload


@pytest.mark.asyncio
async def test_compute_platform_fee_tax_exclusive(seeded_db):
    """Platform fee defaults to exclusive — GST is added on top."""
    config = await load_active_config(seeded_db)
    snap = await freeze_snapshot(seeded_db, config)
    res = compute_platform_fee_tax(
        base_or_total=Decimal("999"),
        recipient_state="KA",
        config=config,
        snapshot_id=snap.id,
    )
    assert res.base == Decimal("999.00")
    # 999 * 0.18 = 179.82  ->  total 1178.82, split 89.91 / 89.91 intra-state.
    assert res.gst.cgst == Decimal("89.91")
    assert res.gst.sgst == Decimal("89.91")
    assert res.total == Decimal("1178.82")


@pytest.mark.asyncio
async def test_compute_booking_tax_inclusive_owner_registered(seeded_db, monkeypatch):
    """Owner-registered + inclusive pricing -> base=2118.64, gst=381.36, total=2500."""
    config = await load_active_config(seeded_db)
    snap = await freeze_snapshot(seeded_db, config)

    # Build a stand-in registered owner without hitting the User table for FK
    from app.models.user import User, GSTRegistrationType
    owner = User(
        id="o1", email="o@x.com", hashed_password="x", name="O",
        gst_registration_type=GSTRegistrationType.REGULAR,
        business_state_code="KA",
    )

    res = compute_booking_tax(
        gross=Decimal("2500"),
        owner=owner,
        listing_gst_category="READING_ROOM",
        place_of_supply_state="KA",
        config=config,
        snapshot_id=snap.id,
    )
    assert res.base == Decimal("2118.64")
    assert q2(res.gst.cgst + res.gst.sgst + res.gst.igst) == Decimal("381.36")
    assert res.gross == Decimal("2500.00")
    assert res.treatment.value == "OWNER_REGISTERED"


@pytest.mark.asyncio
async def test_accounting_enabled_flag(seeded_db):
    config = await load_active_config(seeded_db)
    assert accounting_enabled(config) is True
