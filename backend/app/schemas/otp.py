from pydantic import BaseModel, EmailStr
from datetime import datetime
from typing import Optional


class OTPRequest(BaseModel):
    email: EmailStr
    phone: Optional[str] = None  # No longer used, kept for backward compatibility
    otp_type: str  # 'registration', 'password_reset', 'phone_verification'


class OTPVerify(BaseModel):
    email: EmailStr
    otp_code: str
    otp_type: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    email: EmailStr
    otp_code: str
    new_password: str


class OTPResponse(BaseModel):
    success: bool
    message: str
    expires_in_seconds: Optional[int] = None


class PasswordResetResponse(BaseModel):
    success: bool
    message: str
