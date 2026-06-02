import uuid
from datetime import datetime
from sqlalchemy import Column, String, Enum, DateTime, Text
from app.database import Base
import enum


class AuditActionType(str, enum.Enum):
    # Trust & Safety
    FLAG_RAISED = "flag_raised"
    FLAG_RESOLVED = "flag_resolved"
    FLAG_REJECTED = "flag_rejected"
    FLAG_ESCALATED = "flag_escalated"
    OWNER_RESUBMITTED = "owner_resubmitted"
    
    # Reminders
    REMINDER_SENT = "reminder_sent"
    REMINDER_ACKNOWLEDGED = "reminder_acknowledged"
    REMINDER_COMPLETED = "reminder_completed"
    
    # Identity
    IDENTITY_VERIFIED = "identity_verified"
    IDENTITY_REJECTED = "identity_rejected"
    
    # Venue/Listing
    VENUE_APPROVED = "venue_approved"
    VENUE_REJECTED = "venue_rejected"
    VENUE_SUSPENDED = "venue_suspended"
    VENUE_RESTORED = "venue_restored"
    
    # Promotions
    PROMOTION_APPROVED = "promotion_approved"
    PROMOTION_REJECTED = "promotion_rejected"
    
    # User Management
    USER_BLOCKED = "user_blocked"
    USER_UNBLOCKED = "user_unblocked"
    ROLE_CHANGED = "role_changed"
    
    # System
    SETTINGS_CHANGED = "settings_changed"
    CACHE_CLEARED = "cache_cleared"
    OTHER = "other"


class AuditLog(Base):
    """
    Immutable audit log for all trust & safety actions.
    Read-only after creation - no updates or deletes allowed.
    """
    __tablename__ = "audit_logs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # Actor (who performed the action)
    actor_id = Column(String, nullable=False)
    actor_name = Column(String, nullable=True)
    actor_role = Column(String, nullable=False)  # Super Admin, Admin, etc.
    
    # Action
    action_type = Column(Enum(AuditActionType), nullable=False)
    action_description = Column(Text, nullable=True)  # Human-readable description
    
    # Target entity
    entity_type = Column(String, nullable=True)  # user, reading_room, accommodation, etc.
    entity_id = Column(String, nullable=True)
    entity_name = Column(String, nullable=True)
    
    # Additional context (JSON serialized)
    extra_data = Column(Text, nullable=True)  # JSON string with additional details
    
    # Immutable timestamp
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # IP and session info for security audits
    ip_address = Column(String, nullable=True)
    session_id = Column(String, nullable=True)
