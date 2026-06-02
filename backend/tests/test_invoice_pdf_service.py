"""Smoke tests for the PDF renderers.

We don't parse the PDF byte-stream — we just confirm that each renderer:
  - Returns a non-empty bytes object
  - Produces something that looks like a PDF (`%PDF-` header)
  - Doesn't blow up when given the realistic field shapes the routers send

This catches reportlab-API regressions cheaply on every CI run.
"""
from __future__ import annotations

from datetime import datetime

import pytest

from app.services.invoice_pdf_service import (
    render_credit_note,
    render_eco_tax_invoice,
    render_non_gst_receipt,
    render_owner_tax_invoice,
    render_platform_tax_invoice,
    render_settlement_statement,
)


SUPPLIER = {
    "legal_name": "StudySpace Technology Pvt Ltd",
    "address": "12, Brigade Road, Bengaluru, KA",
    "gstin": "29AABCT1234A1Z5",
    "state_code": "KA",
}
RECIPIENT = {
    "legal_name": "Acme Reading Rooms Pvt Ltd",
    "address": "100ft Rd, Indiranagar, Bengaluru",
    "gstin": "29ACMEZ1234Z1Z5",
    "state_code": "KA",
}


def _is_pdf(data: bytes) -> bool:
    return data[:5] == b"%PDF-"


def test_platform_tax_invoice_renders():
    pdf = render_platform_tax_invoice(
        invoice_number="SS/PLF/25-26/000001",
        invoice_date=datetime(2025, 6, 1),
        supplier=SUPPLIER, recipient=RECIPIENT,
        line={"description": "Listing fee — Acme Hostel", "period": "One-time"},
        cgst=89.91, sgst=89.91, igst=0,
        base_amount=999.00, total=1178.82,
        hsn_sac="998599", place_of_supply="KA",
    )
    assert _is_pdf(pdf)
    assert len(pdf) > 1000  # non-trivial size


def test_platform_tax_invoice_with_igst_renders():
    """Inter-state — IGST only, no CGST/SGST rows."""
    pdf = render_platform_tax_invoice(
        invoice_number="SS/PLF/25-26/000002",
        invoice_date=datetime(2025, 6, 1),
        supplier=SUPPLIER,
        recipient={**RECIPIENT, "state_code": "MH"},
        line={"description": "Maintenance fee", "period": "2025-06"},
        cgst=0, sgst=0, igst=89.91,
        base_amount=499.50, total=589.41,
        hsn_sac="998599", place_of_supply="MH",
    )
    assert _is_pdf(pdf)


def test_settlement_statement_renders_with_lines():
    pdf = render_settlement_statement(
        statement_number="SS/STM/25-26/000001",
        owner_name="Acme Reading Rooms Pvt Ltd",
        owner_gstin="29ACMEZ1234Z1Z5",
        bank_masked="HDFC ****4421",
        period_start=datetime(2025, 5, 1),
        period_end=datetime(2025, 5, 31),
        totals={
            "gross": 84000.00, "refunds": 3000.00,
            "tcs": 357.00, "tds": 71.40, "offset": 588.82,
            "net": 79982.78,
        },
        payout_ref="HDFC1234567890",
        payout_at=datetime(2025, 6, 3),
        lines=[
            {"kind": "BOOKING", "reference_id": "bk-1", "base_amount": 2500.0,
             "deduction": 0, "net": 2500.0},
            {"kind": "TCS_CGST", "reference_id": None, "base_amount": 0,
             "deduction": 178.50, "net": -178.50},
        ],
    )
    assert _is_pdf(pdf)


def test_settlement_statement_renders_empty():
    pdf = render_settlement_statement(
        statement_number="SS/STM/25-26/000002",
        owner_name="Solo Owner",
        owner_gstin=None,
        bank_masked=None,
        period_start=datetime(2025, 5, 1),
        period_end=datetime(2025, 5, 31),
        totals={"gross": 0, "refunds": 0, "tcs": 0, "tds": 0,
                "offset": 0, "net": 0},
        payout_ref=None, payout_at=None, lines=[],
    )
    assert _is_pdf(pdf)


def test_credit_note_renders():
    pdf = render_credit_note(
        credit_note_number="SS/CN/25-26/000001",
        original_invoice_number="SS/OBI/25-26/000123",
        issue_date=datetime(2025, 6, 4),
        supplier=RECIPIENT,
        recipient={"legal_name": "Ananya R", "gstin": None, "state_code": "KA"},
        reason="SERVICE_ISSUE",
        base_amount=423.73, cgst=38.14, sgst=38.13, igst=0,
        total=500.00, hsn_sac="996311", place_of_supply="KA",
    )
    assert _is_pdf(pdf)


def test_owner_tax_invoice_renders():
    """OWNER_TAX_INVOICE (booking) — registered owner, intra-state."""
    pdf = render_owner_tax_invoice(
        invoice_number="SS/OBI/25-26/000001",
        invoice_date=datetime(2025, 6, 4),
        supplier=RECIPIENT,                       # owner (with GSTIN)
        recipient={"legal_name": "Ananya R", "gstin": None, "state_code": "KA"},
        line={"description": "Cabin 12 — Acme Reading Room", "period": "Jun 2025"},
        cgst=190.68, sgst=190.68, igst=0,
        base_amount=2118.64, total=2500.00,
        hsn_sac="996311", place_of_supply="KA",
    )
    assert _is_pdf(pdf)


def test_eco_tax_invoice_renders():
    """ECO_TAX_INVOICE — Sec 9(5) deemed supplier (platform is the supplier)."""
    pdf = render_eco_tax_invoice(
        invoice_number="SS/ECO/25-26/000001",
        invoice_date=datetime(2025, 6, 4),
        platform_party=SUPPLIER,
        underlying_owner={"legal_name": "Comfort Stays"},
        recipient={"legal_name": "Ananya R", "gstin": None, "state_code": "KA"},
        line={"description": "Short-stay accommodation", "period": "Jun 2025"},
        cgst=190.68, sgst=190.68, igst=0,
        base_amount=2118.64, total=2500.00,
        hsn_sac="996311", place_of_supply="KA",
    )
    assert _is_pdf(pdf)


def test_non_gst_receipt_renders():
    """NON_GST_RECEIPT — unregistered owner, supply not covered by Sec 9(5)."""
    pdf = render_non_gst_receipt(
        receipt_number="SS/RCT/25-26/000001",
        receipt_date=datetime(2025, 6, 4),
        supplier={"legal_name": "Bharat Lodge", "gstin": None, "state_code": "KA"},
        recipient={"legal_name": "Ananya R", "gstin": None, "state_code": "KA"},
        line={"description": "Hostel bed — monthly", "period": "Jun 2025"},
        total=1800.00,
    )
    assert _is_pdf(pdf)
