"""Tag pre-accounting invoice rows as LEGACY so new docs don't collide.

Idempotent — only touches rows where doc_type is NULL.
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
        # Cross-DB compatible UPDATE — doc_type column exists post-migration.
        result = await db.execute(
            text(
                "UPDATE invoices SET doc_type = 'LEGACY' "
                "WHERE doc_type IS NULL OR doc_type = ''"
            )
        )
        await db.commit()
        # rowcount may be -1 on some drivers; guard accordingly.
        affected = getattr(result, "rowcount", 0) or 0
        print(f"✅ Backfilled {affected} legacy invoice rows.")


if __name__ == "__main__":
    asyncio.run(run())
