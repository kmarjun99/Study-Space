
from pydantic import BaseModel, EmailStr
from typing import Optional
from app.models.user import UserRole, VerificationStatus

class UserBase(BaseModel):
    email: EmailStr
    name: str
    role: UserRole = UserRole.STUDENT
    avatar_url: Optional[str] = None
    phone: Optional[str] = None
    verification_status: VerificationStatus = VerificationStatus.NOT_REQUIRED

class UserCreate(UserBase):
    password: str

class UserUpdate(BaseModel):
    name: Optional[str] = None
    avatar_url: Optional[str] = None
    phone: Optional[str] = None
    password: Optional[str] = None

class AdminUserUpdate(BaseModel):
    """Schema for admin to update any user field including role and verification status"""
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    role: Optional[UserRole] = None
    avatar_url: Optional[str] = None
    phone: Optional[str] = None
    verification_status: Optional[VerificationStatus] = None

class UserResponse(UserBase):
    id: str
    has_active_waitlist: Optional[bool] = False

    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str
    user_id: str
    role: UserRole
    name: str
    email: str
    avatar_url: Optional[str] = None
    has_active_waitlist: bool = False

class TokenData(BaseModel):
    email: Optional[str] = None
    role: Optional[UserRole] = None
