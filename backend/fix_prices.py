import asyncio
from sqlalchemy.future import select
from app.database import AsyncSessionLocal
from app.models.reading_room import ReadingRoom, Cabin

async def fix_prices():
    async with AsyncSessionLocal() as session:
        # Find the room created by likely admin or just the one with 2998
        result = await session.execute(select(ReadingRoom).where(ReadingRoom.price_start == 2998))
        rooms = result.scalars().all()
        
        if not rooms:
            print("No rooms found with price 2998.")
        
        for room in rooms:
            print(f"Updating Room: {room.name} (ID: {room.id}) from {room.price_start} to 3000.0")
            room.price_start = 3000.0
            
            # Update cabins
            result_cabins = await session.execute(select(Cabin).where(Cabin.reading_room_id == room.id))
            cabins = result_cabins.scalars().all()
            
            count = 0
            for cabin in cabins:
                if cabin.price == 2998:
                    cabin.price = 3000.0
                    count += 1
            
            print(f"Updated {count} cabins for this room.")
            
        await session.commit()
        print("✅ Corrected prices to 3000.")

if __name__ == "__main__":
    asyncio.run(fix_prices())
