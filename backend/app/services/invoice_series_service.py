"""Atomic per-series invoice numbering.

GST law requires sequential, non-gapped invoice numbers per series per FY.
Timestamp-mod approaches (like the legacy `generate_invoice_number`) can
collide under concurrency — that's why this exists.

Strategy:
  - Row-level lock (`SELECT ... FOR UPDATE`) the counter row.
  - Increment, then return the new number.
  - For SQLite (dev), SQLite's writer-level serialization is enough; we use a
    plain SELECT + UPDATE in a transaction.

Caller is responsible for the surrounding transaction (commit/rollback).
"""
from __future__ import annotations

from datetime import date
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.invoice_series_counter import InvoiceSeriesCounter


def current_fiscal_year(as_of: Optional[date] = None) -> str:
    """Indian FY format: 'YY-YY' (e.g., '25-26' for Apr 2025 - Mar 2026)."""
    d = as_of or date.today()
    if d.month >= 4:
        start, end = d.year, d.year + 1
    else:
        start, end = d.year - 1, d.year
    return f"{start % 100:02d}-{end % 100:02d}"


def format_invoice_number(
    series_code: str, fiscal_year: str, seq_no: int, prefix: str = "SS"
) -> str:
    """Canonical display number e.g. 'SS/PLF/25-26/000001'."""
    return f"{prefix}/{series_code}/{fiscal_year}/{seq_no:06d}"


class InvoiceSeriesService:
    @staticmethod
    async def next_number(
        db: AsyncSession,
        *,
        series_code: str,
        fiscal_year: Optional[str] = None,
    ) -> tuple[str, str, int]:
        """Allocate the next sequence number atomically.

        Returns (display_number, fiscal_year, sequence_no).
        Caller must commit the surrounding transaction.
        """
        fy = fiscal_year or current_fiscal_year()
        dialect = db.bind.dialect.name if db.bind is not None else "sqlite"

        # Postgres: SELECT ... FOR UPDATE on the counter row, or insert.
        # SQLite: writer lock is implicit; SELECT then UPDATE is safe within tx.
        if dialect == "postgresql":
            row = (await db.execute(
                select(InvoiceSeriesCounter)
                .where(
                    (InvoiceSeriesCounter.series_code == series_code)
                    & (InvoiceSeriesCounter.fiscal_year == fy)
                )
                .with_for_update()
            )).scalar_one_or_none()
        else:
            row = (await db.execute(
                select(InvoiceSeriesCounter)
                .where(
                    (InvoiceSeriesCounter.series_code == series_code)
                    & (InvoiceSeriesCounter.fiscal_year == fy)
                )
            )).scalar_one_or_none()

        if row is None:
            # First number in this series/FY — two concurrent first-callers
            # race here because the FOR UPDATE above had no row to lock.
            # Use a SAVEPOINT around the INSERT; on IntegrityError the other
            # caller won the race, so we recover by re-SELECTing (now with
            # the row lock available) and incrementing normally.
            try:
                async with db.begin_nested():
                    db.add(InvoiceSeriesCounter(
                        series_code=series_code,
                        fiscal_year=fy,
                        last_no=1,
                    ))
                    await db.flush()
                new_no = 1
            except IntegrityError:
                if dialect == "postgresql":
                    row = (await db.execute(
                        select(InvoiceSeriesCounter)
                        .where(
                            (InvoiceSeriesCounter.series_code == series_code)
                            & (InvoiceSeriesCounter.fiscal_year == fy)
                        )
                        .with_for_update()
                    )).scalar_one()
                else:
                    row = (await db.execute(
                        select(InvoiceSeriesCounter)
                        .where(
                            (InvoiceSeriesCounter.series_code == series_code)
                            & (InvoiceSeriesCounter.fiscal_year == fy)
                        )
                    )).scalar_one()
                new_no = row.last_no + 1
                await db.execute(
                    update(InvoiceSeriesCounter)
                    .where(
                        (InvoiceSeriesCounter.series_code == series_code)
                        & (InvoiceSeriesCounter.fiscal_year == fy)
                    )
                    .values(last_no=new_no)
                )
        else:
            new_no = row.last_no + 1
            await db.execute(
                update(InvoiceSeriesCounter)
                .where(
                    (InvoiceSeriesCounter.series_code == series_code)
                    & (InvoiceSeriesCounter.fiscal_year == fy)
                )
                .values(last_no=new_no)
            )

        return format_invoice_number(series_code, fy, new_no), fy, new_no
