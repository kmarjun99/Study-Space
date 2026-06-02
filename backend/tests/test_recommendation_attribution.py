"""Recommendation attribution tests (Phase 4D).

Covers:
  - Master flag off → no-op
  - mark_clicked is idempotent (second call does not reset clicked_at)
  - attribute_booking prefers most-recent click
  - attribute_booking falls back to most-recent impression when no click
  - attribute_booking respects window
  - attribute_booking does not re-attribute a log row already converted
  - is_click_attributed flag is true when click-attributed, false when impression-attributed
  - Different listing_id leaves logs untouched
  - funnel aggregator counts impressions / clicks / conversions per surface
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

from app.models.recommendation_log import (
    RecommendationLog, RecommendationSurface,
)
from app.models.tax_config import TaxConfig
from app.services import recommendation_attribution_service as attribution


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
    await _set(db, "recommendations.attribution_enabled", True)


async def _log(
    db, *, user_id="u1", listing_id="L1",
    surface=RecommendationSurface.FOR_YOU,
    created_at=None, clicked_at=None,
) -> RecommendationLog:
    row = RecommendationLog(
        id=str(uuid.uuid4()),
        user_id=user_id, listing_id=listing_id,
        surface=surface, listing_type="reading_room",
        rank=1, score=10.0,
        created_at=created_at or datetime.utcnow(),
        clicked_at=clicked_at,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


# ---------- attribution gates ---------------------------------------------

@pytest.mark.asyncio
async def test_attribute_master_flag_off(seeded_db):
    db = seeded_db
    await _log(db)
    result = await attribution.attribute_booking(
        db, booking_id="B1", user_id="u1", listing_id="L1",
    )
    assert result is None


@pytest.mark.asyncio
async def test_click_stamp_is_idempotent(seeded_db):
    db = seeded_db
    log = await _log(db)
    r1 = await attribution.mark_clicked(db, log_id=log.id)
    first_ts = r1.clicked_at
    assert first_ts is not None
    # Second click shouldn't reset the timestamp
    r2 = await attribution.mark_clicked(db, log_id=log.id)
    assert r2.clicked_at == first_ts


@pytest.mark.asyncio
async def test_attribute_prefers_most_recent_click(seeded_db):
    db = seeded_db
    await _enable(db)
    older = await _log(
        db, created_at=datetime.utcnow() - timedelta(days=2),
        clicked_at=datetime.utcnow() - timedelta(days=2),
    )
    newer = await _log(
        db, created_at=datetime.utcnow() - timedelta(hours=2),
        clicked_at=datetime.utcnow() - timedelta(hours=2),
        surface=RecommendationSurface.SIMILAR,
    )
    result = await attribution.attribute_booking(
        db, booking_id="B1", user_id="u1", listing_id="L1",
    )
    assert result is not None
    assert result.id == newer.id
    assert result.is_click_attributed is True
    # The older log row should NOT be touched
    await db.refresh(older)
    assert older.converted_booking_id is None


@pytest.mark.asyncio
async def test_attribute_falls_back_to_impression(seeded_db):
    db = seeded_db
    await _enable(db)
    log = await _log(db)
    result = await attribution.attribute_booking(
        db, booking_id="B1", user_id="u1", listing_id="L1",
    )
    assert result is not None
    assert result.id == log.id
    assert result.is_click_attributed is False  # impression-attributed
    assert result.converted_booking_id == "B1"


@pytest.mark.asyncio
async def test_attribute_respects_window(seeded_db):
    db = seeded_db
    await _enable(db)
    # Window default is 7 days — log from 30 days ago should be skipped
    await _log(db, created_at=datetime.utcnow() - timedelta(days=30))
    result = await attribution.attribute_booking(
        db, booking_id="B1", user_id="u1", listing_id="L1",
    )
    assert result is None


@pytest.mark.asyncio
async def test_attribute_does_not_overwrite(seeded_db):
    db = seeded_db
    await _enable(db)
    log = await _log(db)
    r1 = await attribution.attribute_booking(
        db, booking_id="B1", user_id="u1", listing_id="L1",
    )
    assert r1 is not None and r1.id == log.id

    # Second booking — same log row should NOT be re-stamped; no other log exists
    r2 = await attribution.attribute_booking(
        db, booking_id="B2", user_id="u1", listing_id="L1",
    )
    assert r2 is None
    await db.refresh(log)
    assert log.converted_booking_id == "B1"


@pytest.mark.asyncio
async def test_attribute_only_for_matching_listing(seeded_db):
    db = seeded_db
    await _enable(db)
    log_other = await _log(db, listing_id="L_OTHER")
    result = await attribution.attribute_booking(
        db, booking_id="B1", user_id="u1", listing_id="L_TARGET",
    )
    assert result is None
    await db.refresh(log_other)
    assert log_other.converted_booking_id is None


@pytest.mark.asyncio
async def test_attribute_only_for_matching_user(seeded_db):
    db = seeded_db
    await _enable(db)
    log_other = await _log(db, user_id="u_other")
    result = await attribution.attribute_booking(
        db, booking_id="B1", user_id="u_target", listing_id="L1",
    )
    assert result is None
    await db.refresh(log_other)
    assert log_other.converted_booking_id is None


# ---------- funnel --------------------------------------------------------

@pytest.mark.asyncio
async def test_funnel_aggregates_counts_per_surface(seeded_db):
    db = seeded_db
    await _enable(db)
    # 3 impressions on FOR_YOU
    f1 = await _log(db, surface=RecommendationSurface.FOR_YOU)
    f2 = await _log(db, surface=RecommendationSurface.FOR_YOU,
                    listing_id="L2", user_id="u2")
    await _log(db, surface=RecommendationSurface.FOR_YOU,
               listing_id="L3", user_id="u3")
    # 2 impressions on SIMILAR, 1 clicked
    s1 = await _log(db, surface=RecommendationSurface.SIMILAR,
                    listing_id="L4", user_id="u4",
                    clicked_at=datetime.utcnow())
    await _log(db, surface=RecommendationSurface.SIMILAR,
               listing_id="L5", user_id="u5")

    # Convert f1 (impression-attributed) and s1 (click-attributed)
    await attribution.attribute_booking(
        db, booking_id="B1", user_id="u1", listing_id="L1",
    )
    await attribution.attribute_booking(
        db, booking_id="B2", user_id="u4", listing_id="L4",
    )

    summary = await attribution.funnel_summary(db)
    by = {s.surface: s for s in summary.surfaces}

    assert by["FOR_YOU"].impressions == 3
    assert by["FOR_YOU"].conversions == 1
    assert by["FOR_YOU"].impression_attributed_conversions == 1
    assert by["FOR_YOU"].click_attributed_conversions == 0

    assert by["SIMILAR"].impressions == 2
    assert by["SIMILAR"].clicks == 1
    assert by["SIMILAR"].conversions == 1
    assert by["SIMILAR"].click_attributed_conversions == 1

    assert summary.total_impressions == 5
    assert summary.total_clicks == 1
    assert summary.total_conversions == 2

    # Suppress unused warnings for fixtures (mypy/pyright don't see asserts)
    assert f2 is not None
    assert s1.id is not None
