"""Settlement API.

Owner-facing endpoints (read-only on the owner's own runs).
Super-admin endpoints to trigger the aggregator manually and record payout UTRs.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_admin, get_current_super_admin
from app.models.settlement import SettlementLine, SettlementRun, SettlementStatus
from app.models.user import User, UserRole
from app.services import settlement_service
from app.services.invoice_pdf_service import render_settlement_statement
from app.services.invoice_series_service import (
    InvoiceSeriesService, current_fiscal_year, format_invoice_number,
)


router = APIRouter(tags=["Settlements"])


# ---------- schemas --------------------------------------------------------

class SettlementRunOut(BaseModel):
    id: str
    owner_id: str
    period_start: str
    period_end: str
    gross: float
    refunds: float
    platform_offset: float
    tcs_total: float
    tds_total: float
    net_payout: float
    status: str
    payout_ref: Optional[str]
    payout_at: Optional[str]
    failure_reason: Optional[str]
    created_at: str

    @classmethod
    def from_model(cls, r: SettlementRun) -> "SettlementRunOut":
        return cls(
            id=r.id,
            owner_id=r.owner_id,
            period_start=r.period_start.isoformat(),
            period_end=r.period_end.isoformat(),
            gross=float(r.gross),
            refunds=float(r.refunds),
            platform_offset=float(r.platform_offset),
            tcs_total=float(r.tcs_total),
            tds_total=float(r.tds_total),
            net_payout=float(r.net_payout),
            status=r.status.value,
            payout_ref=r.payout_ref,
            payout_at=r.payout_at.isoformat() if r.payout_at else None,
            failure_reason=r.failure_reason,
            created_at=r.created_at.isoformat(),
        )


class SettlementLineOut(BaseModel):
    id: str
    kind: str
    reference_type: Optional[str]
    reference_id: Optional[str]
    base_amount: float
    deduction: float
    net: float
    narration: Optional[str]


class SettlementDetailOut(BaseModel):
    run: SettlementRunOut
    lines: list[SettlementLineOut]


# ---------- owner endpoints ------------------------------------------------

owner_router = APIRouter(prefix="/owner/settlements", tags=["Owner Settlements"])


@owner_router.get("", response_model=list[SettlementRunOut])
async def list_my_settlements(
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    rows = (await db.execute(
        select(SettlementRun)
        .where(SettlementRun.owner_id == current_user.id)
        .order_by(SettlementRun.created_at.desc())
    )).scalars().all()
    return [SettlementRunOut.from_model(r) for r in rows]


@owner_router.get("/{run_id}/pdf")
async def get_my_settlement_pdf(
    run_id: str,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Render the SETTLEMENT_STATEMENT for this run as a PDF.

    Allocates a sequential SS/STM/{FY}/{NNNNNN} number on first download
    and persists it on the SettlementRun (via an Invoice row), so the same
    PDF re-renders with the same number on subsequent calls.
    """
    run = await db.get(SettlementRun, run_id)
    if run is None or (
        current_user.role != UserRole.SUPER_ADMIN and run.owner_id != current_user.id
    ):
        raise HTTPException(status_code=404, detail="Settlement not found")

    # Allocate or reuse the statement number
    from app.models.invoice import Invoice, InvoiceDocType
    stmt_invoice: Invoice | None = None
    if run.statement_invoice_id:
        stmt_invoice = await db.get(Invoice, run.statement_invoice_id)
    if stmt_invoice is None:
        number, fy, seq = await InvoiceSeriesService.next_number(db, series_code="STM")
        stmt_invoice = Invoice(
            invoice_number=number,
            user_id=run.owner_id,
            amount=float(run.gross),
            tax_amount=0.0,
            total_amount=float(run.net_payout),
            venue_name="StudySpace Settlement",
            doc_type=InvoiceDocType.SETTLEMENT_STATEMENT,
            series_code="STM",
            fiscal_year=fy,
            sequence_no=seq,
        )
        db.add(stmt_invoice)
        await db.flush()
        run.statement_invoice_id = stmt_invoice.id
        await db.commit()

    # Owner info
    owner = await db.get(User, run.owner_id)
    bank_masked = None
    if owner and owner.bank_account_number:
        n = owner.bank_account_number
        bank_masked = f"{(owner.bank_ifsc or '')[:4]} ****{n[-4:] if len(n) >= 4 else n}"

    # Line items
    lines = (await db.execute(
        select(SettlementLine).where(SettlementLine.run_id == run.id)
    )).scalars().all()
    line_dicts = [
        {
            "kind": line.kind.value,
            "reference_id": line.reference_id,
            "base_amount": float(line.base_amount),
            "deduction": float(line.deduction),
            "net": float(line.net),
        }
        for line in lines
    ]

    pdf_bytes = render_settlement_statement(
        statement_number=stmt_invoice.invoice_number,
        owner_name=(owner.legal_name or owner.name) if owner else "Unknown",
        owner_gstin=owner.gstin if owner else None,
        bank_masked=bank_masked,
        period_start=run.period_start,
        period_end=run.period_end,
        totals={
            "gross": float(run.gross),
            "refunds": float(run.refunds),
            "tcs": float(run.tcs_total),
            "tds": float(run.tds_total),
            "offset": float(run.platform_offset),
            "net": float(run.net_payout),
        },
        payout_ref=run.payout_ref,
        payout_at=run.payout_at,
        lines=line_dicts,
    )
    filename = stmt_invoice.invoice_number.replace("/", "_") + ".pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )


