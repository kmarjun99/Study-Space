"""Support ticket model — user-submitted support requests with admin response flow.

Mirrors the style of `owner_charge.py`:
- String UUID primary key with python-side default
- `native_enum=False` SqlEnum columns
- `datetime.utcnow` bare-callable timestamp defaults
- No SQLAlchemy `relationship()` declarations (joins done in queries)
"""
import enum
import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, ForeignKey, DateTime, Enum, Text, JSON,
)
from app.database import Base


class SupportCategory(str, enum.Enum):
    PAYMENT_ISSUE = "PAYMENT_ISSUE"
    TECHNICAL_ISSUE = "TECHNICAL_ISSUE"
    ACCOUNT = "ACCOUNT"
    BOOKING = "BOOKING"
    OTHER = "OTHER"


class SupportTicketPriority(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    URGENT = "URGENT"


class SupportTicketStatus(str, enum.Enum):
    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"


class SupportTicket(Base):
    __tablename__ = "support_tickets"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)

    # Denormalized snapshot of the creator at ticket creation time.
    user_name = Column(String, nullable=True)
    user_email = Column(String, nullable=True)

    subject = Column(String(200), nullable=False)
    category = Column(Enum(SupportCategory, native_enum=False), nullable=False)
    priority = Column(
        Enum(SupportTicketPriority, native_enum=False),
        default=SupportTicketPriority.MEDIUM,
        nullable=False,
    )
    message = Column(Text, nullable=False)

    status = Column(
        Enum(SupportTicketStatus, native_enum=False),
        default=SupportTicketStatus.OPEN,
        nullable=False,
    )
    admin_response = Column(Text, nullable=True)
    assigned_to = Column(String, ForeignKey("users.id"), nullable=True, index=True)
    meta_data = Column(JSON, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False,
    )
    resolved_at = Column(DateTime, nullable=True)
