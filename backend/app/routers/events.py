"""Public event-ingestion API.

Single + batch ingest with `event_id` idempotency. Anonymous events (no JWT)
are allowed by default — gated by `events.anonymous_allowed` config flag.

Right-to-erasure endpoint deletes every event row belonging to the caller.
Consent gating happens inside `event_tracking_service`, not here.
"""
from __future__ import annotations

import json
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user, get_current_user_optional
from app.models.user import User
from app.services import event_tracking_service
from app.services.event_tracking_service import (
    EventInput,
    EventValidationError,
    IngestResult,
)


router = APIRouter(prefix="/events", tags=["Intelligence: Events"])


class EventIn(BaseModel):
    event_id: str
    event_name: str
    event_category: str
    user_id: Optional[str] = None
    anonymous_session_id: Optional[str] = None
    entity_type: Optional[str] = None
    entity_id: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None
    device_type: Optional[str] = None
    platform: Optional[str] = None
    source_page: Optional[str] = None
    referrer: Optional[str] = None
    city: Optional[str] = None
    location_query: Optional[str] = None

    def to_input(self, *, fallback_user_id: Optional[str]) -> EventInput:
        # If the caller is authenticated, override any client-supplied user_id
        # with the JWT identity (prevents impersonation).
        uid = fallback_user_id or self.user_id
        return EventInput(
            event_id=self.event_id,
            event_name=self.event_name,
            event_category=self.event_category,
            user_id=uid,
            anonymous_session_id=self.anonymous_session_id,
            entity_type=self.entity_type,
            entity_id=self.entity_id,
            metadata=self.metadata,
            device_type=self.device_type,
            platform=self.platform,
            source_page=self.source_page,
            referrer=self.referrer,
            city=self.city,
            location_query=self.location_query,
        )


class IngestResultOut(BaseModel):
    accepted: int
    duplicates: int
    rejected_no_consent: int
    rejected_validation: int
    errors: list[str]


def _to_result_out(r: IngestResult) -> IngestResultOut:
    return IngestResultOut(
        accepted=r.accepted,
        duplicates=r.duplicates,
        rejected_no_consent=r.rejected_no_consent,
        rejected_validation=r.rejected_validation,
        errors=r.errors,
    )


# ---------- single event --------------------------------------------------

@router.post("")
async def post_event(
    body: EventIn,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    """Ingest one event. Returns 202 if accepted, 200 with status=duplicate
    if dropped as a duplicate, 200 with status=no_consent if consent gated."""
    fallback = current_user.id if current_user is not None else None
    try:
        event = body.to_input(fallback_user_id=fallback)
        row = await event_tracking_service.record_event(db, event=event)
    except EventValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    await db.commit()

    if row is None:
        return {"status": "dropped"}
    return {"status": "accepted", "event_id": row.event_id}


class BatchIn(BaseModel):
    events: list[EventIn]


@router.post("/batch", response_model=IngestResultOut)
async def post_event_batch(
    body: BatchIn,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    """Ingest multiple events. Each event is processed independently;
    one invalid event doesn't fail the rest of the batch."""
    fallback = current_user.id if current_user is not None else None
    try:
        result = await event_tracking_service.record_batch(
            db, events=[e.to_input(fallback_user_id=fallback) for e in body.events],
        )
    except EventValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    await db.commit()
    return _to_result_out(result)


# ---------- right to erasure ----------------------------------------------

@router.delete("/me")
async def delete_my_events(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Hard-delete every event row belonging to the caller.

    Anonymous-session events recorded BEFORE the user logged in cannot be
    reached this way (no user_id link). Callers who want a full sweep
    should also wipe their localStorage anonymous_session_id and re-issue.
    """
    deleted = await event_tracking_service.delete_user_events(
        db, user_id=current_user.id,
    )
    await db.commit()
    return {"deleted": deleted}


# ---------- transparency: "what do you know about me?" --------------------

class UserEventOut(BaseModel):
    id: str
    event_id: str
    event_name: str
    event_category: str
    entity_type: Optional[str]
    entity_id: Optional[str]
    metadata: Optional[dict[str, Any]]
    source_page: Optional[str]
    city: Optional[str]
    created_at: str


@router.get("/me", response_model=list[UserEventOut])
async def list_my_recent_events(
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return the most recent events recorded against this user — the
    transparency surface so users can audit what's being tracked."""
    if limit < 1 or limit > 500:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 500")
    rows = await event_tracking_service.list_recent_events_for_user(
        db, user_id=current_user.id, limit=limit,
    )
    return [
        UserEventOut(
            id=r.id,
            event_id=r.event_id,
            event_name=r.event_name,
            event_category=r.event_category.value,
            entity_type=r.entity_type.value if r.entity_type else None,
            entity_id=r.entity_id,
            metadata=json.loads(r.metadata_json) if r.metadata_json else None,
            source_page=r.source_page,
            city=r.city,
            created_at=r.created_at.isoformat(),
        )
        for r in rows
    ]
