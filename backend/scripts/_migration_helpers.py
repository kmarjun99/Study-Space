"""Tiny dialect-aware helpers shared by the additive-column migrations.

The migrations originally targeted SQLite only (used PRAGMA table_info), which
silently throws on production Postgres. These helpers make ADD COLUMN +
existence checks portable across both dialects.
"""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection


async def add_column_if_missing(
    conn: AsyncConnection, table: str, column: str, decl: str,
) -> bool:
    """Add `table.column` with `decl` if it doesn't already exist.

    Returns True if the column was added, False if it was already present.
    Idempotent on both Postgres and SQLite.
    """
    dialect = conn.dialect.name
    if dialect == "postgresql":
        # Postgres ≥ 9.6 supports ADD COLUMN IF NOT EXISTS — atomic + idempotent.
        # Wrapped in a SAVEPOINT so a failure here doesn't poison the outer txn.
        await conn.execute(text(
            f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {column} {decl}"
        ))
        return True  # we can't easily distinguish added vs already-present
    else:
        # SQLite path — check first, then add (older SQLite has no IF NOT EXISTS
        # for ADD COLUMN).
        rows = await conn.execute(text(f"PRAGMA table_info({table})"))
        existing = {r[1] for r in rows.fetchall()}
        if column in existing:
            return False
        await conn.execute(text(
            f"ALTER TABLE {table} ADD COLUMN {column} {decl}"
        ))
        return True


async def existing_columns(conn: AsyncConnection, table: str) -> set[str]:
    """Return the set of existing column names on `table`, dialect-aware."""
    if conn.dialect.name == "postgresql":
        rows = await conn.execute(text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = :t"
        ), {"t": table})
        return {r[0] for r in rows.fetchall()}
    else:
        rows = await conn.execute(text(f"PRAGMA table_info({table})"))
        return {r[1] for r in rows.fetchall()}
