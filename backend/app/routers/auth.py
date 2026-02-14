from datetime import timedelta
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.schemas.user import Token, UserCreate, UserResponse, UserBase
from app.core.security import verify_password, get_password_hash, create_access_token
from app.deps import get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])
from app.database import get_db

from app.models.user import User, UserRole, VerificationStatus

@router.post("/register", response_model=Token)
async def register(user_in: UserCreate, db: AsyncSession = Depends(get_db)):
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
