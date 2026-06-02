"""
Migration script to add location_id to reading_rooms and accommodations,
and backfill based on existing city/locality data.

Run with: python migrate_locations.py
"""
import asyncio
import sys
sys.path.insert(0, '.')

from sqlalchemy import text
from app.database import AsyncSessionLocal, engine, Base
from app.models.location import Location
from app.models.reading_room import ReadingRoom
from app.models.accommodation import Accommodation


async def migrate_locations():
    """Add location_id column and backfill data."""
    
    print("🔄 Location Migration Starting...")
    print("=" * 50)
    
    async with engine.begin() as conn:
        # 1. Create locations table if not exists
        print("\n1️⃣ Ensuring tables exist...")
        await conn.run_sync(Base.metadata.create_all)
        print("   ✅ All tables created/verified")
        
        # 2. Check if location_id columns exist, add if not
        print("\n2️⃣ Checking for location_id columns...")
        
        # Check reading_rooms
        try:
            result = await conn.execute(text("SELECT location_id FROM reading_rooms LIMIT 1"))
            print("   ✅ reading_rooms.location_id already exists")
        except Exception:
            print("   ⚠️  Adding location_id to reading_rooms...")
            await conn.execute(text("ALTER TABLE reading_rooms ADD COLUMN location_id VARCHAR REFERENCES locations(id)"))
            print("   ✅ Added location_id to reading_rooms")
        
        # Check accommodations
        try:
            result = await conn.execute(text("SELECT location_id FROM accommodations LIMIT 1"))
            print("   ✅ accommodations.location_id already exists")
        except Exception:
            print("   ⚠️  Adding location_id to accommodations...")
            await conn.execute(text("ALTER TABLE accommodations ADD COLUMN location_id VARCHAR REFERENCES locations(id)"))
            print("   ✅ Added location_id to accommodations")
    
    # 3. Backfill location_id based on existing city/locality data
    print("\n3️⃣ Backfilling location_id...")
    
    async with AsyncSessionLocal() as session:
        from sqlalchemy.future import select
        from sqlalchemy import func
        
        # Get all locations for matching
        result = await session.execute(select(Location))
        locations = result.scalars().all()
        
        if not locations:
            print("   ⚠️  No locations found. Run seed_locations.py first!")
            return
        
        # Create lookup maps
        city_map = {}  # city_normalized -> location_id (for city-level match)
        locality_map = {}  # (city_normalized, locality_normalized) -> location_id
        
        for loc in locations:
            if loc.locality_normalized:
                locality_map[(loc.city_normalized, loc.locality_normalized)] = loc.id
            if loc.city_normalized not in city_map:
                city_map[loc.city_normalized] = loc.id
        
        # Backfill reading_rooms
        print("\n   📚 Processing reading_rooms...")
        result = await session.execute(
            select(ReadingRoom).where(ReadingRoom.location_id == None)
        )
        rooms = result.scalars().all()
        
        rooms_updated = 0
        for room in rooms:
            if room.city:
                city_norm = Location.normalize(room.city)
                locality_norm = Location.normalize(room.locality) if room.locality else None
                
                # Try locality match first
                if locality_norm and (city_norm, locality_norm) in locality_map:
                    room.location_id = locality_map[(city_norm, locality_norm)]
                    rooms_updated += 1
                # Fall back to city match
                elif city_norm in city_map:
                    room.location_id = city_map[city_norm]
                    rooms_updated += 1
        
        print(f"      ✅ Updated {rooms_updated} reading rooms")
        
        # Backfill accommodations
        print("\n   🏠 Processing accommodations...")
        result = await session.execute(
            select(Accommodation).where(Accommodation.location_id == None)
        )
        accommodations = result.scalars().all()
        
        acc_updated = 0
        for acc in accommodations:
            if acc.city:
                city_norm = Location.normalize(acc.city)
                locality_norm = Location.normalize(acc.locality) if acc.locality else None
                
                # Try locality match first
                if locality_norm and (city_norm, locality_norm) in locality_map:
                    acc.location_id = locality_map[(city_norm, locality_norm)]
                    acc_updated += 1
                # Fall back to city match
                elif city_norm in city_map:
                    acc.location_id = city_map[city_norm]
                    acc_updated += 1
        
        print(f"      ✅ Updated {acc_updated} accommodations")
        
        await session.commit()
    
    print("\n" + "=" * 50)
    print("🎉 Migration Complete!")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(migrate_locations())
