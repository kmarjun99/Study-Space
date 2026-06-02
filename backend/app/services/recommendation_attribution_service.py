"""Recommendation attribution service (Phase 4D).

When a booking confirms, find the most recent matching recommendation_log
row for `(user_id, listing_id)` inside the attribution window and stamp
`converted_booking_id` + `converted_at`. Attribution prefers click data
when available (more intentional than a passive impression), falling back
to most-recent impression so attribution still works for surfaces where
frontend click instrumentation isn't wired up yet.

Hard rules:
  - Master-flag gated by `recommendations.attribution_enabled`.
  - Never overwrite a previously attributed log row (first-booking wins
    per recommendation_log row, last-impression wins per booking).
  - Click endpoint stamps clicked_at idempotently.
  - Funnel aggregates over all logs, grouped by surface.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.recommendation_log import RecommendationLog, RecommendationSurface
from app.services.tax_engine import cfg_get, load_active_config


# ---------- click marking --------------------------------------------------

async def mark_clicked(
    db: AsyncSession, *, log_id: str,
) -> Optional[RecommendationLog]:
    """Public endpoint hook. Idempotent — if already clicked, returns row
    unchanged so duplicate beacons don't reset timestamps."""
    row = await db.get(RecommendationLog, log_id)
    if row is None:
        return None
    if row.clicked_at is None:
        row.clicked_at = datetime.utcnow()
        await db.flush()
    return row


# ---------- attribution ----------------------------------------------------

async def attribute_booking(
    db: AsyncSession,
    *,
    booking_id: str,
    user_id: str,
    listing_id: str,
) -> Optional[RecommendationLog]:
    """Stamp the most recent matching recommendation_log for this user +
    listing inside the attribution window.

    Prefers clicked logs (last-click); falls back to last impression if
    no click recorded for this listing.

    Returns the attributed log row (or None). Caller commits.
    """
    config = await load_active_config(db)
    if not bool(cfg_get(config, "recommendations.attribution_enabled", False)):
        return None

    window_days = int(cfg_get(
        config, "recommendations.attribution_window_days", 7,
    ))
    cutoff = datetime.utcnow() - timedelta(days=window_days)

    # Last-click preference
    row = (await db.execute(
        select(RecommendationLog).where(and_(
            RecommendationLog.user_id == user_id,
            RecommendationLog.listing_id == listing_id,
            RecommendationLog.clicked_at.isnot(None),
            RecommendationLog.clicked_at >= cutoff,
            RecommendationLog.converted_booking_id.is_(None),
        ))
        .order_by(RecommendationLog.clicked_at.desc())
        .limit(1)
    )).scalar_one_or_none()

    if row is None:
        # Fallback: most-recent impression
        row = (await db.execute(
            select(RecommendationLog).where(and_(
                RecommendationLog.user_id == user_id,
                RecommendationLog.listing_id == listing_id,
                RecommendationLog.created_at >= cutoff,
                RecommendationLog.converted_booking_id.is_(None),
            ))
            .order_by(RecommendationLog.created_at.desc())
            .limit(1)
        )).scalar_one_or_none()

    if row is None:
        return None

    row.converted_booking_id = booking_id
    row.converted_at = datetime.utcnow()
    row.is_click_attributed = row.clicked_at is not None
    await db.flush()
    return row


# ---------- funnel aggregator ---------------------------------------------

@dataclass
class SurfaceFunnel:
    surface: str
    impressions: int = 0
    clicks: int = 0
    conversions: int = 0
    click_attributed_conversions: int = 0
    impression_attributed_conversions: int = 0

    @property
    def ctr(self) -> float:
        return (self.clicks / self.impressions) if self.impressions else 0.0

    @property
    def cvr(self) -> float:
        return (self.conversions / self.impressions) if self.impressions else 0.0


@dataclass
class AttributionFunnel:
    surfaces: list[SurfaceFunnel] = field(default_factory=list)
    total_impressions: int = 0
    total_clicks: int = 0
    total_conversions: int = 0


async def funnel_summary(db: AsyncSession) -> AttributionFunnel:
    """Aggregate impression/click/conversion counts grouped by surface.
    Powers the super-admin attribution dashboard."""
    by_surface: dict[str, SurfaceFunnel] = {
        s.value: SurfaceFunnel(surface=s.value) for s in RecommendationSurface
    }

    rows = (await db.execute(
        select(
            RecommendationLog.surface,
            func.count(RecommendationLog.id).label("impressions"),
            func.count(RecommendationLog.clicked_at).label("clicks"),
            func.count(RecommendationLog.converted_booking_id).label("conversions"),
        )
        .group_by(RecommendationLog.surface)
    )).all()

    out = AttributionFunnel()
    for surface_val, impressions, clicks, conversions in rows:
        key = surface_val.value if hasattr(surface_val, "value") else str(surface_val)
        sf = by_surface.setdefault(key, SurfaceFunnel(surface=key))
        sf.impressions = int(impressions or 0)
        sf.clicks = int(clicks or 0)
        sf.conversions = int(conversions or 0)
        out.total_impressions += sf.impressions
        out.total_clicks += sf.clicks
        out.total_conversions += sf.conversions

    # Click-vs-impression attribution split
    split_rows = (await db.execute(
        select(
            RecommendationLog.surface,
            RecommendationLog.is_click_attributed,
            func.count(RecommendationLog.id).label("n"),
        )
        .where(RecommendationLog.converted_booking_id.isnot(None))
        .group_by(RecommendationLog.surface, RecommendationLog.is_click_attributed)
    )).all()
    for surface_val, is_click, n in split_rows:
        key = surface_val.value if hasattr(surface_val, "value") else str(surface_val)
        sf = by_surface.setdefault(key, SurfaceFunnel(surface=key))
        if is_click:
            sf.click_attributed_conversions = int(n)
        else:
            sf.impression_attributed_conversions = int(n)

    out.surfaces = list(by_surface.values())
    return out
