import asyncio
from sqlalchemy.future import select
from app.database import AsyncSessionLocal
from app.models.inquiry import Inquiry
from app.models.user import User
from app.models.accommodation import Accommodation

async def check_owner():
    async with AsyncSessionLocal() as session:
        # Find the manuals injected inquiry
        res = await session.execute(select(Inquiry).where(Inquiry.question.like("%manual test%")))
        inq = res.scalars().first()
        
        with open("owner_details.txt", "w") as f:
            if not inq:
                f.write("Control Inquiry NOT FOUND!\n")
            owner = res_user.scalars().first()
            if owner:
                f.write(f"Owner Name: {owner.name}\n")
                f.write(f"Owner Email: {owner.email}\n")
                f.write(f"Owner Role: {owner.role}\n")
            else:
                f.write("Owner User NOT FOUND!\n")

if __name__ == "__main__":
    asyncio.run(check_owner())
