from datetime import timedelta, datetime, timezone
import hashlib
import secrets
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Response, Request, Cookie
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.schemas.user import Token, UserCreate, UserResponse, UserBase
from app.schemas.otp import CompleteOwnerInviteRequest, CompleteRegistrationRequest, OTPResponse
from app.core.security import verify_password, get_password_hash, create_access_token
from app.core.config import settings
from app.deps import get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])
from app.database import get_db

from app.models.user import User, UserRole, VerificationStatus
from app.models.auth_session import RefreshSession
from app.models.waitlist import WaitlistEntry, WaitlistStatus
from app.services import otp_service

REFRESH_COOKIE_NAME = "studySpace_refresh"


def _utcnow() -> datetime:
    return datetime.utcnow()


def _hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _refresh_cookie_secure() -> bool:
    return settings.ENVIRONMENT != "development"


def _refresh_cookie_samesite() -> str:
    # Dev runs over http://localhost, so SameSite=None would be rejected
    # because it requires Secure. Production can use None to support the
    # current split frontend/backend deployments as well as same-origin proxying.
    return "none" if _refresh_cookie_secure() else "lax"


def _delete_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        key=REFRESH_COOKIE_NAME,
        path="/",
        secure=_refresh_cookie_secure(),
        samesite=_refresh_cookie_samesite(),
    )


def _set_refresh_cookie(response: Response, raw_token: str, expires_at: datetime) -> None:
    max_age = max(0, int((expires_at - _utcnow()).total_seconds()))
    cookie_expires_at = expires_at.replace(tzinfo=timezone.utc)
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=raw_token,
        max_age=max_age,
        expires=cookie_expires_at,
        httponly=True,
        secure=_refresh_cookie_secure(),
        samesite=_refresh_cookie_samesite(),
        path="/",
    )


async def _has_active_waitlist(db: AsyncSession, user: User) -> bool:
    wl_result = await db.execute(select(WaitlistEntry).where(
        WaitlistEntry.user_id == user.id,
        WaitlistEntry.status.in_([WaitlistStatus.ACTIVE, WaitlistStatus.NOTIFIED])
    ))
    return wl_result.scalars().first() is not None


def _token_response(
    *,
    user: User,
    access_token: str,
    access_expires_at: datetime,
    refresh_expires_at: datetime,
    has_active_waitlist: bool,
) -> dict:
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user_id": str(user.id),
        "role": user.role,
        "name": user.name,
        "email": user.email,
        "avatar_url": user.avatar_url,
        "has_active_waitlist": has_active_waitlist,
        "access_token_expires_at": access_expires_at,
        "refresh_token_expires_at": refresh_expires_at,
    }


async def _issue_session(
    *,
    user: User,
    db: AsyncSession,
    response: Response,
    request: Request,
    has_active_waitlist: bool,
    existing_session: Optional[RefreshSession] = None,
) -> dict:
    now = _utcnow()
    access_expires_at = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        subject=user.email,
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )

    raw_refresh_token = secrets.token_urlsafe(48)
    refresh_expires_at = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

    if existing_session is None:
        absolute_expires_at = now + timedelta(days=settings.REFRESH_SESSION_ABSOLUTE_DAYS)
        refresh_session = RefreshSession(
            user_id=user.id,
            token_hash=_hash_refresh_token(raw_refresh_token),
            user_agent=request.headers.get("user-agent"),
            created_at=now,
            last_used_at=now,
            expires_at=min(refresh_expires_at, absolute_expires_at),
            absolute_expires_at=absolute_expires_at,
        )
        db.add(refresh_session)
        refresh_expires_at = refresh_session.expires_at
    else:
        refresh_expires_at = min(refresh_expires_at, existing_session.absolute_expires_at)
        existing_session.token_hash = _hash_refresh_token(raw_refresh_token)
        existing_session.last_used_at = now
        existing_session.expires_at = refresh_expires_at

    await db.commit()
    _set_refresh_cookie(response, raw_refresh_token, refresh_expires_at)

    return _token_response(
        user=user,
        access_token=access_token,
        access_expires_at=access_expires_at,
        refresh_expires_at=refresh_expires_at,
        has_active_waitlist=has_active_waitlist,
    )

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
    response: Response,
    http_request: Request,
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
    
    # Set verification status based on role. Student OTP proves email ownership;
    # owner/admin accounts still require platform verification.
    v_status = VerificationStatus.VERIFIED if user_role == UserRole.STUDENT else VerificationStatus.NOT_REQUIRED
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
        verification_status=v_status,
        email_verified_at=datetime.utcnow() if user_role == UserRole.STUDENT else None,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    
    print(f"✅ User created successfully after OTP verification: {user.email}")

    return await _issue_session(
        user=user,
        db=db,
        response=response,
        request=http_request,
        has_active_waitlist=False,
    )

