"""Ledger service tests.

Proves the three core ledger invariants:
  1. Σdebit == Σcredit per posting group.
  2. Each entry has exactly one of (debit, credit) non-zero.
  3. Posting twice for the same (source_type, source_id) is a no-op.
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from app.services.ledger_service import Entry, LedgerImbalanceError, LedgerService


@pytest.mark.asyncio
async def test_balanced_post_succeeds(seeded_db):
    entries = [
        Entry(account_code="1010", debit=Decimal("100")),
        Entry(account_code="2010", credit=Decimal("100")),
    ]
    group = await LedgerService.post_entries(
        seeded_db, txn_group_id=None,
        source_type="TEST", source_id="t1",
        entries=entries,
    )
    await seeded_db.commit()
    assert group


@pytest.mark.asyncio
async def test_imbalanced_post_rejected(seeded_db):
    entries = [
        Entry(account_code="1010", debit=Decimal("100")),
        Entry(account_code="2010", credit=Decimal("90")),
    ]
    with pytest.raises(LedgerImbalanceError):
        await LedgerService.post_entries(
            seeded_db, txn_group_id=None,
            source_type="TEST", source_id="t2",
            entries=entries,
        )


@pytest.mark.asyncio
async def test_entry_with_both_dr_and_cr_rejected(seeded_db):
    bad = [
        Entry(account_code="1010", debit=Decimal("50"), credit=Decimal("50")),
        Entry(account_code="2010", credit=Decimal("50")),
    ]
    with pytest.raises(LedgerImbalanceError):
        await LedgerService.post_entries(
            seeded_db, txn_group_id=None,
            source_type="TEST", source_id="t3",
            entries=bad,
        )


@pytest.mark.asyncio
async def test_single_entry_rejected(seeded_db):
    """A balanced posting cannot consist of a single row."""
    with pytest.raises(LedgerImbalanceError):
        await LedgerService.post_entries(
            seeded_db, txn_group_id=None,
            source_type="TEST", source_id="t4",
            entries=[Entry(account_code="1010", debit=Decimal("100"))],
        )


@pytest.mark.asyncio
async def test_double_post_is_idempotent(seeded_db):
    entries = [
        Entry(account_code="1010", debit=Decimal("100")),
        Entry(account_code="2010", credit=Decimal("100")),
    ]
    g1 = await LedgerService.post_entries(
        seeded_db, txn_group_id=None,
        source_type="TEST", source_id="t-idem",
        entries=entries,
    )
    g2 = await LedgerService.post_entries(
        seeded_db, txn_group_id=None,
        source_type="TEST", source_id="t-idem",
        entries=entries,
    )
    await seeded_db.commit()
    assert g1 == g2

    # Only ONE pair of rows exists (idempotent re-call did not insert duplicates).
    from sqlalchemy import select, func
    from app.models.ledger_entry import LedgerEntry
    count = (await seeded_db.execute(
        select(func.count(LedgerEntry.id))
        .where(LedgerEntry.source_id == "t-idem")
    )).scalar_one()
    assert count == 2


@pytest.mark.asyncio
async def test_integrity_check_reports_nothing_for_balanced_groups(seeded_db):
    await LedgerService.post_entries(
        seeded_db, txn_group_id=None,
        source_type="TEST", source_id="t-ok",
        entries=[
            Entry(account_code="1010", debit=Decimal("100")),
            Entry(account_code="2010", credit=Decimal("100")),
        ],
    )
    await seeded_db.commit()
    bad = await LedgerService.integrity_check(seeded_db)
    assert bad == []


@pytest.mark.asyncio
async def test_account_balance(seeded_db):
    await LedgerService.post_entries(
        seeded_db, txn_group_id=None,
        source_type="TEST", source_id="bal",
        entries=[
            Entry(account_code="1010", debit=Decimal("200")),
            Entry(account_code="2010", credit=Decimal("200"), party_id="owner-x"),
        ],
    )
    await seeded_db.commit()
    bank = await LedgerService.get_account_balance(seeded_db, account_code="1010")
    owner = await LedgerService.get_account_balance(seeded_db, account_code="2010", party_id="owner-x")
    assert bank == Decimal("200.00")
    assert owner == Decimal("-200.00")  # liability: credit normal -> negative when shown as dr-cr
