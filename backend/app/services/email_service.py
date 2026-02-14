from fastapi_mail import FastMail, MessageSchema, ConnectionConfig, MessageType
from pydantic import EmailStr
from typing import List, Optional
import os
from pathlib import Path
from app.core.config import settings

# Email configuration
conf = ConnectionConfig(
    MAIL_USERNAME=settings.mail_username or os.getenv("mail_username", ""),
    MAIL_PASSWORD=settings.mail_password or os.getenv("mail_password", ""),
    MAIL_FROM=settings.mail_from or os.getenv("mail_from", "noreply@studyspace.com"),
    MAIL_PORT=settings.mail_port or int(os.getenv("mail_port", "587")),
    MAIL_SERVER=settings.mail_server or os.getenv("mail_server", "smtp.gmail.com"),
    MAIL_STARTTLS=True,
    MAIL_SSL_TLS=False,
    USE_CREDENTIALS=True,
    VALIDATE_CERTS=True,
    TEMPLATE_FOLDER=Path(__file__).parent.parent / 'templates' / 'email'
)

fm = FastMail(conf)


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
        message = MessageSchema(
            subject="Booking Confirmation - StudySpace",
            recipients=[recipient_email],
            template_body={
                "recipient_name": recipient_name,
                **booking_details
            },
            subtype=MessageType.html
        )
        
        await fm.send_message(message, template_name="booking_confirmation.html")
        return True
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
        message = MessageSchema(
            subject="Booking Extended - StudySpace",
            recipients=[recipient_email],
            template_body={
                "recipient_name": recipient_name,
                **extension_details
            },
            subtype=MessageType.html
        )
        
        await fm.send_message(message, template_name="booking_extension.html")
        return True
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
        message = MessageSchema(
            subject="Your Inquiry Has Been Answered - StudySpace",
            recipients=[recipient_email],
            template_body={
                "recipient_name": recipient_name,
                **inquiry_details
            },
            subtype=MessageType.html
        )
        
        await fm.send_message(message, template_name="inquiry_response.html")
        return True
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
        message = MessageSchema(
            subject="New Inquiry for Your Venue - StudySpace",
            recipients=[recipient_email],
            template_body={
                "recipient_name": recipient_name,
                **inquiry_details
            },
            subtype=MessageType.html
        )
        
        await fm.send_message(message, template_name="new_inquiry_notification.html")
        return True
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
        
        message = MessageSchema(
            subject=subject_map.get(otp_type, "Your OTP - StudySpace"),
            recipients=[recipient_email],
            body=html_content,
            subtype=MessageType.html
        )
        
        await fm.send_message(message)
        return True
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
