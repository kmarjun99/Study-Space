from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from typing import List
from datetime import datetime
import uuid

from app.database import get_db
from app.deps import get_current_user
from app.models.user import User
from pydantic import BaseModel


router = APIRouter(prefix="/notifications", tags=["notifications"])


class Notification(BaseModel):
    id: str
    user_id: str
    title: str
    message: str
    read: bool
    date: str
    notification_type: str
    message_id: str | None = None

    class Config:
        from_attributes = True


# Helper function to create notifications (can be called from other routers)
async def create_notification(
    db: AsyncSession,
    user_id: str,
    title: str,
    message: str,
    notification_type: str = "info",
    message_id: str | None = None
):
    """Helper function to create a notification"""
    from app.models.notification import Notification as NotificationModel
    
    notification = NotificationModel(
        id=str(uuid.uuid4()),
        user_id=user_id,
        title=title,
        message=message,
        read=False,
        date=datetime.utcnow(),
        type=notification_type,
        message_id=message_id
    )
    db.add(notification)
    await db.commit()
    await db.refresh(notification)
    return notification


@router.get("/", response_model=List[Notification])
async def get_notifications(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get all notifications for current user"""
    from app.models.notification import Notification as NotificationModel
    
    result = await db.execute(
        select(NotificationModel)
        .where(NotificationModel.user_id == current_user.id)
        .order_by(NotificationModel.date.desc())
    )
    notifications = result.scalars().all()
    
    return [
        Notification(
            id=n.id,
            user_id=n.user_id,
            title=n.title,
            message=n.message,
            read=n.read,
            date=n.date.isoformat() if n.date else "",
            notification_type=n.type,
            message_id=n.message_id
        )
        for n in notifications
    ]


@router.put("/{notification_id}/read")
async def mark_notification_read(
    notification_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Mark a notification as read"""
    from app.models.notification import Notification as NotificationModel
    
    result = await db.execute(
        select(NotificationModel).where(
            and_(
                NotificationModel.id == notification_id,
                NotificationModel.user_id == current_user.id
            )
        )
    )
    notification = result.scalar_one_or_none()
    
    if notification:
        notification.read = True
        await db.commit()
    
    return {"status": "success"}
