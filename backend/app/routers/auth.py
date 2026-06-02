from datetime import timedelta, datetime, timezone
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.schemas.user import Token, UserCreate, UserResponse, UserBase
from app.schemas.otp import CompleteRegistrationRequest, OTPResponse
from app.core.security import verify_password, get_password_hash, create_access_token
from app.deps import get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])
from app.database import get_db

from app.models.user import User, UserRole, VerificationStatus
from app.services import otp_service

@router.post("/register", response_model=OTPResponse)
async def register(
    user_in: UserCreate, 
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """
    Step 1: Validate email and send OTP
    User data stays in frontend - NOT stored in database yet
    """
    # Check if user already exists
    result = await db.execute(select(User).where(User.email == user_in.email))
    if result.scalars().first():
        raise HTTPException(
            status_code=400,
            detail="The user with this username already exists in the system",
        )
    
    # Send OTP for registration verification
    # Note: No user data is stored anywhere - it stays in the frontend
    otp_code, expires_in = await otp_service.create_otp(
        db=db,
        email=user_in.email,
        phone=None,
        otp_type='registration',
        expires_in_minutes=10,
        background_tasks=background_tasks
    )
    
    print(f"✅ OTP sent to {user_in.email}: {otp_code}")
    
    return OTPResponse(
        success=True,
        message=f"OTP sent to {user_in.email}. Please verify to complete registration.",
        expires_in_seconds=expires_in
    )


@router.post("/complete-registration", response_model=Token)
async def complete_registration(
    request: CompleteRegistrationRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Step 2: Verify OTP and create user
    User is only created AFTER successful OTP verification
    """
    # Verify OTP first
    success, message = await otp_service.verify_otp(
        db=db,
        email=request.email,
        otp_code=request.otp_code,
        otp_type='registration'
    )
    
    if not success:
        raise HTTPException(status_code=400, detail=message)
    
    # Check if user was created in the meantime (race condition)
    result = await db.execute(select(User).where(User.email == request.email))
    if result.scalars().first():
        raise HTTPException(
            status_code=400,
            detail="User already exists. Please login."
        )
    
    # Parse role
    try:
        user_role = UserRole(request.role)
    except ValueError:
        user_role = UserRole.STUDENT
    
    # Set verification status based on role
    v_status = VerificationStatus.NOT_REQUIRED
    if user_role in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
        v_status = VerificationStatus.PENDING
    
    # NOW create the user (only after OTP verification)
    user = User(
        email=request.email,
        hashed_password=get_password_hash(request.password),
        name=request.name,
        role=user_role,
        avatar_url=request.avatar_url,
        phone=request.phone,
        verification_status=v_status
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    
    # Create access token
    access_token = create_access_token(subject=user.email)
    
    print(f"✅ User created successfully after OTP verification: {user.email}")
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user_id": str(user.id),
        "role": user.role,
        "name": user.name,
        "email": user.email,
        "avatar_url": user.avatar_url,
        "has_active_waitlist": False
    }

@router.post("/login", response_model=Token)
async def login(form_data: Annotated[OAuth2PasswordRequestForm, Depends()], db: AsyncSession = Depends(get_db)):
    # Note: OAuth2PasswordRequestForm expects 'username' field, which we treat as email
    result = await db.execute(select(User).where(User.email == form_data.username))
    user = result.scalars().first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = create_access_token(subject=user.email)
    
    # Check waitlist status
    wl_result = await db.execute(select(WaitlistEntry).where(
        WaitlistEntry.user_id == user.id,
        WaitlistEntry.status.in_([WaitlistStatus.ACTIVE, WaitlistStatus.NOTIFIED])
    ))
    has_active = wl_result.scalars().first() is not None

    return {
        "access_token": access_token, 
        "token_type": "bearer",
        "user_id": str(user.id),
        "role": user.role,
        "name": user.name,
        "email": user.email,
        "avatar_url": user.avatar_url,
        "has_active_waitlist": has_active
    }

from app.models.waitlist import WaitlistEntry, WaitlistStatus

@router.get("/me", response_model=UserResponse)
async def read_users_me(
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db)
):
    # Check for active waitlist entries
    query = select(WaitlistEntry).where(
        WaitlistEntry.user_id == current_user.id,
        WaitlistEntry.status.in_([WaitlistStatus.ACTIVE, WaitlistStatus.NOTIFIED])
    )
    result = await db.execute(query)
    has_active = result.scalars().first() is not None
    
    # Convert ORM model to Pydantic and add extra field
    user_data = UserResponse.model_validate(current_user)
    user_data.has_active_waitlist = has_active
    
    return user_data
