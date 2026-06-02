"""Owner insights service (Phase 5).

Aggregates Phase 1–4D behavioral data into per-owner / per-listing summaries
that surface in the owner dashboard.

PRIVACY HARD RULE — repeated from project brief:
  "Do not sell personal user data to owners; Owners get aggregated insights only"

Every returned number is a COUNT or RATE. No user_ids, names, emails, search
queries containing user content, or anything traceable to an individual user
ever leaves this module. Suppress series with fewer than `k_anonymity_floor`
distinct users so a single user's activity can't be re-identified.

Counts are pulled from:
  - `recommendation_logs`   → impressions, clicks
  - `user_events`           → views, search-to-listing conversion
  - `favorites`             → saves
  - `inquiries`             → contact attempts (owner already sees these)
  - `bookings`              → confirmed bookings
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.booking import Booking, BookingStatus
from app.models.favorite import Favorite
from app.models.inquiry import Inquiry
from app.models.reading_room import Cabin, ReadingRoom
from app.models.accommodation import Accommodation
from app.models.recommendation_log import RecommendationLog
from app.models.user_event import UserEvent
from app.services.tax_engine import cfg_get, load_active_config


# Minimum distinct-user count below which a metric is suppressed (returned
# as None) to protect against re-identification of an individual user.
DEFAULT_K_ANONYMITY = 5


def _suppress_if_low(n_distinct_users: int, value: int, k: int) -> Optional[int]:
    return value if n_distinct_users >= k else None


@dataclass
class ListingInsight:
    listing_id: str
    listing_type: str
    name: Optional[str] = None
    impressions: int = 0
    clicks: int = 0
    views: int = 0
    saves: int = 0
    inquiries: int = 0
    bookings: int = 0
    distinct_viewers: int = 0
    # Suppressed when distinct_viewers < k.
    view_to_inquiry_rate: Optional[float] = None
    view_to_booking_rate: Optional[float] = None
    low_volume_suppressed: bool = False


@dataclass
class OwnerInsightSummary:
    owner_id: str
    window_days: int
    listings: list[ListingInsight] = field(default_factory=list)
    total_impressions: int = 0
    total_views: int = 0
    total_saves: int = 0
    total_inquiries: int = 0
    total_bookings: int = 0


async def _config(db: AsyncSession) -> dict:
    return await load_active_config(db)


async def _flag_on(db: AsyncSession) -> bool:
    return bool(cfg_get(await _config(db), "insights.enabled", False))


# ---------- per-listing aggregator -----------------------------------------

async def _aggregate_one_listing(
    db: AsyncSession,
    *,
    listing_id: str,
    listing_type: str,
    name: Optional[str],
    since: datetime,
    k: int,
) -> ListingInsight:
    out = ListingInsight(
        listing_id=listing_id, listing_type=listing_type, name=name,
    )

    # Impressions + clicks from recommendation_logs
    reco_row = (await db.execute(
        select(
            func.count(RecommendationLog.id),
            func.count(RecommendationLog.clicked_at),
        )
        .where(and_(
            RecommendationLog.listing_id == listing_id,
            RecommendationLog.created_at >= since,
        ))
    )).first()
    out.impressions = int(reco_row[0] or 0) if reco_row else 0
    out.clicks = int(reco_row[1] or 0) if reco_row else 0

    # Views from user_events (entity_id match, category VIEW)
    view_row = (await db.execute(
        select(
            func.count(UserEvent.id),
            func.count(func.distinct(UserEvent.user_id)),
        )
        .where(and_(
            UserEvent.entity_id == listing_id,
            UserEvent.event_category == "VIEW",
            UserEvent.created_at >= since,
        ))
    )).first()
    out.views = int(view_row[0] or 0) if view_row else 0
    out.distinct_viewers = int(view_row[1] or 0) if view_row else 0

    # Saves from favorites
    if listing_type == "reading_room":
        fav_row = (await db.execute(
            select(func.count(Favorite.id)).where(
                Favorite.reading_room_id == listing_id,
            )
        )).first()
    else:
        fav_row = (await db.execute(
            select(func.count(Favorite.id)).where(
                Favorite.accommodation_id == listing_id,
            )
        )).first()
    out.saves = int(fav_row[0] or 0) if fav_row else 0

    # Inquiries (accommodation only — reading_rooms don't have inquiries
    # in current schema; check before querying)
    if listing_type == "accommodation":
        inq_row = (await db.execute(
            select(func.count(Inquiry.id)).where(and_(
                Inquiry.accommodation_id == listing_id,
                Inquiry.created_at >= since,
            ))
        )).first()
        out.inquiries = int(inq_row[0] or 0) if inq_row else 0

    # Bookings — for reading_rooms join through cabins
    if listing_type == "reading_room":
        bk_row = (await db.execute(
            select(func.count(Booking.id))
            .join(Cabin, Cabin.id == Booking.cabin_id)
            .where(and_(
                Cabin.reading_room_id == listing_id,
                Booking.status == BookingStatus.ACTIVE,
                Booking.created_at >= since,
            ))
        )).first()
    else:
        bk_row = (await db.execute(
            select(func.count(Booking.id)).where(and_(
                Booking.accommodation_id == listing_id,
                Booking.status == BookingStatus.ACTIVE,
                Booking.created_at >= since,
            ))
        )).first()
    out.bookings = int(bk_row[0] or 0) if bk_row else 0

    # Conversion rates — suppressed if fewer than k distinct viewers
    if out.distinct_viewers >= k and out.views > 0:
        out.view_to_inquiry_rate = round(out.inquiries / out.views, 4)
        out.view_to_booking_rate = round(out.bookings / out.views, 4)
    else:
        # Still expose absolute counts; just don't reveal a ratio that could
        # zero-in on a single user.
        out.low_volume_suppressed = out.distinct_viewers < k

    return out


# ---------- public: per-owner summary --------------------------------------

async def summary_for_owner(
    db: AsyncSession,
    *,
    owner_id: str,
    window_days: int = 30,
) -> Optional[OwnerInsightSummary]:
    """Returns None when `insights.enabled=False` so the caller can render an
    empty state without leaking that the feature exists."""
    if not await _flag_on(db):
        return None

    config = await _config(db)
    k = int(cfg_get(config, "insights.k_anonymity_floor", DEFAULT_K_ANONYMITY))
    since = datetime.utcnow() - timedelta(days=window_days)

    out = OwnerInsightSummary(owner_id=owner_id, window_days=window_days)

    # Reading rooms owned
    rr_rows = (await db.execute(
        select(ReadingRoom.id, ReadingRoom.name)
        .where(ReadingRoom.owner_id == owner_id)
    )).all()
    for rid, rname in rr_rows:
        out.listings.append(await _aggregate_one_listing(
            db, listing_id=rid, listing_type="reading_room",
            name=rname, since=since, k=k,
        ))

    # Accommodations owned
    acc_rows = (await db.execute(
        select(Accommodation.id, Accommodation.name)
        .where(Accommodation.owner_id == owner_id)
    )).all()
    for aid, aname in acc_rows:
        out.listings.append(await _aggregate_one_listing(
            db, listing_id=aid, listing_type="accommodation",
            name=aname, since=since, k=k,
        ))

    # Totals
    for li in out.listings:
        out.total_impressions += li.impressions
        out.total_views += li.views
        out.total_saves += li.saves
        out.total_inquiries += li.inquiries
        out.total_bookings += li.bookings

    return out
