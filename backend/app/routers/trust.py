"""
Trust & Safety Router

All actions here:
1. Persist state to database
2. Update related entities (venue trust_status, user verification)
3. Log to audit trail
4. Return updated data

NO UI-ONLY ACTIONS - Every button click persists.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from datetime import datetime
from typing import List, Optional
import json

from app.database import get_db
from app.models.trust_flag import TrustFlag, TrustFlagType, TrustFlagStatus
from app.models.reminder import Reminder, ReminderType, ReminderStatus
from app.models.audit_log import AuditLog, AuditActionType
from app.models.reading_room import ReadingRoom
from app.models.accommodation import Accommodation
from app.models.user import User

# Trust status values (stored as strings in DB)
TRUST_STATUS_CLEAR = "CLEAR"
TRUST_STATUS_FLAGGED = "FLAGGED"
TRUST_STATUS_UNDER_REVIEW = "UNDER_REVIEW"
TRUST_STATUS_SUSPENDED = "SUSPENDED"
from pydantic import BaseModel

router = APIRouter(prefix="/api/trust", tags=["Trust & Safety"])


# ================== SCHEMAS ==================

class FlagCreate(BaseModel):
    entity_type: str  # 'reading_room' or 'accommodation'
    entity_id: str
    flag_type: str
    custom_reason: Optional[str] = None


class FlagResolve(BaseModel):
    action: str  # 'approve', 'reject', 'escalate'
    notes: Optional[str] = None


class OwnerResubmit(BaseModel):
    notes: str


class ReminderCreate(BaseModel):
    user_id: str
    reminder_type: str
    missing_fields: Optional[str] = None  # JSON array
    message: Optional[str] = None
    blocks_listings: bool = True
    blocks_payments: bool = True
    blocks_bookings: bool = False


# ================== HELPER FUNCTIONS ==================

async def log_audit(
    db: AsyncSession,
    actor_id: str,
    actor_name: str,
    actor_role: str,
    action_type: AuditActionType,
    description: str,
    entity_type: str = None,
    entity_id: str = None,
    entity_name: str = None,
    metadata: dict = None
):
    """Create an immutable audit log entry."""
    entry = AuditLog(
        actor_id=actor_id,
        actor_name=actor_name,
        actor_role=actor_role,
        action_type=action_type,
        action_description=description,
        entity_type=entity_type,
        entity_id=entity_id,
        entity_name=entity_name,
        extra_data=json.dumps(metadata) if metadata else None,
        timestamp=datetime.utcnow()
    )
    db.add(entry)
    await db.commit()
    return entry


async def update_venue_trust_status(db: AsyncSession, entity_type: str, entity_id: str, trust_status: str):
    """Update venue trust status in the database."""
    if entity_type == "reading_room":
        result = await db.execute(select(ReadingRoom).where(ReadingRoom.id == entity_id))
        venue = result.scalars().first()
        if venue:
            venue.trust_status = trust_status
            await db.commit()
            return venue
    elif entity_type == "accommodation":
        result = await db.execute(select(Accommodation).where(Accommodation.id == entity_id))
        venue = result.scalars().first()
        if venue:
            # Add trust_status to accommodation if exists
            if hasattr(venue, 'trust_status'):
                venue.trust_status = trust_status
            await db.commit()
            return venue
    return None


# ================== FLAG ENDPOINTS ==================

@router.get("/flags")
async def get_all_flags(
    status: Optional[str] = None,
    entity_type: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """Get all trust flags with optional filters."""
    query = select(TrustFlag)
    
    if status:
        query = query.where(TrustFlag.status == status)
    if entity_type:
        query = query.where(TrustFlag.entity_type == entity_type)
    
    query = query.order_by(TrustFlag.created_at.desc())
    result = await db.execute(query)
    flags = result.scalars().all()
    
    # Convert to dict for JSON response
    return [
        {
            "id": f.id,
            "entity_type": f.entity_type,
            "entity_id": f.entity_id,
            "entity_name": f.entity_name,
            "flag_type": str(f.flag_type.value) if f.flag_type else None,
            "custom_reason": f.custom_reason,
            "raised_by": f.raised_by,
            "raised_by_name": f.raised_by_name,
            "status": str(f.status.value) if f.status else None,
            "resolution_notes": f.resolution_notes,
            "resolved_by": f.resolved_by,
            "resolved_by_name": f.resolved_by_name,
            "created_at": f.created_at.isoformat() if f.created_at else None,
            "updated_at": f.updated_at.isoformat() if f.updated_at else None,
            "resolved_at": f.resolved_at.isoformat() if f.resolved_at else None,
            "owner_notes": f.owner_notes,
            "resubmitted_at": f.resubmitted_at.isoformat() if f.resubmitted_at else None
        }
        for f in flags
    ]


@router.post("/flags")
async def create_flag(
    data: FlagCreate,
    actor_id: str = Query(..., description="ID of Super Admin creating flag"),
    actor_name: str = Query("Super Admin", description="Name of actor"),
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new trust flag on a venue.
    - Updates venue trust_status to FLAGGED
    - Logs to audit trail
    - Returns created flag
    """
    # Get entity name for display
    entity_name = None
    if data.entity_type == "reading_room":
        result = await db.execute(select(ReadingRoom).where(ReadingRoom.id == data.entity_id))
        venue = result.scalars().first()
        if venue:
            entity_name = venue.name
    elif data.entity_type == "accommodation":
        result = await db.execute(select(Accommodation).where(Accommodation.id == data.entity_id))
        venue = result.scalars().first()
        if venue:
            entity_name = venue.name
    
    if not entity_name:
        raise HTTPException(status_code=404, detail="Entity not found")
    
    # Check for existing active flag
    existing_query = select(TrustFlag).where(
        TrustFlag.entity_id == data.entity_id,
        TrustFlag.status.in_([TrustFlagStatus.ACTIVE, TrustFlagStatus.OWNER_RESUBMITTED])
    )
    existing_result = await db.execute(existing_query)
    existing = existing_result.scalars().first()
    
    if existing:
        raise HTTPException(status_code=400, detail="Active flag already exists for this entity")
    
    # Create flag
    flag = TrustFlag(
        entity_type=data.entity_type,
        entity_id=data.entity_id,
        entity_name=entity_name,
        flag_type=TrustFlagType(data.flag_type),
        custom_reason=data.custom_reason,
        raised_by=actor_id,
        raised_by_name=actor_name,
        status=TrustFlagStatus.ACTIVE
    )
    db.add(flag)
    
    # Update venue trust status
    await update_venue_trust_status(db, data.entity_type, data.entity_id, TRUST_STATUS_FLAGGED)
    
    await db.commit()
    await db.refresh(flag)
    
    # Log audit
    await log_audit(
        db=db,
        actor_id=actor_id,
        actor_name=actor_name,
        actor_role="SUPER_ADMIN",
        action_type=AuditActionType.FLAG_RAISED,
        description=f"Flag raised on {entity_name}: {data.flag_type}",
        entity_type=data.entity_type,
        entity_id=data.entity_id,
        entity_name=entity_name,
        metadata={"flag_type": data.flag_type, "reason": data.custom_reason}
    )
    
    return {"id": flag.id, "status": "created", "entity_name": entity_name}


