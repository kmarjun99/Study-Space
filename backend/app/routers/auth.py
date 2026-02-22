from datetime import timedelta, datetime, timezone
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from pydantic import BaseModel
from app.schemas.user import Token, UserCreate, UserResponse, UserBase
from app.core.security import verify_password, get_password_hash, create_access_token
from app.deps import get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])
from app.database import get_db

from app.models.user import User, UserRole, VerificationStatus
from app.models.pending_registration import PendingRegistration
from app.models.waitlist import WaitlistEntry, WaitlistStatus
from app.services import otp_service

class InitiateRegistrationRequest(BaseModel):
    email: str
    password: str
    name: str
    role: UserRole = UserRole.STUDENT
    phone: str | None = None
    avatar_url: str | None = None

class VerifyAndRegisterRequest(BaseModel):
    email: str
    otp_code: str

@router.post("/initiate-registration")
async def initiate_registration(
    request: InitiateRegistrationRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """
    Step 1: Initiate registration by sending OTP
    - Checks if email already exists
    - Stores registration data temporarily
    - Sends OTP email immediately
    """
    # Check if user already exists
    result = await db.execute(select(User).where(User.email == request.email))
    if result.scalars().first():
        raise HTTPException(
            status_code=400,
            detail="The user with this email already exists in the system",
        )
    
    # Delete any existing pending registration for this email
    existing = await db.execute(
        select(PendingRegistration).where(PendingRegistration.email == request.email)
    )
    existing_pending = existing.scalars().first()
    if existing_pending:
        await db.delete(existing_pending)
    
    # Create pending registration (expires in 24 hours)
    pending_reg = PendingRegistration(
        email=request.email,
        hashed_password=get_password_hash(request.password),
        name=request.name,
        role=request.role.value if isinstance(request.role, UserRole) else request.role,
        phone=request.phone,
        avatar_url=request.avatar_url,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=24)
    )
    db.add(pending_reg)
    await db.commit()
    
    # Send OTP immediately
    try:
        otp_code, expires_in = await otp_service.create_otp(
            db=db,
            email=request.email,
            phone=None,
            otp_type='registration',
            expires_in_minutes=10,
            background_tasks=background_tasks
        )
        
        return {
            "success": True,
            "message": f"OTP sent to {request.email}. Please check your email (including spam folder).",
            "expires_in_seconds": expires_in
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to send OTP: {str(e)}")

@router.post("/verify-and-register", response_model=Token)
async def verify_and_register(
    request: VerifyAndRegisterRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Step 2: Verify OTP and complete registration
    - Verifies OTP code
    - Creates user in database ONLY after OTP verification
    - Returns access token
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
    
    # Get pending registration
    result = await db.execute(
        select(PendingRegistration).where(PendingRegistration.email == request.email)
    )
    pending_reg = result.scalars().first()
    
    if not pending_reg:
        raise HTTPException(
            status_code=404,
            detail="Pending registration not found. Please start registration again."
        )
    
    if pending_reg.is_expired():
        await db.delete(pending_reg)
        await db.commit()
        raise HTTPException(
            status_code=400,
            detail="Registration session expired. Please start registration again."
        )
    
    # Check if user was created in the meantime
    existing = await db.execute(select(User).where(User.email == request.email))
    if existing.scalars().first():
        await db.delete(pending_reg)
        await db.commit()
        raise HTTPException(
            status_code=400,
            detail="User already exists. Please login instead."
        )
    
    # Set verification status based on role
    role_enum = UserRole(pending_reg.role) if isinstance(pending_reg.role, str) else pending_reg.role
    v_status = VerificationStatus.NOT_REQUIRED
    if role_enum in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
        v_status = VerificationStatus.PENDING
    
    # Create actual user NOW (only after OTP verification)
    user = User( # type: ignore
        email=pending_reg.email,
        hashed_password=pending_reg.hashed_password,
        name=pending_reg.name,
        role=role_enum,
        avatar_url=pending_reg.avatar_url,
        phone=pending_reg.phone,
        verification_status=v_status
    )
    db.add(user)
    
    # Delete pending registration
    await db.delete(pending_reg)
    
    await db.commit()
    await db.refresh(user)
    
    # Generate access token
    access_token = create_access_token(subject=user.email)
    
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

@router.post("/register", response_model=Token)
async def register(user_in: UserCreate, db: AsyncSession = Depends(get_db)):
    """
    DEPRECATED: Old registration endpoint (kept for backward compatibility)
    Use /initiate-registration and /verify-and-register instead
    """
    result = await db.execute(select(User).where(User.email == user_in.email))
    if result.scalars().first():
        raise HTTPException(
            status_code=400,
            detail="The user with this username already exists in the system",
        )
    
    # Set verification status based on role
    v_status = VerificationStatus.NOT_REQUIRED
    if user_in.role in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
        v_status = VerificationStatus.PENDING

    user = User( # type: ignore
        email=user_in.email,
        hashed_password=get_password_hash(user_in.password),
        name=user_in.name,
        role=user_in.role or UserRole.STUDENT,
        avatar_url=user_in.avatar_url,
        phone=user_in.phone,
        verification_status=v_status
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    access_token = create_access_token(subject=user.email)
    
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
