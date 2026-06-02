"""Event tracking service tests.

Phase 1 contracts:
  - Master flag OFF -> no row ever inserted
  - Duplicate event_id -> idempotent drop (not error)
  - Unknown category / oversized metadata -> EventValidationError
  - Anonymous event recorded when events.anonymous_allowed=True
  - consent.required_for_analytics gates authenticated users
  - delete_user_events wipes only that user's rows
  - record_batch processes each event independently
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

from app.models.tax_config import TaxConfig
from app.models.user import User, UserRole
from app.models.user_consent_preferences import UserConsentPreferences
from app.models.user_event import UserEvent
from app.services import event_tracking_service
from app.services.event_tracking_service import (
    EventInput,
    EventValidationError,
)


async def _set(db, key, value):
    row = (await db.execute(
        select(TaxConfig).where(TaxConfig.key == key)
    )).scalar_one_or_none()
    if row is None:
        db.add(TaxConfig(key=key, value=json.dumps(value)))
    else:
        row.value = json.dumps(value)
    await db.commit()


async def _make_user(db, *, uid: str = "u-evt", consent: bool = False) -> User:
    u = User(id=uid, email=f"{uid}@x.com", hashed_password="x",
             name="U", role=UserRole.STUDENT)
    db.add(u)
    await db.flush()
    if consent:
        db.add(UserConsentPreferences(
            user_id=uid, allow_analytics_tracking=True,
        ))
    await db.commit()
    return u


# ---------- master flag ---------------------------------------------------

@pytest.mark.asyncio
async def test_master_flag_off_drops_event(seeded_db):
    await _set(seeded_db, "events.enabled", False)
    user = await _make_user(seeded_db)

    row = await event_tracking_service.record_event(
        seeded_db,
        event=EventInput(
            event_id="evt-1", event_name="search.location",
            event_category="SEARCH", user_id=user.id,
        ),
    )
    await seeded_db.commit()
    assert row is None
    # No rows persisted
    rows = (await seeded_db.execute(select(UserEvent))).scalars().all()
    assert rows == []


@pytest.mark.asyncio
async def test_master_flag_on_records_event(seeded_db):
    await _set(seeded_db, "events.enabled", True)
    user = await _make_user(seeded_db)

    row = await event_tracking_service.record_event(
        seeded_db,
        event=EventInput(
            event_id="evt-on", event_name="search.location",
            event_category="SEARCH", user_id=user.id,
            metadata={"q": "Kochi"},
        ),
    )
    await seeded_db.commit()
    assert row is not None
    assert row.event_id == "evt-on"
    persisted = (await seeded_db.execute(select(UserEvent))).scalars().all()
    assert len(persisted) == 1


# ---------- idempotency ---------------------------------------------------

@pytest.mark.asyncio
async def test_duplicate_event_id_is_idempotent_drop(seeded_db):
    await _set(seeded_db, "events.enabled", True)
    user = await _make_user(seeded_db)

    payload = EventInput(
        event_id="evt-dup", event_name="search.location",
        event_category="SEARCH", user_id=user.id,
    )
    r1 = await event_tracking_service.record_event(seeded_db, event=payload)
    await seeded_db.commit()
    r2 = await event_tracking_service.record_event(seeded_db, event=payload)
    await seeded_db.commit()

    assert r1 is not None
    assert r2 is None        # second call dropped, did not raise

    rows = (await seeded_db.execute(select(UserEvent))).scalars().all()
    assert len(rows) == 1


# ---------- validation ----------------------------------------------------

@pytest.mark.asyncio
async def test_unknown_category_rejected(seeded_db):
    await _set(seeded_db, "events.enabled", True)
    user = await _make_user(seeded_db)
    with pytest.raises(EventValidationError):
        await event_tracking_service.record_event(
            seeded_db,
            event=EventInput(
                event_id="evt-bad-cat", event_name="x",
                event_category="NONSENSE", user_id=user.id,
            ),
        )


@pytest.mark.asyncio
async def test_unknown_entity_type_rejected(seeded_db):
    await _set(seeded_db, "events.enabled", True)
    user = await _make_user(seeded_db)
    with pytest.raises(EventValidationError):
        await event_tracking_service.record_event(
            seeded_db,
            event=EventInput(
                event_id="evt-bad-ent", event_name="view",
                event_category="VIEW", entity_type="rocketship",
                user_id=user.id,
            ),
        )


@pytest.mark.asyncio
async def test_missing_identity_rejected_for_non_system(seeded_db):
    """No user_id AND no anonymous_session_id -> bounce (unless SYSTEM)."""
    await _set(seeded_db, "events.enabled", True)
    with pytest.raises(EventValidationError):
        await event_tracking_service.record_event(
            seeded_db,
            event=EventInput(
                event_id="evt-no-id", event_name="view",
                event_category="VIEW",
            ),
        )


@pytest.mark.asyncio
async def test_system_event_allowed_without_identity(seeded_db):
    await _set(seeded_db, "events.enabled", True)
    row = await event_tracking_service.record_event(
        seeded_db,
        event=EventInput(
            event_id="evt-sys", event_name="cron.tick",
            event_category="SYSTEM",
        ),
    )
    await seeded_db.commit()
    assert row is not None


@pytest.mark.asyncio
async def test_oversized_metadata_rejected(seeded_db):
    await _set(seeded_db, "events.enabled", True)
    user = await _make_user(seeded_db)
    big = {"k": "x" * 5000}
    with pytest.raises(EventValidationError):
        await event_tracking_service.record_event(
            seeded_db,
            event=EventInput(
                event_id="evt-big", event_name="view",
                event_category="VIEW", user_id=user.id, metadata=big,
            ),
        )


# ---------- consent gating -----------------------------------------------

@pytest.mark.asyncio
async def test_anonymous_session_allowed_by_default(seeded_db):
    """events.anonymous_allowed defaults True; anon session passes the gate."""
    await _set(seeded_db, "events.enabled", True)
    await _set(seeded_db, "events.anonymous_allowed", True)

    row = await event_tracking_service.record_event(
        seeded_db,
        event=EventInput(
            event_id="evt-anon", event_name="search.location",
            event_category="SEARCH", anonymous_session_id="sess-1",
        ),
    )
    await seeded_db.commit()
    assert row is not None
    assert row.user_id is None
    assert row.anonymous_session_id == "sess-1"


@pytest.mark.asyncio
async def test_anonymous_session_blocked_when_flag_off(seeded_db):
    await _set(seeded_db, "events.enabled", True)
    await _set(seeded_db, "events.anonymous_allowed", False)

    row = await event_tracking_service.record_event(
        seeded_db,
        event=EventInput(
            event_id="evt-anon2", event_name="search.location",
            event_category="SEARCH", anonymous_session_id="sess-2",
        ),
    )
    await seeded_db.commit()
    assert row is None


@pytest.mark.asyncio
async def test_consent_required_gates_authenticated_user(seeded_db):
    """When consent.required_for_analytics=True, only users with the
    allow_analytics_tracking row flag can record events."""
    await _set(seeded_db, "events.enabled", True)
    await _set(seeded_db, "consent.required_for_analytics", True)

    no_consent = await _make_user(seeded_db, uid="u-noc", consent=False)
    with_consent = await _make_user(seeded_db, uid="u-wc", consent=True)

    r1 = await event_tracking_service.record_event(
        seeded_db,
        event=EventInput(
            event_id="evt-noc", event_name="view",
            event_category="VIEW", user_id=no_consent.id,
        ),
    )
    r2 = await event_tracking_service.record_event(
        seeded_db,
        event=EventInput(
            event_id="evt-wc", event_name="view",
            event_category="VIEW", user_id=with_consent.id,
        ),
    )
    await seeded_db.commit()
    assert r1 is None
    assert r2 is not None


# ---------- batch ---------------------------------------------------------

@pytest.mark.asyncio
async def test_batch_processes_independently(seeded_db):
    """One bad event in a batch doesn't drop the rest."""
    await _set(seeded_db, "events.enabled", True)
    user = await _make_user(seeded_db)
    events = [
        EventInput(event_id="b1", event_name="search", event_category="SEARCH",
                   user_id=user.id),
        EventInput(event_id="b2", event_name="bad", event_category="WRONG",
                   user_id=user.id),  # invalid category
        EventInput(event_id="b1", event_name="search", event_category="SEARCH",
                   user_id=user.id),  # duplicate
        EventInput(event_id="b3", event_name="view", event_category="VIEW",
                   user_id=user.id),
    ]
    result = await event_tracking_service.record_batch(seeded_db, events=events)
    await seeded_db.commit()
    assert result.accepted == 2          # b1, b3
    assert result.duplicates == 1        # second b1
    assert result.rejected_validation == 1  # b2


