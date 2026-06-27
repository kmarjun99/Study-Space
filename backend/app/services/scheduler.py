"""APScheduler glue. Started from main.py at app startup.

Defines four jobs:
  - expire_held_bookings    : every 60s — releases cabin holds past expiry
  - generate_maintenance_charges : daily 02:00 IST — issues monthly fees
  - maintenance_dunning     : daily 09:00 IST — applies dunning matrix
  - ledger_integrity_check  : daily 04:00 IST — asserts ledger balances
  - cabin_renewal_reminders : daily 08:30 IST — renewal reminders + expiry aging

All jobs are best-effort and never raise — failures are logged.
"""
from __future__ import annotations

import logging
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import select, update

from app.database import AsyncSessionLocal
from app.models.booking import Booking, BookingStatus
from app.models.owner_charge import OwnerCharge, OwnerChargeStatus
from app.models.reading_room import Cabin, CabinStatus
from app.services.ledger_service import LedgerService
from app.services.owner_billing_service import (
    dunning_step,
    generate_maintenance_charges_for_today,
)
from app.services.settlement_service import run_settlements
from app.services.profile_intelligence_service import rebuild_all_active_profiles
from app.services.segment_service import recompute_all_active_segments
from app.services.notification_automation_service import evaluate_all_active_rules
from app.services.notification_dispatcher_service import dispatch_pending
from app.services.renewal_service import process_renewal_reminders_once
from app.services.tax_engine import cfg_get, load_active_config


_log = logging.getLogger("studyspace.scheduler")
_scheduler: AsyncIOScheduler | None = None


# ---------- jobs ------------------------------------------------------------

async def expire_held_bookings_once(db) -> dict:
    """Release cabin holds whose hold_expires_at is in the past.

    Extracted from the scheduler entry-point so it can be unit-tested. Returns
    a summary `{released_holds, expired_bookings}`. The caller owns the
    transaction (commit/rollback).

    Safe by construction:
      - Only touches Cabin rows where `held_by_user_id IS NOT NULL`
        AND `hold_expires_at < now()`. Paid / OCCUPIED cabins are never touched.
      - Only marks Booking rows as EXPIRED where status=HELD and expires_at<now.
        ACTIVE bookings are never affected.
    """
    now_iso = datetime.utcnow().isoformat()
    rows = (await db.execute(
        select(Cabin).where(
            (Cabin.held_by_user_id.isnot(None))
            & (Cabin.hold_expires_at < now_iso)
        )
    )).scalars().all()
    for cabin in rows:
        cabin.held_by_user_id = None
        cabin.hold_expires_at = None
        # Only flip RESERVED → AVAILABLE; never touch OCCUPIED / MAINTENANCE.
        if cabin.status == CabinStatus.RESERVED:
            cabin.status = CabinStatus.AVAILABLE

    result = await db.execute(
        update(Booking)
        .where(
            (Booking.status == BookingStatus.HELD)
            & (Booking.expires_at.isnot(None))
            & (Booking.expires_at < datetime.utcnow())
        )
        .values(status=BookingStatus.EXPIRED)
    )
    return {
        "released_holds": len(rows),
        "expired_bookings": getattr(result, "rowcount", 0) or 0,
    }


async def job_expire_held_bookings() -> None:
    """Scheduler entry-point — thin wrapper over the testable function."""
    try:
        async with AsyncSessionLocal() as db:
            summary = await expire_held_bookings_once(db)
            await db.commit()
            if summary["released_holds"]:
                _log.info("expire_held_bookings: %s", summary)
    except Exception as exc:
        _log.warning("expire_held_bookings failed: %s", exc)


async def job_generate_maintenance_charges() -> None:
    try:
        async with AsyncSessionLocal() as db:
            summary = await generate_maintenance_charges_for_today(db)
            _log.info("generate_maintenance_charges: %s", summary)
    except Exception as exc:
        _log.warning("generate_maintenance_charges failed: %s", exc)


async def job_maintenance_dunning() -> None:
    try:
        async with AsyncSessionLocal() as db:
            charges = (await db.execute(
                select(OwnerCharge.id).where(
                    OwnerCharge.status.in_([
                        OwnerChargeStatus.DUE,
                        OwnerChargeStatus.OVERDUE,
                    ])
                )
            )).scalars().all()
            applied = 0
            for cid in charges:
                status = await dunning_step(db, charge_id=cid)
                if status not in ("skip", "not-yet-due", "skip-no-listing", "skip-no-due-date"):
                    applied += 1
            await db.commit()
            _log.info("maintenance_dunning: applied=%d total=%d", applied, len(charges))
    except Exception as exc:
        _log.warning("maintenance_dunning failed: %s", exc)


async def job_rebuild_intelligence_profiles() -> None:
    """Daily — rebuild profile rows for users active in the last 24 hours.

    Gated by `intelligence.profile_aggregation_enabled`. When OFF, the
    service returns a skip summary without touching the DB.
    """
    try:
        async with AsyncSessionLocal() as db:
            summary = await rebuild_all_active_profiles(db, since_days=1)
            _log.info("rebuild_intelligence_profiles: %s", summary)
    except Exception as exc:
        _log.warning("rebuild_intelligence_profiles failed: %s", exc)


