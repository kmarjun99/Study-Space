"""Owner-facing billing API: charges, pay-now (Razorpay order), and invoice PDF.

Designed to live alongside the existing /razorpay router. Charges are
StudySpace's own revenue (listing fee + monthly maintenance fee), so the
flow re-uses Razorpay but the verify path goes through `/webhooks/razorpay`
for ledger posting and invoice issuance.
"""
from __future__ import annotations

from typing import Optional  # noqa: F401  (used in helper type hints)

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_admin, get_current_super_admin
from app.models.invoice import Invoice
from app.models.owner_charge import (
    ListingType,
    OwnerCharge,
    OwnerChargeStatus,
    OwnerChargeType,
)
from app.models.party import Party
from app.models.user import User, UserRole
from app.services.invoice_pdf_service import render_platform_tax_invoice
from app.services.owner_billing_service import (
    create_listing_fee_charge,
    mark_charge_paid,
)
from app.services.payment_service import payment_service


router = APIRouter(prefix="/owner/charges", tags=["Owner Billing"])


# ---------- response schemas ------------------------------------------------

class ChargeOut(BaseModel):
    id: str
    owner_id: str
    listing_id: Optional[str]
    listing_type: Optional[str]
    charge_type: str
    period_key: Optional[str]
    base_amount: float
    gst_amount: float
    total_amount: float
    gst_rate_applied: Optional[float]
    status: str
    due_date: Optional[str]
    invoice_id: Optional[str]
    razorpay_payment_id: Optional[str]
    created_at: str
    paid_at: Optional[str]

    @classmethod
    def from_model(cls, c: OwnerCharge) -> "ChargeOut":
        return cls(
            id=c.id,
            owner_id=c.owner_id,
            listing_id=c.listing_id,
            listing_type=c.listing_type.value if c.listing_type else None,
            charge_type=c.charge_type.value,
            period_key=c.period_key,
            base_amount=float(c.base_amount),
            gst_amount=float(c.gst_amount or 0),
            total_amount=float(c.total_amount),
            gst_rate_applied=float(c.gst_rate_applied) if c.gst_rate_applied is not None else None,
            status=c.status.value,
            due_date=c.due_date.isoformat() if c.due_date else None,
            invoice_id=c.invoice_id,
            razorpay_payment_id=c.razorpay_payment_id,
            created_at=c.created_at.isoformat(),
            paid_at=c.paid_at.isoformat() if c.paid_at else None,
        )


class CreateListingFeeRequest(BaseModel):
    listing_id: str
    listing_type: str           # 'READING_ROOM' | 'ACCOMMODATION'
    plan_id: str


class PayOrderResponse(BaseModel):
    order_id: str
    amount: int                 # paise
    currency: str
    razorpay_key_id: str
    is_demo: bool = False
    charge_id: str


# ---------- endpoints -------------------------------------------------------

@router.get("", response_model=list[ChargeOut])
async def list_my_charges(
    status: Optional[str] = None,
    owner_id: Optional[str] = None,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """List charges. Owners see only their own. Super admin can pass
    `?owner_id=` to audit any owner's charges (else sees nothing because
    super admins don't own charges themselves).
    """
    stmt = select(OwnerCharge)
    if current_user.role == UserRole.SUPER_ADMIN:
        if owner_id:
            stmt = stmt.where(OwnerCharge.owner_id == owner_id)
        # No owner_id filter for super admin returns everything (admin lens).
    else:
        # Owners can only see their own, ignoring any spoofed owner_id.
        stmt = stmt.where(OwnerCharge.owner_id == current_user.id)
    if status:
        try:
            stmt = stmt.where(OwnerCharge.status == OwnerChargeStatus(status))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}") from exc
    stmt = stmt.order_by(OwnerCharge.created_at.desc())
    rows = (await db.execute(stmt)).scalars().all()
    return [ChargeOut.from_model(c) for c in rows]


@router.post("/listing-fee", response_model=ChargeOut)
async def create_listing_fee(
    body: CreateListingFeeRequest,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Idempotently create a one-time listing fee charge for the current owner."""
    try:
        lt = ListingType(body.listing_type)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid listing_type") from exc

    result = await create_listing_fee_charge(
        db,
        owner_id=current_user.id,
        listing_id=body.listing_id,
        listing_type=lt,
        plan_id=body.plan_id,
    )
    await db.commit()
    return ChargeOut.from_model(result.charge)


@router.post("/{charge_id}/pay-order", response_model=PayOrderResponse)
async def create_pay_order(
    charge_id: str,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Create a Razorpay order for an owner charge."""
    charge = await db.get(OwnerCharge, charge_id)
    if charge is None or charge.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Charge not found")
    # Only DUE / OVERDUE / FAILED charges are payable. PAID is already
    # collected; WAIVED was forgiven by super admin; DRAFT shouldn't reach
    # a pay button. Accepting any of those would issue a Razorpay order
    # that can never be reconciled back to a real obligation.
    payable_statuses = {
        OwnerChargeStatus.DUE,
        OwnerChargeStatus.OVERDUE,
        OwnerChargeStatus.FAILED,
    }
    if charge.status not in payable_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"Charge is {charge.status.value}; only DUE/OVERDUE/FAILED can be paid.",
        )

    order = payment_service.create_order(
        amount=float(charge.total_amount),
        receipt=f"charge_{charge.id}",
        notes={
            "charge_id": charge.id,
            "owner_id": current_user.id,
            "charge_type": charge.charge_type.value,
            "period": charge.period_key or "",
        },
    )
    charge.razorpay_order_id = order["id"]
    await db.commit()

    return PayOrderResponse(
        order_id=order["id"],
        amount=order["amount"],
        currency=order["currency"],
        razorpay_key_id=payment_service.razorpay_key_id,
        is_demo=order.get("is_demo", False),
        charge_id=charge.id,
    )


