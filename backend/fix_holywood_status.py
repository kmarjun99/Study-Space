import asyncio
from sqlalchemy import select
from app.database import AsyncSessionLocal
from app.models.accommodation import Accommodation
from app.models.reading_room import ListingStatus

async def fix_holywood_status():
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Accommodation).where(Accommodation.name.ilike("%Holywood%")))
        acc = result.scalars().first()
        if acc:
            print(f"Found Accommodation: {acc.name} (ID: {acc.id})")
            print(f"Current Status: {acc.status}")
            
            # Revert to PAYMENT_PENDING
            acc.status = ListingStatus.PAYMENT_PENDING
            # Ensure is_verified is False
            acc.is_verified = False
            
            await session.commit()
            print(f"Updated Status to: {acc.status}")
        else:
            print("Accommodation 'Holywood' not found.")

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(fix_holywood_status())
