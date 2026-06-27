from datetime import datetime
import uuid

from sqlalchemy import Column, DateTime, ForeignKey, String

from app.database import Base


class RefreshSession(Base):
    """Server-side record for a bounded refresh-token session.

    Access JWTs remain short lived. This table lets the backend revoke refresh
    cookies on logout and enforce a hard maximum session lifetime.
    """

    __tablename__ = "refresh_sessions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    token_hash = Column(String(64), unique=True, nullable=False, index=True)
    user_agent = Column(String, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    last_used_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=False, index=True)
    absolute_expires_at = Column(DateTime, nullable=False, index=True)
    revoked_at = Column(DateTime, nullable=True, index=True)
