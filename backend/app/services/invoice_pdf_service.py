"""Reportlab PDF renderers for the new GST-aware documents.

Three doc types are rendered here:

  - PLATFORM_TAX_INVOICE   (mySpace → Owner: listing / maintenance fee)
  - SETTLEMENT_STATEMENT   (Per-owner monthly net payout statement)
  - CREDIT_NOTE            (Refund-against-an-invoice — Sec 34 CGST)

The existing legacy renderer (routers/invoices.py) keeps handling booking
invoices unchanged. This module is the *new* one and is used only by the
new endpoints.

All amounts are formatted with the existing money utility patterns. The
documents include the four pieces a CA will look for:
  1. Supplier identity (name, GSTIN, address, state code)
  2. Recipient identity (name, GSTIN if any, place of supply)
  3. Tax breakdown line items (taxable, CGST/SGST/IGST)
  4. Sequential document number (from invoice_series_counter) + footer note
"""
from __future__ import annotations

from datetime import datetime
from io import BytesIO
from typing import Any, Optional

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import (
    Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)

# Reuse the page-style helpers — keeps every doc consistent.
_BRAND = colors.HexColor("#4F46E5")
_INK = colors.HexColor("#1F2937")
_MUTED = colors.HexColor("#6B7280")
_LINE = colors.HexColor("#E5E7EB")


def _doc(buf: BytesIO) -> SimpleDocTemplate:
    return SimpleDocTemplate(
        buf, pagesize=A4,
        rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36,
    )


def _styles() -> dict[str, ParagraphStyle]:
    s = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "title", parent=s["Heading1"], fontSize=22, textColor=_BRAND,
            spaceAfter=4, alignment=TA_CENTER,
        ),
        "subtitle": ParagraphStyle(
            "subtitle", parent=s["Heading2"], fontSize=12, textColor=_INK,
            spaceAfter=14, alignment=TA_CENTER,
        ),
        "h2": ParagraphStyle(
            "h2", parent=s["Heading3"], fontSize=11, textColor=_INK,
            spaceBefore=10, spaceAfter=6,
        ),
        "label": ParagraphStyle(
            "label", parent=s["Normal"], fontSize=8, textColor=_MUTED,
            spaceAfter=2,
        ),
        "value": ParagraphStyle(
            "value", parent=s["Normal"], fontSize=10, textColor=_INK,
            spaceAfter=4,
        ),
        "footer": ParagraphStyle(
            "footer", parent=s["Normal"], fontSize=8, textColor=_MUTED,
            alignment=TA_CENTER, spaceBefore=10,
        ),
    }


def _money(n: Any) -> str:
    try:
        return f"Rs. {float(n):,.2f}"
    except (TypeError, ValueError):
        return "—"


# ---------- Platform tax invoice -------------------------------------------

