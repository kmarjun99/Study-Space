"""KYC review router tests.

Hits the router functions directly. Covers:
  - Default list excludes already-VERIFIED owners
  - Approve / reject / request-reupload mutate status + write audit log
  - Reject requires a `notes` reason
  - Bank-account number is masked in the response
  - `assert_owner_kyc_verified` raises for PENDING / REJECTED / unset
  - VERIFIED + NOT_REQUIRED both pass the gate
"""
from __future__ import annotations

import pytest
from sqlalchemy import select

from app.models.audit_log import AuditActionType, AuditLog
from app.models.user import KYCStatus, User, UserRole
from app.routers.super_admin_kyc import (
    KYCNotVerified,
    ReviewAction,
    approve_kyc,
    assert_owner_kyc_verified,
    get_owner_kyc,
    list_owners_for_kyc,
    reject_kyc,
    request_reupload,
)


async def _owner(db, *, uid="ok-1", status=None) -> User:
    o = User(
        id=uid, email=f"{uid}@x.com", hashed_password="x", name="Owner",
        role=UserRole.ADMIN,
        legal_name="Owner Pvt Ltd",
        pan="AAAPL1234A", gstin="29ZZZZZ1234Z1Z5",
        business_state_code="KA",
        bank_account_holder="Owner Pvt Ltd",
        bank_account_number="50101234567890",
        bank_ifsc="HDFC0001234",
        kyc_status=status,
    )
    db.add(o)
    await db.commit()
    return o


async def _super(db) -> User:
    s = User(
        id="sa-1", email="sa@x.com", hashed_password="x", name="Super",
        role=UserRole.SUPER_ADMIN,
    )
    db.add(s)
    await db.commit()
    return s


# ---------- list / mask ---------------------------------------------------

@pytest.mark.asyncio
async def test_default_list_excludes_verified(seeded_db):
    sa = await _super(seeded_db)
    await _owner(seeded_db, uid="ok-pending", status=KYCStatus.PENDING)
    await _owner(seeded_db, uid="ok-verified", status=KYCStatus.VERIFIED)

    rows = await list_owners_for_kyc(_=sa, db=seeded_db)
    ids = {r.id for r in rows}
    assert "ok-pending" in ids
    assert "ok-verified" not in ids


@pytest.mark.asyncio
async def test_filtered_list_returns_only_status(seeded_db):
    sa = await _super(seeded_db)
    await _owner(seeded_db, uid="ok-v", status=KYCStatus.VERIFIED)
    await _owner(seeded_db, uid="ok-p", status=KYCStatus.PENDING)

    rows = await list_owners_for_kyc(status="VERIFIED", _=sa, db=seeded_db)
    assert [r.id for r in rows] == ["ok-v"]


@pytest.mark.asyncio
async def test_bank_account_masked(seeded_db):
    sa = await _super(seeded_db)
    o = await _owner(seeded_db, status=KYCStatus.PENDING)
    row = await get_owner_kyc(owner_id=o.id, _=sa, db=seeded_db)
    assert row.bank_account_number_masked == "****7890"
    # Full number must not leak via any field
    assert "50101234567890" not in (row.bank_account_number_masked or "")


@pytest.mark.asyncio
async def test_get_404_for_non_owner(seeded_db):
    """Asking for a student's KYC must 404, not leak their data."""
    from fastapi import HTTPException
    sa = await _super(seeded_db)
    student = User(id="stu", email="stu@x.com", hashed_password="x",
                   name="Stu", role=UserRole.STUDENT)
    seeded_db.add(student)
    await seeded_db.commit()
    with pytest.raises(HTTPException) as exc:
        await get_owner_kyc(owner_id="stu", _=sa, db=seeded_db)
    assert exc.value.status_code == 404


# ---------- review actions ------------------------------------------------

