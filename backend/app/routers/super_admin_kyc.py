"""Super-admin KYC review endpoints for property owners.

The User columns already exist (`kyc_status`, `pan`, `gstin`, bank fields,
`kyc_reviewed_by`, `kyc_reviewed_at`, `kyc_notes`). This router adds:

  - List owners filtered by KYC status
  - View one owner's full KYC details
  - Approve / reject / request-reupload with audit log
  - A reusable enforce_kyc_verified_for_owner helper that the listing
    activation paths call before flipping status to LIVE

Every state change writes an AuditLog row (immutable).
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_super_admin
from app.models.audit_log import AuditActionType, AuditLog
from app.models.user import KYCStatus, User, UserRole


router = APIRouter(prefix="/super-admin/owners", tags=["Super Admin: KYC"])


# ---------- response schemas ----------------------------------------------

class OwnerKYCRow(BaseModel):
    id: str
    email: str
    name: str
    legal_name: Optional[str]
    pan: Optional[str]
    gstin: Optional[str]
    gst_registration_type: Optional[str]
    business_state_code: Optional[str]
    bank_account_holder: Optional[str]
    bank_account_number_masked: Optional[str]
    bank_ifsc: Optional[str]
    kyc_status: Optional[str]
    kyc_reviewed_by: Optional[str]
    kyc_reviewed_at: Optional[str]
    kyc_notes: Optional[str]


def _mask_account(num: Optional[str]) -> Optional[str]:
    """Show only the last 4 digits — never leak full numbers via the API."""
    if not num:
        return None
    if len(num) <= 4:
        return f"****{num}"
    return f"****{num[-4:]}"


def _to_row(u: User) -> OwnerKYCRow:
    return OwnerKYCRow(
        id=u.id,
        email=u.email,
        name=u.name,
        legal_name=u.legal_name,
        pan=u.pan,
        gstin=u.gstin,
        gst_registration_type=(u.gst_registration_type.value
                               if u.gst_registration_type else None),
        business_state_code=u.business_state_code,
        bank_account_holder=u.bank_account_holder,
        bank_account_number_masked=_mask_account(u.bank_account_number),
        bank_ifsc=u.bank_ifsc,
        kyc_status=u.kyc_status.value if u.kyc_status else None,
        kyc_reviewed_by=u.kyc_reviewed_by,
        kyc_reviewed_at=u.kyc_reviewed_at.isoformat() if u.kyc_reviewed_at else None,
        kyc_notes=u.kyc_notes,
    )


# ---------- list / detail --------------------------------------------------

@router.get("/kyc", response_model=list[OwnerKYCRow])
async def list_owners_for_kyc(
    status: Optional[str] = None,
    _: User = Depends(get_current_super_admin),
    db: AsyncSession = Depends(get_db),
):
    """List owners filtered by KYC status (`PENDING` / `VERIFIED` / `REJECTED`
    / `NOT_REQUIRED`). With no filter, returns all owners."""
    stmt = select(User).where(User.role == UserRole.ADMIN)
    if status is None:
        # Default: prioritize work — anything not VERIFIED
        stmt = stmt.where(
            or_(User.kyc_status != KYCStatus.VERIFIED,
                User.kyc_status.is_(None))
        )
    else:
        try:
            target = KYCStatus(status)
        except ValueError as exc:
            raise HTTPException(status_code=400,
                                detail=f"Invalid kyc status: {status}") from exc
        stmt = stmt.where(User.kyc_status == target)
    rows = (await db.execute(stmt.order_by(User.email))).scalars().all()
    return [_to_row(u) for u in rows]


@router.get("/{owner_id}/kyc", response_model=OwnerKYCRow)
async def get_owner_kyc(
    owner_id: str,
    _: User = Depends(get_current_super_admin),
    db: AsyncSession = Depends(get_db),
):
    u = await db.get(User, owner_id)
    if u is None or u.role != UserRole.ADMIN:
        raise HTTPException(status_code=404, detail="Owner not found")
    return _to_row(u)


# ---------- review actions -------------------------------------------------

class ReviewAction(BaseModel):
    notes: Optional[str] = None


async def _apply_action(
    db: AsyncSession,
    *,
    owner_id: str,
    target: KYCStatus,
    actor: User,
    notes: Optional[str],
    action_type: AuditActionType,
    action_description: str,
) -> User:
    """Shared write path. Loads the owner, validates, mutates, audits, returns."""
    owner = await db.get(User, owner_id)
    if owner is None or owner.role != UserRole.ADMIN:
        raise HTTPException(status_code=404, detail="Owner not found")
    if owner.kyc_status == KYCStatus.VERIFIED and target == KYCStatus.VERIFIED:
        # No-op: already verified.
        return owner

    previous = owner.kyc_status.value if owner.kyc_status else "unset"
    owner.kyc_status = target
    owner.kyc_reviewed_by = actor.id
    owner.kyc_reviewed_at = datetime.utcnow()
    if notes is not None:
        owner.kyc_notes = notes

    db.add(AuditLog(
        actor_id=actor.id,
        actor_name=actor.name,
        actor_role=actor.role.value if actor.role else None,
        action_type=action_type,
        action_description=action_description,
        entity_type="user",
        entity_id=owner.id,
        entity_name=owner.legal_name or owner.name,
        extra_data=f'{{"from": "{previous}", "to": "{target.value}"}}',
    ))
    await db.commit()
    await db.refresh(owner)
    return owner


@router.post("/{owner_id}/kyc/approve", response_model=OwnerKYCRow)
async def approve_kyc(
    owner_id: str,
    body: ReviewAction,
    actor: User = Depends(get_current_super_admin),
    db: AsyncSession = Depends(get_db),
):
    owner = await _apply_action(
        db, owner_id=owner_id, target=KYCStatus.VERIFIED,
        actor=actor, notes=body.notes,
        action_type=AuditActionType.IDENTITY_VERIFIED,
        action_description="Owner KYC approved",
    )
    return _to_row(owner)


@router.post("/{owner_id}/kyc/reject", response_model=OwnerKYCRow)
async def reject_kyc(
    owner_id: str,
    body: ReviewAction,
    actor: User = Depends(get_current_super_admin),
    db: AsyncSession = Depends(get_db),
):
    if not body.notes or not body.notes.strip():
        raise HTTPException(status_code=400,
                            detail="Rejection requires a reason in `notes`.")
    owner = await _apply_action(
        db, owner_id=owner_id, target=KYCStatus.REJECTED,
        actor=actor, notes=body.notes,
        action_type=AuditActionType.IDENTITY_REJECTED,
        action_description="Owner KYC rejected",
    )
    return _to_row(owner)


@router.post("/{owner_id}/kyc/request-reupload", response_model=OwnerKYCRow)
async def request_reupload(
    owner_id: str,
    body: ReviewAction,
    actor: User = Depends(get_current_super_admin),
    db: AsyncSession = Depends(get_db),
):
    """Request re-upload — reset status to PENDING with a note explaining
    what needs to change. Equivalent to "send back for correction"."""
    if not body.notes or not body.notes.strip():
        raise HTTPException(status_code=400,
                            detail="Re-upload request requires a reason in `notes`.")
    owner = await _apply_action(
        db, owner_id=owner_id, target=KYCStatus.PENDING,
        actor=actor, notes=body.notes,
        action_type=AuditActionType.REMINDER_SENT,
        action_description="Owner asked to re-upload KYC documents",
    )
    return _to_row(owner)


# ---------- reusable helper for listing-activation paths ------------------

class KYCNotVerified(Exception):
    """Raised by `assert_owner_kyc_verified` when the owner's KYC is not VERIFIED."""


async def assert_owner_kyc_verified(db: AsyncSession, owner_id: str) -> None:
    """Raise `KYCNotVerified` unless the owner's KYC passes the gate.

    Passes: `VERIFIED` (normal) or `NOT_REQUIRED` (grandfathered legacy owners).
    Fails:  `PENDING`, `REJECTED`, or unset (None) — default-deny for unknown.

    Listing-activation endpoints call this and convert `KYCNotVerified` to
    HTTP 400.
    """
    owner = await db.get(User, owner_id)
    if owner is None:
        raise KYCNotVerified(f"Owner {owner_id} not found")
    if owner.kyc_status in (KYCStatus.VERIFIED, KYCStatus.NOT_REQUIRED):
        return
    current = owner.kyc_status.value if owner.kyc_status else "unset"
    raise KYCNotVerified(
        f"Owner KYC must be VERIFIED before listing can go LIVE "
        f"(currently {current})."
    )
