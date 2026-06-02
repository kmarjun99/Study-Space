"""Experiments + cohorts + ML feature export API (Phase 6)."""
from __future__ import annotations

import json
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_super_admin
from app.models.experiment import Experiment, ExperimentStatus
from app.models.user import User
from app.services import (
    cohort_service, experiment_service, feature_export_service,
)


router = APIRouter(tags=["Super Admin: Experiments"])


# ---------- Experiments ----------------------------------------------------

class VariantSpec(BaseModel):
    name: str
    weight: int


class ExperimentIn(BaseModel):
    slug: str
    name: str
    description: Optional[str] = None
    hypothesis: Optional[str] = None
    variants: list[VariantSpec]
    success_event_name: str = "booking.completed"
    starts_at: Optional[str] = None
    ends_at: Optional[str] = None


class ExperimentPatch(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    hypothesis: Optional[str] = None
    status: Optional[str] = None
    success_event_name: Optional[str] = None
    starts_at: Optional[str] = None
    ends_at: Optional[str] = None


def _parse_dt(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"invalid datetime: {s}") from exc


def _to_exp(row: Experiment) -> dict:
    try:
        variants = json.loads(row.variants_json)
    except (ValueError, TypeError):
        variants = []
    return {
        "id": row.id, "slug": row.slug, "name": row.name,
        "description": row.description, "hypothesis": row.hypothesis,
        "variants": variants,
        "success_event_name": row.success_event_name,
        "status": row.status.value,
        "starts_at": row.starts_at.isoformat() if row.starts_at else None,
        "ends_at": row.ends_at.isoformat() if row.ends_at else None,
        "created_at": row.created_at.isoformat(),
        "updated_at": row.updated_at.isoformat(),
    }


@router.get("/super-admin/experiments")
async def list_experiments(
    _: User = Depends(get_current_super_admin),
    db: AsyncSession = Depends(get_db),
):
    rows = await experiment_service.list_experiments(db)
    return [_to_exp(r) for r in rows]


@router.post("/super-admin/experiments")
async def create_experiment(
    body: ExperimentIn,
    actor: User = Depends(get_current_super_admin),
    db: AsyncSession = Depends(get_db),
):
    if sum(v.weight for v in body.variants) <= 0:
        raise HTTPException(status_code=400, detail="variant weights must sum > 0")
    row = Experiment(
        slug=body.slug, name=body.name, description=body.description,
        hypothesis=body.hypothesis,
        variants_json=json.dumps([v.model_dump() for v in body.variants]),
        success_event_name=body.success_event_name,
        status=ExperimentStatus.DRAFT,
        starts_at=_parse_dt(body.starts_at),
        ends_at=_parse_dt(body.ends_at),
        created_by=actor.id,
    )
    db.add(row)
    try:
        await db.commit()
    except Exception as exc:
        await db.rollback()
        raise HTTPException(status_code=400, detail=f"could not create: {exc}") from exc
    await db.refresh(row)
    return _to_exp(row)


@router.patch("/super-admin/experiments/{experiment_id}")
async def patch_experiment(
    experiment_id: str,
    body: ExperimentPatch,
    _: User = Depends(get_current_super_admin),
    db: AsyncSession = Depends(get_db),
):
    row = await db.get(Experiment, experiment_id)
    if row is None:
        raise HTTPException(status_code=404, detail="experiment not found")
    if body.name is not None: row.name = body.name
    if body.description is not None: row.description = body.description
    if body.hypothesis is not None: row.hypothesis = body.hypothesis
    if body.success_event_name is not None: row.success_event_name = body.success_event_name
    if body.starts_at is not None: row.starts_at = _parse_dt(body.starts_at)
    if body.ends_at is not None: row.ends_at = _parse_dt(body.ends_at)
    if body.status is not None:
        try:
            row.status = ExperimentStatus(body.status)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=f"invalid status: {body.status}") from exc
    await db.commit()
    await db.refresh(row)
    return _to_exp(row)


@router.get("/super-admin/experiments/{slug}/results")
async def get_results(
    slug: str,
    _: User = Depends(get_current_super_admin),
    db: AsyncSession = Depends(get_db),
):
    res = await experiment_service.results(db, slug=slug)
    if res is None:
        raise HTTPException(status_code=404, detail="experiment not found")
    return {
        "slug": res.slug, "status": res.status,
        "control_variant": res.control_variant,
        "variants": [
            {
                "variant": v.variant,
                "exposures": v.exposures,
                "converters": v.converters,
                "conversions_total": v.conversions_total,
                "conversion_rate": round(v.conversion_rate, 4),
            }
            for v in res.variants
        ],
        "significance": res.significance,
    }


# ---------- Cohorts --------------------------------------------------------

@router.get("/super-admin/cohorts/weekly")
async def weekly_cohorts(
    cohort_kind: str = "search_first",
    n_cohort_weeks: int = 8,
    n_retention_weeks: int = 8,
    _: User = Depends(get_current_super_admin),
    db: AsyncSession = Depends(get_db),
):
    if cohort_kind not in ("search_first", "booking_first"):
        raise HTTPException(
            status_code=400,
            detail="cohort_kind must be 'search_first' or 'booking_first'",
        )
    report = await cohort_service.build_report(
        db, cohort_kind=cohort_kind,
        n_cohort_weeks=n_cohort_weeks,
        n_retention_weeks=n_retention_weeks,
    )
    if report is None:
        return {"enabled": False}
    return {
        "enabled": True,
        "cohort_kind": report.cohort_kind,
        "weeks": report.weeks,
        "rows": [
            {
                "cohort_week": r.cohort_week, "size": r.size,
                "retention": r.retention,
                "retention_counts": r.retention_counts,
            }
            for r in report.rows
        ],
    }


# ---------- Feature export -------------------------------------------------

@router.get("/super-admin/ml/features.csv")
async def export_features(
    window_days: int = 30,
    _: User = Depends(get_current_super_admin),
    db: AsyncSession = Depends(get_db),
):
    """Streams a privacy-hashed feature CSV for offline ML training."""
    gen = feature_export_service.export_csv_rows(db, window_days=window_days)
    return StreamingResponse(
        gen, media_type="text/csv",
        headers={
            "Content-Disposition":
                f'attachment; filename="studyspace_features_{window_days}d.csv"',
        },
    )
