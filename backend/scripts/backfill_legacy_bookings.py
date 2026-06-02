"""Tag pre-accounting booking rows with gst_treatment=LEGACY.

This means the accounting shadow will NOT retroactively compute or post ledger
entries for these — they are treated as pre-rollout data.
"""
from __future__ import annotations
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text
from app.database import AsyncSessionLocal


async def run() -> None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            text(
                "UPDATE bookings SET gst_treatment = 'LEGACY' "
                "WHERE gst_treatment IS NULL"
            )
        )
        await db.commit()
        affected = getattr(result, "rowcount", 0) or 0
        print(f"✅ Backfilled {affected} legacy booking rows.")


if __name__ == "__main__":
    asyncio.run(run())
