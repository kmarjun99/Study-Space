"""Support ticket API — users create tickets; super admins triage and respond.

Auth model:
- All endpoints require authentication.
- Creation + listing-own + reading-own: any authenticated user.
- Listing all, status changes, response, delete: super admin only.

Notifications are emitted best-effort (try/except, post-commit) using the
`create_notification` helper from `app.routers.notifications`, following the
same pattern as `app/routers/messages.py`.
"""
from __future__ import annotations

from datetime import datetime, time
from typing import Optional, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user, get_current_super_admin
from app.models.support_ticket import (
    SupportCategory,
    SupportTicket,
    SupportTicketPriority,
    SupportTicketStatus,
)
from app.models.user import User, UserRole


router = APIRouter(prefix="/support", tags=["Support Tickets"])


# ---------- response / request schemas --------------------------------------

class SupportTicketOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    user_name: Optional[str]
    user_email: Optional[str]
    subject: str
    category: str
    priority: str
    message: str
    status: str
    admin_response: Optional[str]
    assigned_to: Optional[str]
    meta_data: Optional[dict]
    created_at: str
    updated_at: str
    resolved_at: Optional[str]

    @classmethod
    def from_model(cls, t: SupportTicket) -> "SupportTicketOut":
        return cls(
            id=t.id,
            user_id=t.user_id,
            user_name=t.user_name,
            user_email=t.user_email,
            subject=t.subject,
            category=t.category.value,
            priority=t.priority.value,
            message=t.message,
            status=t.status.value,
            admin_response=t.admin_response,
            assigned_to=t.assigned_to,
            meta_data=t.meta_data,
            created_at=t.created_at.isoformat() if t.created_at else "",
            updated_at=t.updated_at.isoformat() if t.updated_at else "",
            resolved_at=t.resolved_at.isoformat() if t.resolved_at else None,
        )


class CreateTicketBody(BaseModel):
    subject: str
    message: str
    category: str
    priority: Optional[str] = None
    meta_data: Optional[dict] = None


class UpdateStatusBody(BaseModel):
    status: str
    admin_notes: Optional[str] = None


class UpdateResponseBody(BaseModel):
    admin_response: str


# ---------- internal helpers ------------------------------------------------

def _parse_date_param(value: Optional[str], field: str, end_of_day: bool = False) -> Optional[datetime]:
    if not value:
        return None
    try:
        d = datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid {field} date (use YYYY-MM-DD)") from exc
    return datetime.combine(d, time.max if end_of_day else time.min)


async def _notify_super_admins_ticket_created(db: AsyncSession, ticket: SupportTicket) -> None:
    """Fan out a 'new support ticket' notification to all super admins.

    Best-effort: any failure is logged and swallowed so the primary request
    is never blocked. Matches the post-commit notification pattern in
    `app/routers/messages.py`.
    """
    try:
        from app.routers.notifications import create_notification
        result = await db.execute(
            select(User).where(User.role == UserRole.SUPER_ADMIN)
        )
        admins = result.scalars().all()
        preview = ticket.message[:200] + ("..." if len(ticket.message) > 200 else "")
        for admin in admins:
            try:
                await create_notification(
                    db=db,
                    user_id=admin.id,
                    title=f"New support ticket: {ticket.subject[:140]}",
                    message=f"[{ticket.category.value}/{ticket.priority.value}] {preview}",
                    notification_type="info",
                )
            except Exception as inner:
                print(f"[Notifications] Failed to notify super-admin {admin.id} of ticket {ticket.id}: {inner}")
    except Exception as e:
        print(f"[Notifications] Failed to fan out ticket-created notification for {ticket.id}: {e}")


async def _notify_owner_status_change(db: AsyncSession, ticket: SupportTicket) -> None:
    try:
        from app.routers.notifications import create_notification
        nt = "success" if ticket.status == SupportTicketStatus.RESOLVED else "info"
        await create_notification(
            db=db,
            user_id=ticket.user_id,
            title=f"Ticket #{ticket.id[:8]} status: {ticket.status.value}",
            message=f"Your ticket '{ticket.subject[:140]}' is now {ticket.status.value}.",
            notification_type=nt,
        )
    except Exception as e:
        print(f"[Notifications] Failed to send status-change notification for {ticket.id}: {e}")


async def _notify_owner_response_added(db: AsyncSession, ticket: SupportTicket) -> None:
    try:
        from app.routers.notifications import create_notification
        preview = (ticket.admin_response or "")[:200]
        if ticket.admin_response and len(ticket.admin_response) > 200:
            preview += "..."
        await create_notification(
            db=db,
            user_id=ticket.user_id,
            title=f"Support replied: {ticket.subject[:140]}",
            message=preview or "An admin has responded to your ticket.",
            notification_type="info",
        )
    except Exception as e:
        print(f"[Notifications] Failed to send response-added notification for {ticket.id}: {e}")


# ---------- endpoints -------------------------------------------------------

