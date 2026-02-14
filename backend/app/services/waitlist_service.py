from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.models.waitlist import WaitlistEntry, WaitlistStatus, Notification
from app.models.reading_room import Cabin, CabinStatus
from app.models.user import User

class WaitlistService:
    async def check_waitlist_and_notify(self, cabin_id: str, db: AsyncSession):
        """
        Triggered when a cabin becomes AVAILABLE.
        Checks for the next user in the waitlist (FIFO).
        If found:
        1. Updates WaitlistEntry status to NOTIFIED.
        2. Sets Cabin status to RESERVED.
        3. Sets Cabin held_by_user_id.
        4. Sends notification.
        """
        # 1. Get Cabin
        result = await db.execute(select(Cabin).where(Cabin.id == cabin_id))
        cabin = result.scalars().first()
        if not cabin:
            return

        # 2. Get prioritized waitlist entry (FIFO: Oldest created_at first)
        result = await db.execute(
            select(WaitlistEntry)
            .where(
                WaitlistEntry.cabin_id == cabin_id,
                WaitlistEntry.status == WaitlistStatus.ACTIVE
            )
            .order_by(WaitlistEntry.created_at.asc())
        )
        next_entry = result.scalars().first()

        if next_entry:
            # Found someone waiting!
            now = datetime.utcnow()
            expires_in_minutes = 30
            expires_at = now + timedelta(minutes=expires_in_minutes)

            # Update Entry
            next_entry.status = WaitlistStatus.NOTIFIED
            next_entry.notified_at = now
            next_entry.expires_at = expires_at

            # Reserve Cabin
            cabin.status = CabinStatus.RESERVED
            cabin.held_by_user_id = next_entry.user_id
            cabin.hold_expires_at = expires_at.isoformat()

            # Create Notification
            notification = Notification(
                user_id=next_entry.user_id,
                title="Seat Available!",
                message=f"Cabin {cabin.number} is now available! You have {expires_in_minutes} minutes to book it before it's offered to the next person.",
                type="success"
            )
            db.add(notification)

            await db.commit()
            print(f"Waitlist triggered for Cabin {cabin.number}. User {next_entry.user_id} notified.")
        else:
            # No one on waitlist, ensure cabin is marked AVAILABLE (if it wasn't already)
            # This handles cases where a reservation expired but no one else was waiting
            if cabin.status == CabinStatus.RESERVED:
                 cabin.status = CabinStatus.AVAILABLE
                 cabin.held_by_user_id = None
                 cabin.hold_expires_at = None
                 await db.commit()

waitlist_service = WaitlistService()