@pytest.mark.asyncio
async def test_batch_size_limit_enforced(seeded_db):
    await _set(seeded_db, "events.enabled", True)
    await _set(seeded_db, "events.batch_size_limit", 2)
    user = await _make_user(seeded_db)

    too_big = [
        EventInput(event_id=f"b{i}", event_name="search",
                   event_category="SEARCH", user_id=user.id)
        for i in range(5)
    ]
    with pytest.raises(EventValidationError):
        await event_tracking_service.record_batch(seeded_db, events=too_big)


# ---------- right to erasure ---------------------------------------------

@pytest.mark.asyncio
async def test_delete_user_events_wipes_only_that_user(seeded_db):
    await _set(seeded_db, "events.enabled", True)
    alice = await _make_user(seeded_db, uid="alice")
    bob = await _make_user(seeded_db, uid="bob")
    for i in range(3):
        await event_tracking_service.record_event(
            seeded_db,
            event=EventInput(
                event_id=f"alice-{i}", event_name="view",
                event_category="VIEW", user_id=alice.id,
            ),
        )
    await event_tracking_service.record_event(
        seeded_db,
        event=EventInput(
            event_id="bob-0", event_name="view",
            event_category="VIEW", user_id=bob.id,
        ),
    )
    await seeded_db.commit()

    deleted = await event_tracking_service.delete_user_events(
        seeded_db, user_id=alice.id,
    )
    await seeded_db.commit()
    assert deleted == 3

    remaining = (await seeded_db.execute(select(UserEvent))).scalars().all()
    assert len(remaining) == 1
    assert remaining[0].user_id == bob.id


