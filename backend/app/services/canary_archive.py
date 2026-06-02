"""Bundle a real-listing validation run into a single archivable zip.

Per the operational directive, every staging canary run should produce:
  - validation_<id>_<ts>.json      (already written by the validator)
  - the test booking's invoice PDF (if a GST-aware doc was issued)
  - the settlement statement PDF   (if a settlement run exists)
  - the credit note PDF            (if a refund was approved)
  - a snapshot of ledger.csv       (every double-entry row for this booking)

Bundle name: `staging_canary_<listing_id_short>_<ts>.zip`

Pure functions only — no prompts, no DB writes. The CLI script wires this up.
"""
from __future__ import annotations

import csv
import io
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.booking import Booking
from app.models.invoice import Invoice, InvoiceDocType
from app.models.ledger_entry import LedgerEntry
from app.models.party import Party
from app.models.refund import Refund, RefundStatus
from app.models.settlement import SettlementLine, SettlementRun
from app.models.user import User
from app.services.invoice_pdf_service import (
    render_credit_note,
    render_owner_tax_invoice,
    render_platform_tax_invoice,
    render_settlement_statement,
)


async def collect_booking_invoice_pdf(
    db: AsyncSession, *, booking_id: str,
) -> tuple[Optional[str], Optional[bytes]]:
    """Find the GST-aware invoice for this booking (if any) and render its PDF.

    Returns (filename, bytes) or (None, None) if no qualifying invoice exists.
    """
    invoice = (await db.execute(
        select(Invoice).where(
            (Invoice.booking_id == booking_id)
            & (Invoice.doc_type.notin_([InvoiceDocType.CREDIT_NOTE,
                                        InvoiceDocType.LEGACY,
                                        InvoiceDocType.SETTLEMENT_STATEMENT]))
        )
        .limit(1)
    )).scalar_one_or_none()
    if invoice is None:
        return None, None

    booking = await db.get(Booking, booking_id)
    supplier = await db.get(Party, invoice.supplier_party_id) if invoice.supplier_party_id else None
    recipient = await db.get(Party, invoice.recipient_party_id) if invoice.recipient_party_id else None

    # Choose the renderer that matches the doc type. The renderers all return
    # bytes; we pass the same field shape from the Invoice row.
    line = {
        "description": invoice.seat_details or (booking and f"Booking {booking.id[:8]}") or "Supply",
        "period": invoice.plan_duration or "—",
    }
    common_kwargs = dict(
        invoice_number=invoice.invoice_number,
        invoice_date=invoice.generated_at,
        recipient=_party_dict(recipient),
        line=line,
        cgst=float(invoice.cgst or 0),
        sgst=float(invoice.sgst or 0),
        igst=float(invoice.igst or 0),
        base_amount=float(invoice.base_amount or invoice.amount),
        total=float(invoice.total_amount),
        hsn_sac=invoice.hsn_sac,
        place_of_supply=invoice.place_of_supply_state,
    )
    if invoice.doc_type == InvoiceDocType.OWNER_TAX_INVOICE:
        pdf = render_owner_tax_invoice(supplier=_party_dict(supplier), **common_kwargs)
    else:
        # PLATFORM_TAX_INVOICE / ECO_TAX_INVOICE / NON_GST_RECEIPT all use the
        # platform-style template as a sensible fallback; the validator's
        # primary canary listing is the registered-owner path so OWNER_TAX_INVOICE
        # is what 99% of runs will hit.
        pdf = render_platform_tax_invoice(supplier=_party_dict(supplier), **common_kwargs)

    safe_name = invoice.invoice_number.replace("/", "_") + ".pdf"
    return f"invoice_{safe_name}", pdf


async def collect_settlement_pdf(
    db: AsyncSession, *, run_id: str,
) -> tuple[Optional[str], Optional[bytes]]:
    run = await db.get(SettlementRun, run_id)
    if run is None:
        return None, None
    owner = await db.get(User, run.owner_id)
    if owner is None:
        return None, None

    lines = (await db.execute(
        select(SettlementLine).where(SettlementLine.run_id == run.id)
    )).scalars().all()
    bank = None
    if owner.bank_account_number:
        last4 = owner.bank_account_number[-4:]
        bank = f"{(owner.bank_ifsc or '')[:4]} ****{last4}"

    pdf = render_settlement_statement(
        statement_number=f"STAGING/STM/{run.id[:6]}",
        owner_name=owner.legal_name or owner.name,
        owner_gstin=owner.gstin,
        bank_masked=bank,
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
        lines=[
            {
                "kind": line.kind.value,
                "reference_id": line.reference_id,
                "base_amount": float(line.base_amount),
                "deduction": float(line.deduction),
                "net": float(line.net),
            }
            for line in lines
        ],
    )
    return f"settlement_{run.id[:8]}.pdf", pdf


