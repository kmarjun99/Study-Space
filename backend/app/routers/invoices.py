"""
Invoice Generation API Router
Handles:
- GET /bookings/{booking_id}/invoice - Download PDF invoice for a booking
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime
from io import BytesIO

from app.database import get_db
from app.deps import get_current_user
from app.models.user import User, UserRole
from app.models.booking import Booking, BookingStatus, PaymentStatus
from app.models.invoice import Invoice, InvoiceDocType, generate_invoice_number
from app.models.party import Party
from app.models.reading_room import ReadingRoom, Cabin
from app.models.accommodation import Accommodation
from app.models.payment_transaction import PaymentTransaction
from app.services.booking_validator import booking_validator
from app.services.invoice_pdf_service import (
    render_eco_tax_invoice,
    render_non_gst_receipt,
    render_owner_tax_invoice,
)
from app.services.invoice_series_service import (
    InvoiceSeriesService,
    current_fiscal_year,
)

router = APIRouter(tags=["Invoices"])


def generate_pdf_invoice(invoice_data: dict) -> BytesIO:
    """
    Generate a professional PDF invoice using reportlab.
    Falls back to a simple text-based PDF if reportlab is not available.
    """
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib import colors
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch, mm
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
        from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
        
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
        
        elements = []
        styles = getSampleStyleSheet()
        
        # Custom styles
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#4F46E5'),
            spaceAfter=20,
            alignment=TA_CENTER
        )
        
        header_style = ParagraphStyle(
            'Header',
            parent=styles['Normal'],
            fontSize=12,
            textColor=colors.HexColor('#374151'),
            spaceAfter=5
        )
        
        # Header
        elements.append(Paragraph("mySpace", title_style))
        elements.append(Paragraph("TAX INVOICE", ParagraphStyle('InvoiceTitle', parent=styles['Heading2'], alignment=TA_CENTER, textColor=colors.HexColor('#1F2937'))))
        elements.append(Spacer(1, 20))
        
        # Invoice details table
        invoice_info = [
            ['Invoice Number:', invoice_data.get('invoice_number', 'N/A')],
            ['Invoice Date:', invoice_data.get('invoice_date', 'N/A')],
            ['Booking ID:', invoice_data.get('booking_id', 'N/A')[:8] + '...'],
        ]
        
        t = Table(invoice_info, colWidths=[120, 200])
        t.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#374151')),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ]))
        elements.append(t)
        elements.append(Spacer(1, 30))
        
        # Billed To section
        elements.append(Paragraph("<b>BILLED TO:</b>", header_style))
        elements.append(Paragraph(invoice_data.get('user_name', 'N/A'), styles['Normal']))
        elements.append(Paragraph(invoice_data.get('user_email', 'N/A'), styles['Normal']))
        elements.append(Spacer(1, 20))
        
        # Venue details
        elements.append(Paragraph("<b>SERVICE DETAILS:</b>", header_style))
        elements.append(Spacer(1, 10))
        
        service_data = [
            ['Venue:', invoice_data.get('venue_name', 'N/A')],
            ['Address:', invoice_data.get('venue_address', 'N/A')],
            ['Seat/Room:', invoice_data.get('seat_details', 'N/A')],
            ['Duration:', invoice_data.get('plan_duration', 'N/A')],
            ['Start Date:', invoice_data.get('start_date', 'N/A')],
            ['End Date:', invoice_data.get('end_date', 'N/A')],
        ]
        
        t2 = Table(service_data, colWidths=[100, 350])
        t2.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#374151')),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        elements.append(t2)
        elements.append(Spacer(1, 30))
        
        # Payment summary
        elements.append(Paragraph("<b>PAYMENT SUMMARY:</b>", header_style))
        elements.append(Spacer(1, 10))
        
        amount = invoice_data.get('amount', 0)
        tax = invoice_data.get('tax_amount', 0)
        total = invoice_data.get('total_amount', amount)
        
        payment_data = [
            ['Description', 'Amount'],
            ['Booking Charge', f"₹{amount:,.2f}"],
            ['Tax (GST)', f"₹{tax:,.2f}"],
            ['', ''],
            ['TOTAL PAID', f"₹{total:,.2f}"],
        ]
        
        t3 = Table(payment_data, colWidths=[350, 100])
        t3.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTNAME', (0, 1), (-1, -2), 'Helvetica'),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#374151')),
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#F3F4F6')),
            ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#4F46E5')),
            ('TEXTCOLOR', (0, -1), (-1, -1), colors.white),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
            ('TOPPADDING', (0, 0), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -2), 0.5, colors.HexColor('#E5E7EB')),
        ]))
        elements.append(t3)
        elements.append(Spacer(1, 30))
        
        # Payment details
        if invoice_data.get('payment_method'):
            elements.append(Paragraph(f"<b>Payment Method:</b> {invoice_data.get('payment_method', 'N/A')}", styles['Normal']))
        if invoice_data.get('transaction_id'):
            elements.append(Paragraph(f"<b>Transaction ID:</b> {invoice_data.get('transaction_id', 'N/A')}", styles['Normal']))
        elements.append(Spacer(1, 10))
        
        # Status badge
        elements.append(Paragraph("✅ <b>PAID</b>", ParagraphStyle('Paid', parent=styles['Normal'], fontSize=14, textColor=colors.HexColor('#059669'))))
        elements.append(Spacer(1, 40))
        
        # Footer
        footer_style = ParagraphStyle('Footer', parent=styles['Normal'], fontSize=9, textColor=colors.HexColor('#9CA3AF'), alignment=TA_CENTER)
        elements.append(Paragraph("This is a computer-generated invoice and does not require a signature.", footer_style))
        elements.append(Paragraph("For any queries, contact support@studyspace.in", footer_style))
        
        doc.build(elements)
        buffer.seek(0)
        return buffer
        
    except ImportError as e:
        # Fallback: Use fpdf if reportlab not available
        print(f"reportlab not available: {e}, using fpdf fallback")
        try:
            from fpdf import FPDF
            
            buffer = BytesIO()
            pdf = FPDF()
            pdf.add_page()
            pdf.set_font("Arial", "B", 16)
            pdf.cell(0, 10, "STUDYSPACE - TAX INVOICE", ln=True, align="C")
            pdf.ln(10)
            
            pdf.set_font("Arial", "", 10)
            pdf.cell(0, 6, f"Invoice Number: {invoice_data.get('invoice_number', 'N/A')}", ln=True)
            pdf.cell(0, 6, f"Invoice Date: {invoice_data.get('invoice_date', 'N/A')}", ln=True)
            pdf.cell(0, 6, f"Booking ID: {invoice_data.get('booking_id', 'N/A')}", ln=True)
            pdf.ln(5)
            
            pdf.set_font("Arial", "B", 11)
            pdf.cell(0, 6, "BILLED TO:", ln=True)
            pdf.set_font("Arial", "", 10)
            pdf.cell(0, 6, invoice_data.get('user_name', 'N/A'), ln=True)
            pdf.cell(0, 6, invoice_data.get('user_email', 'N/A'), ln=True)
            pdf.ln(5)
            
            pdf.set_font("Arial", "B", 11)
            pdf.cell(0, 6, "SERVICE DETAILS:", ln=True)
            pdf.set_font("Arial", "", 10)
            pdf.cell(0, 6, f"Venue: {invoice_data.get('venue_name', 'N/A')}", ln=True)
            pdf.cell(0, 6, f"Address: {invoice_data.get('venue_address', 'N/A')}", ln=True)
            pdf.cell(0, 6, f"Seat/Room: {invoice_data.get('seat_details', 'N/A')}", ln=True)
            pdf.cell(0, 6, f"Duration: {invoice_data.get('plan_duration', 'N/A')}", ln=True)
            pdf.cell(0, 6, f"Start Date: {invoice_data.get('start_date', 'N/A')}", ln=True)
            pdf.cell(0, 6, f"End Date: {invoice_data.get('end_date', 'N/A')}", ln=True)
            pdf.ln(5)
            
            pdf.set_font("Arial", "B", 11)
            pdf.cell(0, 6, "PAYMENT SUMMARY:", ln=True)
            pdf.set_font("Arial", "", 10)
            pdf.cell(0, 6, f"Amount: Rs {invoice_data.get('amount', 0):,.2f}", ln=True)
            pdf.cell(0, 6, f"Tax: Rs {invoice_data.get('tax_amount', 0):,.2f}", ln=True)
            pdf.set_font("Arial", "B", 11)
            pdf.cell(0, 6, f"Total Paid: Rs {invoice_data.get('total_amount', 0):,.2f}", ln=True)
            pdf.ln(5)
            
            pdf.set_font("Arial", "", 10)
            pdf.cell(0, 6, f"Payment Method: {invoice_data.get('payment_method', 'N/A')}", ln=True)
            pdf.cell(0, 6, f"Transaction ID: {invoice_data.get('transaction_id', 'N/A')}", ln=True)
            pdf.ln(10)
            
            pdf.set_font("Arial", "B", 12)
            pdf.set_text_color(0, 150, 0)
            pdf.cell(0, 6, "STATUS: PAID", ln=True, align="C")
            
            buffer.write(pdf.output(dest='S').encode('latin-1'))
            buffer.seek(0)
            return buffer
            
        except ImportError:
            # Last resort: Return error message
            raise HTTPException(
                status_code=500,
                detail="PDF generation library not available. Please contact support."
            )
        return buffer


@router.get("/bookings/{booking_id}/invoice")
async def download_invoice(
    booking_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Generate and download PDF invoice for a booking.
    - Validates user owns the booking
    - Only for PAID bookings
    - Creates invoice record if not exists
    """
    # Get booking
    result = await db.execute(
        select(Booking).where(Booking.id == booking_id)
    )
    booking = result.scalar_one_or_none()
    
    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Booking not found"
        )
    
    # Validate ownership - Allow:
    # 1. Student who made the booking
    # 2. Super Admin
    # 3. Venue owner (for bookings at their venue)
    is_student = booking.user_id == current_user.id
    is_super_admin = current_user.role == UserRole.SUPER_ADMIN
    is_venue_owner = False
    
    # Check if current user owns the venue
    if booking.cabin_id:
        cabin_result = await db.execute(
            select(Cabin).where(Cabin.id == booking.cabin_id)
        )
        cabin = cabin_result.scalar_one_or_none()
        if cabin:
            room_result = await db.execute(
                select(ReadingRoom).where(ReadingRoom.id == cabin.reading_room_id)
            )
            room = room_result.scalar_one_or_none()
            if room and room.owner_id == current_user.id:
                is_venue_owner = True
    elif booking.accommodation_id:
        acc_result = await db.execute(
            select(Accommodation).where(Accommodation.id == booking.accommodation_id)
        )
        acc = acc_result.scalar_one_or_none()
        if acc and acc.owner_id == current_user.id:
            is_venue_owner = True
    
    # Deny access if none of the conditions are met
    if not (is_student or is_super_admin or is_venue_owner):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only download invoices for your own bookings or bookings at your venues"
        )
    
    # Check payment status
    if booking.payment_status != PaymentStatus.PAID:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invoice can only be generated for paid bookings"
        )
    
    # Get user info
    user_result = await db.execute(
        select(User).where(User.id == booking.user_id)
    )
    user = user_result.scalar_one_or_none()
    
    # Get venue info
    venue_name = "Unknown Venue"
    venue_address = ""
    seat_details = ""
    
    if booking.cabin_id:
        cabin_result = await db.execute(
            select(Cabin).where(Cabin.id == booking.cabin_id)
        )
        cabin = cabin_result.scalar_one_or_none()
        if cabin:
            seat_details = f"Cabin {cabin.number}, Floor {cabin.floor}"
            room_result = await db.execute(
                select(ReadingRoom).where(ReadingRoom.id == cabin.reading_room_id)
            )
            room = room_result.scalar_one_or_none()
            if room:
                venue_name = room.name
                venue_address = room.address or ""
    elif booking.accommodation_id:
        acc_result = await db.execute(
            select(Accommodation).where(Accommodation.id == booking.accommodation_id)
        )
        acc = acc_result.scalar_one_or_none()
        if acc:
            venue_name = acc.name
            venue_address = acc.address or ""
            seat_details = f"{acc.type} - {acc.sharing} Sharing"
    
    # Get payment transaction if exists
    payment_method = "Online Payment"
    transaction_id = booking.transaction_id or ""
    
    payment_result = await db.execute(
        select(PaymentTransaction).where(PaymentTransaction.booking_id == booking_id)
    )
    payment = payment_result.scalar_one_or_none()
    if payment:
        payment_method = payment.method.value if payment.method else "Online Payment"
        transaction_id = payment.gateway_transaction_id or transaction_id
    
    # Check if invoice already exists
    invoice_result = await db.execute(
        select(Invoice).where(Invoice.booking_id == booking_id)
    )
    invoice = invoice_result.scalar_one_or_none()
    
    if not invoice:
        # Plan duration label (new bookings carry `duration_type`; legacy ones
        # are date-derived).
        if hasattr(booking, 'duration_type') and booking.duration_type:
            plan_duration = booking_validator.format_duration_label(booking.duration_type)
        else:
            duration_days = (booking.end_date - booking.start_date).days if booking.end_date and booking.start_date else 30
            duration_months = max(1, duration_days // 30)
            plan_duration = f"{duration_months} Month{'s' if duration_months > 1 else ''}"

        # Persisted GST split derives from whatever the accounting shadow
        # froze on the booking at payment time:
        #   * Accounting was OFF when paid → base_amount/gst_amount are NULL
        #     → invoice is LEGACY: amount=gross, tax=0, total=gross. No
        #     historical row is mutated; old screenshots stay correct.
        #   * Accounting was ON when paid → booking carries Decimal base/gst.
        #     Persist them as floats (legacy column type) so the PDF helper
        #     and any external accounting export see the same numbers.
        base_attr = getattr(booking, "base_amount", None)
        gst_attr = getattr(booking, "gst_amount", None)
        treatment_attr = getattr(booking, "gst_treatment", None)
        has_split = (
            base_attr is not None and gst_attr is not None
            and treatment_attr is not None
            and treatment_attr.value not in ("NOT_COMPUTED", "LEGACY")
        )

        if has_split:
            persisted_base = float(base_attr)
            persisted_tax = float(gst_attr)
            persisted_total = float(booking.amount)
            # Allocate a real, sequential, collision-free invoice number in
            # the appropriate series for the booking's treatment. Falls back
            # to LEGACY numbering on failure so the download never breaks.
            series_code = _series_for_treatment(treatment_attr.value)
            doc_type = _doc_type_for_treatment(treatment_attr.value)
            try:
                invoice_number, fy, seq_no = await InvoiceSeriesService.next_number(
                    db, series_code=series_code,
                )
            except Exception:
                invoice_number = generate_invoice_number()
                fy, seq_no, doc_type, series_code = None, None, InvoiceDocType.LEGACY, None
            # CGST/SGST split mirrors what the accounting shadow already
            # decided (intra-state vs inter-state). Render time will re-read
            # these from the row, so we MUST persist them now.
            place_state = getattr(booking, "place_of_supply_state", None)
            cgst_val, sgst_val, igst_val = _split_state_gst(
                persisted_tax, place_state,
            )
        else:
            persisted_base = booking.amount
            persisted_tax = 0
            persisted_total = booking.amount
            invoice_number = generate_invoice_number()
            doc_type = InvoiceDocType.LEGACY
            series_code, fy, seq_no = None, None, None
            cgst_val = sgst_val = igst_val = 0
            place_state = None

        invoice = Invoice(
            invoice_number=invoice_number,
            booking_id=booking_id,
            user_id=booking.user_id,
            amount=persisted_base,
            tax_amount=persisted_tax,
            total_amount=persisted_total,
            venue_name=venue_name,
            venue_address=venue_address,
            seat_details=seat_details,
            plan_duration=plan_duration,
            start_date=booking.start_date,
            end_date=booking.end_date,
            doc_type=doc_type,
            series_code=series_code,
            fiscal_year=fy,
            sequence_no=seq_no,
            place_of_supply_state=place_state,
            cgst=cgst_val,
            sgst=sgst_val,
            igst=igst_val,
            base_amount=persisted_base if has_split else None,
            tax_snapshot_id=getattr(booking, "frozen_tax_snapshot_id", None),
        )
        db.add(invoice)
        await db.commit()
        await db.refresh(invoice)
    
    # Prepare invoice data
    invoice_data = {
        'invoice_number': invoice.invoice_number,
        'invoice_date': invoice.generated_at.strftime('%d %B %Y') if invoice.generated_at else datetime.utcnow().strftime('%d %B %Y'),
        'booking_id': booking_id,
        'user_name': user.name if user else 'Customer',
        'user_email': user.email if user else '',
        'venue_name': venue_name,
        'venue_address': venue_address,
        'seat_details': seat_details,
        'plan_duration': invoice.plan_duration or 'N/A',
        'start_date': booking.start_date.strftime('%d %B %Y') if booking.start_date else 'N/A',
        'end_date': booking.end_date.strftime('%d %B %Y') if booking.end_date else 'N/A',
        'amount': invoice.amount,
        'tax_amount': invoice.tax_amount,
        'total_amount': invoice.total_amount,
        'payment_method': payment_method,
        'transaction_id': transaction_id
    }
    
    # ---- doc_type dispatch ----
    # Legacy invoices (and any row pre-dating the GST-aware engine) keep using
    # the existing renderer. GST-aware doc_types are rendered with the new
    # templates from invoice_pdf_service. Settlement/credit-note doc_types
    # don't belong on a booking endpoint and fall through to legacy.
    doc_type = invoice.doc_type if invoice.doc_type else InvoiceDocType.LEGACY
    pdf_bytes_or_buffer = await _render_for_doc_type(
        db, invoice, booking, doc_type, invoice_data,
    )
    filename = f"Invoice_{invoice.invoice_number.replace('/', '_')}.pdf"

    if isinstance(pdf_bytes_or_buffer, BytesIO):
        return StreamingResponse(
            pdf_bytes_or_buffer,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )
    # New renderers return raw bytes
    from fastapi.responses import Response
    return Response(
        content=pdf_bytes_or_buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


def _series_for_treatment(treatment: str) -> str:
    """Pick the right per-FY invoice series for a booking's GST treatment.

    Matches the design doc §6: OBI = Owner-billed Invoice (owner-issued),
    ECO = E-Commerce Operator (Sec 9(5), platform issues), RCT = non-GST
    receipt.
    """
    if treatment == "OWNER_REGISTERED":
        return "OBI"
    if treatment == "SEC_9_5":
        return "ECO"
    # NOT_REGISTERED, EXEMPT — no GST involved, plain receipt series.
    return "RCT"


def _doc_type_for_treatment(treatment: str) -> InvoiceDocType:
    if treatment == "OWNER_REGISTERED":
        return InvoiceDocType.OWNER_TAX_INVOICE
    if treatment == "SEC_9_5":
        return InvoiceDocType.ECO_TAX_INVOICE
    return InvoiceDocType.NON_GST_RECEIPT


def _split_state_gst(
    gst_amount: float, place_of_supply_state: str | None,
) -> tuple[float, float, float]:
    """Decide CGST/SGST vs IGST.

    Looks up the platform's home state from `tax_config` lazily; if either
    state is missing we conservatively bucket everything as IGST so the
    total still ties. Render layer reads cgst/sgst/igst back from the row
    so persisting this split is what makes the PDF accurate.
    """
    if not gst_amount or gst_amount <= 0:
        return (0.0, 0.0, 0.0)
    try:
        import os
        platform_state = (os.getenv("PLATFORM_HOME_STATE") or "").upper()
    except Exception:
        platform_state = ""
    pos = (place_of_supply_state or "").upper()
    intra = bool(platform_state and pos and platform_state == pos)
    if intra:
        half = round(gst_amount / 2, 2)
        return (half, round(gst_amount - half, 2), 0.0)
    return (0.0, 0.0, round(gst_amount, 2))


async def _render_for_doc_type(
    db: AsyncSession,
    invoice: Invoice,
    booking: Booking,
    doc_type: InvoiceDocType,
    legacy_data: dict,
):
    """Pick the right renderer based on `doc_type`.

    Falls back to legacy on any missing supporting data so a misconfigured
    invoice never crashes the student's download. PLATFORM_TAX_INVOICE is
    served from /owner/charges/{id}/invoice/pdf — if one is ever reached
    here it indicates misclassification, so we still fall through to the
    legacy renderer rather than 500.
    """
    if doc_type in (InvoiceDocType.LEGACY,
                    InvoiceDocType.SETTLEMENT_STATEMENT,
                    InvoiceDocType.CREDIT_NOTE):
        return generate_pdf_invoice(legacy_data)

    supplier = (await db.get(Party, invoice.supplier_party_id)
                if invoice.supplier_party_id else None)
    recipient = (await db.get(Party, invoice.recipient_party_id)
                 if invoice.recipient_party_id else None)
    supplier_dict = _party_dict(supplier)
    recipient_dict = _party_dict(recipient)

    line = {
        "description": invoice.seat_details or f"Booking {booking.id[:8]}",
        "period": invoice.plan_duration or "—",
    }
    common = dict(
        invoice_number=invoice.invoice_number,
        invoice_date=invoice.generated_at,
        recipient=recipient_dict,
        line=line,
        cgst=float(invoice.cgst or 0),
        sgst=float(invoice.sgst or 0),
        igst=float(invoice.igst or 0),
        base_amount=float(invoice.base_amount or invoice.amount),
        total=float(invoice.total_amount),
        hsn_sac=invoice.hsn_sac,
        place_of_supply=invoice.place_of_supply_state,
    )

    if doc_type == InvoiceDocType.OWNER_TAX_INVOICE:
        return render_owner_tax_invoice(supplier=supplier_dict, **common)
    if doc_type == InvoiceDocType.ECO_TAX_INVOICE:
        return render_eco_tax_invoice(
            platform_party=supplier_dict,
            underlying_owner={"legal_name": supplier_dict.get("legal_name", "—")},
            **common,
        )
    if doc_type == InvoiceDocType.NON_GST_RECEIPT:
        return render_non_gst_receipt(
            receipt_number=invoice.invoice_number,
            receipt_date=invoice.generated_at,
            supplier=supplier_dict,
            recipient=recipient_dict,
            line=line,
            total=float(invoice.total_amount),
        )
    # Unknown doc_type — fall back rather than crash.
    return generate_pdf_invoice(legacy_data)


def _party_dict(p) -> dict:
    if p is None:
        return {}
    return {
        "legal_name": p.legal_name,
        "address": p.address,
        "gstin": p.gstin,
        "state_code": p.state_code,
    }
