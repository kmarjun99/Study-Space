"""
Migration: Add flexible booking duration configuration to reading rooms and bookings
Run this script to add:
- allowed_booking_durations (JSON) to reading_rooms
- duration_prices (JSON) to reading_rooms  
- duration_type to bookings

Usage: python -m scripts.add_booking_duration_config
"""

import asyncio
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy import text
from app.database import async_session_maker

async def add_booking_duration_columns():
    """Add booking duration configuration columns"""
    async with async_session_maker() as db:
        try:
            print("🔧 Adding booking duration columns to reading_rooms table...")
            
            # Add columns to reading_rooms
            await db.execute(text("""
                ALTER TABLE reading_rooms 
                ADD COLUMN IF NOT EXISTS allowed_booking_durations TEXT DEFAULT '["1_DAY", "1_WEEK", "1_MONTH", "3_MONTHS", "6_MONTHS"]'
            """))
            
            await db.execute(text("""
                ALTER TABLE reading_rooms 
                ADD COLUMN IF NOT EXISTS duration_prices TEXT DEFAULT NULL
            """))
            
            print("✅ Added columns to reading_rooms table")
            
            print("🔧 Adding duration_type column to bookings table...")
            
            # Add duration_type to bookings
            await db.execute(text("""
                ALTER TABLE bookings 
                ADD COLUMN IF NOT EXISTS duration_type VARCHAR(20) DEFAULT '1_MONTH'
            """))
            
            print("✅ Added duration_type column to bookings table")
            
            # Set default duration prices for existing venues
            print("🔧 Setting default duration prices for existing venues...")
            
            # This will be updated by owners, but we set a template
            default_prices = '{"1_DAY": null, "1_WEEK": null, "1_MONTH": null, "3_MONTHS": null, "6_MONTHS": null}'
            
            await db.execute(text(f"""
                UPDATE reading_rooms 
                SET duration_prices = '{default_prices}'
                WHERE duration_prices IS NULL
            """))
            
            await db.commit()
            print("✅ Migration completed successfully!")
            print("\n📊 Summary:")
            print("   - reading_rooms.allowed_booking_durations: Stores array of enabled duration types")
            print("   - reading_rooms.duration_prices: Stores custom prices per duration")
            print("   - bookings.duration_type: Stores which duration was used for booking")
            
        except Exception as e:
            await db.rollback()
            print(f"❌ Migration failed: {e}")
            raise

if __name__ == "__main__":
    print("=" * 60)
    print("BOOKING DURATION CONFIGURATION MIGRATION")
    print("=" * 60)
    asyncio.run(add_booking_duration_columns())
    print("=" * 60)
