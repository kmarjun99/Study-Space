"""Notification rule API (Phase 4C — automation).

Super-admin CRUD + manual evaluation/dispatch endpoints. Public engagement
marking endpoints already exist under /campaign-deliveries/{id}/{opened,
clicked,delivered} from Phase 4B — they accept rule-driven deliveries
unchanged because the delivery row is the same shape.
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_super_admin
from app.models.audit_log import AuditActionType, AuditLog
from app.models.campaign import CampaignChannel, CampaignDelivery, DeliveryStatus
from app.models.notification_rule import NotificationRule, TriggerType
from app.models.tax_config import TaxConfig
from app.models.user import User
from app.services import (
    notification_automation_service, notification_dispatcher_service,
)
from app.services.scheduler import get_job_info
from app.services.tax_engine import cfg_get, load_active_config

_AUTOMATION_FLAG = "notification_automation.enabled"
_AUTOMATION_JOB_ID = "notification_automation_tick"


router = APIRouter(
    prefix="/super-admin/notification-rules",
    tags=["Super Admin: Notification Rules"],
)


class RuleOut(BaseModel):
    id: str
    slug: str
    name: str
    description: Optional[str]
    body_template: str
    subject_template: Optional[str]
    trigger_type: str
    trigger_window_minutes: int
    min_event_count: int
    channel: str
    cooldown_hours: int
    frequency_cap_per_user: int
    frequency_cap_window_days: int
    is_active: bool
    created_at: str
    updated_at: str


def _to_rule(r: NotificationRule) -> RuleOut:
    return RuleOut(
        id=r.id, slug=r.slug, name=r.name, description=r.description,
        body_template=r.body_template, subject_template=r.subject_template,
        trigger_type=r.trigger_type.value,
        trigger_window_minutes=r.trigger_window_minutes,
        min_event_count=r.min_event_count,
        channel=r.channel.value,
        cooldown_hours=r.cooldown_hours,
        frequency_cap_per_user=r.frequency_cap_per_user,
        frequency_cap_window_days=r.frequency_cap_window_days,
        is_active=r.is_active,
        created_at=r.created_at.isoformat(),
        updated_at=r.updated_at.isoformat(),
    )


class RuleIn(BaseModel):
    slug: str
    name: str
    description: Optional[str] = None
    body_template: str
    subject_template: Optional[str] = None
    trigger_type: str
    trigger_window_minutes: int = 120
    min_event_count: int = 1
    channel: str
    cooldown_hours: int = 24
    frequency_cap_per_user: int = 3
    frequency_cap_window_days: int = 7
    is_active: bool = False


class RulePatch(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    body_template: Optional[str] = None
    subject_template: Optional[str] = None
    trigger_window_minutes: Optional[int] = None
    min_event_count: Optional[int] = None
    cooldown_hours: Optional[int] = None
    frequency_cap_per_user: Optional[int] = None
    frequency_cap_window_days: Optional[int] = None
    is_active: Optional[bool] = None


@router.get("", response_model=list[RuleOut])
async def list_all(
    include_inactive: bool = True,
    _: User = Depends(get_current_super_admin),
    db: AsyncSession = Depends(get_db),
):
    rows = await notification_automation_service.list_rules(
        db, include_inactive=include_inactive,
    )
    return [_to_rule(r) for r in rows]


@router.post("", response_model=RuleOut)
async def create_rule(
    body: RuleIn,
    actor: User = Depends(get_current_super_admin),
    db: AsyncSession = Depends(get_db),
):
    try:
        trigger = TriggerType(body.trigger_type)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"invalid trigger_type: {body.trigger_type}") from exc
    try:
        channel = CampaignChannel(body.channel)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"invalid channel: {body.channel}") from exc

    row = NotificationRule(
        slug=body.slug, name=body.name, description=body.description,
        body_template=body.body_template,
        subject_template=body.subject_template,
        trigger_type=trigger,
        trigger_window_minutes=body.trigger_window_minutes,
        min_event_count=body.min_event_count,
        channel=channel,
        cooldown_hours=body.cooldown_hours,
        frequency_cap_per_user=body.frequency_cap_per_user,
        frequency_cap_window_days=body.frequency_cap_window_days,
        is_active=body.is_active,
        created_by=actor.id,
    )
    db.add(row)
    try:
        await db.commit()
    except Exception as exc:
        await db.rollback()
        raise HTTPException(
            status_code=400, detail=f"could not create rule: {exc}",
        ) from exc
    await db.refresh(row)
    return _to_rule(row)


@router.patch("/{rule_id}", response_model=RuleOut)
async def patch_rule(
    rule_id: str,
    body: RulePatch,
    _: User = Depends(get_current_super_admin),
    db: AsyncSession = Depends(get_db),
):
    row = await db.get(NotificationRule, rule_id)
    if row is None:
        raise HTTPException(status_code=404, detail="rule not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(row, field, value)
    await db.commit()
    await db.refresh(row)
    return _to_rule(row)


@router.post("/{rule_id}/evaluate")
async def trigger_evaluate(
    rule_id: str,
    _: User = Depends(get_current_super_admin),
    db: AsyncSession = Depends(get_db),
):
    summary = await notification_automation_service.evaluate_rule(
        db, rule_id=rule_id,
    )
    await db.commit()
    return {
        "rule_id": summary.rule_id,
        "queued": summary.queued,
        "skipped_consent": summary.skipped_consent,
        "skipped_cooldown": summary.skipped_cooldown,
        "skipped_frequency": summary.skipped_frequency,
        "reasons": summary.reasons,
    }


@router.post("/dispatch-pending")
async def trigger_dispatch(
    limit: int = 100,
    _: User = Depends(get_current_super_admin),
    db: AsyncSession = Depends(get_db),
):
    """Force the dispatcher to flush QUEUED deliveries now."""
    summary = await notification_dispatcher_service.dispatch_pending(
        db, limit=limit,
    )
    await db.commit()
    return {
        "delivered": summary.delivered,
        "failed": summary.failed,
        "retried": summary.retried,
        "skipped_already_done": summary.skipped_already_done,
    }


class AutomationToggle(BaseModel):
    enabled: bool


@router.get("/automation/status")
async def automation_status(
    _: User = Depends(get_current_super_admin),
    db: AsyncSession = Depends(get_db),
):
    """End-to-end health of the notification-automation subsystem.

    Surfaces the master flag, scheduler state, rule counts and delivery
    health so super-admins can verify the pipeline without DB access. All
    counts are scoped to rule-driven deliveries (notification_rule_id set).
    """
    config = await load_active_config(db)
    enabled = bool(cfg_get(config, _AUTOMATION_FLAG, False))
    batch_size = int(cfg_get(config, "notification_automation.dispatch_batch_size", 200))

    job = get_job_info(_AUTOMATION_JOB_ID)

    total_rules = (await db.execute(
        select(func.count(NotificationRule.id))
    )).scalar_one()
    active_rules = (await db.execute(
        select(func.count(NotificationRule.id))
        .where(NotificationRule.is_active.is_(True))
    )).scalar_one()

    rule_scoped = CampaignDelivery.notification_rule_id.isnot(None)

    def _count(*conds) -> int:
        return select(func.count(CampaignDelivery.id)).where(rule_scoped, *conds)

    queued = (await db.execute(
        _count(CampaignDelivery.status == DeliveryStatus.QUEUED)
    )).scalar_one()
    failed_total = (await db.execute(
        _count(CampaignDelivery.status == DeliveryStatus.FAILED)
    )).scalar_one()

    midnight = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    delivered_today = (await db.execute(
        _count(
            CampaignDelivery.status == DeliveryStatus.DELIVERED,
            CampaignDelivery.delivered_at >= midnight,
        )
    )).scalar_one()
    delivered_total = (await db.execute(
        _count(CampaignDelivery.status == DeliveryStatus.DELIVERED)
    )).scalar_one()

    # Most recent successful dispatch = proxy for "last execution time".
    last_delivered_at = (await db.execute(
        select(func.max(CampaignDelivery.delivered_at)).where(
            rule_scoped,
            CampaignDelivery.status == DeliveryStatus.DELIVERED,
        )
    )).scalar_one()

    # Most recent failure + its reason.
    last_failure = (await db.execute(
        select(CampaignDelivery)
        .where(rule_scoped, CampaignDelivery.status == DeliveryStatus.FAILED)
        .order_by(CampaignDelivery.queued_at.desc())
        .limit(1)
    )).scalars().first()

    return {
        "enabled": enabled,
        "dispatch_batch_size": batch_size,
        "scheduler": {
            "running": job["running"],
            "job_registered": job["registered"],
            "frequency": "every 30 minutes",
            "next_run_time": job["next_run_time"],
            "trigger": job["trigger"],
        },
        "rules": {
            "total": total_rules,
            "active": active_rules,
        },
        "deliveries": {
            "queued": queued,
            "delivered_today": delivered_today,
            "delivered_total": delivered_total,
            "failed_total": failed_total,
        },
        "last_execution_time": last_delivered_at.isoformat() if last_delivered_at else None,
        "last_error": (
            {
                "reason": last_failure.reason,
                "at": last_failure.queued_at.isoformat(),
                "channel": last_failure.channel.value,
            }
            if last_failure else None
        ),
    }


@router.post("/automation/toggle")
async def automation_toggle(
    body: AutomationToggle,
    actor: User = Depends(get_current_super_admin),
    db: AsyncSession = Depends(get_db),
):
    """Enable/disable the master automation flag from the automation page.

    Writes the same `tax_config` key the Tax Config screen edits, and records
    an audit-log entry, so the control is consistent wherever it's flipped.
    """
    encoded = json.dumps(bool(body.enabled))
    row = (await db.execute(
        select(TaxConfig).where(TaxConfig.key == _AUTOMATION_FLAG)
    )).scalar_one_or_none()
    old_value = row.value if row else None

    if row is None:
        row = TaxConfig(
            key=_AUTOMATION_FLAG,
            value=encoded,
            description="Master switch for rule-based push / email notifications.",
            updated_by=actor.id,
        )
        db.add(row)
    else:
        row.value = encoded
        row.updated_by = actor.id
        row.updated_at = datetime.utcnow()

    db.add(AuditLog(
        actor_id=actor.id,
        actor_name=actor.name,
        actor_role=actor.role.value if actor.role else None,
        action_type=AuditActionType.SETTINGS_CHANGED,
        action_description=f"tax_config[{_AUTOMATION_FLAG}] set to {body.enabled}",
        entity_type="tax_config",
        entity_id=_AUTOMATION_FLAG,
        entity_name=_AUTOMATION_FLAG,
        extra_data=json.dumps({"old": old_value, "new": encoded}),
    ))
    await db.commit()
    return {"enabled": bool(body.enabled)}


@router.get("/{rule_id}/deliveries")
async def list_rule_deliveries(
    rule_id: str,
    status: Optional[str] = None,
    limit: int = 200,
    offset: int = 0,
    _: User = Depends(get_current_super_admin),
    db: AsyncSession = Depends(get_db),
):
    target: Optional[DeliveryStatus] = None
    if status:
        try:
            target = DeliveryStatus(status)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=f"invalid status: {status}") from exc
    rows = await notification_automation_service.list_rule_deliveries(
        db, rule_id=rule_id, status=target, limit=limit, offset=offset,
    )
    return [
        {
            "id": d.id,
            "rule_id": d.notification_rule_id,
            "user_id": d.user_id,
            "channel": d.channel.value,
            "status": d.status.value,
            "queued_at": d.queued_at.isoformat(),
            "delivered_at": d.delivered_at.isoformat() if d.delivered_at else None,
            "opened_at": d.opened_at.isoformat() if d.opened_at else None,
            "clicked_at": d.clicked_at.isoformat() if d.clicked_at else None,
            "reason": d.reason,
        }
        for d in rows
    ]
