import asyncio
from sqlalchemy import select
from app.database import AsyncSessionLocal
from app.models.accommodation import Accommodation

async def check_holywood_status():
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Accommodation).where(Accommodation.name.ilike("%Holywood%")))
        acc = result.scalars().first()
        if acc:
            print(f"Accommodation: {acc.name}")
            print(f"ID: {acc.id}")
            print(f"Status: {acc.status}")
            print(f"Owner ID: {acc.owner_id}")
            print(f"Is Verified: {acc.is_verified}")
        else:
            print("Accommodation 'Holywood' not found.")

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(check_holywood_status())
