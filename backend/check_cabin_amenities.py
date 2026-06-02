import asyncio
from sqlalchemy import select
from app.database import AsyncSessionLocal
from app.models.reading_room import Cabin

VENUE_ID = "4a5a3743-0ba6-42de-b6ed-7824a85555d8"

async def check_cabin_amenities():
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Cabin).where(Cabin.reading_room_id == VENUE_ID))
        cabins = result.scalars().all()
        
        print(f"Found {len(cabins)} cabins for venue {VENUE_ID}")
        for c in cabins:
            print(f"ID: {c.id}, Amenities: {c.amenities} (Type: {type(c.amenities)})")

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(check_cabin_amenities())
