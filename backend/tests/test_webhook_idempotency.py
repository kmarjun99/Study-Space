"""Webhook intake idempotency.

Critical claim (acceptance criterion #18): a duplicate webhook POST does NOT
produce a duplicate side effect. The intake row is unique on (gateway, event_id).
"""
from __future__ import annotations

import pytest

from app.services.webhook_service import DuplicateWebhook, WebhookService


@pytest.mark.asyncio
async def test_record_event_persists(db):
    row = await WebhookService.record_event(
        db,
        gateway="razorpay",
        event_id="evt_abc",
        event_type="payment.captured",
        payload={"hello": "world"},
        signature="sig",
    )
    await db.commit()
    assert row.id
    assert row.status == "PENDING"


@pytest.mark.asyncio
async def test_duplicate_event_raises(db):
    await WebhookService.record_event(
        db, gateway="razorpay", event_id="evt_dup",
        event_type="payment.captured", payload={"x": 1},
    )
    await db.commit()
    with pytest.raises(DuplicateWebhook):
        await WebhookService.record_event(
            db, gateway="razorpay", event_id="evt_dup",
            event_type="payment.captured", payload={"x": 1},
        )


@pytest.mark.asyncio
async def test_mark_processed_and_failed(db):
    row = await WebhookService.record_event(
        db, gateway="razorpay", event_id="evt_state",
        event_type="payment.captured", payload={},
    )
    await db.commit()
    await WebhookService.mark_processed(db, row.id)
    await db.commit()
    await db.refresh(row)
    assert row.status == "PROCESSED"
    assert row.processed_at is not None

    # mark_failed bumps attempts and writes error text
    await WebhookService.mark_failed(db, row.id, "explosion")
    await db.commit()
    await db.refresh(row)
    assert row.status == "FAILED"
    assert "explosion" in (row.error or "")
    assert row.attempts == "1"
