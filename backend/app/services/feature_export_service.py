"""Feature export for offline ML training (Phase 6).

Produces per-user feature rows that an offline ML pipeline (sklearn /
LightGBM / etc.) can train on. Streams CSV — no pandas dependency.

Privacy hard rule (from project brief):
  - user_id is replaced with a SHA-256 hash so the dataset can be analysed
    without becoming a re-identification corpus.
  - No emails, names, search-query strings, or other free-text leave the
    service — only normalized scalar features.

The label column is computed live: 1 if the user has any booking, else 0.
That's a "did this user ever convert" signal — fine for warm-start models;
proper churn / repeat-booking labels need event-time splits (Phase 6+).
"""
from __future__ import annotations

import csv
import hashlib
import io
from datetime import datetime, timedelta
from typing import AsyncIterator, Optional

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.booking import Booking
from app.models.user_event import EventCategory, UserEvent
from app.models.user_intelligence_profile import (
    UserIntelligenceProfile,
)
from app.services.tax_engine import cfg_get, load_active_config


HEADER = [
    "user_hash",
    "intent_level", "raw_intent_score",
    "booking_urgency_score", "budget_sensitivity_score",
    "location_sensitivity_score", "premium_interest_score",
    "cancellation_risk_score", "conversion_probability_score",
    "total_searches_30d", "total_views_30d",
    "total_saves_30d", "total_contacts_30d",
    "has_preferred_city", "has_preferred_price_range",
    "label_has_any_booking",
]


def _hash_user_id(user_id: str, salt: str) -> str:
    return hashlib.sha256(f"{salt}:{user_id}".encode("utf-8")).hexdigest()[:16]


async def export_csv_rows(
    db: AsyncSession,
    *,
    window_days: int = 30,
    salt: Optional[str] = None,
) -> AsyncIterator[str]:
    """Async generator yielding one CSV line at a time (with trailing \n).
    Caller writes them to a StreamingResponse body.

    When `experiments.enabled` is OFF we still allow export (it's super-admin
    only and used for offline modelling, not live targeting). The privacy
    hash always applies."""
    config = await load_active_config(db)
    # Independent flag — exports may be useful before A/B testing is on.
    if not bool(cfg_get(config, "ml.feature_export_enabled", False)):
        # Yield header only, then stop. Avoids leaking that the flag is off.
        out = io.StringIO()
        csv.writer(out).writerow(HEADER)
        yield out.getvalue()
        return

    salt = salt or str(cfg_get(config, "ml.hash_salt", "studyspace-v1"))
    since = datetime.utcnow() - timedelta(days=window_days)

    # Header
    header_buf = io.StringIO()
    csv.writer(header_buf).writerow(HEADER)
    yield header_buf.getvalue()

    profiles = (await db.execute(
        select(UserIntelligenceProfile)
    )).scalars().all()

    # Per-user event counts, batched into a single query.
    event_counts = dict()
    for user_id, cat, n in (await db.execute(
        select(
            UserEvent.user_id,
            UserEvent.event_category,
            func.count(UserEvent.id),
        )
        .where(and_(
            UserEvent.user_id.isnot(None),
            UserEvent.created_at >= since,
        ))
        .group_by(UserEvent.user_id, UserEvent.event_category)
    )).all():
        event_counts.setdefault(user_id, {})[cat] = int(n)

    booked_ids = {
        r[0] for r in (await db.execute(
            select(Booking.user_id).distinct()
        )).all()
    }

    for p in profiles:
        c = event_counts.get(p.user_id, {})
        row = [
            _hash_user_id(p.user_id, salt),
            p.intent_level.value if p.intent_level else "",
            p.raw_intent_score,
            p.booking_urgency_score,
            p.budget_sensitivity_score,
            p.location_sensitivity_score,
            p.premium_interest_score,
            p.cancellation_risk_score,
            p.conversion_probability_score,
            c.get(EventCategory.SEARCH, 0),
            c.get(EventCategory.VIEW, 0),
            c.get(EventCategory.SAVE, 0),
            c.get(EventCategory.CONTACT, 0),
            1 if p.preferred_city else 0,
            1 if (p.preferred_price_min is not None
                  and p.preferred_price_max is not None) else 0,
            1 if p.user_id in booked_ids else 0,
        ]
        out = io.StringIO()
        csv.writer(out).writerow(row)
        yield out.getvalue()
