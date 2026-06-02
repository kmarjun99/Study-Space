"""Behavioral event firehose — single writer.

Routers/callers MUST go through this service to record events. The service:
  - Validates the schema (known event_name + category combinations)
  - Enforces idempotency on `event_id`
  - Checks consent before recording (calls privacy_consent_service)
  - Caps metadata size (4KB)
  - Truncates oversized free-text fields rather than dropping the row

Append-only contract: there is no `update_event` or `delete_event` here.
The only deletion path is `delete_user_events` for DPDP right-to-erasure.

Downstream services (profile aggregation, intent scoring, segmentation)
read from `user_events` but never call into this module — keeps the
write-side dependency-free.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user_event import EventCategory, EventEntityType, UserEvent
from app.services import privacy_consent_service
from app.services.tax_engine import cfg_get, load_active_config


METADATA_MAX_BYTES = 4096
TEXT_FIELD_MAX = 255
DEFAULT_BATCH_LIMIT = 100


class EventValidationError(ValueError):
    """Raised when an inbound event fails validation."""


@dataclass
class EventInput:
    """Caller-supplied event payload. Pydantic schemas wrap this."""
    event_id: str
    event_name: str
    event_category: str
    user_id: Optional[str] = None
    anonymous_session_id: Optional[str] = None
    entity_type: Optional[str] = None
    entity_id: Optional[str] = None
    metadata: Optional[dict[str, Any]] = field(default=None)
    device_type: Optional[str] = None
    platform: Optional[str] = None
    source_page: Optional[str] = None
    referrer: Optional[str] = None
    city: Optional[str] = None
    location_query: Optional[str] = None


@dataclass
class IngestResult:
    accepted: int = 0
    duplicates: int = 0
    rejected_no_consent: int = 0
    rejected_validation: int = 0
    errors: list[str] = field(default_factory=list)


def _truncate(s: Optional[str]) -> Optional[str]:
    if s is None:
        return None
    return s[:TEXT_FIELD_MAX]


def _validate(event: EventInput) -> None:
    if not event.event_id or len(event.event_id) > 80:
        raise EventValidationError("event_id is required (max 80 chars)")
    if not event.event_name or len(event.event_name) > 80:
        raise EventValidationError("event_name is required (max 80 chars)")
    try:
        EventCategory(event.event_category)
    except ValueError as exc:
        raise EventValidationError(
            f"event_category must be one of {[c.value for c in EventCategory]}"
        ) from exc
    if event.entity_type is not None:
        try:
            EventEntityType(event.entity_type)
        except ValueError as exc:
            raise EventValidationError(
                f"entity_type must be one of {[e.value for e in EventEntityType]}"
            ) from exc
    if event.user_id is None and event.anonymous_session_id is None:
        # Allow SYSTEM events without an identity, but reject all other categories.
        if event.event_category != EventCategory.SYSTEM.value:
            raise EventValidationError(
                "either user_id or anonymous_session_id is required for non-SYSTEM events"
            )
    if event.metadata is not None:
        encoded = json.dumps(event.metadata, default=str)
        if len(encoded.encode("utf-8")) > METADATA_MAX_BYTES:
            raise EventValidationError(
                f"metadata exceeds {METADATA_MAX_BYTES} bytes after JSON encoding"
            )


async def _check_consent(
    db: AsyncSession, *, event: EventInput,
) -> bool:
    """Layered gate. Returns True if this event may be recorded."""
    # System events always pass — they are platform-internal (e.g., cron
    # invocations) and don't represent user behavior.
    if event.event_category == EventCategory.SYSTEM.value:
        return True
    return await privacy_consent_service.is_analytics_allowed(
        db, user_id=event.user_id,
    )


# ---------- public API ----------------------------------------------------

async def record_event(
    db: AsyncSession, *, event: EventInput,
) -> Optional[UserEvent]:
    """Record a single event. Returns the row on success, None if the
    event was dropped (duplicate, consent, or master flag off).

    Raises `EventValidationError` for schema problems — caller should
    surface as HTTP 400.

    Caller commits.
    """
    _validate(event)

    if not await _check_consent(db, event=event):
        return None

    row = UserEvent(
        event_id=event.event_id,
        user_id=event.user_id,
        anonymous_session_id=event.anonymous_session_id,
        event_name=event.event_name,
        event_category=EventCategory(event.event_category),
        entity_type=EventEntityType(event.entity_type) if event.entity_type else None,
        entity_id=event.entity_id,
        metadata_json=(
            json.dumps(event.metadata, default=str) if event.metadata else None
        ),
        device_type=_truncate(event.device_type),
        platform=_truncate(event.platform),
        source_page=_truncate(event.source_page),
        referrer=_truncate(event.referrer),
        city=_truncate(event.city),
        location_query=_truncate(event.location_query),
    )
    db.add(row)
    try:
        await db.flush()
    except IntegrityError:
        # Duplicate event_id — idempotent drop.
        await db.rollback()
        return None
    return row


async def record_batch(
    db: AsyncSession, *, events: list[EventInput],
) -> IngestResult:
    """Insert up to `events.batch_size_limit` events. Each event is processed
    independently — one invalid event doesn't drop the whole batch.

    Caller commits.
    """
    config = await load_active_config(db)
    limit = int(cfg_get(config, "events.batch_size_limit", DEFAULT_BATCH_LIMIT))
    if len(events) > limit:
        raise EventValidationError(f"batch exceeds limit of {limit}")

    result = IngestResult()
    for event in events:
        try:
            _validate(event)
        except EventValidationError as exc:
            result.rejected_validation += 1
            result.errors.append(f"{event.event_id}: {exc}")
            continue

        if not await _check_consent(db, event=event):
            result.rejected_no_consent += 1
            continue

        row = UserEvent(
            event_id=event.event_id,
            user_id=event.user_id,
            anonymous_session_id=event.anonymous_session_id,
            event_name=event.event_name,
            event_category=EventCategory(event.event_category),
            entity_type=(
                EventEntityType(event.entity_type) if event.entity_type else None
            ),
            entity_id=event.entity_id,
            metadata_json=(
                json.dumps(event.metadata, default=str) if event.metadata else None
            ),
            device_type=_truncate(event.device_type),
            platform=_truncate(event.platform),
            source_page=_truncate(event.source_page),
            referrer=_truncate(event.referrer),
            city=_truncate(event.city),
            location_query=_truncate(event.location_query),
        )
        db.add(row)
        try:
            await db.flush()
            result.accepted += 1
        except IntegrityError:
            await db.rollback()
            result.duplicates += 1
    return result


async def delete_user_events(
    db: AsyncSession, *, user_id: str,
) -> int:
    """DPDP / GDPR right-to-erasure. Hard-deletes every event row for the
    user. Returns the row count deleted. Caller commits.

    Anonymous-session events linked to this user cannot be cleared this way
    because there's no user_id link — that's the trade-off of anonymous
    tracking. If the client supplied anonymous_session_id BEFORE the user
    identified, those rows remain (but are unlinked from any user identity).
    """
    result = await db.execute(
        delete(UserEvent).where(UserEvent.user_id == user_id)
    )
    return getattr(result, "rowcount", 0) or 0


# ---------- read helpers (Phase 2 will move these to a query service) -----

async def list_recent_events_for_user(
    db: AsyncSession, *, user_id: str, limit: int = 100,
) -> list[UserEvent]:
    """Used by /users/me/events for "what data does StudySpace have on me?"."""
    rows = (await db.execute(
        select(UserEvent)
        .where(UserEvent.user_id == user_id)
        .order_by(UserEvent.created_at.desc())
        .limit(limit)
    )).scalars().all()
    return list(rows)
