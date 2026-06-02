"""Double-entry ledger writer.

Single point of truth. Routers MUST NOT insert into `ledger_entries` directly.

Invariants enforced here:
  - Every call validates Σdebit == Σcredit (rejected otherwise).
  - Posting is idempotent on `(txn_group_id, source_type, source_id)`:
    a re-call returns the existing entries instead of inserting duplicates.
  - Entries are insert-only — there is no `update_entries` / `delete_entries`.
    Corrections are made by posting a fresh reversing group.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ledger_entry import LedgerEntry
from app.services.tax_engine import q2, to_decimal, ZERO


@dataclass
class Entry:
    account_code: str
    debit: Decimal = ZERO
    credit: Decimal = ZERO
    party_type: Optional[str] = None
    party_id: Optional[str] = None
    narration: Optional[str] = None
    currency: str = "INR"


class LedgerImbalanceError(ValueError):
    """Raised when a posting group's debits != credits."""


class LedgerService:
    @staticmethod
    def new_txn_group_id() -> str:
        return str(uuid.uuid4())

    @staticmethod
    async def is_already_posted(
        db: AsyncSession, *, source_type: str, source_id: str,
    ) -> bool:
        """Has this business event already been posted?"""
        result = await db.execute(
            select(LedgerEntry.id)
            .where(and_(
                LedgerEntry.source_type == source_type,
                LedgerEntry.source_id == source_id,
            ))
            .limit(1)
        )
        return result.first() is not None

    @staticmethod
    def _validate_balance(entries: list[Entry]) -> tuple[Decimal, Decimal]:
        if len(entries) < 2:
            raise LedgerImbalanceError(
                "A ledger group must contain at least 2 entries."
            )
        dr = ZERO
        cr = ZERO
        for e in entries:
            d = q2(to_decimal(e.debit))
            c = q2(to_decimal(e.credit))
            if (d > 0 and c > 0) or (d == 0 and c == 0):
                raise LedgerImbalanceError(
                    f"Each entry must have exactly one of debit/credit non-zero "
                    f"(account {e.account_code}: dr={d}, cr={c})."
                )
            dr += d
            cr += c
        if q2(dr) != q2(cr):
            raise LedgerImbalanceError(
                f"Σdebit ({q2(dr)}) != Σcredit ({q2(cr)})."
            )
        return q2(dr), q2(cr)

    @classmethod
    async def post_entries(
        cls,
        db: AsyncSession,
        *,
        txn_group_id: Optional[str],
        source_type: str,
        source_id: str,
        entries: list[Entry],
        narration: Optional[str] = None,
    ) -> str:
        """Post a balanced ledger group. Returns the txn_group_id."""
        if await cls.is_already_posted(db, source_type=source_type, source_id=source_id):
            existing = (await db.execute(
                select(LedgerEntry.txn_group_id)
                .where(and_(
                    LedgerEntry.source_type == source_type,
                    LedgerEntry.source_id == source_id,
                ))
                .limit(1)
            )).scalar_one()
            return existing

        cls._validate_balance(entries)
        group_id = txn_group_id or cls.new_txn_group_id()

        for e in entries:
            db.add(LedgerEntry(
                txn_group_id=group_id,
                account_code=e.account_code,
                party_type=e.party_type,
                party_id=e.party_id,
                debit=q2(to_decimal(e.debit)),
                credit=q2(to_decimal(e.credit)),
                currency=e.currency,
                source_type=source_type,
                source_id=source_id,
                narration=e.narration or narration,
            ))
        await db.flush()
        return group_id

    # ---------- read helpers ----------

    @staticmethod
    async def get_account_balance(
        db: AsyncSession,
        *,
        account_code: str,
        party_id: Optional[str] = None,
    ) -> Decimal:
        """Return current balance for an account (Σdebit - Σcredit)."""
        from sqlalchemy import func
        stmt = select(
            func.coalesce(func.sum(LedgerEntry.debit), 0),
            func.coalesce(func.sum(LedgerEntry.credit), 0),
        ).where(LedgerEntry.account_code == account_code)
        if party_id is not None:
            stmt = stmt.where(LedgerEntry.party_id == party_id)
        row = (await db.execute(stmt)).one()
        return q2(to_decimal(row[0]) - to_decimal(row[1]))

    @staticmethod
    async def integrity_check(db: AsyncSession) -> list[str]:
        """Return list of txn_group_ids where Σdr != Σcr.

        Empty list = healthy. Called by the nightly integrity job.
        """
        from sqlalchemy import func
        stmt = (
            select(
                LedgerEntry.txn_group_id,
                func.coalesce(func.sum(LedgerEntry.debit), 0).label("dr"),
                func.coalesce(func.sum(LedgerEntry.credit), 0).label("cr"),
            )
            .group_by(LedgerEntry.txn_group_id)
        )
        rows = (await db.execute(stmt)).all()
        bad: list[str] = []
        for row in rows:
            if q2(to_decimal(row[1])) != q2(to_decimal(row[2])):
                bad.append(row[0])
        return bad