async def job_recompute_segments() -> None:
    """Daily — re-evaluate every active segment against current profiles.

    Gated by `segments.enabled`. Runs after profile rebuild so memberships
    reflect the latest derived state.
    """
    try:
        async with AsyncSessionLocal() as db:
            summary = await recompute_all_active_segments(db)
            _log.info(
                "recompute_segments: evaluated=%d entered=%d exited=%d skipped=%s",
                summary.segments_evaluated,
                summary.memberships_entered,
                summary.memberships_exited,
                summary.skipped,
            )
    except Exception as exc:
        _log.warning("recompute_segments failed: %s", exc)


async def job_settlement_run() -> None:
    try:
        async with AsyncSessionLocal() as db:
            summary = await run_settlements(db)
            _log.info("settlement_run: %s", summary)
    except Exception as exc:
        _log.warning("settlement_run failed: %s", exc)


async def job_notification_automation_tick() -> None:
    """Phase 4C — every 30 min: evaluate all active rules, then dispatch
    pending deliveries. Both halves are gated by
    `notification_automation.enabled` inside the service, so this is a
    no-op until super-admin flips the flag."""
    try:
        async with AsyncSessionLocal() as db:
            config = await load_active_config(db)
            batch_size = int(cfg_get(config, "notification_automation.dispatch_batch_size", 200))
            evals = await evaluate_all_active_rules(db)
            await db.commit()
            dispatched = await dispatch_pending(db, limit=batch_size)
            await db.commit()
            _log.info(
                "notification_automation: evaluated %d rules, dispatched=%d, failed=%d",
                len(evals), dispatched.delivered, dispatched.failed,
            )
    except Exception as exc:
        _log.warning("notification_automation_tick failed: %s", exc)


async def job_cabin_renewal_reminders() -> None:
    try:
        async with AsyncSessionLocal() as db:
            summary = await process_renewal_reminders_once(db)
            await db.commit()
            _log.info("cabin_renewal_reminders: %s", summary)
    except Exception as exc:
        _log.warning("cabin_renewal_reminders failed: %s", exc)


async def job_ledger_integrity_check() -> None:
    try:
        async with AsyncSessionLocal() as db:
            bad = await LedgerService.integrity_check(db)
            if bad:
                _log.error("LEDGER IMBALANCE in %d groups: %s", len(bad), bad[:10])
            else:
                _log.info("ledger_integrity_check: OK")
    except Exception as exc:
        _log.warning("ledger_integrity_check failed: %s", exc)


# ---------- lifecycle -------------------------------------------------------

def start_scheduler() -> AsyncIOScheduler:
    """Idempotent: returns the existing scheduler if already started."""
    global _scheduler
    if _scheduler is not None:
        return _scheduler

    sched = AsyncIOScheduler(timezone="Asia/Kolkata")

    sched.add_job(
        job_expire_held_bookings,
        IntervalTrigger(seconds=60),
        id="expire_held_bookings",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
    )
    sched.add_job(
        job_generate_maintenance_charges,
        CronTrigger(hour=2, minute=0),
        id="generate_maintenance_charges",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
    )
    sched.add_job(
        job_maintenance_dunning,
        CronTrigger(hour=9, minute=0),
        id="maintenance_dunning",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
    )
    sched.add_job(
        job_settlement_run,
        CronTrigger(hour=3, minute=0),
        id="settlement_run",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
    )
    sched.add_job(
        job_ledger_integrity_check,
        CronTrigger(hour=4, minute=0),
        id="ledger_integrity_check",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
    )
    # Intelligence layer — daily refresh of derived user profiles
    sched.add_job(
        job_rebuild_intelligence_profiles,
        CronTrigger(hour=5, minute=0),
        id="rebuild_intelligence_profiles",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
    )
    # Intelligence layer — segment recompute (runs AFTER profile rebuild)
    sched.add_job(
        job_recompute_segments,
        CronTrigger(hour=5, minute=30),
        id="recompute_segments",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
    )
    # Intelligence layer — notification automation (Phase 4C). Cheap query
    # cadence; both halves no-op until `notification_automation.enabled=True`.
    sched.add_job(
        job_notification_automation_tick,
        IntervalTrigger(minutes=30),
        id="notification_automation_tick",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
    )
    sched.add_job(
        job_cabin_renewal_reminders,
        CronTrigger(hour=8, minute=30),
        id="cabin_renewal_reminders",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
    )

    sched.start()
    _scheduler = sched
    _log.info("APScheduler started with %d jobs", len(sched.get_jobs()))
    return sched


def shutdown_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None


def get_job_info(job_id: str) -> dict:
    """Introspect a registered job for the admin health dashboard.

    Returns `{running, registered, next_run_time, trigger}`. Safe to call even
    if the scheduler never started (returns running=False). `next_run_time` is
    an ISO string or None.
    """
    if _scheduler is None:
        return {
            "running": False,
            "registered": False,
            "next_run_time": None,
            "trigger": None,
        }
    job = _scheduler.get_job(job_id)
    if job is None:
        return {
            "running": bool(getattr(_scheduler, "running", False)),
            "registered": False,
            "next_run_time": None,
            "trigger": None,
        }
    next_run = getattr(job, "next_run_time", None)
    return {
        "running": bool(getattr(_scheduler, "running", False)),
        "registered": True,
        "next_run_time": next_run.isoformat() if next_run else None,
        "trigger": str(job.trigger),
    }
