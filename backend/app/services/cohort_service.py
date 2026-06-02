"""Weekly cohort retention analysis (Phase 6).

Defines a cohort as: "users whose first matching event occurred in
calendar week W". Then for each subsequent week W+k (k = 0, 1, …, N),
counts how many of those cohort members took *any* event in that week.

Output is a triangular matrix:

  cohort_week | size | retention_w0 | retention_w1 | ...

`retention_w0` is always 100% by definition; `retention_w1` is the % of
the cohort that came back in the following week, etc.

This service is read-only and runs over `user_events`. Master-flag gated
on `insights.enabled` (re-uses the dashboard flag — cohorts are admin-only
aggregates).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user_event import EventCategory, UserEvent
from app.services.tax_engine import cfg_get, load_active_config


def _week_floor(dt: datetime) -> datetime:
    """Monday 00:00 UTC of the week containing dt."""
    monday = (dt - timedelta(days=dt.weekday())).date()
    return datetime(monday.year, monday.month, monday.day)


@dataclass
class CohortRow:
    cohort_week: str            # ISO date of the Monday of the cohort week
    size: int                   # distinct users in this cohort
    retention: list[float] = field(default_factory=list)
    retention_counts: list[int] = field(default_factory=list)


@dataclass
class CohortReport:
    weeks: int
    cohort_kind: str
    rows: list[CohortRow] = field(default_factory=list)


async def build_report(
    db: AsyncSession,
    *,
    n_cohort_weeks: int = 8,
    n_retention_weeks: int = 8,
    cohort_kind: str = "search_first",
) -> Optional[CohortReport]:
    """Build a weekly cohort × retention matrix.

    `cohort_kind`:
      - "search_first" : cohort entry = user's first SEARCH event
      - "booking_first": cohort entry = user's first BOOKING event

    Returns None when the insights master flag is off.
    """
    config = await load_active_config(db)
    if not bool(cfg_get(config, "insights.enabled", False)):
        return None

    if cohort_kind == "booking_first":
        cohort_category = EventCategory.BOOKING
    else:
        cohort_category = EventCategory.SEARCH

    now = datetime.utcnow()
    earliest = _week_floor(now - timedelta(weeks=n_cohort_weeks - 1))

    # "First event" = MIN(created_at) per user matching the cohort category.
    first_event_rows = (await db.execute(
        select(
            UserEvent.user_id,
            func.min(UserEvent.created_at).label("first_at"),
        )
        .where(and_(
            UserEvent.user_id.isnot(None),
            UserEvent.event_category == cohort_category,
            UserEvent.created_at >= earliest,
        ))
        .group_by(UserEvent.user_id)
    )).all()

    # Bucket each user into a cohort week, keeping only the configured window.
    cohorts: dict[datetime, list[str]] = {}
    user_first: dict[str, datetime] = {}
    for user_id, first_at in first_event_rows:
        if user_id is None or first_at is None:
            continue
        wk = _week_floor(first_at)
        if wk < earliest:
            continue
        cohorts.setdefault(wk, []).append(user_id)
        user_first[user_id] = wk

    if not cohorts:
        return CohortReport(weeks=n_retention_weeks, cohort_kind=cohort_kind)

    # All users we need to look up activity for.
    all_cohort_user_ids = list(user_first.keys())

    # Fetch every event for these users from `earliest` onwards. We bucket
    # them client-side by user → week so we can compute retention per
    # cohort × week.
    activity_rows = (await db.execute(
        select(UserEvent.user_id, UserEvent.created_at)
        .where(and_(
            UserEvent.user_id.in_(all_cohort_user_ids),
            UserEvent.created_at >= earliest,
        ))
    )).all()
    seen_weeks: dict[str, set[datetime]] = {}
    for user_id, created_at in activity_rows:
        seen_weeks.setdefault(user_id, set()).add(_week_floor(created_at))

    out = CohortReport(weeks=n_retention_weeks, cohort_kind=cohort_kind)
    for cohort_week in sorted(cohorts.keys()):
        members = cohorts[cohort_week]
        retention_counts: list[int] = []
        for k in range(n_retention_weeks):
            target_week = cohort_week + timedelta(weeks=k)
            if target_week > _week_floor(now):
                break  # future weeks not yet observable
            count = sum(
                1 for uid in members
                if target_week in seen_weeks.get(uid, set())
            )
            retention_counts.append(count)
        size = len(members)
        retention = [
            round(c / size, 4) if size else 0.0 for c in retention_counts
        ]
        out.rows.append(CohortRow(
            cohort_week=cohort_week.date().isoformat(),
            size=size, retention=retention,
            retention_counts=retention_counts,
        ))
    return out