@router.patch("/flags/{flag_id}/resolve")
async def resolve_flag(
    flag_id: str,
    data: FlagResolve,
    actor_id: str = Query(..., description="ID of Super Admin resolving"),
    actor_name: str = Query("Super Admin", description="Name of actor"),
    db: AsyncSession = Depends(get_db)
):
    """
    Resolve a trust flag.
    - action='approve': Clear flag, restore venue
    - action='reject': Keep flag active
    - action='escalate': Suspend venue
    """
    result = await db.execute(select(TrustFlag).where(TrustFlag.id == flag_id))
    flag = result.scalars().first()
    if not flag:
        raise HTTPException(status_code=404, detail="Flag not found")
    
    if data.action == "approve":
        flag.status = TrustFlagStatus.RESOLVED
        flag.resolution_notes = data.notes
        flag.resolved_by = actor_id
        flag.resolved_by_name = actor_name
        flag.resolved_at = datetime.utcnow()
        
        # Restore venue trust status
        await update_venue_trust_status(db, flag.entity_type, flag.entity_id, TRUST_STATUS_CLEAR)
        
        action_type = AuditActionType.FLAG_RESOLVED
        description = f"Flag resolved for {flag.entity_name}"
        
    elif data.action == "reject":
        flag.status = TrustFlagStatus.ACTIVE  # Keep active
        flag.resolution_notes = data.notes
        
        action_type = AuditActionType.FLAG_REJECTED
        description = f"Owner resubmission rejected for {flag.entity_name}"
        
    elif data.action == "escalate":
        flag.status = TrustFlagStatus.ESCALATED
        flag.resolution_notes = data.notes
        # DON'T set resolved_by/resolved_at - escalated is NOT resolved, it's suspended pending investigation
        
        # Suspend venue
        await update_venue_trust_status(db, flag.entity_type, flag.entity_id, TRUST_STATUS_SUSPENDED)
        
        action_type = AuditActionType.FLAG_ESCALATED
        description = f"Flag escalated, venue suspended: {flag.entity_name}"
        
    else:
        raise HTTPException(status_code=400, detail="Invalid action")
    
    await db.commit()
    await db.refresh(flag)
    
    # Log audit
    await log_audit(
        db=db,
        actor_id=actor_id,
        actor_name=actor_name,
        actor_role="SUPER_ADMIN",
        action_type=action_type,
        description=description,
        entity_type=flag.entity_type,
        entity_id=flag.entity_id,
        entity_name=flag.entity_name,
        metadata={"action": data.action, "notes": data.notes}
    )
    
    return {"id": flag.id, "status": str(flag.status.value), "action": data.action}


