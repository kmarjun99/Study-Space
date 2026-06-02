"""Super-admin platform dashboard service (Phase 5).

Aggregates intelligence-layer signals across the whole platform — top demand
cities, search→view→book funnel, segment sizes, campaign / automation
performance summary. Read-only.

Privacy: this surface is super-admin only. Internal numbers are full counts;
no PII leaves the service. Owners go through `owner_insights_service`
instead.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.booking import Booking, BookingStatus
from app.models.campaign import (
    Campaign, CampaignDelivery, CampaignStatus, DeliveryStatus,
)
from app.models.notification_rule import NotificationRule
from app.models.user_event import EventCategory, UserEvent
from app.models.user_segment import UserSegment, UserSegmentMembership
from app.services.tax_engine import cfg_get, load_active_config


@dataclass
class FunnelStep:
    name: str
    count: int


@dataclass
class CityDemand:
    city: str
    searches: int
    distinct_users: int


@dataclass
class SegmentSnapshot:
    segment_id: str
    slug: str
    name: str
    active_members: int


@dataclass
class CampaignSnapshot:
    campaign_id: str
    slug: str
    status: str
    queued: int
    delivered: int
    clicked: int
    converted: int


@dataclass
class AutomationSnapshot:
    active_rules: int
    queued_total: int
    delivered_total: int
    failed_total: int


@dataclass
class AdminDashboard:
    window_days: int
    funnel: list[FunnelStep] = field(default_factory=list)
    top_cities: list[CityDemand] = field(default_factory=list)
    segments: list[SegmentSnapshot] = field(default_factory=list)
    campaigns: list[CampaignSnapshot] = field(default_factory=list)
    automation: AutomationSnapshot = field(
        default_factory=lambda: AutomationSnapshot(0, 0, 0, 0),
    )


async def build_dashboard(
    db: AsyncSession,
    *,
    window_days: int = 30,
    top_n_cities: int = 10,
    top_n_campaigns: int = 10,
) -> Optional[AdminDashboard]:
    """Returns None when `insights.enabled=False`."""
    config = await load_active_config(db)
    if not bool(cfg_get(config, "insights.enabled", False)):
        return None

    since = datetime.utcnow() - timedelta(days=window_days)
    out = AdminDashboard(window_days=window_days)

    # Search → view → save → contact → book funnel
    category_counts = (await db.execute(
        select(UserEvent.event_category, func.count(UserEvent.id))
        .where(UserEvent.created_at >= since)
        .group_by(UserEvent.event_category)
    )).all()
    cat_map = {c: int(n) for c, n in category_counts}

    search_n = cat_map.get(EventCategory.SEARCH, 0)
    view_n = cat_map.get(EventCategory.VIEW, 0)
    save_n = cat_map.get(EventCategory.SAVE, 0)
    contact_n = cat_map.get(EventCategory.CONTACT, 0)
    book_n = (await db.execute(
        select(func.count(Booking.id)).where(and_(
            Booking.status == BookingStatus.ACTIVE,
            Booking.created_at >= since,
        ))
    )).scalar_one()
    out.funnel = [
        FunnelStep("search", search_n),
        FunnelStep("view", view_n),
        FunnelStep("save", save_n),
        FunnelStep("contact", contact_n),
        FunnelStep("book", int(book_n)),
    ]

    # Top demand cities — from SEARCH events with a non-null city
    city_rows = (await db.execute(
        select(
            UserEvent.city,
            func.count(UserEvent.id).label("n"),
            func.count(func.distinct(UserEvent.user_id)).label("d"),
        )
        .where(and_(
            UserEvent.event_category == EventCategory.SEARCH,
            UserEvent.created_at >= since,
            UserEvent.city.isnot(None),
        ))
        .group_by(UserEvent.city)
        .order_by(func.count(UserEvent.id).desc())
        .limit(top_n_cities)
    )).all()
    out.top_cities = [
        CityDemand(city=c, searches=int(n), distinct_users=int(d))
        for c, n, d in city_rows
    ]

    # Segment sizes (LIVE counts)
    seg_rows = (await db.execute(
        select(
            UserSegment.id, UserSegment.slug, UserSegment.name,
            func.count(UserSegmentMembership.id),
        )
        .join(
            UserSegmentMembership,
            UserSegmentMembership.segment_id == UserSegment.id,
            isouter=True,
        )
        .where(UserSegment.is_active.is_(True))
        .group_by(UserSegment.id, UserSegment.slug, UserSegment.name)
    )).all()
    out.segments = [
        SegmentSnapshot(segment_id=sid, slug=slug, name=name,
                        active_members=int(n))
        for sid, slug, name, n in seg_rows
    ]

    # Campaign summary — top by queued in window
    camp_rows = (await db.execute(
        select(Campaign.id, Campaign.slug, Campaign.status)
        .where(Campaign.status.in_([
            CampaignStatus.ACTIVE, CampaignStatus.PAUSED, CampaignStatus.COMPLETED,
        ]))
        .limit(top_n_campaigns)
    )).all()
    for cid, slug, status in camp_rows:
        counts = (await db.execute(
            select(
                CampaignDelivery.status,
                func.count(CampaignDelivery.id),
                func.count(CampaignDelivery.clicked_at),
                func.count(CampaignDelivery.converted_booking_id),
            )
            .where(and_(
                CampaignDelivery.campaign_id == cid,
                CampaignDelivery.queued_at >= since,
            ))
            .group_by(CampaignDelivery.status)
        )).all()
        queued = sum(int(n) for _s, n, _c, _v in counts)
        delivered = sum(int(n) for s, n, _c, _v in counts
                        if s == DeliveryStatus.DELIVERED)
        clicked = sum(int(c) for _s, _n, c, _v in counts)
        converted = sum(int(v) for _s, _n, _c, v in counts)
        out.campaigns.append(CampaignSnapshot(
            campaign_id=cid, slug=slug,
            status=status.value if hasattr(status, "value") else str(status),
            queued=queued, delivered=delivered,
            clicked=clicked, converted=converted,
        ))

    # Automation summary
    active_rules = (await db.execute(
        select(func.count(NotificationRule.id))
        .where(NotificationRule.is_active.is_(True))
    )).scalar_one()
    rule_delivery_counts = (await db.execute(
        select(CampaignDelivery.status, func.count(CampaignDelivery.id))
        .where(and_(
            CampaignDelivery.notification_rule_id.isnot(None),
            CampaignDelivery.queued_at >= since,
        ))
        .group_by(CampaignDelivery.status)
    )).all()
    automation_map = {s: int(n) for s, n in rule_delivery_counts}
    out.automation = AutomationSnapshot(
        active_rules=int(active_rules),
        queued_total=automation_map.get(DeliveryStatus.QUEUED, 0),
        delivered_total=automation_map.get(DeliveryStatus.DELIVERED, 0),
        failed_total=automation_map.get(DeliveryStatus.FAILED, 0),
    )

    # Recommendation impressions (informational — surface-level funnel
    # already exists in /super-admin/recommendation-attribution/funnel)
    return out
