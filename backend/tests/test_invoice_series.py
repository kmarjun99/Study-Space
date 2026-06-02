"""Invoice-series allocator tests.

Acceptance criterion #12 — strictly monotonic, no gaps per (series, FY).
Also tests sequential allocation under simulated parallel use within one DB
session (true cross-process concurrency requires a row-level lock, exercised
only in Postgres).
"""
from __future__ import annotations

import pytest

from app.services.invoice_series_service import (
    InvoiceSeriesService,
    current_fiscal_year,
    format_invoice_number,
)


def test_fiscal_year_april_boundary():
    from datetime import date
    assert current_fiscal_year(date(2025, 4, 1)) == "25-26"
    assert current_fiscal_year(date(2025, 3, 31)) == "24-25"
    assert current_fiscal_year(date(2026, 1, 1)) == "25-26"


def test_format_invoice_number_padding():
    assert format_invoice_number("PLF", "25-26", 1) == "SS/PLF/25-26/000001"
    assert format_invoice_number("OBI", "25-26", 12345) == "SS/OBI/25-26/012345"


@pytest.mark.asyncio
async def test_sequential_allocation(db):
    nums: list[int] = []
    for _ in range(10):
        full, fy, n = await InvoiceSeriesService.next_number(
            db, series_code="PLF", fiscal_year="25-26",
        )
        nums.append(n)
    await db.commit()
    assert nums == list(range(1, 11))


@pytest.mark.asyncio
async def test_distinct_series_have_independent_counters(db):
    _, _, n_plf = await InvoiceSeriesService.next_number(db, series_code="PLF", fiscal_year="25-26")
    _, _, n_obi = await InvoiceSeriesService.next_number(db, series_code="OBI", fiscal_year="25-26")
    _, _, n_plf2 = await InvoiceSeriesService.next_number(db, series_code="PLF", fiscal_year="25-26")
    await db.commit()
    assert n_plf == 1
    assert n_obi == 1
    assert n_plf2 == 2


@pytest.mark.asyncio
async def test_distinct_fiscal_years_have_independent_counters(db):
    _, _, a = await InvoiceSeriesService.next_number(db, series_code="PLF", fiscal_year="24-25")
    _, _, b = await InvoiceSeriesService.next_number(db, series_code="PLF", fiscal_year="25-26")
    await db.commit()
    assert a == 1
    assert b == 1