class ManualPayBody(BaseModel):
    razorpay_payment_id: str


@router.post("/{charge_id}/confirm", response_model=ChargeOut)
async def confirm_charge_payment(
    charge_id: str,
    body: ManualPayBody,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Client-driven confirmation path (mirrors /razorpay/verify for bookings).

    Webhook path is the source of truth; this endpoint exists so the owner UI
    can show immediate feedback. Both paths are idempotent.
    """
    charge = await db.get(OwnerCharge, charge_id)
    if charge is None or charge.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Charge not found")

    invoice = await mark_charge_paid(
        db, charge_id=charge.id, payment_ref=body.razorpay_payment_id,
    )
    await db.commit()
    await db.refresh(charge)
    return ChargeOut.from_model(charge)


@router.get("/{charge_id}/invoice/pdf")
async def get_charge_invoice_pdf(
    charge_id: str,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Render the PLATFORM_TAX_INVOICE for this charge as a PDF.

    Returns 404 if no invoice has been issued yet (i.e., charge isn't PAID).
    """
    charge = await db.get(OwnerCharge, charge_id)
    if charge is None:
        raise HTTPException(status_code=404, detail="Charge not found")
    if charge.owner_id != current_user.id and current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=403, detail="Forbidden")
    if not charge.invoice_id:
        raise HTTPException(status_code=404, detail="Invoice not yet issued")
    invoice = await db.get(Invoice, charge.invoice_id)
    if invoice is None:
        raise HTTPException(status_code=404, detail="Invoice missing")

    supplier = await db.get(Party, invoice.supplier_party_id) if invoice.supplier_party_id else None
    recipient = await db.get(Party, invoice.recipient_party_id) if invoice.recipient_party_id else None
    pdf_bytes = render_platform_tax_invoice(
        invoice_number=invoice.invoice_number,
        invoice_date=invoice.generated_at,
        supplier=_party_dict(supplier),
        recipient=_party_dict(recipient),
        line={
            "description": invoice.seat_details or charge.charge_type.value,
            "period": charge.period_key or "One-time",
        },
        cgst=float(invoice.cgst or 0),
        sgst=float(invoice.sgst or 0),
        igst=float(invoice.igst or 0),
        base_amount=float(invoice.base_amount or invoice.amount),
        total=float(invoice.total_amount),
        hsn_sac=invoice.hsn_sac,
        place_of_supply=invoice.place_of_supply_state,
    )
    filename = invoice.invoice_number.replace("/", "_") + ".pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )


def _party_dict(p: Optional[Party]) -> dict:
    if p is None:
        return {}
    return {
        "legal_name": p.legal_name,
        "address": p.address,
        "gstin": p.gstin,
        "state_code": p.state_code,
    }


@router.get("/{charge_id}/invoice")
async def get_charge_invoice(
    charge_id: str,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Return invoice metadata. PDF generation reuses the existing
    `routers/invoices.py` endpoint; this one returns the invoice row.
    """
    charge = await db.get(OwnerCharge, charge_id)
    if charge is None:
        raise HTTPException(status_code=404, detail="Charge not found")
    # Owner can see own; super admin can see all
    if charge.owner_id != current_user.id and current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=403, detail="Forbidden")
    if not charge.invoice_id:
        raise HTTPException(status_code=404, detail="Invoice not yet issued")
    invoice = await db.get(Invoice, charge.invoice_id)
    if invoice is None:
        raise HTTPException(status_code=404, detail="Invoice missing")
    return {
        "invoice_number": invoice.invoice_number,
        "doc_type": invoice.doc_type.value if invoice.doc_type else None,
        "series_code": invoice.series_code,
        "fiscal_year": invoice.fiscal_year,
        "sequence_no": invoice.sequence_no,
        "base_amount": float(invoice.base_amount) if invoice.base_amount is not None else None,
        "cgst": float(invoice.cgst) if invoice.cgst is not None else 0.0,
        "sgst": float(invoice.sgst) if invoice.sgst is not None else 0.0,
        "igst": float(invoice.igst) if invoice.igst is not None else 0.0,
        "total_amount": invoice.total_amount,
        "hsn_sac": invoice.hsn_sac,
        "place_of_supply_state": invoice.place_of_supply_state,
        "generated_at": invoice.generated_at.isoformat(),
    }


# ---------- super-admin-only helpers ---------------------------------------

class WaiveBody(BaseModel):
    reason: str


@router.post("/{charge_id}/waive", response_model=ChargeOut)
async def waive_charge(
    charge_id: str,
    body: WaiveBody,
    current_user: User = Depends(get_current_super_admin),
    db: AsyncSession = Depends(get_db),
):
    """Super admin can waive a charge (no payment expected)."""
    charge = await db.get(OwnerCharge, charge_id)
    if charge is None:
        raise HTTPException(status_code=404, detail="Charge not found")
    if charge.status == OwnerChargeStatus.PAID:
        raise HTTPException(status_code=400, detail="Cannot waive a paid charge")
    charge.status = OwnerChargeStatus.WAIVED
    await db.commit()
    return ChargeOut.from_model(charge)