@owner_router.get("/{run_id}", response_model=SettlementDetailOut)
async def get_my_settlement(
    run_id: str,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    run = await db.get(SettlementRun, run_id)
    if run is None or run.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Settlement not found")
    lines = (await db.execute(
        select(SettlementLine).where(SettlementLine.run_id == run.id)
    )).scalars().all()
    return SettlementDetailOut(
        run=SettlementRunOut.from_model(run),
        lines=[
            SettlementLineOut(
                id=line.id,
                kind=line.kind.value,
                reference_type=line.reference_type,
                reference_id=line.reference_id,
                base_amount=float(line.base_amount),
                deduction=float(line.deduction),
                net=float(line.net),
                narration=line.narration,
            )
            for line in lines
        ],
    )


# ---------- super-admin endpoints ------------------------------------------

admin_router = APIRouter(prefix="/admin/settlements", tags=["Admin: Settlements"])


class TriggerRunBody(BaseModel):
    now: Optional[str] = None    # ISO timestamp override; for backfills / tests


@admin_router.post("/run")
async def trigger_run(
    body: TriggerRunBody,
    _: User = Depends(get_current_super_admin),
    db: AsyncSession = Depends(get_db),
):
    when = datetime.fromisoformat(body.now) if body.now else None
    summary = await settlement_service.run_settlements(db, now=when)
    return summary


@admin_router.get("", response_model=list[SettlementRunOut])
async def list_all_settlements(
    status: Optional[str] = None,
    _: User = Depends(get_current_super_admin),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(SettlementRun).order_by(SettlementRun.created_at.desc())
    if status:
        try:
            stmt = stmt.where(SettlementRun.status == SettlementStatus(status))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}") from exc
    rows = (await db.execute(stmt)).scalars().all()
    return [SettlementRunOut.from_model(r) for r in rows]


class MarkPaidBody(BaseModel):
    payout_ref: str


@admin_router.post("/{run_id}/mark-paid", response_model=SettlementRunOut)
async def mark_run_paid(
    run_id: str,
    body: MarkPaidBody,
    _: User = Depends(get_current_super_admin),
    db: AsyncSession = Depends(get_db),
):
    try:
        run = await settlement_service.mark_paid(db, run_id=run_id, payout_ref=body.payout_ref)
        await db.commit()
        return SettlementRunOut.from_model(run)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


class MarkFailedBody(BaseModel):
    reason: str


@admin_router.post("/{run_id}/mark-failed", response_model=SettlementRunOut)
async def mark_run_failed(
    run_id: str,
    body: MarkFailedBody,
    _: User = Depends(get_current_super_admin),
    db: AsyncSession = Depends(get_db),
):
    try:
        run = await settlement_service.mark_failed(db, run_id=run_id, reason=body.reason)
        await db.commit()
        return SettlementRunOut.from_model(run)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


router.include_router(owner_router)
router.include_router(admin_router)
