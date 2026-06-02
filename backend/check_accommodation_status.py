import asyncio
from sqlalchemy.future import select
from app.database import AsyncSessionLocal
from app.models.accommodation import Accommodation

async def check_acc():
    async with AsyncSessionLocal() as session:
        # Find Holywood
        res = await session.execute(select(Accommodation).where(Accommodation.name.like("%Holywood%")))
        accs = res.scalars().all()
        
        with open("acc_status.txt", "w") as f:
            if not accs:
                f.write("No 'Holywood' accommodation found!\n")
                return
            
            for acc in accs:
                f.write(f"ID: {acc.id}\n")
                f.write(f"Name: {acc.name}\n")
                f.write(f"Status: {acc.status}\n")
                f.write(f"Is Verified: {acc.is_verified}\n")
                f.write("-" * 20 + "\n")

if __name__ == "__main__":
    asyncio.run(check_acc())