@pytest.mark.asyncio
async def test_approve_writes_audit_and_verifies(seeded_db):
    sa = await _super(seeded_db)
    o = await _owner(seeded_db, status=KYCStatus.PENDING)
    out = await approve_kyc(
        owner_id=o.id, body=ReviewAction(notes="Docs valid"),
        actor=sa, db=seeded_db,
    )
    assert out.kyc_status == "VERIFIED"
    assert out.kyc_reviewed_by == sa.id

    audits = (await seeded_db.execute(
        select(AuditLog).where(AuditLog.entity_id == o.id)
    )).scalars().all()
    assert any(a.action_type == AuditActionType.IDENTITY_VERIFIED for a in audits)


@pytest.mark.asyncio
async def test_reject_requires_reason(seeded_db):
    from fastapi import HTTPException
    sa = await _super(seeded_db)
    o = await _owner(seeded_db, status=KYCStatus.PENDING)
    with pytest.raises(HTTPException) as exc:
        await reject_kyc(
            owner_id=o.id, body=ReviewAction(notes=None),
            actor=sa, db=seeded_db,
        )
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_reject_records_status_and_notes(seeded_db):
    sa = await _super(seeded_db)
    o = await _owner(seeded_db, status=KYCStatus.PENDING)
    out = await reject_kyc(
        owner_id=o.id, body=ReviewAction(notes="GSTIN invalid"),
        actor=sa, db=seeded_db,
    )
    assert out.kyc_status == "REJECTED"
    assert out.kyc_notes == "GSTIN invalid"


@pytest.mark.asyncio
async def test_request_reupload_resets_to_pending(seeded_db):
    sa = await _super(seeded_db)
    o = await _owner(seeded_db, status=KYCStatus.REJECTED)
    out = await request_reupload(
        owner_id=o.id, body=ReviewAction(notes="Send clearer PAN scan"),
        actor=sa, db=seeded_db,
    )
    assert out.kyc_status == "PENDING"


@pytest.mark.asyncio
async def test_approve_is_idempotent(seeded_db):
    """Re-approving an already-VERIFIED owner is a no-op (no audit storm)."""
    sa = await _super(seeded_db)
    o = await _owner(seeded_db, status=KYCStatus.VERIFIED)
    await approve_kyc(owner_id=o.id, body=ReviewAction(),
                      actor=sa, db=seeded_db)
    audits = (await seeded_db.execute(
        select(AuditLog).where(AuditLog.entity_id == o.id)
    )).scalars().all()
    assert audits == []


# ---------- KYC gate helper -----------------------------------------------

@pytest.mark.asyncio
async def test_assert_raises_for_pending(seeded_db):
    o = await _owner(seeded_db, status=KYCStatus.PENDING)
    with pytest.raises(KYCNotVerified):
        await assert_owner_kyc_verified(seeded_db, o.id)


@pytest.mark.asyncio
async def test_assert_raises_for_rejected(seeded_db):
    o = await _owner(seeded_db, status=KYCStatus.REJECTED)
    with pytest.raises(KYCNotVerified):
        await assert_owner_kyc_verified(seeded_db, o.id)


@pytest.mark.asyncio
async def test_assert_raises_for_unset(seeded_db):
    """The most important branch — legacy owners with no status must NOT
    sneak through. Default-deny."""
    o = await _owner(seeded_db, status=None)
    with pytest.raises(KYCNotVerified):
        await assert_owner_kyc_verified(seeded_db, o.id)


@pytest.mark.asyncio
async def test_assert_passes_for_verified(seeded_db):
    o = await _owner(seeded_db, status=KYCStatus.VERIFIED)
    # Should not raise
    await assert_owner_kyc_verified(seeded_db, o.id)


@pytest.mark.asyncio
async def test_assert_passes_for_not_required(seeded_db):
    """Grandfathered legacy owners marked NOT_REQUIRED skip the gate."""
    o = await _owner(seeded_db, status=KYCStatus.NOT_REQUIRED)
    await assert_owner_kyc_verified(seeded_db, o.id)
