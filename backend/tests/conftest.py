"""Shared pytest fixtures for the accounting test suite.

We deliberately use an isolated in-memory SQLite DB per test so the live
project DB is never touched. Async SQLAlchemy is bound through aiosqlite.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

# Repo path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Force a known SQLite URL BEFORE app.database is imported.
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("ALGORITHM", "HS256")

from app.database import Base  # noqa: E402
# Importing the models package registers all tables with Base.metadata
import app.models  # noqa: F401, E402
from app.models.chart_of_accounts import ChartOfAccounts  # noqa: E402
from app.models.tax_config import TaxConfig  # noqa: E402


@pytest_asyncio.fixture
async def engine():
    eng = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    try:
        yield eng
    finally:
        await eng.dispose()


@pytest_asyncio.fixture
async def db(engine) -> AsyncSession:
    Session = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as session:
        yield session


@pytest_asyncio.fixture
async def seeded_db(db: AsyncSession):
    """A DB with chart_of_accounts + a permissive tax_config seeded."""
    accounts = [
        ("1010", "Razorpay Receivable",       "ASSET",     "Dr"),
        ("1011", "Razorpay Settlement A/c",   "ASSET",     "Dr"),
        ("1020", "Bank — Current",            "ASSET",     "Dr"),
        ("2010", "Owner Payable",             "LIABILITY", "Cr"),
        ("2020", "GST Output — CGST",         "LIABILITY", "Cr"),
        ("2021", "GST Output — SGST",         "LIABILITY", "Cr"),
        ("2022", "GST Output — IGST",         "LIABILITY", "Cr"),
        ("2030", "TCS Payable — CGST",        "LIABILITY", "Cr"),
        ("2031", "TCS Payable — SGST",        "LIABILITY", "Cr"),
        ("2032", "TCS Payable — IGST",        "LIABILITY", "Cr"),
        ("2040", "TDS Payable — 194-O",       "LIABILITY", "Cr"),
        ("2050", "Refund Provision",          "LIABILITY", "Cr"),
        ("4010", "Revenue — Listing Fee",     "INCOME",    "Cr"),
        ("4011", "Revenue — Maintenance Fee", "INCOME",    "Cr"),
        ("4012", "Revenue — Facilitation Fee","INCOME",    "Cr"),
        ("5010", "Payment Gateway Charges",   "EXPENSE",   "Dr"),
    ]
    for code, name, t, side in accounts:
        db.add(ChartOfAccounts(code=code, name=name, type=t, normal_side=side, is_active=True))

    cfg = {
        "accounting.enabled": True,
        "platform.home_state": "KA",
        "platform.gstin": "29AABCT1234A1Z5",
        "platform.legal_name": "StudySpace Technology Pvt Ltd",
        "platform.address": "Bengaluru",
        "gst.platform_fee_rate": 0.18,
        "gst.platform_fee_inclusive": False,
        "gst.platform_fee_sac": "998599",
        "gst.booking.default_rate": 0.18,
        "gst.booking.pricing_is_inclusive": True,
        "gst.booking.default_sac": "996311",
        "gst.booking.sec_9_5_eligible_categories": ["HOTEL_LIKE", "SHORT_STAY"],
        "tcs.enabled": False,
        "tcs.rate_cgst": 0.0025,
        "tcs.rate_sgst": 0.0025,
        "tcs.rate_igst": 0.005,
        "tcs.applies_to_unregistered_owner": False,
        "tds.section_194o_enabled": False,
        "tds.section_194o_rate": 0.001,
        "tds.section_194o_threshold_yearly": 500000,
        "maintenance.overdue.dim_days": 7,
        "maintenance.overdue.suspend_days": 10,
        "maintenance.overdue.hide_days": 15,
        "feature.recurring_maintenance": False,
    }
    for k, v in cfg.items():
        db.add(TaxConfig(key=k, value=json.dumps(v)))
    await db.commit()
    return db
