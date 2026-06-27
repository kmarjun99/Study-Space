import uuid
from sqlalchemy import Boolean, Column, String, Enum, Float, DateTime, ForeignKey
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


class KYCStatus(str, enum.Enum):
    PENDING = "PENDING"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"
    NOT_REQUIRED = "NOT_REQUIRED"


class GSTRegistrationType(str, enum.Enum):
    REGULAR = "REGULAR"
    COMPOSITION = "COMPOSITION"
    UNREGISTERED = "UNREGISTERED"


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    name = Column(String, nullable=False)
    role = Column(Enum(UserRole, native_enum=False), default=UserRole.STUDENT, nullable=False)
    verification_status = Column(Enum(VerificationStatus, native_enum=False), default=VerificationStatus.NOT_REQUIRED, nullable=False)
    avatar_url = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    created_by_owner_id = Column(String, ForeignKey("users.id"), nullable=True, index=True)
    must_set_password = Column(Boolean, nullable=False, default=False)
    email_verified_at = Column(DateTime, nullable=True)

    # Location Data
    current_lat = Column(Float, nullable=True)
    current_long = Column(Float, nullable=True)

    # ---- Accounting & KYC (added for transaction-flow rollout; all nullable) ----
    # Owner-only fields. Students leave these blank.
    legal_name = Column(String, nullable=True)
    pan = Column(String(10), nullable=True)
    gstin = Column(String(15), nullable=True)
    gst_registration_type = Column(
        Enum(GSTRegistrationType, native_enum=False),
        nullable=True,
        default=None,
    )
    business_state_code = Column(String(2), nullable=True)   # e.g. 'KA', 'MH'
    bank_account_holder = Column(String, nullable=True)
    bank_account_number = Column(String, nullable=True)
    bank_ifsc = Column(String(11), nullable=True)
    bank_verified_at = Column(DateTime, nullable=True)
    kyc_status = Column(
        Enum(KYCStatus, native_enum=False),
        nullable=True,
        default=None,
    )
    kyc_reviewed_by = Column(String, nullable=True)
    kyc_reviewed_at = Column(DateTime, nullable=True)
    kyc_notes = Column(String, nullable=True)
