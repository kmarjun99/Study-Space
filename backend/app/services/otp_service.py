"""
OTP Service - Handles OTP generation, storage, verification
Supports both Email and SMS delivery
"""

import random
import string
from datetime import datetime, timedelta, timezone
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import and_

from app.models.otp import OTP, PasswordReset
from app.models.user import User
from app.services.email_service import send_otp_email, send_password_reset_email


def generate_otp(length: int = 6) -> str:
    """Generate a random numeric OTP"""
    return ''.join(random.choices(string.digits, k=length))


def generate_reset_token() -> str:
    """Generate a secure reset token"""
    return ''.join(random.choices(string.ascii_letters + string.digits, k=32))


async def send_otp_sms(phone: str, otp_code: str, otp_type: str = "verification") -> bool:
    """
    Send OTP via SMS (Placeholder for SMS service integration)
    
    Integration options:
    - Twilio
    - AWS SNS
    - MSG91 (for India)
    - Fast2SMS (for India)
    
    For now, this returns True and logs to console (demo mode)
    """
    print(f"📱 SMS OTP: {otp_code} to {phone} (Type: {otp_type})")
    print(f"⚠️  SMS service not configured. Configure Twilio/MSG91 in production.")
    
    # In production, integrate with SMS provider:
    # try:
    #     # Example with Twilio:
    #     # client = Client(account_sid, auth_token)
    #     # message = client.messages.create(
    #     #     body=f"Your StudySpace verification code is: {otp_code}",
    #     #     from_=twilio_phone,
    #     #     to=phone
    #     # )
    #     return True
    # except Exception as e:
    #     print(f"Failed to send SMS: {e}")
    #     return False
    
    return True  # Demo mode - always succeeds


from fastapi import BackgroundTasks

async def create_otp(
    db: AsyncSession,
    email: str,
    phone: Optional[str],
    otp_type: str,
    expires_in_minutes: int = 10,
    background_tasks: Optional[BackgroundTasks] = None
) -> tuple[str, int]:
    """
    Create and send OTP to user
    
    Returns:
    tuple: (otp_code, expires_in_seconds)
    """
    # Invalidate any existing OTPs for this email/type
    result = await db.execute(
        select(OTP).where(
            and_(
                OTP.user_email == email,
                OTP.otp_type == otp_type,
                OTP.is_verified == False
            )
        )
    )
    existing_otps = result.scalars().all()
    for otp in existing_otps:
        otp.is_verified = True  # Mark as used
    
    # Generate new OTP
    otp_code = generate_otp()
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=expires_in_minutes)
    
    # Store in database
    new_otp = OTP(
        user_email=email,
        user_phone=phone,
        otp_code=otp_code,
        otp_type=otp_type,
        expires_at=expires_at
    )
    db.add(new_otp)
    await db.commit()
    
    # Get user name if exists
    user_result = await db.execute(select(User).where(User.email == email))
    user = user_result.scalars().first()
    user_name = user.name if user else "User"
    
    # Send OTP via email only
    if background_tasks:
        background_tasks.add_task(send_otp_email, email, user_name, otp_code, otp_type)
        print(f"✅ OTP created: {otp_code} for {email} (Email scheduled in background)")
    else:
        email_sent = await send_otp_email(email, user_name, otp_code, otp_type)
        print(f"✅ OTP created: {otp_code} for {email} (Email sent: {email_sent})")
    
    return otp_code, expires_in_minutes * 60


async def verify_otp(
    db: AsyncSession,
    email: str,
    otp_code: str,
    otp_type: str
) -> tuple[bool, str]:
    """
    Verify OTP code
    
    Returns:
        tuple: (success: bool, message: str)
    """
    result = await db.execute(
        select(OTP).where(
            and_(
                OTP.user_email == email,
                OTP.otp_type == otp_type,
                OTP.is_verified == False
            )
        ).order_by(OTP.created_at.desc())
    )
    otp = result.scalars().first()
    
    if not otp:
        return False, "No OTP found. Please request a new one."
    
    # Increment attempts
    otp.attempts += 1
    await db.commit()
    
    if otp.attempts > 5:
        return False, "Too many attempts. Please request a new OTP."
    
    if otp.is_expired():
        return False, "OTP has expired. Please request a new one."
    
    if otp.otp_code != otp_code:
        return False, f"Invalid OTP. {5 - otp.attempts} attempts remaining."
    
    # Mark as verified
    otp.is_verified = True
    await db.commit()
    
    return True, "OTP verified successfully"


async def create_password_reset(
    db: AsyncSession,
    email: str,
    background_tasks: Optional[BackgroundTasks] = None
) -> tuple[bool, str, Optional[int]]:
    """
    Create password reset request and send OTP
    
    Returns:
        tuple: (success: bool, message: str, expires_in_seconds: Optional[int])
    """
    # Check if user exists
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalars().first()
    
    if not user:
        # Don't reveal if user exists or not (security best practice)
        return True, "If an account exists with this email, you will receive a password reset code.", None
    
    # Use the same create_otp function for consistency
    otp_code, expires_in = await create_otp(
        db=db,
        email=email,
        phone=None,
        otp_type='password_reset',
        expires_in_minutes=10,
        background_tasks=background_tasks
    )
    
    print(f"🔐 Password reset OTP: {otp_code} for {email}")
    
    return True, "Password reset code sent to your email.", expires_in


async def reset_password_with_otp(
    db: AsyncSession,
    email: str,
    otp_code: str,
    new_password: str
) -> tuple[bool, str]:
    """
    Reset password using OTP
    
    Returns:
        tuple: (success: bool, message: str)
    """
    from app.core.security import get_password_hash
    
    # Find OTP - accept both verified and unverified for password reset
    # (it might be verified from the OTP modal already)
    result = await db.execute(
        select(OTP).where(
            and_(
                OTP.user_email == email,
                OTP.otp_code == otp_code,
                OTP.otp_type == 'password_reset'
            )
        ).order_by(OTP.created_at.desc())
    )
    otp = result.scalars().first()
    
    if not otp:
        return False, "Invalid or expired reset code."
    
    if otp.is_expired():
        return False, "Reset code has expired. Please request a new one."
    
    # Get user
    user_result = await db.execute(select(User).where(User.email == email))
    user = user_result.scalars().first()
    
    if not user:
        return False, "User not found."
    
    # Update password
    user.hashed_password = get_password_hash(new_password)
    otp.is_verified = True  # Mark as used
    
    await db.commit()
    
    print(f"✅ Password reset successful for {email}")
    
    return True, "Password reset successful. You can now log in with your new password."
