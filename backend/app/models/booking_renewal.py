import uuid
from datetime import datetime

from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, String, UniqueConstraint

from app.database import Base


class BookingRenewalReminder(Base):
    """Tracks sent renewal reminders so the scheduler is idempotent."""

    __tablename__ = "booking_renewal_reminders"
    __table_args__ = (
        UniqueConstraint(
            "booking_id",
            "renewal_due_date",
            "reminder_day",
            name="uq_booking_renewal_reminder_once",
        ),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    booking_id = Column(String, ForeignKey("bookings.id"), nullable=False, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    owner_id = Column(String, ForeignKey("users.id"), nullable=True, index=True)
    cabin_id = Column(String, ForeignKey("cabins.id"), nullable=True, index=True)
    renewal_due_date = Column(Date, nullable=False, index=True)
    reminder_day = Column(Integer, nullable=False)
    channel = Column(String(20), nullable=False, default="IN_APP")
    notification_id = Column(String, ForeignKey("notifications.id"), nullable=True)
    sent_at = Column(DateTime, nullable=False, default=datetime.utcnow)