@router.post("/login", response_model=Token)
async def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    response: Response,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    # Note: OAuth2PasswordRequestForm expects 'username' field, which we treat as email
    result = await db.execute(select(User).where(User.email == form_data.username))
    user = result.scalars().first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if user.must_set_password or (
        user.role == UserRole.STUDENT and user.verification_status == VerificationStatus.PENDING
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Please verify your email and set your password before logging in.",
        )
    has_active = await _has_active_waitlist(db, user)

    return await _issue_session(
        user=user,
        db=db,
        response=response,
        request=request,
        has_active_waitlist=has_active,
    )


@router.post("/refresh", response_model=Token)
async def refresh_session(
    response: Response,
    request: Request,
    refresh_token: Annotated[Optional[str], Cookie(alias=REFRESH_COOKIE_NAME)] = None,
    db: AsyncSession = Depends(get_db),
):
    if not refresh_token:
        _delete_refresh_cookie(response)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired")

    now = _utcnow()
    token_hash = _hash_refresh_token(refresh_token)
    result = await db.execute(select(RefreshSession).where(
        RefreshSession.token_hash == token_hash,
        RefreshSession.revoked_at.is_(None),
    ))
    session = result.scalars().first()

    if not session:
        _delete_refresh_cookie(response)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired")

    if session.expires_at <= now or session.absolute_expires_at <= now:
        session.revoked_at = now
        await db.commit()
        _delete_refresh_cookie(response)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired")

    user_result = await db.execute(select(User).where(User.id == session.user_id))
    user = user_result.scalars().first()
    if not user:
        session.revoked_at = now
        await db.commit()
        _delete_refresh_cookie(response)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired")
    if user.must_set_password or (
        user.role == UserRole.STUDENT and user.verification_status == VerificationStatus.PENDING
    ):
        session.revoked_at = now
        await db.commit()
        _delete_refresh_cookie(response)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session requires verification")

    has_active = await _has_active_waitlist(db, user)
    return await _issue_session(
        user=user,
        db=db,
        response=response,
        request=request,
        has_active_waitlist=has_active,
        existing_session=session,
    )


@router.post("/complete-owner-invite", response_model=Token)
async def complete_owner_invite(
    request: CompleteOwnerInviteRequest,
    response: Response,
    http_request: Request,
    db: AsyncSession = Depends(get_db),
):
    if len(request.new_password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters long")

    user = await db.scalar(select(User).where(User.email == request.email))
    if not user or user.role != UserRole.STUDENT:
        raise HTTPException(status_code=404, detail="Invite not found")
    if not user.must_set_password and user.verification_status == VerificationStatus.VERIFIED:
        raise HTTPException(status_code=400, detail="Invite already completed. Please login.")

    success, message = await otp_service.verify_otp(
        db=db,
        email=request.email,
        otp_code=request.otp_code,
        otp_type="owner_invite",
    )
    if not success:
        raise HTTPException(status_code=400, detail=message)

    user.hashed_password = get_password_hash(request.new_password)
    user.must_set_password = False
    user.verification_status = VerificationStatus.VERIFIED
    user.email_verified_at = datetime.utcnow()
    await db.commit()
    await db.refresh(user)

    return await _issue_session(
        user=user,
        db=db,
        response=response,
        request=http_request,
        has_active_waitlist=await _has_active_waitlist(db, user),
    )


@router.post("/logout")
async def logout(
    response: Response,
    refresh_token: Annotated[Optional[str], Cookie(alias=REFRESH_COOKIE_NAME)] = None,
    db: AsyncSession = Depends(get_db),
):
    if refresh_token:
        result = await db.execute(select(RefreshSession).where(
            RefreshSession.token_hash == _hash_refresh_token(refresh_token),
            RefreshSession.revoked_at.is_(None),
        ))
        session = result.scalars().first()
        if session:
            session.revoked_at = _utcnow()
            await db.commit()

    _delete_refresh_cookie(response)
    return {"success": True}

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