@router.post("/flags/{flag_id}/resubmit")
async def owner_resubmit(
    flag_id: str,
    data: OwnerResubmit,
    owner_id: str = Query(..., description="ID of Owner resubmitting"),
    owner_name: str = Query("Owner", description="Name of owner"),
    db: AsyncSession = Depends(get_db)
):
    """
    Owner resubmits after addressing flag issues.
    """
    result = await db.execute(select(TrustFlag).where(TrustFlag.id == flag_id))
    flag = result.scalars().first()
    if not flag:
        raise HTTPException(status_code=404, detail="Flag not found")
    
    if flag.status != TrustFlagStatus.ACTIVE:
        raise HTTPException(status_code=400, detail="Can only resubmit active flags")
    
    flag.status = TrustFlagStatus.OWNER_RESUBMITTED
    flag.owner_notes = data.notes
    flag.resubmitted_at = datetime.utcnow()
    
    # Update venue to under review
    await update_venue_trust_status(db, flag.entity_type, flag.entity_id, TRUST_STATUS_UNDER_REVIEW)
    
    await db.commit()
    await db.refresh(flag)
    
    # Log audit
    await log_audit(
        db=db,
        actor_id=owner_id,
        actor_name=owner_name,
        actor_role="ADMIN",
        action_type=AuditActionType.OWNER_RESUBMITTED,
        description=f"Owner resubmitted for review: {flag.entity_name}",
        entity_type=flag.entity_type,
        entity_id=flag.entity_id,
        entity_name=flag.entity_name,
        metadata={"notes": data.notes}
    )
    
    return {"id": flag.id, "status": str(flag.status.value)}


@router.patch("/flags/{flag_id}/reinstate")
async def reinstate_flag(
    flag_id: str,
    notes: Optional[str] = None,
    actor_id: str = Query(..., description="ID of Super Admin reinstating"),
    actor_name: str = Query("Super Admin", description="Name of actor"),
    db: AsyncSession = Depends(get_db)
):
    """
    Super Admin reinstates a suspended (escalated) venue.
    - Sets flag to RESOLVED
    - Restores venue trust status to CLEAR
    """
    result = await db.execute(select(TrustFlag).where(TrustFlag.id == flag_id))
    flag = result.scalars().first()
    if not flag:
        raise HTTPException(status_code=404, detail="Flag not found")
    
    if flag.status != TrustFlagStatus.ESCALATED:
        raise HTTPException(status_code=400, detail="Can only reinstate escalated flags")
    
    flag.status = TrustFlagStatus.RESOLVED
    flag.resolution_notes = notes or "Venue reinstated by admin"
    flag.resolved_by = actor_id
    flag.resolved_by_name = actor_name
    flag.resolved_at = datetime.utcnow()
    
    # Restore venue trust status
    await update_venue_trust_status(db, flag.entity_type, flag.entity_id, TRUST_STATUS_CLEAR)
    
    await db.commit()
    await db.refresh(flag)
    
    # Log audit
    await log_audit(
        db=db,
        actor_id=actor_id,
        actor_name=actor_name,
        actor_role="SUPER_ADMIN",
        action_type=AuditActionType.FLAG_RESOLVED,
        description=f"Venue reinstated from suspension: {flag.entity_name}",
        entity_type=flag.entity_type,
        entity_id=flag.entity_id,
        entity_name=flag.entity_name,
        metadata={"action": "reinstate", "notes": notes}
    )
    
    return {"id": flag.id, "status": str(flag.status.value), "action": "reinstated"}


