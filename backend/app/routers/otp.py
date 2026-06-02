"""
OTP and Password Reset Router
Handles OTP generation, verification, and password reset flows
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.otp import (
    OTPRequest,
    OTPVerify,
    ForgotPasswordRequest,
    ResetPasswordRequest,
    OTPResponse,
    PasswordResetResponse
)
from app.services import otp_service

router = APIRouter(prefix="/otp", tags=["OTP & Password Reset"])


@router.post("/send", response_model=OTPResponse)
async def send_otp(
    request: OTPRequest,
    background_tasks: BackgroundTasks, 
    db: AsyncSession = Depends(get_db)
):
    """
    Send OTP to user's email only (phone number support removed)
    
    Supported OTP types:
    - registration: For new user registration
    - password_reset: For password reset flow
    - verification: For general account verification
    """
    try:
        otp_code, expires_in = await otp_service.create_otp(
            db=db,
            email=request.email,
            phone=None,  # Phone support removed
            otp_type=request.otp_type,
            expires_in_minutes=10,
            background_tasks=background_tasks
        )
        
        return OTPResponse(
            success=True,
            message=f"OTP sent successfully to {request.email}",
            expires_in_seconds=expires_in
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to send OTP: {str(e)}")


@router.post("/verify", response_model=OTPResponse)
async def verify_otp(
    request: OTPVerify,
    db: AsyncSession = Depends(get_db)
):
    """
    Verify OTP code
    """
    success, message = await otp_service.verify_otp(
        db=db,
        email=request.email,
        otp_code=request.otp_code,
        otp_type=request.otp_type
    )
    
    if not success:
        raise HTTPException(status_code=400, detail=message)
    
    return OTPResponse(
        success=True,
        message=message
    )


@router.post("/forgot-password", response_model=OTPResponse)
async def forgot_password(
    request: ForgotPasswordRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """
    Initiate password reset flow
    Sends OTP to user's email only
    """
    success, message, expires_in = await otp_service.create_password_reset(
        db=db,
        email=request.email,
        background_tasks=background_tasks
    )
    
    return OTPResponse(
        success=success,
        message="Password reset code sent to your email." if success else message,
        expires_in_seconds=expires_in
    )


@router.post("/reset-password", response_model=PasswordResetResponse)
async def reset_password(
    request: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Reset password using OTP
    """
    # Validate password strength
    if len(request.new_password) < 8:
        raise HTTPException(
            status_code=400,
            detail="Password must be at least 8 characters long"
        )
    
    success, message = await otp_service.reset_password_with_otp(
        db=db,
        email=request.email,
        otp_code=request.otp_code,
        new_password=request.new_password
    )
    
    if not success:
        raise HTTPException(status_code=400, detail=message)
    
    return PasswordResetResponse(
        success=success,
        message=message
    )


@router.post("/resend", response_model=OTPResponse)
async def resend_otp(
    request: OTPRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """
    Resend OTP to email only (invalidates previous OTPs)
    """
    try:
        otp_code, expires_in = await otp_service.create_otp(
            db=db,
            email=request.email,
            phone=None,  # Phone support removed
            otp_type=request.otp_type,
            expires_in_minutes=10,
            background_tasks=background_tasks
        )
        
        return OTPResponse(
            success=True,
            message="New OTP sent successfully to your email",
            expires_in_seconds=expires_in
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to resend OTP: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to resend OTP: {str(e)}")
