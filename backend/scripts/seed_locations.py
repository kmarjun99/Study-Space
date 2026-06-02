#!/usr/bin/env python3
"""
Seed locations table from cities.json
Run manually: python scripts/seed_locations.py
Or triggered via API: POST /admin/locations/seed
"""
import asyncio
import json
import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import AsyncSessionLocal, engine, Base
from app.models.location import Location
from sqlalchemy.future import select
from sqlalchemy import func


CITIES_FILE = Path(__file__).parent.parent / "data" / "cities.json"


async def seed_locations(clear_existing: bool = False) -> dict:
    """
    Seed locations table from cities.json.
    Returns a summary dict with inserted/skipped counts.
    """
    if not CITIES_FILE.exists():
        return {"success": False, "error": f"cities.json not found at {CITIES_FILE}"}

    with open(CITIES_FILE, "r", encoding="utf-8") as f:
        cities = json.load(f)

    print(f"📍 Found {len(cities)} cities in cities.json")

    async with AsyncSessionLocal() as db:
        # Check existing count
        count_result = await db.execute(select(func.count()).select_from(Location))
        existing_count = count_result.scalar()

        if existing_count > 0 and not clear_existing:
            print(f"ℹ️  {existing_count} locations already exist. Skipping seeding.")
            print("   Pass clear_existing=True to replace all.")
            return {
                "success": True,
                "inserted": 0,
                "skipped": existing_count,
                "message": f"{existing_count} locations already seeded."
            }

        if clear_existing and existing_count > 0:
            print(f"🗑️  Clearing {existing_count} existing locations...")
            await db.execute(Location.__table__.delete())
            await db.commit()
            print("✅ Cleared.")

        # Batch insert for performance
        BATCH_SIZE = 500
        inserted = 0
        skipped = 0
        batch = []

        for city in cities:
            city_name = (city.get("city_name") or "").strip()
            state = (city.get("state") or "").strip()

            if not city_name or not state:
                skipped += 1
                continue

            loc = Location(
                country="India",
                state=state,
                city=city_name,
                locality=None,
                city_normalized=Location.normalize(city_name),
                locality_normalized=None,
                search_text=Location.create_search_text(city_name, state),
                latitude=city.get("latitude"),
                longitude=city.get("longitude"),
                is_active=True,
            )
            batch.append(loc)
            inserted += 1

            if len(batch) >= BATCH_SIZE:
                db.add_all(batch)
                await db.commit()
                print(f"   Inserted {inserted} locations so far...")
                batch = []

        # Insert remaining
        if batch:
            db.add_all(batch)
            await db.commit()

        print(f"\n✅ Seeding complete!")
        print(f"   Inserted : {inserted}")
        print(f"   Skipped  : {skipped}")
        return {
            "success": True,
            "inserted": inserted,
            "skipped": skipped,
            "total": inserted + skipped,
            "message": f"Successfully seeded {inserted} locations."
        }


async def main():
    print("\n" + "=" * 50)
    print("📍 Seeding Locations from cities.json")
    print("=" * 50 + "\n")

    # Pass --clear to wipe and re-seed
    clear = "--clear" in sys.argv
    result = await seed_locations(clear_existing=clear)

    if not result["success"]:
        print(f"❌ {result.get('error')}")
        sys.exit(1)

    print(f"\n{result['message']}")


if __name__ == "__main__":
    asyncio.run(main())
