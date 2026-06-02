import asyncio
from sqlalchemy.future import select
from app.database import AsyncSessionLocal
from app.models.accommodation import Accommodation
from app.models.reading_room import ListingStatus

async def check_acc():
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Accommodation).where(Accommodation.name.ilike("%Holywood%")))
        accs = result.scalars().all()
        for acc in accs:
            print(f"Name: {acc.name}")
            print(f"Status: {acc.status}")
            print(f"Raw Status Value: {acc.status.value if hasattr(acc.status, 'value') else acc.status}")
            print(f"Is LIVE?: {acc.status == ListingStatus.LIVE}")

if __name__ == "__main__":
    asyncio.run(check_acc())
