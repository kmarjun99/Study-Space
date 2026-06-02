"""Owner insights API (Phase 5).

Aggregated counts only — no PII. Listing-level metrics are suppressed below
k-anonymity floor so a single user's activity cannot be re-identified.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_admin
from app.models.user import User
from app.services import owner_insights_service


router = APIRouter(prefix="/owner/insights", tags=["Owner: Insights"])


@router.get("")
async def get_insights(
    window_days: int = 30,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    if window_days <= 0 or window_days > 365:
        raise HTTPException(
            status_code=400, detail="window_days must be 1..365",
        )

    summary = await owner_insights_service.summary_for_owner(
        db, owner_id=current_user.id, window_days=window_days,
    )
    if summary is None:
        return {
            "enabled": False,
            "owner_id": current_user.id,
            "message": "Insights are not enabled. Contact your account manager.",
        }
    return {
        "enabled": True,
        "owner_id": summary.owner_id,
        "window_days": summary.window_days,
        "total_impressions": summary.total_impressions,
        "total_views": summary.total_views,
        "total_saves": summary.total_saves,
        "total_inquiries": summary.total_inquiries,
        "total_bookings": summary.total_bookings,
        "listings": [
            {
                "listing_id": li.listing_id,
                "listing_type": li.listing_type,
                "name": li.name,
                "impressions": li.impressions,
                "clicks": li.clicks,
                "views": li.views,
                "saves": li.saves,
                "inquiries": li.inquiries,
                "bookings": li.bookings,
                "distinct_viewers": li.distinct_viewers,
                "view_to_inquiry_rate": li.view_to_inquiry_rate,
                "view_to_booking_rate": li.view_to_booking_rate,
                "low_volume_suppressed": li.low_volume_suppressed,
            }
            for li in summary.listings
        ],
    }
