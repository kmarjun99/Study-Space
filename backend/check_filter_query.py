import asyncio
from sqlalchemy import select
from app.database import AsyncSessionLocal
from app.models.accommodation import Accommodation
from app.models.reading_room import ListingStatus

async def check_query():
    # Simulate: include_unverified=True, User is Admin (so show_unverified=True)
    # Replicating logic from accommodations.py
    
    query = select(Accommodation)
    
    # Logic from router:
    # else:
    #    query = query.where(
    #        Accommodation.status.notin_([ListingStatus.DRAFT, ListingStatus.PAYMENT_PENDING])
    #    )
    
    query = query.where(
        Accommodation.status.notin_([ListingStatus.DRAFT, ListingStatus.PAYMENT_PENDING])
    )
    
    async with AsyncSessionLocal() as session:
        result = await session.execute(query)
        accommodations = result.scalars().all()
        
        print(f"Total Found: {len(accommodations)}")
        found_holywood = False
        for acc in accommodations:
            print(f" - {acc.name} ({acc.status})")
            if "Holywood" in acc.name:
                found_holywood = True
                
        if found_holywood:
            print("FAIL: Holywood is present in the results!")
        else:
            print("SUCCESS: Holywood is NOT present.")

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(check_query())