@router.get("/owner/flags")
async def get_owner_flags(
    owner_id: str = Query(..., description="Owner ID"),
    db: AsyncSession = Depends(get_db)
):
    """Get all flags for venues owned by this owner."""
    # Get owner's venue IDs
    room_result = await db.execute(select(ReadingRoom.id).where(ReadingRoom.owner_id == owner_id))
    room_ids = room_result.scalars().all()
    
    acc_result = await db.execute(select(Accommodation.id).where(Accommodation.owner_id == owner_id))
    acc_ids = acc_result.scalars().all()
    
    all_entity_ids = list(room_ids) + list(acc_ids)
    
    if not all_entity_ids:
        return []
    
    # Include ESCALATED flags - owner must see suspended venues
    query = select(TrustFlag).where(
        TrustFlag.entity_id.in_(all_entity_ids),
        TrustFlag.status.in_([TrustFlagStatus.ACTIVE, TrustFlagStatus.OWNER_RESUBMITTED, TrustFlagStatus.ESCALATED])
    ).order_by(TrustFlag.created_at.desc())
    result = await db.execute(query)
    flags = result.scalars().all()
    
    return [
        {
            "id": f.id,
            "entity_type": f.entity_type,
            "entity_id": f.entity_id,
            "entity_name": f.entity_name,
            "flag_type": str(f.flag_type.value) if f.flag_type else None,
            "custom_reason": f.custom_reason,
            "raised_by": f.raised_by,
            "raised_by_name": f.raised_by_name,
            "status": str(f.status.value) if f.status else None,
            "resolution_notes": f.resolution_notes,
            "resolved_by": f.resolved_by,
            "resolved_by_name": f.resolved_by_name,
            "created_at": f.created_at.isoformat() if f.created_at else None,
            "updated_at": f.updated_at.isoformat() if f.updated_at else None,
            "resolved_at": f.resolved_at.isoformat() if f.resolved_at else None,
            "owner_notes": f.owner_notes,
            "resubmitted_at": f.resubmitted_at.isoformat() if f.resubmitted_at else None
        }
        for f in flags
    ]


# ================== REMINDER ENDPOINTS ==================

