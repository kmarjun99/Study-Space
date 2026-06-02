"""Super-admin ledger explorer.

Lets super admins inspect double-entry rows without DB access. Supports:
  - Date range
  - Account code (exact)
  - Party type / party id (exact)
  - Source type / source id (exact)
  - Debit-only / Credit-only / both
  - Per-page limit
  - CSV export of the filtered set
  - Per-txn-group balance check (Σdr == Σcr per group)

Super-admin only. Owners and students must not reach this router.
"""
from __future__ import annotations

import csv
import io
from datetime import datetime
from decimal import Decimal
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_super_admin
from app.models.ledger_entry import LedgerEntry
from app.models.user import User
from app.services.tax_engine import q2, to_decimal


router = APIRouter(prefix="/super-admin/ledger", tags=["Super Admin: Ledger"])


# ---------- response schemas -----------------------------------------------

class LedgerRow(BaseModel):
    id: str
    posted_at: str
    txn_group_id: str
    account_code: str
    party_type: Optional[str]
    party_id: Optional[str]
    debit: float
    credit: float
    currency: str
    source_type: str
    source_id: str
    narration: Optional[str]

    @classmethod
    def from_model(cls, r: LedgerEntry) -> "LedgerRow":
        return cls(
            id=r.id,
            posted_at=r.posted_at.isoformat(),
            txn_group_id=r.txn_group_id,
            account_code=r.account_code,
            party_type=r.party_type,
            party_id=r.party_id,
            debit=float(r.debit),
            credit=float(r.credit),
            currency=r.currency,
            source_type=r.source_type,
            source_id=r.source_id,
            narration=r.narration,
        )


class LedgerPage(BaseModel):
    rows: list[LedgerRow]
    total: int
    sum_debit: float
    sum_credit: float


class GroupBalanceRow(BaseModel):
    txn_group_id: str
    sum_debit: float
    sum_credit: float
    balanced: bool


# ---------- filter helpers ------------------------------------------------

def _apply_filters(
    stmt,
    *,
    posted_from: Optional[datetime],
    posted_to: Optional[datetime],
    account_code: Optional[str],
    party_type: Optional[str],
    party_id: Optional[str],
    source_type: Optional[str],
    source_id: Optional[str],
    txn_group_id: Optional[str],
    side: Optional[str],
):
    if posted_from is not None:
        stmt = stmt.where(LedgerEntry.posted_at >= posted_from)
    if posted_to is not None:
        stmt = stmt.where(LedgerEntry.posted_at < posted_to)
    if account_code:
        stmt = stmt.where(LedgerEntry.account_code == account_code)
    if party_type:
        stmt = stmt.where(LedgerEntry.party_type == party_type)
    if party_id:
        stmt = stmt.where(LedgerEntry.party_id == party_id)
    if source_type:
        stmt = stmt.where(LedgerEntry.source_type == source_type)
    if source_id:
        stmt = stmt.where(LedgerEntry.source_id == source_id)
    if txn_group_id:
        stmt = stmt.where(LedgerEntry.txn_group_id == txn_group_id)
    if side == "DEBIT":
        stmt = stmt.where(LedgerEntry.debit > 0)
    elif side == "CREDIT":
        stmt = stmt.where(LedgerEntry.credit > 0)
    return stmt


# ---------- endpoints ------------------------------------------------------

