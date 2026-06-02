"""Super-admin CRUD for `tax_config`.

Reads are open to all admins; writes are super-admin only. Every write is
audited via the existing AuditLog table.
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_admin, get_current_super_admin
from app.models.audit_log import AuditActionType, AuditLog
from app.models.tax_config import TaxConfig
from app.models.user import User


router = APIRouter(prefix="/admin/tax-config", tags=["Admin: Tax Config"])


class TaxConfigOut(BaseModel):
    key: str
    value: Any
    description: str | None
    updated_by: str | None
    updated_at: str | None


class TaxConfigUpdate(BaseModel):
    value: Any
    description: str | None = None


@router.get("", response_model=list[TaxConfigOut])
async def list_keys(
    _: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    rows = (await db.execute(select(TaxConfig).order_by(TaxConfig.key))).scalars().all()
    out: list[TaxConfigOut] = []
    for row in rows:
        try:
            parsed = json.loads(row.value)
        except json.JSONDecodeError:
            parsed = row.value
        out.append(TaxConfigOut(
            key=row.key,
            value=parsed,
            description=row.description,
            updated_by=row.updated_by,
            updated_at=row.updated_at.isoformat() if row.updated_at else None,
        ))
    return out


@router.put("/{key}", response_model=TaxConfigOut)
async def upsert_key(
    key: str,
    body: TaxConfigUpdate,
    current_user: User = Depends(get_current_super_admin),
    db: AsyncSession = Depends(get_db),
):
    """Upsert a config key. Value is stored as JSON-encoded text."""
    encoded = json.dumps(body.value)

    row = (await db.execute(
        select(TaxConfig).where(TaxConfig.key == key)
    )).scalar_one_or_none()

    old_value = row.value if row else None

    if row is None:
        row = TaxConfig(
            key=key,
            value=encoded,
            description=body.description,
            updated_by=current_user.id,
        )
        db.add(row)
    else:
        row.value = encoded
        if body.description is not None:
            row.description = body.description
        row.updated_by = current_user.id
        row.updated_at = datetime.utcnow()

    # Audit
    db.add(AuditLog(
        actor_id=current_user.id,
        actor_name=current_user.name,
        actor_role=current_user.role.value if current_user.role else None,
        action_type=AuditActionType.SETTINGS_CHANGED,
        action_description=f"tax_config[{key}] changed",
        entity_type="tax_config",
        entity_id=key,
        entity_name=key,
        extra_data=json.dumps({"old": old_value, "new": encoded}),
    ))
    await db.commit()
    await db.refresh(row)

    try:
        parsed = json.loads(row.value)
    except json.JSONDecodeError:
        parsed = row.value
    return TaxConfigOut(
        key=row.key,
        value=parsed,
        description=row.description,
        updated_by=row.updated_by,
        updated_at=row.updated_at.isoformat(),
    )
