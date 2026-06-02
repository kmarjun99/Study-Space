"""Razorpay webhook receiver.

Razorpay sends event POSTs that may arrive duplicated, out of order, or while
we are still committing a previous handler. This endpoint:

  1. Verifies the X-Razorpay-Signature header against `RAZORPAY_WEBHOOK_SECRET`.
     (When the secret is not configured we accept demo mode for parity with the
     rest of the codebase.)
  2. Inserts a `webhook_events` row keyed on the gateway event_id. Duplicates
     are returned as 200 OK without side effects.
  3. Dispatches to the right handler based on the order receipt prefix:
        - `booking_*`  -> shadow-post booking ledger
        - `charge_*`   -> mark owner charge paid + issue invoice + post ledger
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.booking import Booking
from app.models.owner_charge import OwnerCharge
from app.services.accounting_shadow import AccountingShadow
from app.services.owner_billing_service import mark_charge_paid
from app.services.webhook_service import DuplicateWebhook, WebhookService


router = APIRouter(prefix="/webhooks", tags=["Webhooks"])
_log = logging.getLogger("studyspace.webhooks")


def _verify_signature(body: bytes, signature: str | None) -> bool:
    """Verify Razorpay webhook signature.

    Returns True in demo mode (no secret configured) — mirrors the existing
    razorpay router's behavior so the dev experience is consistent.
    """
    secret = os.getenv("RAZORPAY_WEBHOOK_SECRET", "")
    if not secret:
        return True  # demo / dev
    if not signature:
        return False
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


@router.post("/razorpay")
async def razorpay_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    raw = await request.body()
    signature = request.headers.get("X-Razorpay-Signature")

    if not _verify_signature(raw, signature):
        raise HTTPException(status_code=400, detail="Invalid signature")

    try:
        payload: dict[str, Any] = json.loads(raw or b"{}")
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Invalid JSON") from exc

    event_id = (
        payload.get("id")
        or (payload.get("payload", {}).get("payment", {}).get("entity", {}) or {}).get("id")
        or ""
    )
    event_type = payload.get("event")
    if not event_id:
        raise HTTPException(status_code=400, detail="Missing event id")

    # Idempotent insert — committed in its own transaction so the row
    # SURVIVES a later rollback during dispatch. Without this commit, a
    # dispatch failure rolls back the webhook_events row too, leaving no
    # failure marker AND removing the UNIQUE(gateway, event_id) row that
    # blocks Razorpay retries from being processed twice.
    try:
        ev = await WebhookService.record_event(
            db,
            gateway="razorpay",
            event_id=event_id,
            event_type=event_type,
            payload=payload,
            signature=signature,
        )
        await db.commit()
    except DuplicateWebhook:
        return {"status": "duplicate", "event_id": event_id}

    # Dispatch in its own transaction. Failures roll back ONLY the dispatch
    # writes — the webhook_events row from above is already committed.
    try:
        await _dispatch(db, payload, event_type)
        await WebhookService.mark_processed(db, ev.id)
        await db.commit()
        return {"status": "ok", "event_id": event_id}
    except Exception as exc:
        await db.rollback()
        _log.exception("Webhook dispatch failed for %s: %s", event_id, exc)
        # Failure tag: webhook_events row is intact thanks to the commit
        # above, so the get-by-id inside mark_failed finds it.
        try:
            await WebhookService.mark_failed(db, ev.id, str(exc))
            await db.commit()
        except Exception:  # pragma: no cover -- last-resort safety net
            _log.exception("Could not record webhook failure marker")
        # Return 500 so Razorpay retries — and the UNIQUE row above ensures
        # the retry's record_event() raises DuplicateWebhook (handled above)
        # so the failed handler doesn't re-run blindly.
        raise HTTPException(status_code=500, detail="Dispatch failed") from exc


async def _dispatch(db: AsyncSession, payload: dict, event_type: str | None) -> None:
    """Branch on the event + receipt prefix to decide what to do."""
    if not event_type:
        return
    # Only act on capture/authorized events
    if event_type not in {"payment.captured", "payment.authorized", "order.paid"}:
        return

    entity = (payload.get("payload", {})
              .get("payment", {})
              .get("entity")) or {}
    payment_id = entity.get("id")
    order_id = entity.get("order_id")
    receipt = (entity.get("notes") or {}).get("receipt") or ""

    # Receipt format set by our code (`booking_<uuid>` / `charge_<uuid>`)
    # We can also look up the order_id against our local rows.
    if receipt.startswith("booking_") or await _is_booking_order(db, order_id):
        booking_id = receipt[len("booking_"):] if receipt.startswith("booking_") \
            else await _booking_id_from_order(db, order_id)
        if booking_id:
            await AccountingShadow.shadow_post_booking_paid(db, booking_id=booking_id)
        return

    if receipt.startswith("charge_") or await _is_charge_order(db, order_id):
        charge_id = receipt[len("charge_"):] if receipt.startswith("charge_") \
            else await _charge_id_from_order(db, order_id)
        if charge_id:
            await mark_charge_paid(
                db, charge_id=charge_id, payment_ref=payment_id or order_id or "",
            )


async def _is_booking_order(db: AsyncSession, order_id: str | None) -> bool:
    if not order_id:
        return False
    row = (await db.execute(
        select(Booking.id).where(Booking.transaction_id == order_id).limit(1)
    )).first()
    return row is not None


async def _booking_id_from_order(db: AsyncSession, order_id: str | None) -> str | None:
    if not order_id:
        return None
    row = (await db.execute(
        select(Booking.id).where(Booking.transaction_id == order_id).limit(1)
    )).first()
    return row[0] if row else None


async def _is_charge_order(db: AsyncSession, order_id: str | None) -> bool:
    if not order_id:
        return False
    row = (await db.execute(
        select(OwnerCharge.id).where(OwnerCharge.razorpay_order_id == order_id).limit(1)
    )).first()
    return row is not None


async def _charge_id_from_order(db: AsyncSession, order_id: str | None) -> str | None:
    if not order_id:
        return None
    row = (await db.execute(
        select(OwnerCharge.id).where(OwnerCharge.razorpay_order_id == order_id).limit(1)
    )).first()
    return row[0] if row else None