@router.get("", response_model=LedgerPage)
async def query_ledger(
    posted_from: Optional[datetime] = None,
    posted_to: Optional[datetime] = None,
    account_code: Optional[str] = None,
    party_type: Optional[str] = None,
    party_id: Optional[str] = None,
    source_type: Optional[str] = None,
    source_id: Optional[str] = None,
    txn_group_id: Optional[str] = None,
    side: Optional[Literal["DEBIT", "CREDIT"]] = None,
    limit: int = 200,
    offset: int = 0,
    _: User = Depends(get_current_super_admin),
    db: AsyncSession = Depends(get_db),
) -> LedgerPage:
    """Page through ledger entries with the supplied filters."""
    if limit < 1 or limit > 1000:
        raise HTTPException(status_code=400,
                            detail="limit must be between 1 and 1000")

    base = _apply_filters(
        select(LedgerEntry),
        posted_from=posted_from, posted_to=posted_to,
        account_code=account_code, party_type=party_type, party_id=party_id,
        source_type=source_type, source_id=source_id,
        txn_group_id=txn_group_id, side=side,
    )

    # Totals across the (unpaginated) filter result
    totals_stmt = _apply_filters(
        select(
            func.count(LedgerEntry.id),
            func.coalesce(func.sum(LedgerEntry.debit), 0),
            func.coalesce(func.sum(LedgerEntry.credit), 0),
        ),
        posted_from=posted_from, posted_to=posted_to,
        account_code=account_code, party_type=party_type, party_id=party_id,
        source_type=source_type, source_id=source_id,
        txn_group_id=txn_group_id, side=side,
    )
    total_n, total_dr, total_cr = (await db.execute(totals_stmt)).one()

    rows = (await db.execute(
        base.order_by(LedgerEntry.posted_at.desc()).offset(offset).limit(limit)
    )).scalars().all()

    return LedgerPage(
        rows=[LedgerRow.from_model(r) for r in rows],
        total=int(total_n),
        sum_debit=float(to_decimal(total_dr)),
        sum_credit=float(to_decimal(total_cr)),
    )


@router.get("/export.csv")
async def export_ledger_csv(
    posted_from: Optional[datetime] = None,
    posted_to: Optional[datetime] = None,
    account_code: Optional[str] = None,
    party_type: Optional[str] = None,
    party_id: Optional[str] = None,
    source_type: Optional[str] = None,
    source_id: Optional[str] = None,
    txn_group_id: Optional[str] = None,
    side: Optional[Literal["DEBIT", "CREDIT"]] = None,
    _: User = Depends(get_current_super_admin),
    db: AsyncSession = Depends(get_db),
):
    """CSV export of the filtered ledger. No pagination — caller is responsible
    for using a tight filter so the result fits in memory."""
    stmt = _apply_filters(
        select(LedgerEntry),
        posted_from=posted_from, posted_to=posted_to,
        account_code=account_code, party_type=party_type, party_id=party_id,
        source_type=source_type, source_id=source_id,
        txn_group_id=txn_group_id, side=side,
    ).order_by(LedgerEntry.posted_at)
    rows = (await db.execute(stmt)).scalars().all()

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow([
        "posted_at", "txn_group_id", "source_type", "source_id",
        "account_code", "party_type", "party_id",
        "debit", "credit", "currency", "narration",
    ])
    for r in rows:
        w.writerow([
            r.posted_at.isoformat(), r.txn_group_id, r.source_type, r.source_id,
            r.account_code, r.party_type or "", r.party_id or "",
            f"{r.debit:.2f}", f"{r.credit:.2f}", r.currency, r.narration or "",
        ])
    filename = f"ledger_{datetime.utcnow().strftime('%Y%m%dT%H%M%S')}.csv"
    return Response(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/groups/{txn_group_id}", response_model=GroupBalanceRow)
async def get_group_balance(
    txn_group_id: str,
    _: User = Depends(get_current_super_admin),
    db: AsyncSession = Depends(get_db),
) -> GroupBalanceRow:
    """Return Σdr / Σcr / balanced for one txn_group_id."""
    row = (await db.execute(
        select(
            func.coalesce(func.sum(LedgerEntry.debit), 0),
            func.coalesce(func.sum(LedgerEntry.credit), 0),
        ).where(LedgerEntry.txn_group_id == txn_group_id)
    )).one()
    dr = q2(to_decimal(row[0]))
    cr = q2(to_decimal(row[1]))
    return GroupBalanceRow(
        txn_group_id=txn_group_id,
        sum_debit=float(dr),
        sum_credit=float(cr),
        balanced=(dr == cr) and (dr > Decimal("0") or cr > Decimal("0")),
    )
