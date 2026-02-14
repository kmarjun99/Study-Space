from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, and_, desc, func
from pydantic import BaseModel
from datetime import datetime
import uuid

from app.database import get_db
from app.deps import get_current_user
from app.models.user import User
from app.models.message import Conversation as ConversationModel, Message as MessageModel
from app.models.reading_room import ReadingRoom
from app.models.accommodation import Accommodation

router = APIRouter(prefix="/messages", tags=["messages"])


# Pydantic schemas
class MessageCreate(BaseModel):
    receiver_id: str
    content: str
    venue_id: str | None = None


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
    venue_id: str | None = None
    venue_name: str | None = None

    class Config:
        from_attributes = True


class ConversationResponse(BaseModel):
    id: str
    participant_ids: List[str]
    participants: List[dict]
    last_message: MessageResponse | None = None
    unread_count: int
    venue_id: str | None = None
    venue_name: str | None = None
    venue_type: str | None = None

    class Config:
        from_attributes = True


@router.post("/send", response_model=MessageResponse)
async def send_message(
    message_data: MessageCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Send a message to another user"""
    
    # Verify receiver exists
    receiver_result = await db.execute(select(User).where(User.id == message_data.receiver_id))
    receiver = receiver_result.scalar_one_or_none()
    
    if not receiver:
        raise HTTPException(status_code=404, detail="Receiver not found")
    
    # Find or create conversation
    # Note: For simple send, we might not have venue context easily unless passed.
    # If passed in message_data, we use it. 
    # Current frontend simple send might not pass venue_id? 
    # But if it's from a specific context, it should.
    
    query = select(ConversationModel).where(
        or_(
            and_(
                ConversationModel.participant1_id == current_user.id,
                ConversationModel.participant2_id == message_data.receiver_id
            ),
            and_(
                ConversationModel.participant1_id == message_data.receiver_id,
                ConversationModel.participant2_id == current_user.id
            )
        )
    )

    # If venue_id is provided in message creation, try to match conversation for that venue
    if message_data.venue_id:
         # We don't know type here easily unless we fetch venue or pass it.
         # For safety, let's try to match either.
         query = query.where(
             or_(
                 ConversationModel.venue_id == message_data.venue_id,
                 ConversationModel.accommodation_id == message_data.venue_id
             )
         )

    conv_result = await db.execute(query)
    conversation = conv_result.scalar_one_or_none()
    
    if not conversation:
        # Create new conversation
        # If venue_id passed, we need to know type to assign correctly...
        # This part is tricky without type. 
        # But standard flow uses /conversations/start which handles type.
        # Direct send is usually for existing chats.
        # If no chat exists, we create a generic one or try update it later?
        # For now, create basic conversation (maybe without venue if type unknown)
        
        conversation = ConversationModel(
            id=str(uuid.uuid4()),
            participant1_id=current_user.id,
            participant2_id=message_data.receiver_id,
            # If we don't know type, we might misassign. Safe to leave null if unsure?
            # Or assume ReadingRoom if matches?
            # Let's leave venue specific logic to start_conversation mostly.
            venue_id=message_data.venue_id if not message_data.venue_id else None, 
            # Logic hole: if we send message with venue_id but no chat exists, we might lose context?
            # Ideally frontend calls /start first.
            created_at=datetime.utcnow(),
            last_message_at=datetime.utcnow()
        )
        db.add(conversation)
        await db.flush()
    
    # Create message
    message = MessageModel(
        id=str(uuid.uuid4()),
        conversation_id=conversation.id,
        sender_id=current_user.id,
        receiver_id=message_data.receiver_id,
        content=message_data.content,
        timestamp=datetime.utcnow(),
        read=False
    )
    db.add(message)
    
    # Update conversation last message time
    conversation.last_message_at = datetime.utcnow()
    
    await db.commit()
    await db.refresh(message)
    
    # Create notification for receiver (optional)
    try:
        from app.routers.notifications import create_notification
        await create_notification(
            db=db,
            user_id=message_data.receiver_id,
            title=f"New message from {current_user.name}",
            message=message_data.content[:100] + "..." if len(message_data.content) > 100 else message_data.content,
            notification_type="info",
            message_id=message.id
        )
    except Exception as e:
        print(f"Failed to create notification: {e}")
    
    return MessageResponse(
        id=message.id,
        conversation_id=message.conversation_id,
        sender_id=message.sender_id,
        sender_name=current_user.name,
        sender_role=current_user.role,
        receiver_id=message.receiver_id,
        receiver_name=receiver.name,
        receiver_role=receiver.role,
        content=message.content,
        timestamp=message.timestamp.isoformat(),
        read=message.read,
        venue_id=conversation.venue_id
    )


@router.get("/conversations", response_model=List[ConversationResponse])
async def get_conversations(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get all conversations for current user"""
    
    result = await db.execute(
        select(ConversationModel)
        .where(
            or_(
                ConversationModel.participant1_id == current_user.id,
                ConversationModel.participant2_id == current_user.id
            )
        )
        .order_by(desc(ConversationModel.last_message_at))
    )
    conversations = result.scalars().all()
    
    response_list = []
    for conv in conversations:
        # Get other participant
        other_user_id = conv.participant2_id if conv.participant1_id == current_user.id else conv.participant1_id
        other_user_result = await db.execute(select(User).where(User.id == other_user_id))
        other_user = other_user_result.scalar_one_or_none()
        
        if not other_user:
            continue
        
        # Get last message
        last_msg_result = await db.execute(
            select(MessageModel)
            .where(MessageModel.conversation_id == conv.id)
            .order_by(desc(MessageModel.timestamp))
            .limit(1)
        )
        last_message = last_msg_result.scalar_one_or_none()
        
        # Count unread messages
        unread_result = await db.execute(
            select(func.count(MessageModel.id))
            .where(
                and_(
                    MessageModel.conversation_id == conv.id,
                    MessageModel.receiver_id == current_user.id,
                    MessageModel.read == False
                )
            )
        )
        unread_count = unread_result.scalar()
        
        # Get sender info for last message
        last_msg_response = None
        if last_message:
            sender_result = await db.execute(select(User).where(User.id == last_message.sender_id))
            sender = sender_result.scalar_one_or_none()
            receiver_result = await db.execute(select(User).where(User.id == last_message.receiver_id))
            receiver = receiver_result.scalar_one_or_none()
            
            if sender and receiver:
                last_msg_response = MessageResponse(
                    id=last_message.id,
                    conversation_id=last_message.conversation_id,
                    sender_id=last_message.sender_id,
                    sender_name=sender.name,
                    sender_role=sender.role,
                    receiver_id=last_message.receiver_id,
                    receiver_name=receiver.name,
                    receiver_role=receiver.role,
                    content=last_message.content,
                    timestamp=last_message.timestamp.isoformat(),
                    read=last_message.read
                )
        
        # Get venue name based on type
        venue_name = None
        if conv.venue_type == 'accommodation' and conv.accommodation_id:
             venue_result = await db.execute(select(Accommodation).where(Accommodation.id == conv.accommodation_id))
             venue = venue_result.scalar_one_or_none()
             if venue:
                 venue_name = venue.name
        elif conv.venue_id: # Default to Reading Room if venue_id exists
             venue_result = await db.execute(select(ReadingRoom).where(ReadingRoom.id == conv.venue_id))
             venue = venue_result.scalar_one_or_none()
             if venue:
                 venue_name = venue.name
        
        response_list.append(ConversationResponse(
            id=conv.id,
            participant_ids=[conv.participant1_id, conv.participant2_id],
            participants=[
                {
                    "id": current_user.id,
                    "name": current_user.name,
                    "role": current_user.role,
                    "avatarUrl": getattr(current_user, 'avatar_url', None)
                },
                {
                    "id": other_user.id,
                    "name": other_user.name,
                    "role": other_user.role,
                    "avatarUrl": getattr(other_user, 'avatar_url', None)
                }
            ],
            last_message=last_msg_response,
            unread_count=unread_count or 0,
            venue_id=conv.venue_id if conv.venue_type != 'accommodation' else conv.accommodation_id,
            venue_name=venue_name,
            venue_type=conv.venue_type
        ))
    
    return response_list


@router.get("/conversations/{conversation_id}/messages", response_model=List[MessageResponse])
async def get_messages(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get all messages in a conversation"""
    
    # Verify user is part of conversation
    conv_result = await db.execute(
        select(ConversationModel).where(ConversationModel.id == conversation_id)
    )
    conversation = conv_result.scalar_one_or_none()
    
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    if current_user.id not in [conversation.participant1_id, conversation.participant2_id]:
        raise HTTPException(status_code=403, detail="Not authorized to view this conversation")
    
    # Get messages
    result = await db.execute(
        select(MessageModel)
        .where(MessageModel.conversation_id == conversation_id)
        .order_by(MessageModel.timestamp)
    )
    messages = result.scalars().all()
    
    response_list = []
    for msg in messages:
        sender_result = await db.execute(select(User).where(User.id == msg.sender_id))
        sender = sender_result.scalar_one_or_none()
        receiver_result = await db.execute(select(User).where(User.id == msg.receiver_id))
        receiver = receiver_result.scalar_one_or_none()
        
        if sender and receiver:
            response_list.append(MessageResponse(
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
                read=msg.read
            ))
    
    return response_list


@router.put("/{message_id}/read")
async def mark_message_read(
    message_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Mark a message as read"""
    
    result = await db.execute(
        select(MessageModel).where(MessageModel.id == message_id)
    )
    message = result.scalar_one_or_none()
    
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")
    
    if message.receiver_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    message.read = True
    await db.commit()
    
    return {"status": "success"}


@router.put("/conversations/{conversation_id}/read")
async def mark_conversation_read(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Mark all messages in conversation as read"""
    
    result = await db.execute(
        select(MessageModel)
        .where(
            and_(
                MessageModel.conversation_id == conversation_id,
                MessageModel.receiver_id == current_user.id,
                MessageModel.read == False
            )
        )
    )
    messages = result.scalars().all()
    
    for msg in messages:
        msg.read = True
    
    await db.commit()
    
    return {"status": "success", "marked_read": len(messages)}


@router.get("/unread-count")
async def get_unread_count(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get total unread message count"""
    
    result = await db.execute(
        select(func.count(MessageModel.id))
        .where(
            and_(
                MessageModel.receiver_id == current_user.id,
                MessageModel.read == False
            )
        )
    )
    count = result.scalar()
    
    return {"count": count or 0}


@router.post("/conversations/start")
async def start_conversation(
    data: dict,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Start or get existing conversation with a user, ensuring venue context."""
    
    participant_id = data.get("participant_id")
    venue_id = data.get("venue_id")
    venue_type = data.get("venue_type") # 'reading_room' (default) or 'accommodation'
    
    if not participant_id:
        raise HTTPException(status_code=400, detail="participant_id required")
    
    # Check if conversation exists
    # If venue_id is provided, we check for a conversation TIED to that venue.
    # This enforces separation: 1 chat per venue.
    
    query = select(ConversationModel).where(
        or_(
            and_(
                ConversationModel.participant1_id == current_user.id,
                ConversationModel.participant2_id == participant_id
            ),
            and_(
                ConversationModel.participant1_id == participant_id,
                ConversationModel.participant2_id == current_user.id
            )
        )
    )
    
    if venue_id:
        if venue_type == 'accommodation':
            query = query.where(ConversationModel.accommodation_id == venue_id)
        else:
            query = query.where(ConversationModel.venue_id == venue_id)
            
    result = await db.execute(query)
    conversation = result.scalar_one_or_none()
    
    if conversation:
        # Return existing conversation
        other_user_id = conversation.participant2_id if conversation.participant1_id == current_user.id else conversation.participant1_id
        other_user_result = await db.execute(select(User).where(User.id == other_user_id))
        other_user = other_user_result.scalar_one_or_none()
        
        # Get venue name based on type
        venue_name = None
        if conversation.venue_type == 'accommodation' and conversation.accommodation_id:
             venue_result = await db.execute(select(Accommodation).where(Accommodation.id == conversation.accommodation_id))
             venue = venue_result.scalar_one_or_none()
             if venue:
                 venue_name = venue.name
        elif conversation.venue_id: 
             venue_result = await db.execute(select(ReadingRoom).where(ReadingRoom.id == conversation.venue_id))
             venue = venue_result.scalar_one_or_none()
             if venue:
                 venue_name = venue.name
        
        return ConversationResponse(
            id=conversation.id,
            participant_ids=[conversation.participant1_id, conversation.participant2_id],
            participants=[
                {
                    "id": current_user.id,
                    "name": current_user.name,
                    "role": current_user.role,
                    "avatarUrl": getattr(current_user, 'avatar_url', None)
                },
                {
                    "id": other_user.id,
                    "name": other_user.name,
                    "role": other_user.role,
                    "avatarUrl": getattr(other_user, 'avatar_url', None)
                }
            ] if other_user else [],
            last_message=None,
            unread_count=0,
            venue_id=conversation.venue_id if conversation.venue_type != 'accommodation' else conversation.accommodation_id,
            venue_name=venue_name,
            venue_type=conversation.venue_type
        )
    
    # Create new conversation
    rr_id = None
    acc_id = None
    if venue_type == 'accommodation':
        acc_id = venue_id
    elif venue_id: # Assume reading room if ID exists but not accommodation
        rr_id = venue_id
        
    conversation = ConversationModel(
        id=str(uuid.uuid4()),
        participant1_id=current_user.id,
        participant2_id=participant_id,
        venue_id=rr_id,
        accommodation_id=acc_id,
        venue_type=venue_type,
        created_at=datetime.utcnow(),
        last_message_at=datetime.utcnow()
    )
    db.add(conversation)
    await db.commit()
    await db.refresh(conversation)
    
    other_user_result = await db.execute(select(User).where(User.id == participant_id))
    other_user = other_user_result.scalar_one_or_none()
    
    # Fetch venue name for response
    venue_name = None
    if venue_type == 'accommodation' and acc_id:
            venue_result = await db.execute(select(Accommodation).where(Accommodation.id == acc_id))
            venue = venue_result.scalar_one_or_none()
            if venue:
                venue_name = venue.name
    elif rr_id:
            venue_result = await db.execute(select(ReadingRoom).where(ReadingRoom.id == rr_id))
            venue = venue_result.scalar_one_or_none()
            if venue:
                venue_name = venue.name

    return ConversationResponse(
        id=conversation.id,
        participant_ids=[conversation.participant1_id, conversation.participant2_id],
        participants=[
            {
                "id": current_user.id,
                "name": current_user.name,
                "role": current_user.role,
                "avatarUrl": getattr(current_user, 'avatar_url', None)
            },
            {
                "id": other_user.id,
                "name": other_user.name,
                "role": other_user.role,
                "avatarUrl": getattr(other_user, 'avatar_url', None)
            }
        ] if other_user else [],
        last_message=None,
        unread_count=0,
        venue_id=venue_id,
        venue_name=venue_name,
        venue_type=venue_type
    )
