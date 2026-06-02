"""Layered consent management.

One row per user in `user_consent_preferences`. Lazy-create on first read
with all flags OFF (opt-in policy). All gate questions live here so callers
never read consent flags directly — keeps the policy in one place.

Privacy-relevant invariants:
  - Default all flags OFF.
  - `is_analytics_allowed(user_id=None)` returns the config-level default
    for anonymous sessions (no per-user row to read).
  - Toggling a flag stamps `consent_policy_version` so we can prove which
    policy text the user accepted at the time.
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user_consent_preferences import UserConsentPreferences
from app.services.tax_engine import cfg_get, load_active_config


# ---------- core read/write -----------------------------------------------

async def get_or_create(
    db: AsyncSession, *, user_id: str,
) -> UserConsentPreferences:
    """Return the user's consent row, creating it (default-OFF) on first call.

    Caller MUST commit if a new row was created.
    """
    row = await db.get(UserConsentPreferences, user_id)
    if row is not None:
        return row
    row = UserConsentPreferences(user_id=user_id)
    db.add(row)
    await db.flush()
    return row


async def update_preferences(
    db: AsyncSession,
    *,
    user_id: str,
    allow_analytics_tracking: Optional[bool] = None,
    allow_personalized_recommendations: Optional[bool] = None,
    allow_marketing_notifications: Optional[bool] = None,
    allow_whatsapp_updates: Optional[bool] = None,
    allow_location_based_suggestions: Optional[bool] = None,
    consent_policy_version: Optional[str] = None,
) -> UserConsentPreferences:
    """Partial update — only flags actually passed are touched."""
    row = await get_or_create(db, user_id=user_id)

    if allow_analytics_tracking is not None:
        row.allow_analytics_tracking = allow_analytics_tracking
    if allow_personalized_recommendations is not None:
        row.allow_personalized_recommendations = allow_personalized_recommendations
    if allow_marketing_notifications is not None:
        row.allow_marketing_notifications = allow_marketing_notifications
    if allow_whatsapp_updates is not None:
        row.allow_whatsapp_updates = allow_whatsapp_updates
    if allow_location_based_suggestions is not None:
        row.allow_location_based_suggestions = allow_location_based_suggestions
    if consent_policy_version is not None:
        row.consent_policy_version = consent_policy_version

    await db.flush()
    return row


# ---------- gate questions (one per use-site) -----------------------------

async def is_analytics_allowed(
    db: AsyncSession, *, user_id: Optional[str],
) -> bool:
    """Is this user / session allowed in the behavioral event firehose?

    For anonymous sessions (user_id=None), gate on the config flag
    `events.anonymous_allowed`. For authenticated users, gate on their
    `allow_analytics_tracking` row; if `consent.required_for_analytics`
    is OFF, also pass when the row defaults exist (lazy create).
    """
    config = await load_active_config(db)
    if not bool(cfg_get(config, "events.enabled", False)):
        return False

    if user_id is None:
        return bool(cfg_get(config, "events.anonymous_allowed", True))

    consent_required = bool(cfg_get(config, "consent.required_for_analytics", False))
    if not consent_required:
        return True
    row = await db.get(UserConsentPreferences, user_id)
    return bool(row and row.allow_analytics_tracking)


async def is_personalization_allowed(
    db: AsyncSession, *, user_id: Optional[str],
) -> bool:
    """Can we use this user's behavior to personalize recommendations?"""
    if user_id is None:
        return False
    row = await db.get(UserConsentPreferences, user_id)
    return bool(row and row.allow_personalized_recommendations)


async def is_marketing_notification_allowed(
    db: AsyncSession, *, user_id: Optional[str],
) -> bool:
    if user_id is None:
        return False
    row = await db.get(UserConsentPreferences, user_id)
    return bool(row and row.allow_marketing_notifications)


async def is_whatsapp_allowed(
    db: AsyncSession, *, user_id: Optional[str],
) -> bool:
    if user_id is None:
        return False
    row = await db.get(UserConsentPreferences, user_id)
    return bool(row and row.allow_whatsapp_updates)


async def is_location_based_allowed(
    db: AsyncSession, *, user_id: Optional[str],
) -> bool:
    if user_id is None:
        return False
    row = await db.get(UserConsentPreferences, user_id)
    return bool(row and row.allow_location_based_suggestions)


# ---------- right to erasure ----------------------------------------------

async def revoke_all_consents(db: AsyncSession, *, user_id: str) -> None:
    """One-call utility for the "Stop everything" button. Caller commits."""
    row = await get_or_create(db, user_id=user_id)
    row.allow_analytics_tracking = False
    row.allow_personalized_recommendations = False
    row.allow_marketing_notifications = False
    row.allow_whatsapp_updates = False
    row.allow_location_based_suggestions = False
    await db.flush()
