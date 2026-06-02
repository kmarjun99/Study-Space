"""Tests for the pre-deploy safety-flag gate.

Three claims:
  1. With all protected flags either OFF or unset, the gate returns 0.
  2. If any one of them is ON without explicit --allow, the gate returns 1.
  3. --allow lets the operator bypass a specific flag and the gate returns 0
     (with that flag and only that flag bypassed).
"""
from __future__ import annotations

import json

import pytest
from sqlalchemy import select

from app.models.tax_config import TaxConfig
from scripts.check_safety_flags import PROTECTED_FLAGS, check


async def _set(db, key, value):
    row = (await db.execute(
        select(TaxConfig).where(TaxConfig.key == key)
    )).scalar_one_or_none()
    if row is None:
        db.add(TaxConfig(key=key, value=json.dumps(value)))
    else:
        row.value = json.dumps(value)
    await db.commit()


@pytest.mark.asyncio
async def test_passes_when_all_flags_off(seeded_db, monkeypatch):
    # The seeded fixture turns accounting.enabled ON for the shadow tests.
    # Explicitly flip it off here so this gate test reflects production state.
    await _set(seeded_db, "accounting.enabled", False)
    monkeypatch.setattr(
        "scripts.check_safety_flags.AsyncSessionLocal",
        lambda: _FakeSession(seeded_db),
    )
    rc = await check()
    assert rc == 0


@pytest.mark.asyncio
async def test_blocks_when_a_flag_is_on(seeded_db, monkeypatch):
    await _set(seeded_db, "accounting.enabled", True)
    monkeypatch.setattr(
        "scripts.check_safety_flags.AsyncSessionLocal",
        lambda: _FakeSession(seeded_db),
    )
    rc = await check()
    assert rc == 1


@pytest.mark.asyncio
async def test_allow_bypasses_one_flag(seeded_db, monkeypatch):
    await _set(seeded_db, "accounting.enabled", True)
    monkeypatch.setattr(
        "scripts.check_safety_flags.AsyncSessionLocal",
        lambda: _FakeSession(seeded_db),
    )
    rc = await check(allow={"accounting.enabled"})
    assert rc == 0


@pytest.mark.asyncio
async def test_allow_does_not_bypass_other_flags(seeded_db, monkeypatch):
    """Bypass one but trip another."""
    await _set(seeded_db, "accounting.enabled", True)
    await _set(seeded_db, "feature.gst_invoices", True)
    monkeypatch.setattr(
        "scripts.check_safety_flags.AsyncSessionLocal",
        lambda: _FakeSession(seeded_db),
    )
    rc = await check(allow={"accounting.enabled"})
    assert rc == 1


def test_protected_list_is_non_empty():
    """Sanity: the list must cover at least the four flags the friend named."""
    keys = {k for k, _ in PROTECTED_FLAGS}
    for required in [
        "accounting.enabled",
        "feature.gst_invoices",
        "feature.credit_notes",
        "feature.per_listing_price_mode",
    ]:
        assert required in keys


# ---------- session shim ---------------------------------------------------

class _FakeSession:
    """Mimics `async with AsyncSessionLocal() as db:` but yields the fixture's db."""

    def __init__(self, db):
        self._db = db

    async def __aenter__(self):
        return self._db

    async def __aexit__(self, exc_type, exc, tb):
        return False
