"""Backfill all intelligence-layer additive columns onto existing tables.

Idempotent. Safe to re-run. Consolidates what
`migrate_add_notification_rule_id.py` + `migrate_add_reco_attribution.py`
do (and adds the Phase 3 recommendation_priority / recommendation_excluded
columns on listings that don't have a standalone migration script yet).

Works on Postgres (production) AND SQLite (local dev) via the shared
dialect-aware helper. The original PRAGMA-only version silently no-op'd
on Postgres because PRAGMA is SQLite syntax; `BOOLEAN DEFAULT 0` is also
SQLite-only — Postgres needs `DEFAULT FALSE`.

Run with:
    python -m scripts.migrate_intelligence_columns
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text
from app.database import engine
from scripts._migration_helpers import add_column_if_missing


# `BOOLEAN DEFAULT FALSE` works on BOTH Postgres and SQLite. Don't use
# `DEFAULT 0` — Postgres rejects it (no implicit int -> bool cast).
# `TIMESTAMP` instead of `DATETIME` for portability.
COLUMNS: list[tuple[str, str, str]] = [
    # Phase 3 — listing-level recommendation knobs.
    ("reading_rooms", "recommendation_priority", "INTEGER"),
    ("reading_rooms", "recommendation_excluded", "BOOLEAN DEFAULT FALSE NOT NULL"),
    ("accommodations", "recommendation_priority", "INTEGER"),
    ("accommodations", "recommendation_excluded", "BOOLEAN DEFAULT FALSE NOT NULL"),
    # Phase 4C — notification automation deliveries reuse campaign_deliveries.
    ("campaign_deliveries", "notification_rule_id", "VARCHAR"),
    # Phase 4D — recommendation attribution stamps.
    ("recommendation_logs", "clicked_at", "TIMESTAMP"),
    ("recommendation_logs", "converted_at", "TIMESTAMP"),
    ("recommendation_logs", "converted_booking_id", "VARCHAR"),
    ("recommendation_logs", "is_click_attributed", "BOOLEAN DEFAULT FALSE NOT NULL"),
]

INDEXES: list[tuple[str, str, str]] = [
    # (index_name, table, columns)
    ("ix_camp_deliv_rule", "campaign_deliveries", "notification_rule_id"),
    ("ix_reco_log_user_listing",
     "recommendation_logs", "user_id, listing_id, created_at"),
]


async def run() -> None:
    added = 0
    async with engine.begin() as conn:
        for table, col, decl in COLUMNS:
            if await add_column_if_missing(conn, table, col, decl):
                added += 1

        for index_name, table, cols in INDEXES:
            await conn.execute(text(
                f"CREATE INDEX IF NOT EXISTS {index_name} ON {table} ({cols})"
            ))

    print(f"✅ intelligence columns migration applied ({added} touched).")


if __name__ == "__main__":
    asyncio.run(run())