# ---------- field truncation ---------------------------------------------

@pytest.mark.asyncio
async def test_oversized_text_fields_are_truncated_not_rejected(seeded_db):
    """Source page / referrer / location query > 255 chars should be
    truncated, not bounced. Important for noisy real-world clients."""
    await _set(seeded_db, "events.enabled", True)
    user = await _make_user(seeded_db)
    long_str = "x" * 1000
    row = await event_tracking_service.record_event(
        seeded_db,
        event=EventInput(
            event_id="evt-trunc", event_name="search", event_category="SEARCH",
            user_id=user.id,
            source_page=long_str, referrer=long_str,
            location_query=long_str,
        ),
    )
    await seeded_db.commit()
    assert row is not None
    assert len(row.source_page) == 255
    assert len(row.referrer) == 255
    assert len(row.location_query) == 255


# ---------- read helpers --------------------------------------------------

@pytest.mark.asyncio
async def test_list_recent_events_for_user_is_user_scoped(seeded_db):
    await _set(seeded_db, "events.enabled", True)
    alice = await _make_user(seeded_db, uid="alice2")
    bob = await _make_user(seeded_db, uid="bob2")
    for i in range(3):
        await event_tracking_service.record_event(
            seeded_db,
            event=EventInput(
                event_id=f"alice2-{i}", event_name="view",
                event_category="VIEW", user_id=alice.id,
            ),
        )
    await event_tracking_service.record_event(
        seeded_db,
        event=EventInput(
            event_id="bob2-0", event_name="view",
            event_category="VIEW", user_id=bob.id,
        ),
    )
    await seeded_db.commit()
    rows = await event_tracking_service.list_recent_events_for_user(
        seeded_db, user_id=alice.id,
    )
    assert len(rows) == 3
    assert all(r.user_id == alice.id for r in rows)
