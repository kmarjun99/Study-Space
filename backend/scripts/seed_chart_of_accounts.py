"""Seed the chart_of_accounts table.

Idempotent: re-running upserts rows by primary key (account code).
"""
from __future__ import annotations
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select
from app.database import AsyncSessionLocal
from app.models.chart_of_accounts import ChartOfAccounts


ACCOUNTS: list[dict] = [
    # Assets
    {"code": "1010", "name": "Razorpay Receivable",            "type": "ASSET",     "normal_side": "Dr"},
    {"code": "1011", "name": "Razorpay Settlement A/c",        "type": "ASSET",     "normal_side": "Dr"},
    {"code": "1020", "name": "Bank — Current",                 "type": "ASSET",     "normal_side": "Dr"},
    # Liabilities
    {"code": "2010", "name": "Owner Payable",                  "type": "LIABILITY", "normal_side": "Cr"},
    {"code": "2020", "name": "GST Output — CGST",              "type": "LIABILITY", "normal_side": "Cr"},
    {"code": "2021", "name": "GST Output — SGST",              "type": "LIABILITY", "normal_side": "Cr"},
    {"code": "2022", "name": "GST Output — IGST",              "type": "LIABILITY", "normal_side": "Cr"},
    {"code": "2030", "name": "TCS Payable — CGST",             "type": "LIABILITY", "normal_side": "Cr"},
    {"code": "2031", "name": "TCS Payable — SGST",             "type": "LIABILITY", "normal_side": "Cr"},
    {"code": "2032", "name": "TCS Payable — IGST",             "type": "LIABILITY", "normal_side": "Cr"},
    {"code": "2040", "name": "TDS Payable — 194-O",            "type": "LIABILITY", "normal_side": "Cr"},
    {"code": "2050", "name": "Refund Provision",               "type": "LIABILITY", "normal_side": "Cr"},
    # Income (platform revenue only — never used by booking flow)
    {"code": "4010", "name": "Revenue — Listing Fee",          "type": "INCOME",    "normal_side": "Cr"},
    {"code": "4011", "name": "Revenue — Maintenance Fee",      "type": "INCOME",    "normal_side": "Cr"},
    {"code": "4012", "name": "Revenue — Facilitation Fee",     "type": "INCOME",    "normal_side": "Cr"},
    # Expenses
    {"code": "5010", "name": "Payment Gateway Charges",        "type": "EXPENSE",   "normal_side": "Dr"},
]


async def run() -> None:
    async with AsyncSessionLocal() as db:
        existing = {
            row.code for row in (await db.execute(select(ChartOfAccounts))).scalars().all()
        }
        added = 0
        for a in ACCOUNTS:
            if a["code"] in existing:
                continue
            db.add(ChartOfAccounts(**a, is_active=True))
            added += 1
        await db.commit()
        print(f"✅ chart_of_accounts seeded ({added} new, {len(existing)} pre-existing).")


if __name__ == "__main__":
    asyncio.run(run())
