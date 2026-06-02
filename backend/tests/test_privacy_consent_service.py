"""Privacy / consent service tests.

Phase 1 contracts:
  - get_or_create returns defaults (all OFF) on first call
  - update_preferences is partial (only sent fields touch the row)
  - revoke_all turns every flag OFF, even if previously on
  - Each is_*_allowed gate respects its own flag, never another
  - Anonymous (user_id=None) is never personalized / marketed to
"""
from __future__ import annotations

import json

import pytest
from sqlalchemy import select

from app.models.tax_config import TaxConfig
from app.models.user import User, UserRole
from app.models.user_consent_preferences import UserConsentPreferences
from app.services import privacy_consent_service


async def _set(db, key, value):
    row = (await db.execute(
        select(TaxConfig).where(TaxConfig.key == key)
    )).scalar_one_or_none()
    if row is None:
        db.add(TaxConfig(key=key, value=json.dumps(value)))
    else:
        row.value = json.dumps(value)
    await db.commit()


async def _user(db, uid="u-c") -> User:
    u = User(id=uid, email=f"{uid}@x.com", hashed_password="x", name="U",
             role=UserRole.STUDENT)
    db.add(u)
    await db.commit()
    return u


# ---------- defaults -------------------------------------------------------

@pytest.mark.asyncio
async def test_get_or_create_defaults_all_off(seeded_db):
    user = await _user(seeded_db)
    row = await privacy_consent_service.get_or_create(seeded_db, user_id=user.id)
    await seeded_db.commit()
    assert row.allow_analytics_tracking is False
    assert row.allow_personalized_recommendations is False
    assert row.allow_marketing_notifications is False
    assert row.allow_whatsapp_updates is False
    assert row.allow_location_based_suggestions is False


@pytest.mark.asyncio
async def test_get_or_create_is_idempotent(seeded_db):
    user = await _user(seeded_db)
    r1 = await privacy_consent_service.get_or_create(seeded_db, user_id=user.id)
    await seeded_db.commit()
    r2 = await privacy_consent_service.get_or_create(seeded_db, user_id=user.id)
    await seeded_db.commit()
    assert r1.user_id == r2.user_id
    # No duplicate row created
    rows = (await seeded_db.execute(
        select(UserConsentPreferences).where(
            UserConsentPreferences.user_id == user.id
        )
    )).scalars().all()
    assert len(rows) == 1


# ---------- partial updates -----------------------------------------------

@pytest.mark.asyncio
async def test_update_only_touches_sent_fields(seeded_db):
    user = await _user(seeded_db)
    await privacy_consent_service.update_preferences(
        seeded_db, user_id=user.id,
        allow_analytics_tracking=True,
        allow_personalized_recommendations=True,
    )
    await seeded_db.commit()
    # Now update only marketing — others must stay True
    await privacy_consent_service.update_preferences(
        seeded_db, user_id=user.id,
        allow_marketing_notifications=True,
    )
    await seeded_db.commit()
    row = await privacy_consent_service.get_or_create(seeded_db, user_id=user.id)
    assert row.allow_analytics_tracking is True
    assert row.allow_personalized_recommendations is True
    assert row.allow_marketing_notifications is True
    # Untouched flag still off
    assert row.allow_whatsapp_updates is False


@pytest.mark.asyncio
async def test_consent_policy_version_stamped(seeded_db):
    user = await _user(seeded_db)
    await privacy_consent_service.update_preferences(
        seeded_db, user_id=user.id,
        allow_analytics_tracking=True,
        consent_policy_version="2026-05",
    )
    await seeded_db.commit()
    row = await privacy_consent_service.get_or_create(seeded_db, user_id=user.id)
    assert row.consent_policy_version == "2026-05"


# ---------- revoke_all ----------------------------------------------------

@pytest.mark.asyncio
async def test_revoke_all_zeros_every_flag(seeded_db):
    user = await _user(seeded_db)
    await privacy_consent_service.update_preferences(
        seeded_db, user_id=user.id,
        allow_analytics_tracking=True,
        allow_personalized_recommendations=True,
        allow_marketing_notifications=True,
        allow_whatsapp_updates=True,
        allow_location_based_suggestions=True,
    )
    await seeded_db.commit()
    await privacy_consent_service.revoke_all_consents(seeded_db, user_id=user.id)
    await seeded_db.commit()
    row = await privacy_consent_service.get_or_create(seeded_db, user_id=user.id)
    assert row.allow_analytics_tracking is False
    assert row.allow_personalized_recommendations is False
    assert row.allow_marketing_notifications is False
    assert row.allow_whatsapp_updates is False
    assert row.allow_location_based_suggestions is False


# ---------- gate questions ------------------------------------------------

@pytest.mark.asyncio
async def test_analytics_gate_off_when_master_flag_off(seeded_db):
    await _set(seeded_db, "events.enabled", False)
    user = await _user(seeded_db)
    await privacy_consent_service.update_preferences(
        seeded_db, user_id=user.id, allow_analytics_tracking=True,
    )
    await seeded_db.commit()
    assert await privacy_consent_service.is_analytics_allowed(
        seeded_db, user_id=user.id,
    ) is False


@pytest.mark.asyncio
async def test_analytics_gate_passes_anonymous_when_flag_on(seeded_db):
    await _set(seeded_db, "events.enabled", True)
    await _set(seeded_db, "events.anonymous_allowed", True)
    assert await privacy_consent_service.is_analytics_allowed(
        seeded_db, user_id=None,
    ) is True


@pytest.mark.asyncio
async def test_analytics_gate_blocks_anonymous_when_flag_off(seeded_db):
    await _set(seeded_db, "events.enabled", True)
    await _set(seeded_db, "events.anonymous_allowed", False)
    assert await privacy_consent_service.is_analytics_allowed(
        seeded_db, user_id=None,
    ) is False


@pytest.mark.asyncio
async def test_personalization_requires_user_id(seeded_db):
    assert await privacy_consent_service.is_personalization_allowed(
        seeded_db, user_id=None,
    ) is False


@pytest.mark.asyncio
async def test_personalization_gate_respects_flag(seeded_db):
    user = await _user(seeded_db)
    assert await privacy_consent_service.is_personalization_allowed(
        seeded_db, user_id=user.id,
    ) is False
    await privacy_consent_service.update_preferences(
        seeded_db, user_id=user.id,
        allow_personalized_recommendations=True,
    )
    await seeded_db.commit()
    assert await privacy_consent_service.is_personalization_allowed(
        seeded_db, user_id=user.id,
    ) is True


@pytest.mark.asyncio
async def test_marketing_and_whatsapp_are_independent_flags(seeded_db):
    user = await _user(seeded_db)
    await privacy_consent_service.update_preferences(
        seeded_db, user_id=user.id,
        allow_marketing_notifications=True,
    )
    await seeded_db.commit()
    assert await privacy_consent_service.is_marketing_notification_allowed(
        seeded_db, user_id=user.id,
    ) is True
    # WhatsApp NOT auto-on
    assert await privacy_consent_service.is_whatsapp_allowed(
        seeded_db, user_id=user.id,
    ) is False


@pytest.mark.asyncio
async def test_consent_required_blocks_user_without_consent(seeded_db):
    """consent.required_for_analytics=True + user with no row -> blocked."""
    await _set(seeded_db, "events.enabled", True)
    await _set(seeded_db, "consent.required_for_analytics", True)
    user = await _user(seeded_db)
    assert await privacy_consent_service.is_analytics_allowed(
        seeded_db, user_id=user.id,
    ) is False
