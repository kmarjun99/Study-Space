"""Owner self-service KYC submission.

The super-admin side (super_admin_kyc.py) could already list / approve /
reject owner KYC — but there was NO way for an owner to actually SUBMIT
their KYC details in the first place. The User columns (legal_name, pan,
gstin, bank_*, kyc_status) existed but nothing populated them, so the
super-admin review queue was permanently empty and listings could never
pass the `assert_owner_kyc_verified` gate.

This router closes that gap:

  GET  /owner/kyc  — the current owner's own KYC record (full bank
                     account number is NEVER returned; masked to last 4)
  PUT  /owner/kyc  — submit / update KYC. Sets kyc_status = PENDING so
                     the super-admin review queue picks it up. Blocks
                     edits while already VERIFIED (owner must contact
                     support to change verified details — prevents an
                     owner swapping bank details post-verification).

Validation is intentionally light-but-real: PAN and GSTIN format checks,
IFSC format, 2-letter state code. We don't call external verification
APIs here — that's the super-admin reviewer's job.
"""
from __future__ import annotations

import re
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_admin
from app.models.audit_log import AuditActionType, AuditLog
from app.models.user import GSTRegistrationType, KYCStatus, User


router = APIRouter(prefix="/owner/kyc", tags=["Owner KYC"])


# Indian format regexes. Deliberately permissive on case (we upper() before
# storing) but strict on shape so obviously-wrong values are rejected at
# submit time rather than surfacing as a reviewer rejection days later.
_PAN_RE = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")
_GSTIN_RE = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][0-9A-Z][Z][0-9A-Z]$")
_IFSC_RE = re.compile(r"^[A-Z]{4}0[A-Z0-9]{6}$")
_STATE_RE = re.compile(r"^[A-Z]{2}$")


class OwnerKYCOut(BaseModel):
    legal_name: Optional[str]
    pan: Optional[str]
    gstin: Optional[str]
    gst_registration_type: Optional[str]
    business_state_code: Optional[str]
    bank_account_holder: Optional[str]
    bank_account_number_masked: Optional[str]
    bank_ifsc: Optional[str]
    kyc_status: Optional[str]
    kyc_notes: Optional[str]          # reviewer feedback (rejection reason etc.)
    kyc_reviewed_at: Optional[str]


class OwnerKYCSubmit(BaseModel):
    legal_name: str
    gst_registration_type: str        # REGULAR | COMPOSITION | UNREGISTERED
    business_state_code: str          # 2-letter, e.g. KA
    pan: Optional[str] = None         # required unless UNREGISTERED? PAN always wise
    gstin: Optional[str] = None       # required when REGULAR/COMPOSITION
    bank_account_holder: str
    bank_account_number: str
    bank_ifsc: str

    @field_validator("pan")
    @classmethod
    def _pan(cls, v):
        if v is None or v == "":
            return None
        v = v.strip().upper()
        if not _PAN_RE.match(v):
            raise ValueError("PAN must look like ABCDE1234F")
        return v

    @field_validator("gstin")
    @classmethod
    def _gstin(cls, v):
        if v is None or v == "":
            return None
        v = v.strip().upper()
        if not _GSTIN_RE.match(v):
            raise ValueError("GSTIN must be a valid 15-character GSTIN")
        return v

    @field_validator("business_state_code")
    @classmethod
    def _state(cls, v):
        v = (v or "").strip().upper()
        if not _STATE_RE.match(v):
            raise ValueError("Business state must be a 2-letter code, e.g. KA")
        return v

    @field_validator("bank_ifsc")
    @classmethod
    def _ifsc(cls, v):
        v = (v or "").strip().upper()
        if not _IFSC_RE.match(v):
            raise ValueError("IFSC must look like HDFC0001234")
        return v

    @field_validator("gst_registration_type")
    @classmethod
    def _reg_type(cls, v):
        v = (v or "").strip().upper()
        valid = {e.value for e in GSTRegistrationType}
        if v not in valid:
            raise ValueError(f"gst_registration_type must be one of {sorted(valid)}")
        return v


def _mask_account(num: Optional[str]) -> Optional[str]:
    if not num:
        return None
    return f"****{num[-4:]}" if len(num) > 4 else f"****{num}"


def _to_out(u: User) -> OwnerKYCOut:
    return OwnerKYCOut(
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
        kyc_notes=u.kyc_notes,
        kyc_reviewed_at=u.kyc_reviewed_at.isoformat() if u.kyc_reviewed_at else None,
    )


@router.get("", response_model=OwnerKYCOut)
async def get_my_kyc(
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Return the current owner's KYC record (bank number masked)."""
    return _to_out(current_user)


@router.put("", response_model=OwnerKYCOut)
async def submit_my_kyc(
    body: OwnerKYCSubmit,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Submit / update KYC. Moves the owner to PENDING for super-admin review.

    Refuses to overwrite an already-VERIFIED record — a verified owner
    changing their bank account or GSTIN must go through support so the
    change is re-reviewed rather than silently trusted.
    """
    if current_user.kyc_status == KYCStatus.VERIFIED:
        raise HTTPException(
            status_code=409,
            detail="KYC is already verified. Contact support to change "
                   "verified details.",
        )

    # Business rule: registered owners (REGULAR/COMPOSITION) must supply a
    # GSTIN; unregistered owners may omit it. PAN is required for everyone
    # because payouts + TDS need it.
    reg_type = body.gst_registration_type
    if reg_type in ("REGULAR", "COMPOSITION") and not body.gstin:
        raise HTTPException(
            status_code=422,
            detail="GSTIN is required for REGULAR / COMPOSITION registration.",
        )
    if not body.pan:
        raise HTTPException(
            status_code=422,
            detail="PAN is required for payouts and TDS compliance.",
        )

    prev_status = current_user.kyc_status.value if current_user.kyc_status else None

    current_user.legal_name = body.legal_name.strip()
    current_user.pan = body.pan
    current_user.gstin = body.gstin
    current_user.gst_registration_type = GSTRegistrationType(reg_type)
    current_user.business_state_code = body.business_state_code
    current_user.bank_account_holder = body.bank_account_holder.strip()
    current_user.bank_account_number = body.bank_account_number.strip()
    current_user.bank_ifsc = body.bank_ifsc
    # Re-submission resets the review state: clear stale reviewer fields and
    # move back into the PENDING queue.
    current_user.kyc_status = KYCStatus.PENDING
    current_user.kyc_reviewed_by = None
    current_user.kyc_reviewed_at = None
    current_user.kyc_notes = None

    db.add(AuditLog(
        actor_id=current_user.id,
        actor_name=current_user.name,
        actor_role=current_user.role.value if current_user.role else None,
        action_type=AuditActionType.OWNER_RESUBMITTED,
        action_description=(
            f"Owner submitted KYC for review "
            f"(was {prev_status or 'unset'} → PENDING)"
        ),
        entity_type="user_kyc",
        entity_id=current_user.id,
        entity_name=current_user.legal_name or current_user.name,
    ))

    await db.commit()
    await db.refresh(current_user)
    return _to_out(current_user)
