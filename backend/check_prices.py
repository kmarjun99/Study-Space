import asyncio
from sqlalchemy.future import select
from app.database import AsyncSessionLocal
from app.models.reading_room import ReadingRoom

async def check_prices():
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(ReadingRoom))
        rooms = result.scalars().all()
        for room in rooms:
            print(f"Room: {room.name}, ID: {room.id}")
            print(f"  Price Start: {room.price_start}")

if __name__ == "__main__":
    asyncio.run(check_prices())
