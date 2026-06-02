"""Migration — add dispatch_attempts to campaign_deliveries.

Backs the bounded retry/backoff in notification_dispatcher_service: transient
delivery failures stay QUEUED and are retried up to MAX_DISPATCH_ATTEMPTS,
tracked by this counter.

Idempotent. Safe to re-run. Works on Postgres (production) AND SQLite (local
dev) via the shared dialect-aware helper. Existing rows default to 0.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import engine
from scripts._migration_helpers import add_column_if_missing


async def run() -> None:
    async with engine.begin() as conn:
        added = await add_column_if_missing(
            conn, "campaign_deliveries", "dispatch_attempts",
            "INTEGER NOT NULL DEFAULT 0",
        )
        if added:
            print("✅ Added dispatch_attempts column (default 0).")
        else:
            print("ℹ️  dispatch_attempts already present — nothing to do.")


if __name__ == "__main__":
    asyncio.run(run())
