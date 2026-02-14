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
from app.models.invoice import Invoice, generate_invoice_number
from app.models.reading_room import ReadingRoom, Cabin
from app.models.accommodation import Accommodation
from app.models.payment_transaction import PaymentTransaction

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
        elements.append(Paragraph("StudySpace", title_style))
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
    
    # Validate ownership (users can only download their own invoices)
    # Super Admin can download any invoice
    if booking.user_id != current_user.id and current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only download invoices for your own bookings"
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
        # Create new invoice
        invoice_number = generate_invoice_number()
        
        # Calculate duration
        duration_days = (booking.end_date - booking.start_date).days if booking.end_date and booking.start_date else 30
        duration_months = max(1, duration_days // 30)
        plan_duration = f"{duration_months} Month{'s' if duration_months > 1 else ''}"
        
        invoice = Invoice(
            invoice_number=invoice_number,
            booking_id=booking_id,
            user_id=booking.user_id,
            amount=booking.amount,
            tax_amount=0,  # No separate tax for now
            total_amount=booking.amount,
            venue_name=venue_name,
            venue_address=venue_address,
            seat_details=seat_details,
            plan_duration=plan_duration,
            start_date=booking.start_date,
            end_date=booking.end_date
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
    
    # Generate PDF
    pdf_buffer = generate_pdf_invoice(invoice_data)
    
    # Return as downloadable PDF
    filename = f"Invoice_{invoice.invoice_number}.pdf"
    
    return StreamingResponse(
        pdf_buffer,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename={filename}"
        }
    )