def render_platform_tax_invoice(
    *,
    invoice_number: str,
    invoice_date: datetime,
    supplier: dict[str, Any],
    recipient: dict[str, Any],
    line: dict[str, Any],
    cgst: float, sgst: float, igst: float,
    base_amount: float, total: float,
    hsn_sac: Optional[str],
    place_of_supply: Optional[str],
) -> bytes:
    """Render a B2B platform-fee invoice (mySpace -> Owner).

    `line` is a single-row dict with `{description, period, qty, rate}`.
    """
    buf = BytesIO()
    doc = _doc(buf)
    st = _styles()
    elements: list = []

    elements.append(Paragraph("mySpace", st["title"]))
    elements.append(Paragraph("PLATFORM TAX INVOICE", st["subtitle"]))

    # Header strip: invoice meta on the right, party blocks on the left
    meta_rows = [
        [Paragraph("Invoice No.", st["label"]), Paragraph(invoice_number, st["value"])],
        [Paragraph("Date", st["label"]), Paragraph(invoice_date.strftime("%d %b %Y"), st["value"])],
        [Paragraph("Place of Supply", st["label"]), Paragraph(place_of_supply or "—", st["value"])],
        [Paragraph("Reverse Charge", st["label"]), Paragraph("No", st["value"])],
    ]
    meta = Table(meta_rows, colWidths=[110, 180])
    meta.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    elements.append(meta)
    elements.append(Spacer(1, 10))

    # Parties
    parties_table = [[
        _party_block("Supplier", supplier, st),
        _party_block("Recipient", recipient, st),
    ]]
    parties = Table(parties_table, colWidths=[260, 260])
    parties.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOX", (0, 0), (-1, -1), 0.5, _LINE),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, _LINE),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    elements.append(parties)
    elements.append(Spacer(1, 16))

    # Line items
    elements.append(Paragraph("Particulars", st["h2"]))
    items_data = [
        ["#", "Description", "SAC", "Period", "Taxable (Rs.)"],
        ["1", line.get("description", ""), hsn_sac or "—", line.get("period", "—"),
         f"{base_amount:,.2f}"],
    ]
    items = Table(items_data, colWidths=[24, 240, 60, 100, 100])
    items.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F3F4F6")),
        ("TEXTCOLOR", (0, 0), (-1, 0), _INK),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (-1, 0), (-1, -1), "RIGHT"),
        ("BOX", (0, 0), (-1, -1), 0.5, _LINE),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, _LINE),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
    ]))
    elements.append(items)
    elements.append(Spacer(1, 12))

    # Totals
    totals_rows: list = [["Taxable Value", f"{base_amount:,.2f}"]]
    if cgst > 0:
        totals_rows.append(["CGST", f"{cgst:,.2f}"])
    if sgst > 0:
        totals_rows.append(["SGST", f"{sgst:,.2f}"])
    if igst > 0:
        totals_rows.append(["IGST", f"{igst:,.2f}"])
    totals_rows.append(["Grand Total", f"{total:,.2f}"])
    totals = Table(totals_rows, colWidths=[400, 124])
    totals.setStyle(TableStyle([
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("LINEABOVE", (0, -1), (-1, -1), 0.5, _LINE),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    elements.append(totals)

    elements.append(Spacer(1, 30))
    elements.append(Paragraph(
        "Computer-generated document. "
        "Tax rates frozen at issuance per tax_snapshot referenced in our records.",
        st["footer"],
    ))

    doc.build(elements)
    return buf.getvalue()


# ---------- Settlement statement -------------------------------------------

def render_settlement_statement(
    *,
    statement_number: str,
    owner_name: str,
    owner_gstin: Optional[str],
    bank_masked: Optional[str],
    period_start: datetime,
    period_end: datetime,
    totals: dict[str, float],
    payout_ref: Optional[str],
    payout_at: Optional[datetime],
    lines: list[dict[str, Any]],
) -> bytes:
    """Render the per-owner monthly settlement statement (design doc §7)."""
    buf = BytesIO()
    doc = _doc(buf)
    st = _styles()
    elements: list = []

    elements.append(Paragraph("mySpace", st["title"]))
    elements.append(Paragraph("SETTLEMENT STATEMENT", st["subtitle"]))

    # Top meta block
    meta = Table([
        [Paragraph("Statement #", st["label"]), Paragraph(statement_number, st["value"])],
        [Paragraph("Owner", st["label"]),
         Paragraph(f"{owner_name} ({owner_gstin or 'GSTIN not provided'})", st["value"])],
        [Paragraph("Period", st["label"]),
         Paragraph(f"{period_start.strftime('%d %b %Y')} – {period_end.strftime('%d %b %Y')}", st["value"])],
        [Paragraph("Bank A/c", st["label"]), Paragraph(bank_masked or "—", st["value"])],
    ], colWidths=[110, 414])
    meta.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    elements.append(meta)
    elements.append(Spacer(1, 16))

    # Summary block (mirrors design doc §7 layout)
    summary_rows = [
        ["A.", "Gross bookings collected on your behalf", _money(totals.get("gross"))],
        ["B.", "Refunds processed in period", f"({_money(totals.get('refunds'))})"],
        ["C.", "TCS deducted (Sec 52 CGST)", f"({_money(totals.get('tcs'))})"],
        ["D.", "TDS deducted u/s 194-O", f"({_money(totals.get('tds'))})"],
        ["E.", "Platform deductions (maintenance fee etc.)", f"({_money(totals.get('offset'))})"],
        ["",  "Net payout", _money(totals.get("net"))],
    ]
    summary = Table(summary_rows, colWidths=[24, 380, 120])
    summary.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("ALIGN", (2, 0), (2, -1), "RIGHT"),
        ("LINEBELOW", (0, -2), (-1, -2), 0.5, _LINE),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
    ]))
    elements.append(summary)
    elements.append(Spacer(1, 10))

    if payout_ref:
        elements.append(Paragraph(
            f"UTR: <b>{payout_ref}</b> credited "
            f"{payout_at.strftime('%d %b %Y') if payout_at else 'pending'}",
            st["value"],
        ))
        elements.append(Spacer(1, 12))

    # Line-level appendix
    elements.append(Paragraph("Booking-level breakdown", st["h2"]))
    if not lines:
        elements.append(Paragraph("(no line items)", st["value"]))
    else:
        line_rows = [["#", "Kind", "Reference", "Base", "Deduction", "Net"]]
        for i, line in enumerate(lines, 1):
            line_rows.append([
                str(i),
                line.get("kind", "").replace("_", " "),
                (line.get("reference_id") or "")[:8] or "—",
                _money(line.get("base_amount")),
                _money(line.get("deduction")),
                _money(line.get("net")),
            ])
        items = Table(line_rows, colWidths=[24, 110, 90, 92, 92, 92])
        items.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F3F4F6")),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("ALIGN", (3, 0), (-1, -1), "RIGHT"),
            ("BOX", (0, 0), (-1, -1), 0.5, _LINE),
            ("INNERGRID", (0, 0), (-1, -1), 0.25, _LINE),
        ]))
        elements.append(items)

    elements.append(Spacer(1, 24))
    elements.append(Paragraph(
        "GST shown above is owed by you to government and is included in (A). "
        "Pay your output GST via your GSTR-3B; report GSTR-1 with the appended invoice numbers. "
        "TCS appears in your GSTR-2A from our GSTR-8 filing. TDS reflects in 26AS.",
        st["footer"],
    ))

    doc.build(elements)
    return buf.getvalue()


