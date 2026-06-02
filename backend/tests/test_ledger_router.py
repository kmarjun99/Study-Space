"""Tests for the super-admin ledger explorer endpoints.

Hits the router functions directly. Each filter combination must:
  - narrow the result set correctly
  - return correct totals (Σdr / Σcr) over the unpaginated set
  - never leak rows that don't match the filter

The CSV export must include the header row and one row per matching entry.
The group-balance endpoint must mark balanced groups correctly.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal

import pytest

from app.models.user import User, UserRole
from app.routers.ledger import (
    export_ledger_csv,
    get_group_balance,
    query_ledger,
)
from app.services.ledger_service import Entry, LedgerService
from app.services.tax_engine import q2


async def _super(db) -> User:
    s = User(id="sa-ledger", email="sa-ledger@x.com", hashed_password="x",
             name="Super", role=UserRole.SUPER_ADMIN)
    db.add(s)
    await db.commit()
    return s


async def _seed_groups(db) -> tuple[str, str]:
    """Post two balanced ledger groups: a booking + a settlement."""
    g1 = await LedgerService.post_entries(
        db, txn_group_id=None,
        source_type="BOOKING", source_id="bk-X",
        entries=[
            Entry(account_code="1010", debit=Decimal("2500"),
                  party_type="STUDENT", party_id="stu-1",
                  narration="Razorpay receipt"),
            Entry(account_code="2010", credit=Decimal("2500"),
                  party_type="OWNER", party_id="own-1",
                  narration="Owner payable"),
        ],
    )
    g2 = await LedgerService.post_entries(
        db, txn_group_id=None,
        source_type="SETTLEMENT", source_id="run-Y",
        entries=[
            Entry(account_code="2010", debit=Decimal("2500"),
                  party_type="OWNER", party_id="own-1",
                  narration="Owner payable cleared"),
            Entry(account_code="1011", credit=Decimal("2500"),
                  party_type="OWNER", party_id="own-1",
                  narration="Payout via RazorpayX"),
        ],
    )
    await db.commit()
    return g1, g2


# ---------- query_ledger ---------------------------------------------------

@pytest.mark.asyncio
async def test_unfiltered_query_returns_all_rows_with_totals(seeded_db):
    sa = await _super(seeded_db)
    await _seed_groups(seeded_db)

    page = await query_ledger(_=sa, db=seeded_db)
    assert page.total == 4
    assert page.sum_debit == 5000.0
    assert page.sum_credit == 5000.0


@pytest.mark.asyncio
async def test_filter_by_account_code(seeded_db):
    sa = await _super(seeded_db)
    await _seed_groups(seeded_db)
    page = await query_ledger(account_code="2010", _=sa, db=seeded_db)
    # 2010 (Owner Payable) is credited in group 1 (2500 Cr) + debited in group 2 (2500 Dr)
    assert page.total == 2
    assert page.sum_debit == 2500.0
    assert page.sum_credit == 2500.0


@pytest.mark.asyncio
async def test_filter_by_source_type(seeded_db):
    sa = await _super(seeded_db)
    await _seed_groups(seeded_db)
    page = await query_ledger(source_type="BOOKING", _=sa, db=seeded_db)
    assert page.total == 2
    assert all(r.source_type == "BOOKING" for r in page.rows)


@pytest.mark.asyncio
async def test_filter_by_party(seeded_db):
    sa = await _super(seeded_db)
    await _seed_groups(seeded_db)
    page = await query_ledger(party_type="OWNER", party_id="own-1",
                              _=sa, db=seeded_db)
    # Owner appears in: group1 (2010 Cr 2500), group2 (2010 Dr 2500, 1011 Cr 2500)
    assert page.total == 3


@pytest.mark.asyncio
async def test_side_debit_only(seeded_db):
    sa = await _super(seeded_db)
    await _seed_groups(seeded_db)
    page = await query_ledger(side="DEBIT", _=sa, db=seeded_db)
    assert all(r.debit > 0 and r.credit == 0 for r in page.rows)
    assert page.sum_credit == 0.0


@pytest.mark.asyncio
async def test_side_credit_only(seeded_db):
    sa = await _super(seeded_db)
    await _seed_groups(seeded_db)
    page = await query_ledger(side="CREDIT", _=sa, db=seeded_db)
    assert all(r.credit > 0 and r.debit == 0 for r in page.rows)
    assert page.sum_debit == 0.0


@pytest.mark.asyncio
async def test_pagination(seeded_db):
    sa = await _super(seeded_db)
    await _seed_groups(seeded_db)
    page1 = await query_ledger(limit=2, offset=0, _=sa, db=seeded_db)
    page2 = await query_ledger(limit=2, offset=2, _=sa, db=seeded_db)
    assert len(page1.rows) == 2
    assert len(page2.rows) == 2
    # Both pages report the same total (the unpaginated count)
    assert page1.total == page2.total == 4
    # Rows don't overlap
    assert {r.id for r in page1.rows}.isdisjoint({r.id for r in page2.rows})


@pytest.mark.asyncio
async def test_limit_validation(seeded_db):
    from fastapi import HTTPException
    sa = await _super(seeded_db)
    with pytest.raises(HTTPException) as exc:
        await query_ledger(limit=0, _=sa, db=seeded_db)
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_date_range_filter(seeded_db):
    sa = await _super(seeded_db)
    await _seed_groups(seeded_db)
    # All rows are "now" — filtering by tomorrow should yield zero
    future = datetime.utcnow() + timedelta(days=1)
    page = await query_ledger(posted_from=future, _=sa, db=seeded_db)
    assert page.total == 0
    assert page.rows == []


# ---------- CSV export ----------------------------------------------------

@pytest.mark.asyncio
async def test_csv_export_header_and_rows(seeded_db):
    sa = await _super(seeded_db)
    await _seed_groups(seeded_db)
    resp = await export_ledger_csv(_=sa, db=seeded_db)
    body = resp.body.decode("utf-8")
    lines = body.strip().split("\n")
    assert len(lines) == 1 + 4  # header + 4 rows
    assert lines[0].startswith("posted_at,txn_group_id")
    assert "BOOKING" in body and "SETTLEMENT" in body


@pytest.mark.asyncio
async def test_csv_export_respects_filter(seeded_db):
    sa = await _super(seeded_db)
    await _seed_groups(seeded_db)
    resp = await export_ledger_csv(source_type="BOOKING", _=sa, db=seeded_db)
    body = resp.body.decode("utf-8")
    lines = body.strip().split("\n")
    assert len(lines) == 1 + 2  # header + 2 booking rows
    assert "SETTLEMENT" not in body


# ---------- group balance ------------------------------------------------

@pytest.mark.asyncio
async def test_group_balance_marks_balanced(seeded_db):
    sa = await _super(seeded_db)
    g1, _ = await _seed_groups(seeded_db)
    row = await get_group_balance(txn_group_id=g1, _=sa, db=seeded_db)
    assert q2(Decimal(str(row.sum_debit))) == q2(Decimal("2500"))
    assert q2(Decimal(str(row.sum_credit))) == q2(Decimal("2500"))
    assert row.balanced is True


@pytest.mark.asyncio
async def test_group_balance_unknown_group(seeded_db):
    """Unknown groups return zeros and balanced=False (no rows summed)."""
    sa = await _super(seeded_db)
    row = await get_group_balance(txn_group_id="nope", _=sa, db=seeded_db)
    assert row.sum_debit == 0.0
    assert row.sum_credit == 0.0
    assert row.balanced is False
