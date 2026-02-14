import uuid
from sqlalchemy import Column, String, Enum, Float
from app.database import Base
import enum


class UserRole(str, enum.Enum):
    STUDENT = "STUDENT"
    ADMIN = "ADMIN"
    SUPER_ADMIN = "SUPER_ADMIN"

class VerificationStatus(str, enum.Enum):
    PENDING = "PENDING"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"
    NOT_REQUIRED = "NOT_REQUIRED"

class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    name = Column(String, nullable=False)
    role = Column(Enum(UserRole), default=UserRole.STUDENT, nullable=False)
    verification_status = Column(Enum(VerificationStatus), default=VerificationStatus.NOT_REQUIRED, nullable=False)
    avatar_url = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    
    # Location Data
    current_lat = Column(Float, nullable=True)
    current_long = Column(Float, nullable=True)
