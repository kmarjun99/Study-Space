"""Per-user consent preferences.

India's DPDP Act and global privacy norms lean toward opt-in. We default
**every personalization/marketing flag to OFF**. The user must affirmatively
grant consent in Privacy Settings before targeted recommendations,
notifications, or WhatsApp messages can fire.

`allow_analytics_tracking` controls the behavioral event firehose. With it
off, only operational events (login, booking confirmation — captured by
existing tables) are recorded. The `user_events` table is bypassed entirely.

Decisions stored, not consent-policy text. The product surface owns the
consent UI and policy version string.
"""
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String

from app.database import Base


class UserConsentPreferences(Base):
    __tablename__ = "user_consent_preferences"

    # One row per user. user_id is PK + FK.
    user_id = Column(String, ForeignKey("users.id"), primary_key=True)

    # ---- Layered consent flags (all default-OFF per opt-in policy) ----

    # Master gate for the behavioral event firehose. With this off, NO row is
    # written to user_events for this user (functional events go through
    # other tables like Booking, PaymentTransaction, AuditLog).
    allow_analytics_tracking = Column(Boolean, nullable=False, default=False)

    # Use behavior data to personalize listing recommendations + "you may
    # like" surfaces. Requires `allow_analytics_tracking=True` to be meaningful.
    allow_personalized_recommendations = Column(Boolean, nullable=False, default=False)

    # In-app + push + email marketing nudges (e.g., "complete your booking").
    allow_marketing_notifications = Column(Boolean, nullable=False, default=False)

    # WhatsApp follow-ups. Separate from marketing_notifications because
    # WhatsApp carries stricter regulatory + spam-cost implications.
    allow_whatsapp_updates = Column(Boolean, nullable=False, default=False)

    # Location-based recommendations + "near me" surfaces. Separate flag
    # because it touches a sensitive data class.
    allow_location_based_suggestions = Column(Boolean, nullable=False, default=False)

    # Which version of the privacy policy the user accepted when they
    # last toggled any flag. Store the version string the product surface
    # is showing at the time of consent (e.g., "2026-05").
    consent_policy_version = Column(String(20), nullable=True)

    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False,
    )
