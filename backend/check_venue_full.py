import asyncio
from sqlalchemy import select
from app.database import AsyncSessionLocal
from app.models.reading_room import ReadingRoom
import json

VENUE_ID = "4a5a3743-0ba6-42de-b6ed-7824a85555d8"

async def check_venue():
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(ReadingRoom).where(ReadingRoom.id == VENUE_ID))
        venue = result.scalars().first()
        
        if venue:
            print(f"Venue: {venue.name}")
            # print all dict attributes
            for k, v in venue.__dict__.items():
                if not k.startswith('_'):
                    print(f"{k}: {v} (Type: {type(v)})")
        else:
            print("Venue not found")

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(check_venue())
