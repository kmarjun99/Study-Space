import logging
logging.basicConfig(level=logging.ERROR)
import asyncio
from sqlalchemy.future import select
from app.database import AsyncSessionLocal
from app.models.reading_room import ReadingRoom
from app.models.accommodation import Accommodation

async def check_hyd():
    async with AsyncSessionLocal() as session:
        print("--- START CHECK ---")
        # Check Reading Rooms
        res_rr = await session.execute(select(ReadingRoom).where(ReadingRoom.city == "Hyderabad"))
        rooms = res_rr.scalars().all()
        print(f"Reading Rooms in Hyderabad: {len(rooms)}")
        for r in rooms:
            print(f"- {r.name} (Status: {r.status})")

        # Check Accommodations
        res_acc = await session.execute(select(Accommodation).where(Accommodation.city == "Hyderabad"))
        accs = res_acc.scalars().all()
        print(f"\nAccommodations in Hyderabad: {len(accs)}")
        for a in accs:
            print(f"- {a.name} (Status: {a.status})")
        print("--- END CHECK ---")

if __name__ == "__main__":
    asyncio.run(check_hyd())