@router.post("/tickets", response_model=SupportTicketOut)
async def create_ticket(
    body: CreateTicketBody,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a support ticket as the current authenticated user."""
    if not body.subject or not body.subject.strip():
        raise HTTPException(status_code=400, detail="Subject is required")
    if not body.message or not body.message.strip():
        raise HTTPException(status_code=400, detail="Message is required")
    if len(body.subject) > 200:
        raise HTTPException(status_code=400, detail="Subject must be 200 characters or fewer")

    try:
        category = SupportCategory(body.category)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid category") from exc

    if body.priority is not None:
        try:
            priority = SupportTicketPriority(body.priority)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid priority") from exc
    else:
        priority = SupportTicketPriority.MEDIUM

    ticket = SupportTicket(
        user_id=current_user.id,
        user_name=getattr(current_user, "name", None),
        user_email=getattr(current_user, "email", None),
        subject=body.subject.strip(),
        category=category,
        priority=priority,
        message=body.message,
        status=SupportTicketStatus.OPEN,
        meta_data=body.meta_data,
    )
    db.add(ticket)
    await db.commit()
    await db.refresh(ticket)

    # Best-effort fan-out to super admins. Runs after the ticket is committed
    # so a notification failure cannot roll back the ticket creation.
    await _notify_super_admins_ticket_created(db, ticket)

    return SupportTicketOut.from_model(ticket)


@router.get("/my-tickets", response_model=list[SupportTicketOut])
async def list_my_tickets(
    status: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List the current user's own tickets. Optional ?status= filter."""
    stmt = select(SupportTicket).where(SupportTicket.user_id == current_user.id)
    if status:
        try:
            stmt = stmt.where(SupportTicket.status == SupportTicketStatus(status))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}") from exc
    stmt = stmt.order_by(SupportTicket.created_at.desc())
    rows = (await db.execute(stmt)).scalars().all()
    return [SupportTicketOut.from_model(t) for t in rows]


@router.get("/tickets", response_model=list[SupportTicketOut])
async def list_all_tickets(
    status: Optional[str] = None,
    priority: Optional[str] = None,
    category: Optional[str] = None,
    from_: Optional[str] = Query(default=None, alias="from"),
    to: Optional[str] = None,
    current_user: User = Depends(get_current_super_admin),
    db: AsyncSession = Depends(get_db),
):
    """Super-admin only: list all tickets with optional filters."""
    stmt = select(SupportTicket)
    if status:
        try:
            stmt = stmt.where(SupportTicket.status == SupportTicketStatus(status))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}") from exc
    if priority:
        try:
            stmt = stmt.where(SupportTicket.priority == SupportTicketPriority(priority))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=f"Invalid priority: {priority}") from exc
    if category:
        try:
            stmt = stmt.where(SupportTicket.category == SupportCategory(category))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=f"Invalid category: {category}") from exc

    dt_from = _parse_date_param(from_, "from", end_of_day=False)
    dt_to = _parse_date_param(to, "to", end_of_day=True)
    if dt_from is not None:
        stmt = stmt.where(SupportTicket.created_at >= dt_from)
    if dt_to is not None:
        stmt = stmt.where(SupportTicket.created_at <= dt_to)

    stmt = stmt.order_by(SupportTicket.created_at.desc())
    rows = (await db.execute(stmt)).scalars().all()
    return [SupportTicketOut.from_model(t) for t in rows]


@router.get("/tickets/{ticket_id}", response_model=SupportTicketOut)
async def get_ticket(
    ticket_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return one ticket. Owner or super admin only."""
    ticket = await db.get(SupportTicket, ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found")
    if ticket.user_id != current_user.id and current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=403, detail="Forbidden")
    return SupportTicketOut.from_model(ticket)


@router.patch("/tickets/{ticket_id}/status", response_model=SupportTicketOut)
async def update_ticket_status(
    ticket_id: str,
    body: UpdateStatusBody,
    current_user: User = Depends(get_current_super_admin),
    db: AsyncSession = Depends(get_db),
):
    """Super-admin only: change a ticket's status."""
    ticket = await db.get(SupportTicket, ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found")

    try:
        new_status = SupportTicketStatus(body.status)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid status") from exc

    ticket.status = new_status
    if new_status in (SupportTicketStatus.RESOLVED, SupportTicketStatus.CLOSED) and ticket.resolved_at is None:
        ticket.resolved_at = datetime.utcnow()

    # admin_notes is accepted on the wire for parity with frontend, but is not
    # persisted as a separate column. If provided, append it to admin_response
    # so it isn't silently dropped.
    if body.admin_notes:
        prefix = (ticket.admin_response + "\n\n") if ticket.admin_response else ""
        ticket.admin_response = f"{prefix}[status:{new_status.value}] {body.admin_notes}"

    await db.commit()
    await db.refresh(ticket)

    await _notify_owner_status_change(db, ticket)

    return SupportTicketOut.from_model(ticket)


@router.patch("/tickets/{ticket_id}/response", response_model=SupportTicketOut)
async def update_ticket_response(
    ticket_id: str,
    body: UpdateResponseBody,
    current_user: User = Depends(get_current_super_admin),
    db: AsyncSession = Depends(get_db),
):
    """Super-admin only: set the admin_response. Auto-assigns the ticket to
    the responder if it has no current assignee."""
    if not body.admin_response or not body.admin_response.strip():
        raise HTTPException(status_code=400, detail="admin_response is required")

    ticket = await db.get(SupportTicket, ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found")

    ticket.admin_response = body.admin_response
    if ticket.assigned_to is None:
        ticket.assigned_to = current_user.id

    await db.commit()
    await db.refresh(ticket)

    await _notify_owner_response_added(db, ticket)

    return SupportTicketOut.from_model(ticket)


@router.delete("/tickets/{ticket_id}")
async def delete_ticket(
    ticket_id: str,
    current_user: User = Depends(get_current_super_admin),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Super-admin only: hard-delete a ticket."""
    ticket = await db.get(SupportTicket, ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found")
    await db.delete(ticket)
    await db.commit()
    return {"ok": True}
