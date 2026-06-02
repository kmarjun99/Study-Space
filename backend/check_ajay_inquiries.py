import asyncio
from sqlalchemy.future import select
from app.database import AsyncSessionLocal
from app.models.inquiry import Inquiry
from app.models.user import User

async def check_ajay():
    async with AsyncSessionLocal() as session:
        # Get Ajay
        res = await session.execute(select(User).where(User.email == "ajuvinod5873@gmail.com"))
        user = res.scalars().first()
        if not user:
            print("Ajay not found")
            return

        print(f"Checking inquiries for {user.name} ({user.id})")
        res_inq = await session.execute(select(Inquiry).where(Inquiry.student_id == user.id))
        inqs = res_inq.scalars().all()
        print(f"Found {len(inqs)} Inquiries:")
        for i in inqs:
            print(f"- To Owner: {i.owner_id} | Q: {i.question} | Status: {i.status}")

if __name__ == "__main__":
    asyncio.run(check_ajay())
