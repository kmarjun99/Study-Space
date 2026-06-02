"""Recommendation attribution API (Phase 4D).

Public click endpoint + super-admin funnel summary.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_super_admin
from app.models.user import User
from app.services import recommendation_attribution_service as attribution


router = APIRouter(tags=["Intelligence: Recommendation Attribution"])


@router.post("/recommendation-logs/{log_id}/clicked")
async def record_click(
    log_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Public — typically called by a pixel-style redirect endpoint that
    stamps the click then forwards to the listing URL. No auth because the
    `log_id` IS the unforgeable token (UUID); a production deployment can
    add a signed HMAC if click fraud becomes a concern."""
    row = await attribution.mark_clicked(db, log_id=log_id)
    if row is None:
        raise HTTPException(status_code=404, detail="log not found")
    await db.commit()
    return {"ok": True}


@router.get("/super-admin/recommendation-attribution/funnel")
async def get_funnel(
    _: User = Depends(get_current_super_admin),
    db: AsyncSession = Depends(get_db),
):
    summary = await attribution.funnel_summary(db)
    return {
        "total_impressions": summary.total_impressions,
        "total_clicks": summary.total_clicks,
        "total_conversions": summary.total_conversions,
        "surfaces": [
            {
                "surface": s.surface,
                "impressions": s.impressions,
                "clicks": s.clicks,
                "conversions": s.conversions,
                "click_attributed_conversions": s.click_attributed_conversions,
                "impression_attributed_conversions": s.impression_attributed_conversions,
                "ctr": round(s.ctr, 4),
                "cvr": round(s.cvr, 4),
            }
            for s in summary.surfaces
        ],
    }
