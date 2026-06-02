"""Super-admin platform dashboard API (Phase 5)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_super_admin
from app.models.user import User
from app.services import admin_dashboard_service


router = APIRouter(
    prefix="/super-admin/dashboard", tags=["Super Admin: Dashboard"],
)


@router.get("")
async def get_dashboard(
    window_days: int = 30,
    _: User = Depends(get_current_super_admin),
    db: AsyncSession = Depends(get_db),
):
    summary = await admin_dashboard_service.build_dashboard(
        db, window_days=window_days,
    )
    if summary is None:
        return {"enabled": False}
    return {
        "enabled": True,
        "window_days": summary.window_days,
        "funnel": [{"name": s.name, "count": s.count} for s in summary.funnel],
        "top_cities": [
            {"city": c.city, "searches": c.searches, "distinct_users": c.distinct_users}
            for c in summary.top_cities
        ],
        "segments": [
            {"segment_id": s.segment_id, "slug": s.slug,
             "name": s.name, "active_members": s.active_members}
            for s in summary.segments
        ],
        "campaigns": [
            {"campaign_id": c.campaign_id, "slug": c.slug, "status": c.status,
             "queued": c.queued, "delivered": c.delivered,
             "clicked": c.clicked, "converted": c.converted}
            for c in summary.campaigns
        ],
        "automation": {
            "active_rules": summary.automation.active_rules,
            "queued_total": summary.automation.queued_total,
            "delivered_total": summary.automation.delivered_total,
            "failed_total": summary.automation.failed_total,
        },
    }
