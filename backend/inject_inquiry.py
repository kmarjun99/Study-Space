import asyncio
from sqlalchemy.future import select
from app.database import AsyncSessionLocal
from app.models.inquiry import Inquiry, InquiryStatus, InquiryType
from app.models.user import User
from app.models.accommodation import Accommodation
from datetime import datetime

async def inject_inquiry():
    async with AsyncSessionLocal() as session:
        # Get Ajay
        res = await session.execute(select(User).where(User.email == "ajuvinod5873@gmail.com"))
        student = res.scalars().first()
        if not student:
            print("Ajay not found")
            return

        # Get Accommodation (Holywood)
        res_acc = await session.execute(select(Accommodation).limit(1))
        acc = res_acc.scalars().first()
        if not acc:
            print("No accommodation found")
            return
            
        print(f"Creating inquiry for Student {student.name} -> Acc {acc.name} (Owner {acc.owner_id})")
        
        inquiry = Inquiry(
            id="manual-test-id-123",
            accommodation_id=acc.id,
            student_id=student.id,
            owner_id=acc.owner_id,
            type=InquiryType.QUESTION,
            question="This is a manual test message to verify the UI.",
            student_name=student.name,
            student_phone=student.phone or "1234567890",
            status=InquiryStatus.PENDING,
            created_at=datetime.utcnow()
        )
        
        session.add(inquiry)
        await session.commit()
        print("Inquiry inserted.")

if __name__ == "__main__":
    asyncio.run(inject_inquiry())
