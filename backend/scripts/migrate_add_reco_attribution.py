"""Phase 4D migration — add attribution columns to recommendation_logs.

Idempotent. Safe to re-run.

Works on Postgres (production) AND SQLite (local dev) via the shared
dialect-aware helper. The original PRAGMA-only version silently no-op'd
on Postgres because PRAGMA is SQLite syntax. `BOOLEAN DEFAULT 0` is also
SQLite-only — Postgres needs `DEFAULT FALSE`.
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
COLUMNS = [
    ("clicked_at", "TIMESTAMP"),
    ("converted_at", "TIMESTAMP"),
    ("converted_booking_id", "VARCHAR"),
    ("is_click_attributed", "BOOLEAN DEFAULT FALSE NOT NULL"),
]


async def run() -> None:
    async with engine.begin() as conn:
        added = 0
        for col, decl in COLUMNS:
            if await add_column_if_missing(conn, "recommendation_logs", col, decl):
                added += 1
        await conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_reco_log_user_listing "
            "ON recommendation_logs (user_id, listing_id, created_at)"
        ))
        print(f"✅ recommendation_logs attribution migration applied ({added} added or already-present).")


if __name__ == "__main__":
    asyncio.run(run())