async def collect_credit_note_pdf(
    db: AsyncSession, *, booking_id: str,
) -> tuple[Optional[str], Optional[bytes]]:
    refund = (await db.execute(
        select(Refund).where(
            (Refund.booking_id == booking_id)
            & (Refund.status.in_([RefundStatus.APPROVED, RefundStatus.PROCESSED]))
        )
        .order_by(Refund.requested_at.desc())
        .limit(1)
    )).scalar_one_or_none()
    if refund is None:
        return None, None
    cn = (await db.execute(
        select(Invoice).where(
            (Invoice.doc_type == InvoiceDocType.CREDIT_NOTE)
            & (Invoice.payment_id == refund.id)
        )
    )).scalar_one_or_none()
    if cn is None:
        return None, None

    supplier = await db.get(Party, cn.supplier_party_id) if cn.supplier_party_id else None
    recipient = await db.get(Party, cn.recipient_party_id) if cn.recipient_party_id else None
    pdf = render_credit_note(
        credit_note_number=cn.invoice_number,
        original_invoice_number=None,
        issue_date=cn.generated_at,
        supplier=_party_dict(supplier),
        recipient=_party_dict(recipient),
        reason=(refund.reason.value if refund.reason else "—"),
        base_amount=float(cn.base_amount or cn.amount),
        cgst=float(cn.cgst or 0),
        sgst=float(cn.sgst or 0),
        igst=float(cn.igst or 0),
        total=float(cn.total_amount),
        hsn_sac=cn.hsn_sac,
        place_of_supply=cn.place_of_supply_state,
    )
    safe = cn.invoice_number.replace("/", "_") + ".pdf"
    return f"credit_note_{safe}", pdf


async def collect_ledger_csv(
    db: AsyncSession, *, booking_id: str,
) -> tuple[str, bytes]:
    """All ledger rows touching this booking (BOOKING + CREDIT_NOTE + SETTLEMENT)."""
    booking = await db.get(Booking, booking_id)
    refund_ids: list[str] = []
    if booking is not None:
        refunds = (await db.execute(
            select(Refund.id).where(Refund.booking_id == booking_id)
        )).scalars().all()
        refund_ids = list(refunds)

    cn_invoice_ids: list[str] = []
    if refund_ids:
        cn_rows = (await db.execute(
            select(Invoice.id).where(
                (Invoice.doc_type == InvoiceDocType.CREDIT_NOTE)
                & (Invoice.payment_id.in_(refund_ids))
            )
        )).scalars().all()
        cn_invoice_ids = list(cn_rows)

    settlement_ids: list[str] = []
    if booking is not None and booking.settlement_run_id:
        settlement_ids = [booking.settlement_run_id]

    relevant_source_ids = {booking_id, *cn_invoice_ids, *settlement_ids}
    rows = (await db.execute(
        select(LedgerEntry)
        .where(LedgerEntry.source_id.in_(relevant_source_ids))
        .order_by(LedgerEntry.posted_at)
    )).scalars().all()

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow([
        "posted_at", "txn_group_id", "source_type", "source_id",
        "account_code", "party_type", "party_id",
        "debit", "credit", "narration",
    ])
    for r in rows:
        w.writerow([
            r.posted_at.isoformat(), r.txn_group_id, r.source_type, r.source_id,
            r.account_code, r.party_type or "", r.party_id or "",
            f"{r.debit:.2f}", f"{r.credit:.2f}", r.narration or "",
        ])
    return "ledger.csv", buf.getvalue().encode("utf-8")


# ---------- public bundle entry-point --------------------------------------

async def build_archive_bundle(
    db: AsyncSession,
    *,
    listing_id: str,
    booking_id: Optional[str],
    settlement_run_id: Optional[str],
    validation_json_path: Optional[Path],
) -> tuple[str, bytes]:
    """Return (filename, zip_bytes) for the validator archive bundle.

    Caller decides where to write it. None of the four PDF collectors are
    required to succeed — whichever artifacts are available get bundled, and
    a `manifest.txt` records what was found vs. skipped so the dev can see at
    a glance whether the staging rehearsal was complete.
    """
    ts = datetime.utcnow().strftime("%Y%m%dT%H%M%S")
    name = f"staging_canary_{listing_id[:8]}_{ts}.zip"
    manifest_lines = [f"# Staging canary bundle for listing {listing_id}",
                      f"# Generated: {datetime.utcnow().isoformat()}Z\n"]

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        if validation_json_path is not None and validation_json_path.exists():
            zf.write(validation_json_path, arcname=validation_json_path.name)
            manifest_lines.append(f"included: {validation_json_path.name}")
        else:
            manifest_lines.append("missing : validation JSON (validator did not write one)")

        if booking_id is not None:
            for collector, label in [
                (collect_booking_invoice_pdf, "booking invoice PDF"),
                (collect_credit_note_pdf, "credit note PDF"),
            ]:
                fname, data = await collector(db, booking_id=booking_id)
                if fname is not None and data is not None:
                    zf.writestr(fname, data)
                    manifest_lines.append(f"included: {fname}")
                else:
                    manifest_lines.append(f"missing : {label} (none found for booking {booking_id[:8]})")

            lfname, ldata = await collect_ledger_csv(db, booking_id=booking_id)
            zf.writestr(lfname, ldata)
            manifest_lines.append(f"included: {lfname}")
        else:
            manifest_lines.append("missing : booking invoice + credit note + ledger (no booking)")

        if settlement_run_id is not None:
            sfname, sdata = await collect_settlement_pdf(db, run_id=settlement_run_id)
            if sfname is not None and sdata is not None:
                zf.writestr(sfname, sdata)
                manifest_lines.append(f"included: {sfname}")
            else:
                manifest_lines.append(f"missing : settlement PDF (run {settlement_run_id[:8]} not found)")
        else:
            manifest_lines.append("missing : settlement PDF (no settlement run yet)")

        zf.writestr("manifest.txt", "\n".join(manifest_lines) + "\n")

    return name, buf.getvalue()


def _party_dict(p) -> dict:
    if p is None:
        return {}
    return {
        "legal_name": p.legal_name,
        "address": p.address,
        "gstin": p.gstin,
        "state_code": p.state_code,
    }
