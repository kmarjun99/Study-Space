import asyncio
from sqlalchemy import select
from app.database import AsyncSessionLocal
from app.models.accommodation import Accommodation

async def check_holywood_status():
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Accommodation).where(Accommodation.name.ilike("%Holywood%")))
        acc = result.scalars().first()
        if acc:
            print(f"STATUS_CHECK:{acc.status}")
            print(f"IS_VERIFIED:{acc.is_verified}")
            print(f"PAYMENT_ID:{acc.payment_id}")
        else:
            print("STATUS_CHECK:NOT_FOUND")

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(check_holywood_status())
