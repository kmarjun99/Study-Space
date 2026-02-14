import asyncio
import traceback

async def test_create():
    from app.database import engine, AsyncSessionLocal, Base  
    from app.models.reading_room import ReadingRoom, ListingStatus
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async with AsyncSessionLocal() as session:
        try:
            new_room = ReadingRoom(
                name="Test Room",
                address="Test Address",
                city="Trivandrum",
                state="Kerala",
                pincode="695001",
                price_start=30000,
                amenities="WiFi,AC",
                owner_id="test-owner-id",
                status=ListingStatus.DRAFT,
                is_verified=False
            )
            session.add(new_room)
            await session.commit()
            print("SUCCESS: Room created with ID:", new_room.id)
        except Exception as e:
            print("ERROR:", e)
            traceback.print_exc()

asyncio.run(test_create())
