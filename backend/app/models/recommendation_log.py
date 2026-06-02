"""Append-only log of every listing impression served via a recommendation surface.

Phase 4 (campaigns + attribution) reads this to compute click-through and
conversion rates. We only LOG impressions here; click + conversion arrive
as separate `user_events` (event_name='ad.clicked', 'booking.completed' etc.)
and are joined by `(user_id, listing_id, surface)` at attribution time.

Indexed by user, surface, and listing for the three query patterns the
attribution job needs.
"""
import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean, Column, DateTime, Enum, Float, ForeignKey, Index, Integer, String,
)

from app.database import Base


class RecommendationSurface(str, enum.Enum):
    FOR_YOU = "FOR_YOU"
    SIMILAR = "SIMILAR"
    TRENDING = "TRENDING"
    RECENTLY_VIEWED = "RECENTLY_VIEWED"


class RecommendationLog(Base):
    __tablename__ = "recommendation_logs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    # Either a logged-in user or an anonymous session. Both may be null
    # if recommendations are server-rendered for an unauth API caller.
    user_id = Column(String, nullable=True, index=True)
    anonymous_session_id = Column(String(80), nullable=True, index=True)

    surface = Column(Enum(RecommendationSurface, native_enum=False),
                     nullable=False, index=True)

    listing_type = Column(String(30), nullable=False)   # 'reading_room' | 'accommodation'
    listing_id = Column(String, nullable=False, index=True)

    rank = Column(Integer, nullable=False)              # 1-based position in result list
    score = Column(Float, nullable=False)               # internal ranking score
    reason_code = Column(String(40), nullable=True)     # 'profile_city_match', 'sponsored', etc.

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Phase 4D — attribution funnel. clicked_at is stamped by the public
    # /recommendation-logs/{id}/clicked endpoint (frontend instrumentation).
    # converted_at + converted_booking_id are stamped by the booking
    # attribution hook (most-recent-impression OR most-recent-click wins,
    # whichever is newer, inside the attribution window).
    clicked_at = Column(DateTime, nullable=True)
    converted_at = Column(DateTime, nullable=True)
    converted_booking_id = Column(String, ForeignKey("bookings.id"), nullable=True)
    is_click_attributed = Column(Boolean, nullable=False, default=False)

    __table_args__ = (
        Index("ix_reco_log_user_surface", "user_id", "surface", "created_at"),
        Index("ix_reco_log_listing_created", "listing_id", "created_at"),
        Index("ix_reco_log_user_listing", "user_id", "listing_id", "created_at"),
    )
