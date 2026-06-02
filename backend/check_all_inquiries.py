import asyncio
from sqlalchemy.future import select
from app.database import AsyncSessionLocal
from app.models.inquiry import Inquiry

async def check_all():
    async with AsyncSessionLocal() as session:
        res = await session.execute(select(Inquiry))
        inqs = res.scalars().all()
        print(f"Total Inquiries in DB: {len(inqs)}")
        for i in inqs:
            print(f"ID: {i.id} | Student: {i.student_id} | Q: {i.question}")

if __name__ == "__main__":
    asyncio.run(check_all())
