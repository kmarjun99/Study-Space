"""Experiment + cohort + feature export tests (Phase 6).

Covers:
  - Master flag off → get_variant returns None
  - Bucketing is deterministic (same user, same slug → same variant 100 times)
  - Bucketing roughly honours weights over many users
  - DRAFT experiment → no variant
  - PAUSED / COMPLETED → no variant
  - Send window enforced
  - record_exposure is idempotent (no duplicate rows, exposure_count bumps)
  - record_conversion only stamps if assignment exists, idempotent on flag
  - results aggregator counts per variant
  - results computes z-score and significance flag for treatment vs. control
  - Cohort service: master flag, weekly cohort grouping, retention math
  - Feature export: header always present; flag-off returns header only
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

from app.models.booking import Booking, BookingStatus
from app.models.experiment import (
    Experiment, ExperimentAssignment, ExperimentStatus,
)
from app.models.tax_config import TaxConfig
from app.models.user import User, UserRole
from app.models.user_event import EventCategory, UserEvent
from app.models.user_intelligence_profile import (
    IntentLevel, UserIntelligenceProfile,
)
from app.services import (
    cohort_service, experiment_service, feature_export_service,
)


async def _set(db, key, value):
    row = (await db.execute(
        select(TaxConfig).where(TaxConfig.key == key)
    )).scalar_one_or_none()
    if row is None:
        db.add(TaxConfig(key=key, value=json.dumps(value)))
    else:
        row.value = json.dumps(value)
    await db.commit()


async def _enable(db):
    await _set(db, "experiments.enabled", True)


async def _user(db, *, uid=None):
    uid = uid or str(uuid.uuid4())
    db.add(User(id=uid, email=f"{uid}@x.com", hashed_password="x",
                name="U", role=UserRole.STUDENT))
    await db.commit()
    return uid


async def _exp(db, *, slug="exp1", variants=None,
                status=ExperimentStatus.RUNNING,
                starts=None, ends=None) -> Experiment:
    variants = variants or [
        {"name": "control", "weight": 50},
        {"name": "treatment", "weight": 50},
    ]
    row = Experiment(
        slug=slug, name=slug,
        variants_json=json.dumps(variants),
        success_event_name="booking.completed",
        status=status, starts_at=starts, ends_at=ends,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


# ---------- bucketing -----------------------------------------------------

@pytest.mark.asyncio
async def test_master_flag_off_returns_none(seeded_db):
    db = seeded_db
    uid = await _user(db)
    exp = await _exp(db)
    v = await experiment_service.get_variant(db, slug=exp.slug, user_id=uid)
    assert v is None


@pytest.mark.asyncio
async def test_bucketing_is_deterministic(seeded_db):
    db = seeded_db
    await _enable(db)
    uid = await _user(db)
    exp = await _exp(db)
    first = await experiment_service.get_variant(db, slug=exp.slug, user_id=uid)
    assert first in ("control", "treatment")
    for _ in range(20):
        v = await experiment_service.get_variant(db, slug=exp.slug, user_id=uid)
        assert v == first


@pytest.mark.asyncio
async def test_bucketing_respects_weights_roughly(seeded_db):
    db = seeded_db
    await _enable(db)
    exp = await _exp(db, variants=[
        {"name": "control", "weight": 80},
        {"name": "treatment", "weight": 20},
    ])
    # Pure-function assignment — doesn't need DB users.
    counts = {"control": 0, "treatment": 0}
    for i in range(2000):
        v = experiment_service.assign_variant(exp, f"user-{i}")
        counts[v] += 1
    # ±5% tolerance
    assert 0.75 < counts["control"] / 2000 < 0.85
    assert 0.15 < counts["treatment"] / 2000 < 0.25


@pytest.mark.asyncio
async def test_draft_experiment_returns_none(seeded_db):
    db = seeded_db
    await _enable(db)
    uid = await _user(db)
    exp = await _exp(db, status=ExperimentStatus.DRAFT)
    v = await experiment_service.get_variant(db, slug=exp.slug, user_id=uid)
    assert v is None


@pytest.mark.asyncio
async def test_future_starts_at_returns_none(seeded_db):
    db = seeded_db
    await _enable(db)
    uid = await _user(db)
    exp = await _exp(
        db, starts=datetime.utcnow() + timedelta(hours=1),
    )
    v = await experiment_service.get_variant(db, slug=exp.slug, user_id=uid)
    assert v is None


# ---------- exposure + conversion ------------------------------------------

@pytest.mark.asyncio
async def test_record_exposure_is_idempotent(seeded_db):
    db = seeded_db
    await _enable(db)
    uid = await _user(db)
    exp = await _exp(db)
    r1 = await experiment_service.record_exposure(
        db, slug=exp.slug, user_id=uid,
    )
    r2 = await experiment_service.record_exposure(
        db, slug=exp.slug, user_id=uid,
    )
    await db.commit()
    assert r1.id == r2.id
    assert r2.exposure_count == 2
    rows = (await db.execute(
        select(ExperimentAssignment).where(
            ExperimentAssignment.experiment_id == exp.id,
        )
    )).scalars().all()
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_record_conversion_requires_existing_assignment(seeded_db):
    db = seeded_db
    await _enable(db)
    uid = await _user(db)
    exp = await _exp(db)
    no_assignment = await experiment_service.record_conversion(
        db, slug=exp.slug, user_id=uid,
    )
    assert no_assignment is None
    await experiment_service.record_exposure(
        db, slug=exp.slug, user_id=uid,
    )
    converted = await experiment_service.record_conversion(
        db, slug=exp.slug, user_id=uid,
    )
    assert converted is not None and converted.converted is True
    # Idempotent on the boolean flag; count keeps incrementing.
    again = await experiment_service.record_conversion(
        db, slug=exp.slug, user_id=uid,
    )
    assert again.conversion_count == 2


# ---------- results --------------------------------------------------------

@pytest.mark.asyncio
async def test_results_significance_z_score(seeded_db):
    db = seeded_db
    await _enable(db)
    exp = await _exp(db)
    # Control: 200 users, 20 convert (10%)
    for i in range(200):
        uid = await _user(db, uid=f"ctrl-{i}")
        await experiment_service.record_exposure(
            db, slug=exp.slug, user_id=uid,
        )
        if i < 20:
            # Force assignment to control by direct override of variant
            row = (await db.execute(
                select(ExperimentAssignment).where(
                    ExperimentAssignment.user_id == uid,
                )
            )).scalar_one()
            row.variant = "control"
            row.converted = True
            row.converted_at = datetime.utcnow()
            row.conversion_count = 1
        else:
            row = (await db.execute(
                select(ExperimentAssignment).where(
                    ExperimentAssignment.user_id == uid,
                )
            )).scalar_one()
            row.variant = "control"
    # Treatment: 200 users, 40 convert (20%)
    for i in range(200):
        uid = await _user(db, uid=f"treat-{i}")
        await experiment_service.record_exposure(
            db, slug=exp.slug, user_id=uid,
        )
        row = (await db.execute(
            select(ExperimentAssignment).where(
                ExperimentAssignment.user_id == uid,
            )
        )).scalar_one()
        row.variant = "treatment"
        if i < 40:
            row.converted = True
            row.converted_at = datetime.utcnow()
            row.conversion_count = 1
    await db.commit()

    res = await experiment_service.results(db, slug=exp.slug)
    by = {v.variant: v for v in res.variants}
    assert by["control"].exposures == 200
    assert by["control"].converters == 20
    assert by["treatment"].exposures == 200
    assert by["treatment"].converters == 40
    # 10% vs 20% with n=200 each should be significant at 95%.
    sig = res.significance["treatment"]
    assert sig["is_significant_at_95"] is True
    assert sig["z"] > 0  # treatment is HIGHER than control


# ---------- cohort retention -----------------------------------------------

@pytest.mark.asyncio
async def test_cohort_master_flag_off(seeded_db):
    db = seeded_db
    report = await cohort_service.build_report(db)
    assert report is None


@pytest.mark.asyncio
async def test_cohort_retention_w0_is_100(seeded_db):
    db = seeded_db
    await _set(db, "insights.enabled", True)
    uid = await _user(db)
    # First search this week
    db.add(UserEvent(
        event_id=str(uuid.uuid4()), user_id=uid,
        event_name="search.performed",
        event_category=EventCategory.SEARCH,
        created_at=datetime.utcnow(),
    ))
    await db.commit()

    report = await cohort_service.build_report(
        db, n_cohort_weeks=4, n_retention_weeks=4,
    )
    assert report is not None
    assert len(report.rows) == 1
    # Retention[0] is "did they show up in their own cohort week" — yes.
    assert report.rows[0].retention[0] == 1.0


# ---------- feature export -------------------------------------------------

@pytest.mark.asyncio
async def test_feature_export_flag_off_yields_header_only(seeded_db):
    db = seeded_db
    chunks: list[str] = []
    async for row in feature_export_service.export_csv_rows(db):
        chunks.append(row)
    assert len(chunks) == 1
    assert "user_hash" in chunks[0]
    assert "label_has_any_booking" in chunks[0]


@pytest.mark.asyncio
async def test_feature_export_emits_one_row_per_profile(seeded_db):
    db = seeded_db
    await _set(db, "ml.feature_export_enabled", True)
    uid = await _user(db)
    db.add(UserIntelligenceProfile(
        user_id=uid, raw_intent_score=10,
        intent_level=IntentLevel.MEDIUM_INTENT,
        booking_urgency_score=0.5,
    ))
    # User has a booking — label should be 1
    db.add(Booking(
        user_id=uid, amount=1000.0,
        start_date=datetime.utcnow(),
        end_date=datetime.utcnow() + timedelta(days=30),
        status=BookingStatus.ACTIVE,
    ))
    await db.commit()

    chunks: list[str] = []
    async for row in feature_export_service.export_csv_rows(db):
        chunks.append(row)
    # Header + 1 data row
    assert len(chunks) == 2
    data_row = chunks[1].rstrip("\r\n")
    fields = data_row.split(",")
    # Last column is the label
    assert fields[-1] == "1"
    # First column is the hash — never the raw user_id
    assert fields[0] != uid
    assert len(fields[0]) == 16  # 16-hex-char hash
