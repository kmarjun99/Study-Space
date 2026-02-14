"""
Seed sample messages for testing the messaging system
"""
import asyncio
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timedelta
import uuid

from app.database import AsyncSessionLocal
from app.models.user import User, UserRole
from app.models.reading_room import ReadingRoom
from app.models.message import Conversation, Message as MessageModel


async def seed_messages():
    """Create sample conversations and messages"""
    
    async with AsyncSessionLocal() as db:
        print("🌱 Starting message seeding...")
        
        # Get all admins (venue owners)
        admin_result = await db.execute(
            select(User).where(User.role == UserRole.ADMIN).limit(3)
        )
        admins = admin_result.scalars().all()
        
        # Get all students
        student_result = await db.execute(
            select(User).where(User.role == UserRole.STUDENT).limit(5)
        )
        students = student_result.scalars().all()
        
        if not admins:
            print("❌ No admin users found. Please seed users first.")
            return
        
        if not students:
            print("❌ No student users found. Please seed users first.")
            return
        
        # Get some venues
        venue_result = await db.execute(
            select(ReadingRoom).limit(3)
        )
        venues = venue_result.scalars().all()
        
        print(f"Found {len(admins)} admins, {len(students)} students, {len(venues)} venues")
        
        conversations_created = 0
        messages_created = 0
        
        # Create conversations between students and venue owners
        for i, admin in enumerate(admins[:2]):  # First 2 admins
            for j, student in enumerate(students[:3]):  # First 3 students
                # Check if conversation already exists
                existing = await db.execute(
                    select(Conversation).where(
                        ((Conversation.participant1_id == admin.id) & (Conversation.participant2_id == student.id)) |
                        ((Conversation.participant1_id == student.id) & (Conversation.participant2_id == admin.id))
                    )
                )
                if existing.scalar_one_or_none():
                    print(f"⏭️  Conversation already exists between {admin.name} and {student.name}")
                    continue
                
                # Create conversation
                venue_id = venues[i % len(venues)].id if venues else None
                conversation = Conversation(
                    id=str(uuid.uuid4()),
                    participant1_id=student.id,
                    participant2_id=admin.id,
                    venue_id=venue_id,
                    created_at=datetime.utcnow() - timedelta(days=2-i, hours=j),
                    last_message_at=datetime.utcnow() - timedelta(hours=j+1)
                )
                db.add(conversation)
                await db.flush()
                conversations_created += 1
                
                # Create some sample messages
                sample_messages = [
                    {
                        "sender": student,
                        "content": f"Hi! I'm interested in booking a spot at your reading room. Is it available for next week?",
                        "time_offset": timedelta(days=2-i, hours=j)
                    },
                    {
                        "sender": admin,
                        "content": f"Hello {student.name}! Yes, we have availability next week. What dates are you looking at?",
                        "time_offset": timedelta(days=2-i, hours=j-1)
                    },
                    {
                        "sender": student,
                        "content": "I need it from Monday to Friday, 9 AM to 6 PM. Do you have air conditioning?",
                        "time_offset": timedelta(days=1, hours=j+2)
                    },
                    {
                        "sender": admin,
                        "content": "Yes, all our rooms are fully air-conditioned. The rate is ₹200/hour. Would you like to proceed with the booking?",
                        "time_offset": timedelta(hours=j+3)
                    }
                ]
                
                # Only add first 2-3 messages for some conversations to vary
                num_messages = 2 + (i + j) % 3
                
                for idx, msg_data in enumerate(sample_messages[:num_messages]):
                    message = MessageModel(
                        id=str(uuid.uuid4()),
                        conversation_id=conversation.id,
                        sender_id=msg_data["sender"].id,
                        receiver_id=admin.id if msg_data["sender"].id == student.id else student.id,
                        content=msg_data["content"],
                        timestamp=datetime.utcnow() - msg_data["time_offset"],
                        read=(idx < num_messages - 1)  # Last message unread
                    )
                    db.add(message)
                    messages_created += 1
                
                # Update conversation last message time
                conversation.last_message_at = datetime.utcnow() - sample_messages[num_messages-1]["time_offset"]
                
                print(f"✅ Created conversation between {student.name} and {admin.name} with {num_messages} messages")
        
        await db.commit()
        
        print(f"\n🎉 Seeding complete!")
        print(f"   - {conversations_created} conversations created")
        print(f"   - {messages_created} messages created")
        print(f"\n💡 Tip: Login as any student or admin to see the messages!")


if __name__ == "__main__":
    asyncio.run(seed_messages())
