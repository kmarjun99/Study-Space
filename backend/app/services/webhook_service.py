"""Idempotent webhook intake + retry helpers.

Razorpay (and any future gateway) POSTs may arrive duplicated, out of order,
or while we're still committing a previous handler. The contract:

  1. Compute `event_id` from the payload (Razorpay sends one).
  2. INSERT a `webhook_events` row with UNIQUE (gateway, event_id).
  3. If INSERT failed -> already handled; reply 200 OK without side effects.
  4. Else mark PROCESSED on success, FAILED on exception (caller can retry).
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.webhook_event import WebhookEvent


class DuplicateWebhook(Exception):
    """Raised when the same gateway+event_id has already been recorded."""


class WebhookService:
    @staticmethod
    async def record_event(
        db: AsyncSession,
        *,
        gateway: str,
        event_id: str,
        event_type: Optional[str],
        payload: dict[str, Any] | str,
        signature: Optional[str] = None,
    ) -> WebhookEvent:
        """Insert the event row. Raises DuplicateWebhook on collision."""
        payload_str = payload if isinstance(payload, str) else json.dumps(payload, default=str)
        row = WebhookEvent(
            gateway=gateway,
            event_id=event_id,
            event_type=event_type,
            payload=payload_str,
            signature=signature,
            status="PENDING",
        )
        db.add(row)
        try:
            await db.flush()
        except IntegrityError:
            await db.rollback()
            raise DuplicateWebhook(f"{gateway}/{event_id} already recorded")
        return row

    @staticmethod
    async def mark_processed(db: AsyncSession, event_row_id: str) -> None:
        ev = await db.get(WebhookEvent, event_row_id)
        if ev is None:
            return
        ev.status = "PROCESSED"
        ev.processed_at = datetime.utcnow()
        await db.flush()

    @staticmethod
    async def mark_failed(db: AsyncSession, event_row_id: str, error: str) -> None:
        ev = await db.get(WebhookEvent, event_row_id)
        if ev is None:
            return
        ev.status = "FAILED"
        ev.error = error[:2000]
        try:
            ev.attempts = str(int(ev.attempts or "0") + 1)
        except ValueError:
            ev.attempts = "1"
        await db.flush()

    @staticmethod
    async def list_pending(db: AsyncSession, limit: int = 50) -> list[WebhookEvent]:
        rows = (await db.execute(
            select(WebhookEvent)
            .where(WebhookEvent.status == "PENDING")
            .order_by(WebhookEvent.received_at)
            .limit(limit)
        )).scalars().all()
        return list(rows)
