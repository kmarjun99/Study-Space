"""A/B experiment service (Phase 6).

Deterministic bucketing: a user always lands in the same variant for a
given experiment, computed from SHA-256(slug + ":" + user_id) so it works
in pure code without any state.

`get_variant(slug, user_id)` is cheap and idempotent — call it on every
request that needs to make a variant-dependent decision. `record_exposure`
upserts the assignment row (used by reporting). `record_conversion` stamps
converted_at on an existing assignment.

`results(slug)` aggregates per-variant exposures and conversions and
computes a simple two-proportion z-test for control vs. each treatment.
This is intentionally lightweight — no scipy/numpy dependency.
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from sqlalchemy import and_, case, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.experiment import (
    Experiment, ExperimentAssignment, ExperimentStatus,
)
from app.services.tax_engine import cfg_get, load_active_config


# ---------- deterministic bucketing ---------------------------------------

def _hash_to_unit(slug: str, user_id: str) -> float:
    """SHA-256 → [0, 1). Pure, fast, no state."""
    h = hashlib.sha256(f"{slug}:{user_id}".encode("utf-8")).hexdigest()
    return (int(h[:16], 16) % 10_000_000) / 10_000_000.0


def _variants_from_row(row: Experiment) -> list[tuple[str, int]]:
    try:
        items = json.loads(row.variants_json)
    except (ValueError, TypeError):
        return [("control", 100)]
    out: list[tuple[str, int]] = []
    for it in items:
        name = str(it.get("name", "")).strip()
        weight = int(it.get("weight", 0))
        if name and weight > 0:
            out.append((name, weight))
    return out or [("control", 100)]


def assign_variant(row: Experiment, user_id: str) -> str:
    """Pure deterministic assignment — no DB write."""
    variants = _variants_from_row(row)
    total = sum(w for _n, w in variants) or 100
    u = _hash_to_unit(row.slug, user_id)
    cumulative = 0
    for name, weight in variants:
        cumulative += weight
        if u < (cumulative / total):
            return name
    return variants[-1][0]


# ---------- public ---------------------------------------------------------

async def get_variant(
    db: AsyncSession, *, slug: str, user_id: str,
) -> Optional[str]:
    """Returns the variant the user is in, or None when the master flag is
    off or the experiment is not RUNNING. Cheap — read-only."""
    config = await load_active_config(db)
    if not bool(cfg_get(config, "experiments.enabled", False)):
        return None
    row = (await db.execute(
        select(Experiment).where(Experiment.slug == slug)
    )).scalar_one_or_none()
    if row is None or row.status != ExperimentStatus.RUNNING:
        return None
    now = datetime.utcnow()
    if row.starts_at and now < row.starts_at:
        return None
    if row.ends_at and now > row.ends_at:
        return None
    return assign_variant(row, user_id)


async def record_exposure(
    db: AsyncSession, *, slug: str, user_id: str,
) -> Optional[ExperimentAssignment]:
    """Upsert assignment row. Idempotent — re-exposure bumps `exposure_count`
    and `last_seen_at` but never moves the user across variants. Caller
    commits."""
    variant = await get_variant(db, slug=slug, user_id=user_id)
    if variant is None:
        return None
    exp = (await db.execute(
        select(Experiment).where(Experiment.slug == slug)
    )).scalar_one()

    existing = (await db.execute(
        select(ExperimentAssignment).where(and_(
            ExperimentAssignment.experiment_id == exp.id,
            ExperimentAssignment.user_id == user_id,
        ))
    )).scalar_one_or_none()
    if existing is not None:
        existing.exposure_count += 1
        existing.last_seen_at = datetime.utcnow()
        await db.flush()
        return existing

    row = ExperimentAssignment(
        experiment_id=exp.id, user_id=user_id, variant=variant,
    )
    db.add(row)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        # Race — reread.
        return (await db.execute(
            select(ExperimentAssignment).where(and_(
                ExperimentAssignment.experiment_id == exp.id,
                ExperimentAssignment.user_id == user_id,
            ))
        )).scalar_one()
    return row


async def record_conversion(
    db: AsyncSession, *, slug: str, user_id: str,
) -> Optional[ExperimentAssignment]:
    """Stamp converted on an existing assignment (re-conversions increment
    `conversion_count` but only the first stamps `converted_at`)."""
    config = await load_active_config(db)
    if not bool(cfg_get(config, "experiments.enabled", False)):
        return None
    exp = (await db.execute(
        select(Experiment).where(Experiment.slug == slug)
    )).scalar_one_or_none()
    if exp is None:
        return None
    row = (await db.execute(
        select(ExperimentAssignment).where(and_(
            ExperimentAssignment.experiment_id == exp.id,
            ExperimentAssignment.user_id == user_id,
        ))
    )).scalar_one_or_none()
    if row is None:
        return None
    if not row.converted:
        row.converted = True
        row.converted_at = datetime.utcnow()
    row.conversion_count += 1
    await db.flush()
    return row


# ---------- results --------------------------------------------------------

@dataclass
class VariantResult:
    variant: str
    exposures: int = 0
    converters: int = 0
    conversions_total: int = 0

    @property
    def conversion_rate(self) -> float:
        return self.converters / self.exposures if self.exposures else 0.0


def _two_proportion_z(p1: float, n1: int, p2: float, n2: int) -> Optional[float]:
    """Standard z-test for difference in two binomial proportions. Returns
    z-score (None if inputs are degenerate). Caller interprets significance."""
    if n1 == 0 or n2 == 0:
        return None
    pooled = (p1 * n1 + p2 * n2) / (n1 + n2)
    denom = pooled * (1 - pooled) * (1 / n1 + 1 / n2)
    if denom <= 0:
        return None
    return (p2 - p1) / math.sqrt(denom)


@dataclass
class ExperimentResults:
    slug: str
    status: str
    variants: list[VariantResult] = field(default_factory=list)
    control_variant: Optional[str] = None
    significance: dict[str, dict] = field(default_factory=dict)


async def results(
    db: AsyncSession, *, slug: str,
) -> Optional[ExperimentResults]:
    exp = (await db.execute(
        select(Experiment).where(Experiment.slug == slug)
    )).scalar_one_or_none()
    if exp is None:
        return None

    converted_int = case((ExperimentAssignment.converted.is_(True), 1), else_=0)
    rows = (await db.execute(
        select(
            ExperimentAssignment.variant,
            func.count(ExperimentAssignment.id).label("exposures"),
            func.sum(converted_int).label("converters"),
            func.sum(ExperimentAssignment.conversion_count).label("total"),
        )
        .where(ExperimentAssignment.experiment_id == exp.id)
        .group_by(ExperimentAssignment.variant)
    )).all()

    out = ExperimentResults(
        slug=exp.slug,
        status=exp.status.value,
        control_variant=_variants_from_row(exp)[0][0],
    )
    for variant, exposures, converters, total in rows:
        out.variants.append(VariantResult(
            variant=variant,
            exposures=int(exposures or 0),
            converters=int(converters or 0),
            conversions_total=int(total or 0),
        ))

    # Two-proportion z-test: each treatment vs. control.
    by_name = {v.variant: v for v in out.variants}
    ctrl = by_name.get(out.control_variant) if out.control_variant else None
    if ctrl and ctrl.exposures > 0:
        for v in out.variants:
            if v.variant == ctrl.variant:
                continue
            z = _two_proportion_z(
                ctrl.conversion_rate, ctrl.exposures,
                v.conversion_rate, v.exposures,
            )
            out.significance[v.variant] = {
                "z": z,
                # Two-tailed at α=0.05 → |z| ≥ 1.96.
                "is_significant_at_95": (z is not None and abs(z) >= 1.96),
                "lift": (v.conversion_rate - ctrl.conversion_rate),
            }
    return out


# ---------- read helpers ---------------------------------------------------

async def list_experiments(
    db: AsyncSession, *, include_completed: bool = True,
) -> list[Experiment]:
    stmt = select(Experiment).order_by(Experiment.created_at.desc())
    if not include_completed:
        stmt = stmt.where(Experiment.status != ExperimentStatus.COMPLETED)
    return list((await db.execute(stmt)).scalars().all())
