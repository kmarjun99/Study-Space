from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Email, To, Content
from pydantic import EmailStr
from typing import List, Optional
import os
from pathlib import Path
from app.core.config import settings

# SendGrid configuration
SENDGRID_API_KEY = settings.sendgrid_api_key or os.getenv("SENDGRID_API_KEY", "")
MAIL_FROM = settings.mail_from or os.getenv("mail_from", "noreply@studyspace.com")

sg = SendGridAPIClient(SENDGRID_API_KEY) if SENDGRID_API_KEY else None


async def _send_email(to_email: str, subject: str, html_content: str):
    """Internal helper to send email via SendGrid"""
    if not sg:
        print("SendGrid API key not configured")
        return False
    
    try:
        message = Mail(
            from_email=MAIL_FROM,
            to_emails=to_email,
            subject=subject,
            html_content=html_content
        )
        response = sg.send(message)
        return response.status_code in [200, 201, 202]
    except Exception as e:
        print(f"Failed to send email: {e}")
        return False


async def send_booking_confirmation_email(
    recipient_email: EmailStr,
    recipient_name: str,
    booking_details: dict
):
    """
    Send booking confirmation email to user
    
    Args:
        recipient_email: User's email address
        recipient_name: User's name
        booking_details: Dictionary containing:
            - venue_name: Name of the venue/accommodation
            - booking_type: 'cabin' or 'accommodation'
            - start_date: Booking start date
            - end_date: Booking end date
            - amount: Total amount paid
            - transaction_id: Payment transaction ID
            - venue_address: Address of the venue
            - cabin_number: Cabin/room number (optional)
    """
    try:
        html_content = f"""
        <h2>Booking Confirmed!</h2>
        <p>Dear {recipient_name},</p>
        <p>Your booking has been confirmed.</p>
        <ul>
            <li><strong>Venue:</strong> {booking_details.get('venue_name')}</li>
            <li><strong>Check-in:</strong> {booking_details.get('start_date')}</li>
            <li><strong>Check-out:</strong> {booking_details.get('end_date')}</li>
            <li><strong>Amount:</strong> ₹{booking_details.get('amount')}</li>
            <li><strong>Transaction ID:</strong> {booking_details.get('transaction_id')}</li>
        </ul>
        <p>Thank you for choosing StudySpace!</p>
        """
        return await _send_email(recipient_email, "Booking Confirmation - StudySpace", html_content)
    except Exception as e:
        print(f"Failed to send booking confirmation email: {e}")
        return False


async def send_booking_extension_email(
    recipient_email: EmailStr,
    recipient_name: str,
    extension_details: dict
):
    """
    Send booking extension confirmation email
    
    Args:
        recipient_email: User's email address
        recipient_name: User's name
        extension_details: Dictionary containing:
            - venue_name: Name of the venue
            - old_end_date: Original end date
            - new_end_date: New end date
            - extension_amount: Additional amount paid
            - total_amount: Total booking amount
            - days_extended: Number of days extended
    """
    try:
        html_content = f"""
        <h2>Booking Extended!</h2>
        <p>Dear {recipient_name},</p>
        <p>Your booking has been successfully extended.</p>
        <ul>
            <li><strong>Venue:</strong> {extension_details.get('venue_name')}</li>
            <li><strong>Original End Date:</strong> {extension_details.get('old_end_date')}</li>
            <li><strong>New End Date:</strong> {extension_details.get('new_end_date')}</li>
            <li><strong>Days Extended:</strong> {extension_details.get('days_extended')}</li>
            <li><strong>Extension Amount:</strong> ₹{extension_details.get('extension_amount')}</li>
        </ul>
        """
        return await _send_email(recipient_email, "Booking Extended - StudySpace", html_content)
    except Exception as e:
        print(f"Failed to send booking extension email: {e}")
        return False


async def send_inquiry_response_email(
    recipient_email: EmailStr,
    recipient_name: str,
    inquiry_details: dict
):
    """
    Send inquiry response notification to user
    
    Args:
        recipient_email: User's email address
        recipient_name: User's name
        inquiry_details: Dictionary containing:
            - venue_name: Name of the venue
            - venue_owner: Owner's name
            - original_question: User's original question
            - response: Venue owner's response
            - venue_phone: Contact phone number
    """
    try:
        html_content = f"""
        <h2>Your Inquiry Has Been Answered!</h2>
        <p>Dear {recipient_name},</p>
        <p>The venue owner has responded to your inquiry about {inquiry_details.get('venue_name')}.</p>
        <p><strong>Your Question:</strong><br>{inquiry_details.get('original_question')}</p>
        <p><strong>Response:</strong><br>{inquiry_details.get('response')}</p>
        <p>You can contact them at: {inquiry_details.get('venue_phone')}</p>
        """
        return await _send_email(recipient_email, "Your Inquiry Has Been Answered - StudySpace", html_content)
    except Exception as e:
        print(f"Failed to send inquiry response email: {e}")
        return False