# ---------- Credit note ----------------------------------------------------

def render_credit_note(
    *,
    credit_note_number: str,
    original_invoice_number: Optional[str],
    issue_date: datetime,
    supplier: dict[str, Any],
    recipient: dict[str, Any],
    reason: str,
    base_amount: float,
    cgst: float, sgst: float, igst: float,
    total: float,
    hsn_sac: Optional[str],
    place_of_supply: Optional[str],
) -> bytes:
    """Render a credit note (Sec 34 CGST). Mirrors the platform-invoice layout
    but with negative semantics and a reference to the original invoice."""
    buf = BytesIO()
    doc = _doc(buf)
    st = _styles()
    elements: list = []

    elements.append(Paragraph("mySpace", st["title"]))
    elements.append(Paragraph("CREDIT NOTE", st["subtitle"]))

    meta = Table([
        [Paragraph("Credit Note #", st["label"]), Paragraph(credit_note_number, st["value"])],
        [Paragraph("Issued", st["label"]), Paragraph(issue_date.strftime("%d %b %Y"), st["value"])],
        [Paragraph("Against Invoice", st["label"]),
         Paragraph(original_invoice_number or "—", st["value"])],
        [Paragraph("Reason", st["label"]), Paragraph(reason or "—", st["value"])],
        [Paragraph("Place of Supply", st["label"]), Paragraph(place_of_supply or "—", st["value"])],
    ], colWidths=[110, 414])
    meta.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    elements.append(meta)
    elements.append(Spacer(1, 12))

    parties = Table([[
        _party_block("Supplier", supplier, st),
        _party_block("Recipient", recipient, st),
    ]], colWidths=[260, 260])
    parties.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOX", (0, 0), (-1, -1), 0.5, _LINE),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, _LINE),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    elements.append(parties)
    elements.append(Spacer(1, 16))

    elements.append(Paragraph("Reversed Amounts", st["h2"]))
    rows: list = [
        ["Taxable Value reversed", f"({base_amount:,.2f})", hsn_sac or "—"],
    ]
    if cgst > 0:
        rows.append(["CGST reversed", f"({cgst:,.2f})", ""])
    if sgst > 0:
        rows.append(["SGST reversed", f"({sgst:,.2f})", ""])
    if igst > 0:
        rows.append(["IGST reversed", f"({igst:,.2f})", ""])
    rows.append(["Total reversed", f"({total:,.2f})", ""])
    table = Table(rows, colWidths=[324, 120, 80])
    table.setStyle(TableStyle([
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("LINEABOVE", (0, -1), (-1, -1), 0.5, _LINE),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    elements.append(table)

    elements.append(Spacer(1, 24))
    elements.append(Paragraph(
        "Issued under Section 34 of CGST Act, 2017. This credit note reverses "
        "the noted amounts from the original invoice. Report this in your GSTR-1 "
        "amendment for the corresponding period.",
        st["footer"],
    ))

    doc.build(elements)
    return buf.getvalue()


# ---------- Owner tax invoice (booking) ------------------------------------

def render_owner_tax_invoice(
    *,
    invoice_number: str,
    invoice_date: datetime,
    supplier: dict[str, Any],          # owner (legal name + GSTIN + state)
    recipient: dict[str, Any],         # student
    line: dict[str, Any],              # {description, period}
    cgst: float, sgst: float, igst: float,
    base_amount: float, total: float,
    hsn_sac: Optional[str],
    place_of_supply: Optional[str],
    platform_legal_name: str = "StudySpace Technology Pvt Ltd",
) -> bytes:
    """Owner -> Student tax invoice, generated by the platform on owner's behalf.

    The supplier section uses the OWNER's identity (legal name + GSTIN). The
    footer makes explicit that the platform is only the facilitator (Sec 2(45)
    CGST) and that the owner is the supplier of record.
    """
    buf = BytesIO()
    doc = _doc(buf)
    st = _styles()
    elements: list = []

    elements.append(Paragraph("mySpace", st["title"]))
    elements.append(Paragraph("TAX INVOICE (Issued on behalf of supplier)", st["subtitle"]))

    meta = Table([
        [Paragraph("Invoice No.", st["label"]), Paragraph(invoice_number, st["value"])],
        [Paragraph("Date", st["label"]), Paragraph(invoice_date.strftime("%d %b %Y"), st["value"])],
        [Paragraph("Place of Supply", st["label"]), Paragraph(place_of_supply or "—", st["value"])],
        [Paragraph("Reverse Charge", st["label"]), Paragraph("No", st["value"])],
    ], colWidths=[110, 414])
    meta.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    elements.append(meta)
    elements.append(Spacer(1, 10))

    elements.append(Table([[
        _party_block("Supplier (Owner)", supplier, st),
        _party_block("Recipient (Student)", recipient, st),
    ]], colWidths=[260, 260], style=TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOX", (0, 0), (-1, -1), 0.5, _LINE),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, _LINE),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ])))
    elements.append(Spacer(1, 16))

    elements.append(Paragraph("Particulars", st["h2"]))
    items_data = [
        ["#", "Description", "SAC", "Period", "Taxable (Rs.)"],
        ["1", line.get("description", ""), hsn_sac or "—", line.get("period", "—"),
         f"{base_amount:,.2f}"],
    ]
    elements.append(Table(items_data, colWidths=[24, 240, 60, 100, 100], style=TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F3F4F6")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (-1, 0), (-1, -1), "RIGHT"),
        ("BOX", (0, 0), (-1, -1), 0.5, _LINE),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, _LINE),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
    ])))
    elements.append(Spacer(1, 12))

    totals_rows: list = [["Taxable Value", f"{base_amount:,.2f}"]]
    if cgst > 0:
        totals_rows.append(["CGST", f"{cgst:,.2f}"])
    if sgst > 0:
        totals_rows.append(["SGST", f"{sgst:,.2f}"])
    if igst > 0:
        totals_rows.append(["IGST", f"{igst:,.2f}"])
    totals_rows.append(["Grand Total", f"{total:,.2f}"])
    elements.append(Table(totals_rows, colWidths=[400, 124], style=TableStyle([
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("LINEABOVE", (0, -1), (-1, -1), 0.5, _LINE),
    ])))

    elements.append(Spacer(1, 28))
    elements.append(Paragraph(
        f"Issued by {platform_legal_name} on behalf of "
        f"<b>{supplier.get('legal_name', '—')}</b>. {platform_legal_name} is a "
        f"facilitating platform under Section 2(45) of CGST Act, 2017 and is not "
        f"the supplier of this service. The owner named above is solely "
        f"responsible for the supply.",
        st["footer"],
    ))

    doc.build(elements)
    return buf.getvalue()


# ---------- ECO tax invoice (Sec 9(5) deemed supplier) ---------------------

def render_eco_tax_invoice(
    *,
    invoice_number: str,
    invoice_date: datetime,
    platform_party: dict[str, Any],     # mySpace (deemed supplier)
    underlying_owner: dict[str, Any],   # owner name displayed in disclosure note
    recipient: dict[str, Any],
    line: dict[str, Any],
    cgst: float, sgst: float, igst: float,
    base_amount: float, total: float,
    hsn_sac: Optional[str],
    place_of_supply: Optional[str],
) -> bytes:
    """Section 9(5) deemed-supplier tax invoice.

    Platform is the supplier of record for GST purposes. Customer-facing fields
    show the platform's identity; the underlying owner is disclosed but is NOT
    the GST supplier here.
    """
    buf = BytesIO()
    doc = _doc(buf)
    st = _styles()
    elements: list = []

    elements.append(Paragraph("mySpace", st["title"]))
    elements.append(Paragraph("TAX INVOICE (Section 9(5) — ECO as Deemed Supplier)", st["subtitle"]))

    meta = Table([
        [Paragraph("Invoice No.", st["label"]), Paragraph(invoice_number, st["value"])],
        [Paragraph("Date", st["label"]), Paragraph(invoice_date.strftime("%d %b %Y"), st["value"])],
        [Paragraph("Place of Supply", st["label"]), Paragraph(place_of_supply or "—", st["value"])],
        [Paragraph("Reverse Charge", st["label"]), Paragraph("No", st["value"])],
    ], colWidths=[110, 414])
    meta.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    elements.append(meta)
    elements.append(Spacer(1, 10))

    elements.append(Table([[
        _party_block("Supplier (Deemed)", platform_party, st),
        _party_block("Recipient (Student)", recipient, st),
    ]], colWidths=[260, 260], style=TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOX", (0, 0), (-1, -1), 0.5, _LINE),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, _LINE),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ])))
    elements.append(Spacer(1, 16))

    elements.append(Paragraph("Particulars", st["h2"]))
    items_data = [
        ["#", "Description", "SAC", "Period", "Taxable (Rs.)"],
        ["1", line.get("description", ""), hsn_sac or "—", line.get("period", "—"),
         f"{base_amount:,.2f}"],
    ]
    elements.append(Table(items_data, colWidths=[24, 240, 60, 100, 100], style=TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F3F4F6")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (-1, 0), (-1, -1), "RIGHT"),
        ("BOX", (0, 0), (-1, -1), 0.5, _LINE),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, _LINE),
    ])))
    elements.append(Spacer(1, 12))

    totals_rows: list = [["Taxable Value", f"{base_amount:,.2f}"]]
    if cgst > 0:
        totals_rows.append(["CGST", f"{cgst:,.2f}"])
    if sgst > 0:
        totals_rows.append(["SGST", f"{sgst:,.2f}"])
    if igst > 0:
        totals_rows.append(["IGST", f"{igst:,.2f}"])
    totals_rows.append(["Grand Total", f"{total:,.2f}"])
    elements.append(Table(totals_rows, colWidths=[400, 124], style=TableStyle([
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("LINEABOVE", (0, -1), (-1, -1), 0.5, _LINE),
    ])))

    elements.append(Spacer(1, 28))
    elements.append(Paragraph(
        f"Tax invoice issued by the e-commerce operator under Section 9(5) of "
        f"CGST Act, 2017. Underlying supplier of accommodation: "
        f"<b>{underlying_owner.get('legal_name', '—')}</b>. The underlying "
        f"supplier is not registered under GST; the GST shown above is the "
        f"liability of the e-commerce operator.",
        st["footer"],
    ))

    doc.build(elements)
    return buf.getvalue()


# ---------- Non-GST receipt ------------------------------------------------

def render_non_gst_receipt(
    *,
    receipt_number: str,
    receipt_date: datetime,
    supplier: dict[str, Any],          # owner (no GSTIN)
    recipient: dict[str, Any],         # student
    line: dict[str, Any],
    total: float,
    platform_legal_name: str = "StudySpace Technology Pvt Ltd",
) -> bytes:
    """Non-tax-invoice receipt.

    Used when the owner is unregistered under GST AND the supply is not
    covered by Section 9(5). No tax is charged. The receipt is still a
    series-numbered, persistent record so refunds + audits are traceable.
    """
    buf = BytesIO()
    doc = _doc(buf)
    st = _styles()
    elements: list = []

    elements.append(Paragraph("mySpace", st["title"]))
    elements.append(Paragraph("BOOKING RECEIPT (Not a Tax Invoice)", st["subtitle"]))

    meta = Table([
        [Paragraph("Receipt No.", st["label"]), Paragraph(receipt_number, st["value"])],
        [Paragraph("Date", st["label"]), Paragraph(receipt_date.strftime("%d %b %Y"), st["value"])],
    ], colWidths=[110, 414])
    meta.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    elements.append(meta)
    elements.append(Spacer(1, 10))

    elements.append(Table([[
        _party_block("Supplier (Owner)", supplier, st),
        _party_block("Recipient (Student)", recipient, st),
    ]], colWidths=[260, 260], style=TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOX", (0, 0), (-1, -1), 0.5, _LINE),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, _LINE),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ])))
    elements.append(Spacer(1, 16))

    elements.append(Paragraph("Particulars", st["h2"]))
    items_data = [
        ["#", "Description", "Period", "Amount (Rs.)"],
        ["1", line.get("description", ""), line.get("period", "—"), f"{total:,.2f}"],
    ]
    elements.append(Table(items_data, colWidths=[24, 300, 100, 100], style=TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F3F4F6")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (-1, 0), (-1, -1), "RIGHT"),
        ("BOX", (0, 0), (-1, -1), 0.5, _LINE),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, _LINE),
    ])))
    elements.append(Spacer(1, 12))

    totals = Table([
        ["Total Received", f"{total:,.2f}"],
    ], colWidths=[400, 124], style=TableStyle([
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("LINEABOVE", (0, 0), (-1, 0), 0.5, _LINE),
    ]))
    elements.append(totals)

    elements.append(Spacer(1, 28))
    elements.append(Paragraph(
        f"Supplier is not registered under GST. No tax is charged on this supply. "
        f"{platform_legal_name} acts only as a facilitating platform under "
        f"Section 2(45) of CGST Act, 2017 between the supplier and the recipient.",
        st["footer"],
    ))

    doc.build(elements)
    return buf.getvalue()


# ---------- helpers --------------------------------------------------------

def _party_block(label: str, party: dict[str, Any], st) -> list:
    return [
        Paragraph(label.upper(), st["label"]),
        Paragraph(party.get("legal_name", "—"), st["value"]),
        Paragraph(party.get("address", "") or "—", st["value"]),
        Paragraph(f"GSTIN: {party.get('gstin') or 'Not registered'}", st["value"]),
        Paragraph(f"State: {party.get('state_code') or '—'}", st["value"]),
    ]
