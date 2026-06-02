"""Idempotent migration: add accounting / GST / KYC columns to existing tables.

This script is safe to run multiple times. It uses ALTER TABLE ... ADD COLUMN
IF NOT EXISTS (Postgres) or a try/except wrapper for SQLite, mirroring the
pattern already in `main.py` startup.

New tables are NOT created here — SQLAlchemy's `Base.metadata.create_all`
handles them (and only creates what's missing).

Run:
    python -m scripts.migrate_add_accounting_columns
"""
from __future__ import annotations
import asyncio
import sys
from pathlib import Path

# Allow running both as module and as direct script
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text
from app.database import engine, AsyncSessionLocal, Base


# (table, column, ddl-type-with-default)
ADDITIVE_COLUMNS: list[tuple[str, str, str]] = [
    # ---- users (owner accounting + KYC) ----
    ("users", "legal_name",              "VARCHAR(255)"),
    ("users", "pan",                     "VARCHAR(10)"),
    ("users", "gstin",                   "VARCHAR(15)"),
    ("users", "gst_registration_type",   "VARCHAR(20)"),
    ("users", "business_state_code",     "VARCHAR(2)"),
    ("users", "bank_account_holder",     "VARCHAR(255)"),
    ("users", "bank_account_number",     "VARCHAR(64)"),
    ("users", "bank_ifsc",               "VARCHAR(11)"),
    ("users", "bank_verified_at",        "TIMESTAMP"),
    ("users", "kyc_status",              "VARCHAR(20)"),
    ("users", "kyc_reviewed_by",         "VARCHAR(36)"),
    ("users", "kyc_reviewed_at",         "TIMESTAMP"),
    ("users", "kyc_notes",               "TEXT"),

    # ---- reading_rooms (maintenance billing + GST category) ----
    ("reading_rooms", "gst_category",         "VARCHAR(30)"),
    ("reading_rooms", "gst_sac",              "VARCHAR(10)"),
    ("reading_rooms", "gst_rate_override",    "NUMERIC(5,4)"),
    ("reading_rooms", "billing_anchor_day",   "SMALLINT DEFAULT 1"),
    ("reading_rooms", "maintenance_status",   "VARCHAR(30) DEFAULT 'CURRENT'"),
    ("reading_rooms", "visibility_score",     "NUMERIC(4,3) DEFAULT 1.000"),
    ("reading_rooms", "price_display_mode",   "VARCHAR(20)"),
    ("reading_rooms", "recommendation_priority", "INTEGER"),
    ("reading_rooms", "recommendation_excluded", "BOOLEAN DEFAULT FALSE"),

    # ---- accommodations (same shape as reading_rooms) ----
    ("accommodations", "gst_category",         "VARCHAR(30)"),
    ("accommodations", "gst_sac",              "VARCHAR(10)"),
    ("accommodations", "gst_rate_override",    "NUMERIC(5,4)"),
    ("accommodations", "billing_anchor_day",   "SMALLINT DEFAULT 1"),
    ("accommodations", "maintenance_status",   "VARCHAR(30) DEFAULT 'CURRENT'"),
    ("accommodations", "visibility_score",     "NUMERIC(4,3) DEFAULT 1.000"),
    ("accommodations", "price_display_mode",   "VARCHAR(20)"),
    ("accommodations", "recommendation_priority", "INTEGER"),
    ("accommodations", "recommendation_excluded", "BOOLEAN DEFAULT FALSE"),

    # ---- bookings (tax breakdown) ----
    ("bookings", "base_amount",              "NUMERIC(12,2)"),
    ("bookings", "gst_amount",               "NUMERIC(12,2)"),
    ("bookings", "gst_rate_applied",         "NUMERIC(5,4)"),
    ("bookings", "gst_treatment",            "VARCHAR(20)"),
    ("bookings", "place_of_supply_state",    "VARCHAR(2)"),
    ("bookings", "frozen_tax_snapshot_id",   "VARCHAR(36)"),
    ("bookings", "paid_at",                  "TIMESTAMP"),
    ("bookings", "settled_at",               "TIMESTAMP"),
    ("bookings", "settlement_run_id",        "VARCHAR(36)"),

    # ---- invoices (doc_type + series + GST split) ----
    ("invoices", "owner_charge_id",          "VARCHAR(36)"),
    ("invoices", "doc_type",                 "VARCHAR(30) DEFAULT 'LEGACY'"),
    ("invoices", "series_code",              "VARCHAR(10)"),
    ("invoices", "fiscal_year",              "VARCHAR(7)"),
    ("invoices", "sequence_no",              "INTEGER"),
    ("invoices", "supplier_party_id",        "VARCHAR(36)"),
    ("invoices", "recipient_party_id",       "VARCHAR(36)"),
    ("invoices", "place_of_supply_state",    "VARCHAR(2)"),
    ("invoices", "cgst",                     "NUMERIC(12,2)"),
    ("invoices", "sgst",                     "NUMERIC(12,2)"),
    ("invoices", "igst",                     "NUMERIC(12,2)"),
    ("invoices", "cess",                     "NUMERIC(12,2)"),
    ("invoices", "base_amount",              "NUMERIC(12,2)"),
    ("invoices", "hsn_sac",                  "VARCHAR(10)"),
    ("invoices", "irn",                      "VARCHAR(64)"),
    ("invoices", "qr_payload",               "TEXT"),
    ("invoices", "tax_snapshot_id",          "VARCHAR(36)"),
]


async def _is_sqlite() -> bool:
    return engine.url.drivername.startswith("sqlite")


async def _column_exists(db, table: str, column: str) -> bool:
    """Cross-DB column-existence check."""
    if await _is_sqlite():
        rows = (await db.execute(text(f"PRAGMA table_info({table})"))).fetchall()
        return any(r[1] == column for r in rows)
    rows = (await db.execute(
        text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name = :t AND column_name = :c"
        ),
        {"t": table, "c": column},
    )).fetchall()
    return bool(rows)


async def _add_column(db, table: str, column: str, ddl: str) -> None:
    if await _column_exists(db, table, column):
        print(f"  · {table}.{column} already present")
        return
    sql = f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"
    try:
        await db.execute(text(sql))
        print(f"  + {table}.{column}  ({ddl})")
    except Exception as exc:
        # Race: another process added the column between our existence check
        # and the ALTER. Re-check; if still missing, re-raise.
        if await _column_exists(db, table, column):
            print(f"  · {table}.{column} created concurrently — ok")
        else:
            print(f"  ! {table}.{column} failed: {exc}")
            raise


async def run() -> None:
    print("=== StudySpace accounting columns migration ===")
    # First, create any new tables defined in metadata.
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✅ New tables created/verified via metadata.create_all")

    # Then, ALTER existing tables to add additive columns.
    async with AsyncSessionLocal() as db:
        for table, column, ddl in ADDITIVE_COLUMNS:
            await _add_column(db, table, column, ddl)
        await db.commit()

    print("✅ Migration complete.")


if __name__ == "__main__":
    asyncio.run(run())