async def send_new_inquiry_notification_email(
    recipient_email: EmailStr,
    recipient_name: str,
    inquiry_details: dict
):
    """
    Send notification to venue owner about new inquiry
    
    Args:
        recipient_email: Venue owner's email
        recipient_name: Venue owner's name
        inquiry_details: Dictionary containing:
            - venue_name: Name of the venue
            - student_name: Student's name
            - student_email: Student's email
            - student_phone: Student's phone (optional)
            - question: The inquiry question
            - inquiry_date: Date of inquiry
    """
    try:
        html_content = f"""
        <h2>New Inquiry for {inquiry_details.get('venue_name')}</h2>
        <p>Dear {recipient_name},</p>
        <p>You have received a new inquiry from a student.</p>
        <ul>
            <li><strong>Student:</strong> {inquiry_details.get('student_name')}</li>
            <li><strong>Email:</strong> {inquiry_details.get('student_email')}</li>
            <li><strong>Phone:</strong> {inquiry_details.get('student_phone', 'Not provided')}</li>
        </ul>
        <p><strong>Question:</strong><br>{inquiry_details.get('question')}</p>
        """
        return await _send_email(recipient_email, "New Inquiry for Your Venue - StudySpace", html_content)
    except Exception as e:
        print(f"Failed to send new inquiry notification email: {e}")
        return False


async def send_otp_email(
    recipient_email: EmailStr,
    recipient_name: str,
    otp_code: str,
    otp_type: str = "verification"
):
    """
    Send OTP to user's email using a consistent template
    
    Args:
        recipient_email: User's email address
        recipient_name: User's name
        otp_code: 6-digit OTP code
        otp_type: Type of OTP (verification, password_reset, registration, etc.)
    """
    
    subject_map = {
        "registration": "Your Registration Code - StudySpace",
        "password_reset": "Password Reset Code - StudySpace",
        "phone_verification": "Phone Verification Code - StudySpace",
        "verification": "Your Verification Code - StudySpace"
    }
    
    # Determine the purpose message based on OTP type
    purpose_map = {
        "registration": "complete your registration",
        "password_reset": "reset your password",
        "phone_verification": "verify your phone number",
        "verification": "verify your account"
    }
    
    purpose_text = purpose_map.get(otp_type, "verify your account")
    
    try:
        # Professional email template with consistent styling
        html_content = f"""
        <!DOCTYPE html>
        <html>
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
            </head>
            <body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; background-color: #f3f4f6;">
                <div style="max-width: 600px; margin: 40px auto; background-color: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);">
                    
                    <!-- Header with gradient -->
                    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 40px 30px; text-align: center;">
                        <h1 style="color: #ffffff; margin: 0; font-size: 28px; font-weight: 700; letter-spacing: -0.5px;">StudySpace</h1>
                        <p style="color: rgba(255, 255, 255, 0.9); margin: 8px 0 0 0; font-size: 14px;">Your trusted space for learning</p>
                    </div>
                    
                    <!-- Main Content -->
                    <div style="padding: 40px 30px;">
                        <h2 style="color: #1f2937; margin: 0 0 16px 0; font-size: 24px; font-weight: 600;">Hello {recipient_name},</h2>
                        <p style="color: #4b5563; font-size: 16px; line-height: 1.6; margin: 0 0 24px 0;">
                            We received a request to {purpose_text}. Use the verification code below to proceed:
                        </p>
                        
                        <!-- OTP Box -->
                        <div style="background: linear-gradient(135deg, #f9fafb 0%, #f3f4f6 100%); padding: 32px; border-radius: 12px; text-align: center; margin: 32px 0; border: 2px solid #e5e7eb;">
                            <p style="color: #6b7280; font-size: 14px; text-transform: uppercase; letter-spacing: 1px; margin: 0 0 12px 0; font-weight: 600;">Your Verification Code</p>
                            <div style="background: #ffffff; padding: 20px; border-radius: 8px; display: inline-block; box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);">
                                <p style="color: #667eea; font-size: 42px; font-weight: 700; letter-spacing: 8px; margin: 0; font-family: 'Courier New', monospace;">{otp_code}</p>
                            </div>
                        </div>
                        
                        <!-- Important Info -->
                        <div style="background: #fef3c7; border-left: 4px solid #f59e0b; padding: 16px 20px; border-radius: 6px; margin: 24px 0;">
                            <p style="color: #92400e; font-size: 14px; margin: 0; line-height: 1.5;">
                                <strong>⏱️ Expires in 10 minutes</strong><br>
                                This code will expire in 10 minutes for security reasons.
                            </p>
                        </div>
                        
                        <p style="color: #6b7280; font-size: 14px; line-height: 1.6; margin: 24px 0 0 0;">
                            If you didn't request this code, please ignore this email or contact support if you have concerns.
                        </p>
                    </div>
                    
                    <!-- Footer -->
                    <div style="background: #f9fafb; padding: 24px 30px; border-top: 1px solid #e5e7eb;">
                        <p style="color: #9ca3af; font-size: 12px; text-align: center; margin: 0; line-height: 1.5;">
                            © 2026 StudySpace. All rights reserved.<br>
                            This is an automated message, please do not reply to this email.
                        </p>
                    </div>
                    
                </div>
            </body>
        </html>
        """
        
        return await _send_email(
            recipient_email,
            subject_map.get(otp_type, "Your OTP - StudySpace"),
            html_content
        )
    except Exception as e:
        print(f"Failed to send OTP email: {e}")
        return False


async def send_password_reset_email(
    recipient_email: EmailStr,
    recipient_name: str,
    otp_code: str
):
    """
    Send password reset OTP email
    """
    return await send_otp_email(recipient_email, recipient_name, otp_code, "password_reset")
