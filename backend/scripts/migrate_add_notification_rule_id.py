"""Phase 4C migration — add notification_rule_id FK to campaign_deliveries.

Idempotent. Safe to re-run. Existing campaign-driven rows are untouched.

Works on Postgres (production) AND SQLite (local dev) via the shared
dialect-aware helper. The original PRAGMA-only version silently no-op'd
on Postgres because PRAGMA is SQLite syntax.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text
from app.database import engine
from scripts._migration_helpers import add_column_if_missing


async def run() -> None:
    async with engine.begin() as conn:
        added = await add_column_if_missing(
            conn, "campaign_deliveries", "notification_rule_id", "VARCHAR",
        )
        await conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_camp_deliv_rule "
            "ON campaign_deliveries (notification_rule_id)"
        ))
        if added:
            print("✅ Added notification_rule_id column + index.")
        else:
            print("ℹ️  notification_rule_id already present — index ensured.")


if __name__ == "__main__":
    asyncio.run(run())