@router.get("/reminders")
async def get_all_reminders(
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """Get all reminders with optional status filter."""
    query = select(Reminder)
    
    if status:
        query = query.where(Reminder.status == status)
    
    query = query.order_by(Reminder.sent_at.desc())
    result = await db.execute(query)
    reminders = result.scalars().all()
    
    return [
        {
            "id": r.id,
            "user_id": r.user_id,
            "user_name": r.user_name,
            "user_email": r.user_email,
            "reminder_type": str(r.reminder_type.value) if r.reminder_type else None,
            "missing_fields": r.missing_fields,
            "message": r.message,
            "sent_by": r.sent_by,
            "sent_by_name": r.sent_by_name,
            "status": str(r.status.value) if r.status else None,
            "blocks_listings": r.blocks_listings,
            "blocks_payments": r.blocks_payments,
            "blocks_bookings": r.blocks_bookings,
            "sent_at": r.sent_at.isoformat() if r.sent_at else None,
            "completed_at": r.completed_at.isoformat() if r.completed_at else None
        }
        for r in reminders
    ]


@router.post("/reminders")
async def send_reminder(
    data: ReminderCreate,
    actor_id: str = Query(..., description="ID of Super Admin sending reminder"),
    actor_name: str = Query("Super Admin", description="Name of actor"),
    db: AsyncSession = Depends(get_db)
):
    """
    Send a verification reminder to a user.
    """
    # Get user info
    result = await db.execute(select(User).where(User.id == data.user_id))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Check for existing pending reminder of same type
    existing_query = select(Reminder).where(
        Reminder.user_id == data.user_id,
        Reminder.reminder_type == data.reminder_type,
        Reminder.status == ReminderStatus.PENDING
    )
    existing_result = await db.execute(existing_query)
    existing = existing_result.scalars().first()
    
    if existing:
        raise HTTPException(status_code=400, detail="Pending reminder of this type already exists")
    
    # Create reminder
    reminder = Reminder(
        user_id=data.user_id,
        user_name=user.name,
        user_email=user.email,
        reminder_type=ReminderType(data.reminder_type),
        missing_fields=data.missing_fields,
        message=data.message,
        sent_by=actor_id,
        sent_by_name=actor_name,
        blocks_listings=data.blocks_listings,
        blocks_payments=data.blocks_payments,
        blocks_bookings=data.blocks_bookings,
        status=ReminderStatus.PENDING
    )
    db.add(reminder)
    await db.commit()
    await db.refresh(reminder)
    
    # Log audit
    await log_audit(
        db=db,
        actor_id=actor_id,
        actor_name=actor_name,
        actor_role="SUPER_ADMIN",
        action_type=AuditActionType.REMINDER_SENT,
        description=f"Verification reminder sent to {user.name}: {data.reminder_type}",
        entity_type="user",
        entity_id=data.user_id,
        entity_name=user.name,
        metadata={"reminder_type": data.reminder_type, "missing_fields": data.missing_fields}
    )
    
    return {"id": reminder.id, "status": "sent", "user_name": user.name}


@router.patch("/reminders/{reminder_id}/complete")
async def complete_reminder(
    reminder_id: str,
    user_id: str = Query(..., description="User completing the reminder"),
    db: AsyncSession = Depends(get_db)
):
    """Mark a reminder as completed."""
    result = await db.execute(select(Reminder).where(Reminder.id == reminder_id))
    reminder = result.scalars().first()
    if not reminder:
        raise HTTPException(status_code=404, detail="Reminder not found")
    
    if reminder.user_id != user_id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    reminder.status = ReminderStatus.COMPLETED
    reminder.completed_at = datetime.utcnow()
    
    await db.commit()
    await db.refresh(reminder)
    
    # Log audit
    await log_audit(
        db=db,
        actor_id=user_id,
        actor_name=reminder.user_name,
        actor_role="USER",
        action_type=AuditActionType.REMINDER_COMPLETED,
        description=f"Verification completed: {reminder.reminder_type}",
        entity_type="user",
        entity_id=user_id,
        entity_name=reminder.user_name,
        metadata={"reminder_type": str(reminder.reminder_type.value) if reminder.reminder_type else None}
    )
    
    return {"id": reminder.id, "status": "completed"}


@router.get("/user/reminders")
async def get_user_reminders(
    user_id: str = Query(..., description="User ID"),
    db: AsyncSession = Depends(get_db)
):
    """Get all reminders for a specific user."""
    result = await db.execute(
        select(Reminder).where(Reminder.user_id == user_id).order_by(Reminder.sent_at.desc())
    )
    reminders = result.scalars().all()
    
    return [
        {
            "id": r.id,
            "reminder_type": str(r.reminder_type.value) if r.reminder_type else None,
            "status": str(r.status.value) if r.status else None,
            "blocks_listings": r.blocks_listings,
            "blocks_payments": r.blocks_payments,
            "blocks_bookings": r.blocks_bookings,
            "sent_at": r.sent_at.isoformat() if r.sent_at else None
        }
        for r in reminders
    ]


@router.get("/user/has-blocks")
async def check_user_blocks(
    user_id: str = Query(..., description="User ID"),
    db: AsyncSession = Depends(get_db)
):
    """Check if user has any active blocks from reminders."""
    result = await db.execute(
        select(Reminder).where(
            Reminder.user_id == user_id,
            Reminder.status == ReminderStatus.PENDING
        )
    )
    pending_reminders = result.scalars().all()
    
    blocks = {
        "has_blocks": len(pending_reminders) > 0,
        "blocks_listings": any(r.blocks_listings for r in pending_reminders),
        "blocks_payments": any(r.blocks_payments for r in pending_reminders),
        "blocks_bookings": any(r.blocks_bookings for r in pending_reminders),
        "pending_reminders": len(pending_reminders),
        "reminder_types": [str(r.reminder_type.value) for r in pending_reminders if r.reminder_type]
    }
    
    return blocks


# ================== AUDIT LOG ENDPOINTS ==================

@router.get("/audit-log")
async def get_audit_log(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    actor_id: Optional[str] = None,
    action_type: Optional[str] = None,
    entity_type: Optional[str] = None,
    limit: int = Query(100, le=500),
    offset: int = Query(0),
    db: AsyncSession = Depends(get_db)
):
    """
    Get audit log entries with filters.
    Read-only - no updates or deletes allowed.
    """
    query = select(AuditLog)
    
    if start_date:
        query = query.where(AuditLog.timestamp >= datetime.fromisoformat(start_date))
    if end_date:
        query = query.where(AuditLog.timestamp <= datetime.fromisoformat(end_date))
    if actor_id:
        query = query.where(AuditLog.actor_id == actor_id)
    if action_type:
        query = query.where(AuditLog.action_type == action_type)
    if entity_type:
        query = query.where(AuditLog.entity_type == entity_type)
    
    # Count total
    count_query = select(AuditLog)
    if action_type:
        count_query = count_query.where(AuditLog.action_type == action_type)
    if entity_type:
        count_query = count_query.where(AuditLog.entity_type == entity_type)
    count_result = await db.execute(count_query)
    total = len(count_result.scalars().all())
    
    # Get entries with pagination
    query = query.order_by(AuditLog.timestamp.desc()).offset(offset).limit(limit)
    result = await db.execute(query)
    entries = result.scalars().all()
    
    return {
        "total": total,
        "entries": [
            {
                "id": e.id,
                "actor_id": e.actor_id,
                "actor_name": e.actor_name,
                "actor_role": e.actor_role,
                "action_type": str(e.action_type.value) if e.action_type else None,
                "action_description": e.action_description,
                "entity_type": e.entity_type,
                "entity_id": e.entity_id,
                "entity_name": e.entity_name,
                "extra_data": e.extra_data,
                "timestamp": e.timestamp.isoformat() if e.timestamp else None
            }
            for e in entries
        ],
        "limit": limit,
        "offset": offset
    }


@router.get("/audit-log/entity/{entity_type}/{entity_id}")
async def get_entity_audit_log(
    entity_type: str,
    entity_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Get audit log for a specific entity (for owner view)."""
    result = await db.execute(
        select(AuditLog).where(
            AuditLog.entity_type == entity_type,
            AuditLog.entity_id == entity_id
        ).order_by(AuditLog.timestamp.desc())
    )
    entries = result.scalars().all()
    
    return [
        {
            "id": e.id,
            "actor_name": e.actor_name,
            "action_type": str(e.action_type.value) if e.action_type else None,
            "action_description": e.action_description,
            "timestamp": e.timestamp.isoformat() if e.timestamp else None
        }
        for e in entries
    ]


# ================== VENUE TRUST STATUS ==================

@router.get("/venue/{entity_type}/{entity_id}/status")
async def get_venue_trust_status(
    entity_type: str,
    entity_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Get trust status for a venue, including any active flags."""
    # Get venue
    venue = None
    if entity_type == "reading_room":
        result = await db.execute(select(ReadingRoom).where(ReadingRoom.id == entity_id))
        venue = result.scalars().first()
    elif entity_type == "accommodation":
        result = await db.execute(select(Accommodation).where(Accommodation.id == entity_id))
        venue = result.scalars().first()
    
    if not venue:
        raise HTTPException(status_code=404, detail="Venue not found")
    
    # Get active flags
    flag_result = await db.execute(
        select(TrustFlag).where(
            TrustFlag.entity_id == entity_id,
            TrustFlag.status.in_([TrustFlagStatus.ACTIVE, TrustFlagStatus.OWNER_RESUBMITTED])
        )
    )
    active_flags = flag_result.scalars().all()
    
    trust_status = getattr(venue, 'trust_status', TRUST_STATUS_CLEAR) or TRUST_STATUS_CLEAR
    
    return {
        "entity_id": entity_id,
        "entity_type": entity_type,
        "entity_name": venue.name,
        "trust_status": trust_status,
        "is_flagged": len(active_flags) > 0,
        "active_flags": [
            {"id": f.id, "flag_type": str(f.flag_type.value) if f.flag_type else None, "status": str(f.status.value) if f.status else None}
            for f in active_flags
        ],
        "can_promote": trust_status == TRUST_STATUS_CLEAR,
        "can_accept_payments": trust_status != TRUST_STATUS_SUSPENDED,
        "is_visible_to_users": trust_status not in [TRUST_STATUS_SUSPENDED, TRUST_STATUS_FLAGGED]
    }
