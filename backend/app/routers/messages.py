from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, and_, desc, func, update
from pydantic import BaseModel, Field, field_validator
from datetime import datetime
import uuid

from app.database import get_db
from app.deps import get_current_user
from app.models.user import User
from app.models.message import Conversation as ConversationModel, Message as MessageModel
from app.models.reading_room import ReadingRoom
from app.models.accommodation import Accommodation
from app.core.socket_manager import (
    send_message_notification,
    send_conversation_update,
    manager,
)

router = APIRouter(prefix="/messages", tags=["messages"])

MAX_MESSAGE_LENGTH = 1000


# ============================================================
# Pydantic schemas
# ============================================================

class MessageCreate(BaseModel):
    receiver_id: str
    content: str = Field(..., min_length=1, max_length=MAX_MESSAGE_LENGTH)
    venue_id: Optional[str] = None
    venue_type: Optional[str] = None  # 'reading_room' or 'accommodation'

    @field_validator("content")
    @classmethod
    def strip_content(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Message content cannot be empty")
        return v


class StartConversationRequest(BaseModel):
    participant_id: str
    venue_id: Optional[str] = None
    venue_type: Optional[str] = None


class TypingEvent(BaseModel):
    receiver_id: str
    conversation_id: str
    is_typing: bool = True


class MessageResponse(BaseModel):
    id: str
    conversation_id: str
    sender_id: str
    sender_name: str
    sender_role: str
    receiver_id: str
    receiver_name: str
    receiver_role: str
    content: str
    timestamp: str
    read: bool
    venue_id: Optional[str] = None
    venue_name: Optional[str] = None

    class Config:
        from_attributes = True


class ConversationResponse(BaseModel):
    id: str
    participant_ids: List[str]
    participants: List[dict]
    last_message: Optional[MessageResponse] = None
    unread_count: int
    venue_id: Optional[str] = None
    venue_name: Optional[str] = None
    venue_type: Optional[str] = None

    class Config:
        from_attributes = True


# ============================================================
# Helpers
# ============================================================

def _participant_dict(user: User) -> dict:
    return {
        "id": user.id,
        "name": user.name,
        "role": user.role,
        "avatarUrl": getattr(user, "avatar_url", None),
    }


async def _resolve_venue_name(db: AsyncSession, conv: ConversationModel) -> Optional[str]:
    """Resolve venue name based on conversation's venue_type."""
    if conv.venue_type == "accommodation" and conv.accommodation_id:
        result = await db.execute(
            select(Accommodation.name).where(Accommodation.id == conv.accommodation_id)
        )
        return result.scalar_one_or_none()
    if conv.venue_id:
        result = await db.execute(
            select(ReadingRoom.name).where(ReadingRoom.id == conv.venue_id)
        )
        return result.scalar_one_or_none()
    return None


def _build_message_response(msg: MessageModel, sender: User, receiver: User,
                            venue_name: Optional[str] = None) -> MessageResponse:
    return MessageResponse(
        id=msg.id,
        conversation_id=msg.conversation_id,
        sender_id=msg.sender_id,
        sender_name=sender.name,
        sender_role=sender.role,
        receiver_id=msg.receiver_id,
        receiver_name=receiver.name,
        receiver_role=receiver.role,
        content=msg.content,
        timestamp=msg.timestamp.isoformat(),
        read=msg.read,
        venue_name=venue_name,
    )


# ============================================================
# Endpoints
# ============================================================

@router.post("/send", response_model=MessageResponse)
async def send_message(
    message_data: MessageCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Send a message to another user. Broadcasts in real time via WebSocket."""

    if current_user.id == message_data.receiver_id:
        raise HTTPException(status_code=400, detail="Cannot send message to yourself")

    receiver = (await db.execute(
        select(User).where(User.id == message_data.receiver_id)
    )).scalar_one_or_none()
    if not receiver:
        raise HTTPException(status_code=404, detail="Receiver not found")

    # Find existing conversation between the two users for this venue context
    query = select(ConversationModel).where(
        or_(
            and_(
                ConversationModel.participant1_id == current_user.id,
                ConversationModel.participant2_id == message_data.receiver_id,
            ),
            and_(
                ConversationModel.participant1_id == message_data.receiver_id,
                ConversationModel.participant2_id == current_user.id,
            ),
        )
    )

    if message_data.venue_id:
        if message_data.venue_type == "accommodation":
            query = query.where(ConversationModel.accommodation_id == message_data.venue_id)
        else:
            query = query.where(ConversationModel.venue_id == message_data.venue_id)

    conversation = (await db.execute(query)).scalar_one_or_none()

    if not conversation:
        # Create a new conversation. Properly assign venue_id vs accommodation_id.
        rr_id = None
        acc_id = None
        if message_data.venue_id:
            if message_data.venue_type == "accommodation":
                acc_id = message_data.venue_id
            else:
                rr_id = message_data.venue_id

        conversation = ConversationModel(
            id=str(uuid.uuid4()),
            participant1_id=current_user.id,
            participant2_id=message_data.receiver_id,
            venue_id=rr_id,
            accommodation_id=acc_id,
            venue_type=message_data.venue_type,
            created_at=datetime.utcnow(),
            last_message_at=datetime.utcnow(),
        )
        db.add(conversation)
        await db.flush()

    message = MessageModel(
        id=str(uuid.uuid4()),
        conversation_id=conversation.id,
        sender_id=current_user.id,
        receiver_id=message_data.receiver_id,
        content=message_data.content,
        timestamp=datetime.utcnow(),
        read=False,
    )
    db.add(message)
    conversation.last_message_at = datetime.utcnow()

    await db.commit()
    await db.refresh(message)

    venue_name = await _resolve_venue_name(db, conversation)
    response = _build_message_response(message, current_user, receiver, venue_name)
    payload = response.model_dump()

    # Broadcast to BOTH participants so the sender's other tabs/devices update too
    try:
        await send_message_notification(receiver.id, payload)
        await send_message_notification(current_user.id, payload)
    except Exception as e:
        print(f"[WS] Failed to broadcast new message: {e}")

    # Best-effort notification record for the receiver
    try:
        from app.routers.notifications import create_notification
        preview = (
            message_data.content[:100] + "..."
            if len(message_data.content) > 100
            else message_data.content
        )
        await create_notification(
            db=db,
            user_id=receiver.id,
            title=f"New message from {current_user.name}",
            message=preview,
            notification_type="info",
            message_id=message.id,
        )
    except Exception as e:
        print(f"[Notifications] Failed to create notification: {e}")

    return response


@router.get("/conversations", response_model=List[ConversationResponse])
async def get_conversations(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all conversations for the current user. Single-pass loading (no N+1)."""

    # 1. Fetch all conversations for the user
    convs = (await db.execute(
        select(ConversationModel)
        .where(
            or_(
                ConversationModel.participant1_id == current_user.id,
                ConversationModel.participant2_id == current_user.id,
            )
        )
        .order_by(desc(ConversationModel.last_message_at))
    )).scalars().all()

    if not convs:
        return []

    conv_ids = [c.id for c in convs]

    # 2. Fetch all "other" users in one query
    other_user_ids = {
        c.participant2_id if c.participant1_id == current_user.id else c.participant1_id
        for c in convs
    }
    users_result = await db.execute(select(User).where(User.id.in_(other_user_ids)))
    user_map = {u.id: u for u in users_result.scalars().all()}

    # 3. Fetch the latest message per conversation in a single query using
    #    PostgreSQL DISTINCT ON. Falls back to grouping for SQLite (dev).
    last_msg_map: dict[str, MessageModel] = {}
    try:
        last_msgs = (await db.execute(
            select(MessageModel)
            .where(MessageModel.conversation_id.in_(conv_ids))
            .order_by(MessageModel.conversation_id, desc(MessageModel.timestamp))
            .distinct(MessageModel.conversation_id)
        )).scalars().all()
        last_msg_map = {m.conversation_id: m for m in last_msgs}
    except Exception:
        # Fallback for engines that don't support DISTINCT ON (SQLite)
        all_msgs = (await db.execute(
            select(MessageModel)
            .where(MessageModel.conversation_id.in_(conv_ids))
            .order_by(MessageModel.conversation_id, desc(MessageModel.timestamp))
        )).scalars().all()
        for m in all_msgs:
            if m.conversation_id not in last_msg_map:
                last_msg_map[m.conversation_id] = m

    # 4. Fetch unread counts per conversation in one query
    unread_rows = (await db.execute(
        select(MessageModel.conversation_id, func.count(MessageModel.id))
        .where(
            and_(
                MessageModel.conversation_id.in_(conv_ids),
                MessageModel.receiver_id == current_user.id,
                MessageModel.read.is_(False),
            )
        )
        .group_by(MessageModel.conversation_id)
    )).all()
    unread_map = {row[0]: row[1] for row in unread_rows}

    # 5. Bulk-resolve all venue names (reading rooms + accommodations) in two queries
    rr_ids = {c.venue_id for c in convs if c.venue_id and c.venue_type != "accommodation"}
    acc_ids = {c.accommodation_id for c in convs if c.accommodation_id and c.venue_type == "accommodation"}

    rr_name_map: dict[str, str] = {}
    if rr_ids:
        rr_rows = (await db.execute(
            select(ReadingRoom.id, ReadingRoom.name).where(ReadingRoom.id.in_(rr_ids))
        )).all()
        rr_name_map = {row[0]: row[1] for row in rr_rows}

    acc_name_map: dict[str, str] = {}
    if acc_ids:
        acc_rows = (await db.execute(
            select(Accommodation.id, Accommodation.name).where(Accommodation.id.in_(acc_ids))
        )).all()
        acc_name_map = {row[0]: row[1] for row in acc_rows}

    # 6. Build the response
    response_list: List[ConversationResponse] = []
    for conv in convs:
        other_user_id = (
            conv.participant2_id if conv.participant1_id == current_user.id
            else conv.participant1_id
        )
        other_user = user_map.get(other_user_id)
        if not other_user:
            continue

        last_msg = last_msg_map.get(conv.id)
        if not last_msg:
            # Skip conversations with no messages, matches old behaviour
            continue

        # Sender / receiver for the last message
        last_sender = (
            current_user if last_msg.sender_id == current_user.id else other_user
        )
        last_receiver = (
            current_user if last_msg.receiver_id == current_user.id else other_user
        )

        venue_name = (
            acc_name_map.get(conv.accommodation_id) if conv.venue_type == "accommodation"
            else rr_name_map.get(conv.venue_id)
        )

        response_list.append(ConversationResponse(
            id=conv.id,
            participant_ids=[conv.participant1_id, conv.participant2_id],
            participants=[_participant_dict(current_user), _participant_dict(other_user)],
            last_message=_build_message_response(last_msg, last_sender, last_receiver, venue_name),
            unread_count=unread_map.get(conv.id, 0),
            venue_id=(
                conv.accommodation_id if conv.venue_type == "accommodation" else conv.venue_id
            ),
            venue_name=venue_name,
            venue_type=conv.venue_type,
        ))

    return response_list


@router.get("/conversations/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a single conversation by ID."""
    conversation = (await db.execute(
        select(ConversationModel).where(ConversationModel.id == conversation_id)
    )).scalar_one_or_none()

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    if current_user.id not in [conversation.participant1_id, conversation.participant2_id]:
        raise HTTPException(status_code=403, detail="Not authorized to view this conversation")

    other_user_id = (
        conversation.participant2_id if conversation.participant1_id == current_user.id
        else conversation.participant1_id
    )
    other_user = (await db.execute(
        select(User).where(User.id == other_user_id)
    )).scalar_one_or_none()
    if not other_user:
        raise HTTPException(status_code=404, detail="Other participant not found")

    last_msg = (await db.execute(
        select(MessageModel)
        .where(MessageModel.conversation_id == conversation.id)
        .order_by(desc(MessageModel.timestamp))
        .limit(1)
    )).scalar_one_or_none()

    venue_name = await _resolve_venue_name(db, conversation)

    last_msg_response = None
    if last_msg:
        last_sender = current_user if last_msg.sender_id == current_user.id else other_user
        last_receiver = current_user if last_msg.receiver_id == current_user.id else other_user
        last_msg_response = _build_message_response(last_msg, last_sender, last_receiver, venue_name)

    unread_count = (await db.execute(
        select(func.count(MessageModel.id)).where(
            and_(
                MessageModel.conversation_id == conversation.id,
                MessageModel.receiver_id == current_user.id,
                MessageModel.read.is_(False),
            )
        )
    )).scalar() or 0

    return ConversationResponse(
        id=conversation.id,
        participant_ids=[conversation.participant1_id, conversation.participant2_id],
        participants=[_participant_dict(current_user), _participant_dict(other_user)],
        last_message=last_msg_response,
        unread_count=unread_count,
        venue_id=(
            conversation.accommodation_id if conversation.venue_type == "accommodation"
            else conversation.venue_id
        ),
        venue_name=venue_name,
        venue_type=conversation.venue_type,
    )


@router.get("/conversations/{conversation_id}/messages", response_model=List[MessageResponse])
async def get_messages(
    conversation_id: str,
    limit: int = Query(100, ge=1, le=500),
    before: Optional[str] = Query(None, description="ISO timestamp; return messages older than this"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get messages in a conversation with pagination (newest-first cursor)."""

    conversation = (await db.execute(
        select(ConversationModel).where(ConversationModel.id == conversation_id)
    )).scalar_one_or_none()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    if current_user.id not in [conversation.participant1_id, conversation.participant2_id]:
        raise HTTPException(status_code=403, detail="Not authorized to view this conversation")

    msg_query = select(MessageModel).where(MessageModel.conversation_id == conversation_id)
    if before:
        try:
            cutoff = datetime.fromisoformat(before.replace("Z", "+00:00"))
            msg_query = msg_query.where(MessageModel.timestamp < cutoff)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid 'before' timestamp")

    msgs = (await db.execute(
        msg_query.order_by(desc(MessageModel.timestamp)).limit(limit)
    )).scalars().all()

    if not msgs:
        return []

    # Bulk-fetch the two users involved
    other_user_id = (
        conversation.participant2_id if conversation.participant1_id == current_user.id
        else conversation.participant1_id
    )
    other_user = (await db.execute(
        select(User).where(User.id == other_user_id)
    )).scalar_one_or_none()
    if not other_user:
        raise HTTPException(status_code=404, detail="Other participant not found")

    user_map = {current_user.id: current_user, other_user.id: other_user}

    # Return in chronological order (oldest first) for display
    msgs_chronological = list(reversed(msgs))
    return [
        _build_message_response(
            m,
            user_map.get(m.sender_id, current_user),
            user_map.get(m.receiver_id, current_user),
        )
        for m in msgs_chronological
    ]


@router.put("/{message_id}/read")
async def mark_message_read(
    message_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Mark a single message as read."""
    message = (await db.execute(
        select(MessageModel).where(MessageModel.id == message_id)
    )).scalar_one_or_none()

    if not message:
        raise HTTPException(status_code=404, detail="Message not found")
    if message.receiver_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    message.read = True
    await db.commit()

    # Notify the original sender so their UI flips ✓ → ✓✓
    try:
        await manager.send_to_user(message.sender_id, {
            "type": "MESSAGE_READ",
            "payload": {
                "messageId": message.id,
                "conversationId": message.conversation_id,
                "readBy": current_user.id,
            },
        })
    except Exception as e:
        print(f"[WS] Failed to broadcast read receipt: {e}")

    return {"status": "success"}


@router.put("/conversations/{conversation_id}/read")
async def mark_conversation_read(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Bulk-mark all unread messages in a conversation as read using a single UPDATE."""

    # Find the sender so we can notify them after the update
    sender_row = (await db.execute(
        select(MessageModel.sender_id).where(
            and_(
                MessageModel.conversation_id == conversation_id,
                MessageModel.receiver_id == current_user.id,
                MessageModel.read.is_(False),
            )
        ).limit(1)
    )).first()

    result = await db.execute(
        update(MessageModel)
        .where(
            and_(
                MessageModel.conversation_id == conversation_id,
                MessageModel.receiver_id == current_user.id,
                MessageModel.read.is_(False),
            )
        )
        .values(read=True)
        .execution_options(synchronize_session=False)
    )
    await db.commit()
    marked = result.rowcount or 0

    if marked and sender_row:
        try:
            await manager.send_to_user(sender_row[0], {
                "type": "CONVERSATION_READ",
                "payload": {
                    "conversationId": conversation_id,
                    "readBy": current_user.id,
                },
            })
        except Exception as e:
            print(f"[WS] Failed to broadcast conversation read: {e}")

    return {"status": "success", "marked_read": marked}


@router.get("/unread-count")
async def get_unread_count(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get total unread message count for the current user."""
    count = (await db.execute(
        select(func.count(MessageModel.id)).where(
            and_(
                MessageModel.receiver_id == current_user.id,
                MessageModel.read.is_(False),
            )
        )
    )).scalar() or 0
    return {"count": count}


@router.post("/conversations/start", response_model=ConversationResponse)
async def start_conversation(
    data: StartConversationRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Start or get the existing conversation with a user, scoped to a venue if provided."""

    if data.participant_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot start a conversation with yourself")

    # Find an existing conversation matching participants + venue context
    query = select(ConversationModel).where(
        or_(
            and_(
                ConversationModel.participant1_id == current_user.id,
                ConversationModel.participant2_id == data.participant_id,
            ),
            and_(
                ConversationModel.participant1_id == data.participant_id,
                ConversationModel.participant2_id == current_user.id,
            ),
        )
    )
    if data.venue_id:
        if data.venue_type == "accommodation":
            query = query.where(ConversationModel.accommodation_id == data.venue_id)
        else:
            query = query.where(ConversationModel.venue_id == data.venue_id)

    conversation = (await db.execute(query)).scalar_one_or_none()

    if not conversation:
        rr_id = None
        acc_id = None
        if data.venue_id:
            if data.venue_type == "accommodation":
                acc_id = data.venue_id
            else:
                rr_id = data.venue_id

        conversation = ConversationModel(
            id=str(uuid.uuid4()),
            participant1_id=current_user.id,
            participant2_id=data.participant_id,
            venue_id=rr_id,
            accommodation_id=acc_id,
            venue_type=data.venue_type,
            created_at=datetime.utcnow(),
            last_message_at=datetime.utcnow(),
        )
        db.add(conversation)
        await db.commit()
        await db.refresh(conversation)

    # Build response
    other_user = (await db.execute(
        select(User).where(User.id == data.participant_id)
    )).scalar_one_or_none()
    if not other_user:
        raise HTTPException(status_code=404, detail="Participant not found")

    venue_name = await _resolve_venue_name(db, conversation)

    return ConversationResponse(
        id=conversation.id,
        participant_ids=[conversation.participant1_id, conversation.participant2_id],
        participants=[_participant_dict(current_user), _participant_dict(other_user)],
        last_message=None,
        unread_count=0,
        venue_id=(
            conversation.accommodation_id if conversation.venue_type == "accommodation"
            else conversation.venue_id
        ),
        venue_name=venue_name,
        venue_type=conversation.venue_type,
    )


@router.post("/typing")
async def broadcast_typing(
    event: TypingEvent,
    current_user: User = Depends(get_current_user),
):
    """Notify the receiver that the current user is typing. Pure WebSocket fan-out."""
    try:
        await manager.send_to_user(event.receiver_id, {
            "type": "TYPING",
            "payload": {
                "conversationId": event.conversation_id,
                "userId": current_user.id,
                "isTyping": event.is_typing,
            },
        })
    except Exception as e:
        print(f"[WS] Failed to broadcast typing: {e}")
    return {"status": "ok"}
