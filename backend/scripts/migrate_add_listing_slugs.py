"""Add `slug` column to reading_rooms + accommodations and backfill.

Idempotent. Re-runnable.

Slug shape: `{listing-name}-{locality}-{city}`, truncated to 120 chars.
Collisions get `-2`, `-3`, … appended deterministically by `id` order.

Works on Postgres (production) AND SQLite (local dev) via the shared
dialect-aware helper. The original version used PRAGMA table_info (SQLite-
only — silently no-op'd on Postgres) and `ORDER BY ROWID` (SQLite-only;
on Postgres the ROWID column doesn't exist and the query throws). Using
`ORDER BY id` works on both since `id` is the primary key on both tables.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import AsyncSessionLocal, engine
from app.utils.slug import collision_suffix, listing_slug
from scripts._migration_helpers import add_column_if_missing


COLUMNS = [
    ("reading_rooms", "slug", "VARCHAR(120)"),
    ("accommodations", "slug", "VARCHAR(120)"),
]


async def _add_columns() -> None:
    """ALTER TABLE … ADD COLUMN slug — only if missing. Idempotent on both
    Postgres (ADD COLUMN IF NOT EXISTS) and SQLite (existence check first)."""
    async with engine.begin() as conn:
        for table, col, decl in COLUMNS:
            added = await add_column_if_missing(conn, table, col, decl)
            # The unique partial index is idempotent on its own — re-create it
            # every run so an interrupted prior run that added the column but
            # not the index still ends up with the index after this run.
            await conn.execute(text(
                f"CREATE UNIQUE INDEX IF NOT EXISTS ix_{table}_slug "
                f"ON {table} ({col}) WHERE {col} IS NOT NULL"
            ))
            if added:
                print(f"  + {table}.{col}")


async def _backfill_table(db: AsyncSession, table: str) -> int:
    """Walk every row with NULL slug, compute its slug, and resolve any
    collisions deterministically. Returns the count of rows updated."""
    # ORDER BY id is portable (id is the PK on both tables) and gives a
    # deterministic backfill order. The original used ROWID which is SQLite-
    # only — Postgres has no such column and the query would throw.
    rows = (await db.execute(text(
        f"SELECT id, name, locality, city FROM {table} "
        f"WHERE slug IS NULL ORDER BY id ASC"
    ))).all()
    used: set[str] = {
        r[0] for r in (await db.execute(text(
            f"SELECT slug FROM {table} WHERE slug IS NOT NULL"
        ))).all()
    }

    updated = 0
    for row_id, name, locality, city in rows:
        base = listing_slug(name or "listing", locality=locality, city=city)
        if not base:
            base = f"listing-{row_id[:8]}"
        # Probe -2, -3, … until we find a free slot.
        n = 1
        candidate = collision_suffix(base, n)
        while candidate in used:
            n += 1
            candidate = collision_suffix(base, n)
        used.add(candidate)
        await db.execute(text(
            f"UPDATE {table} SET slug = :slug WHERE id = :id"
        ), {"slug": candidate, "id": row_id})
        updated += 1

    return updated


async def run() -> None:
    await _add_columns()

    async with AsyncSessionLocal() as db:
        rr_count = await _backfill_table(db, "reading_rooms")
        acc_count = await _backfill_table(db, "accommodations")
        await db.commit()
        print(
            f"✅ slug backfill complete: "
            f"{rr_count} reading_rooms, {acc_count} accommodations."
        )


if __name__ == "__main__":
    asyncio.run(run())
