
import asyncio
import os
import sys

# Add backend directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.database import engine
from sqlalchemy import text

async def migrate():
    async with engine.begin() as conn:
        print("Checking if columns exist in conversations table...")
        
        # Check if accommodation_id exists
        try:
            await conn.execute(text("SELECT accommodation_id FROM conversations LIMIT 1"))
            print("column 'accommodation_id' already exists.")
        except Exception:
            print("Adding 'accommodation_id' column...")
            try:
                await conn.execute(text("ALTER TABLE conversations ADD COLUMN accommodation_id VARCHAR"))
                print("Added 'accommodation_id' column.")
            except Exception as e:
                print(f"Failed to add accommodation_id: {e}")

        # Check if venue_type exists
        try:
            await conn.execute(text("SELECT venue_type FROM conversations LIMIT 1"))
            print("column 'venue_type' already exists.")
        except Exception:
            print("Adding 'venue_type' column...")
            try:
                await conn.execute(text("ALTER TABLE conversations ADD COLUMN venue_type VARCHAR"))
                print("Added 'venue_type' column.")
            except Exception as e:
                print(f"Failed to add venue_type: {e}")

    print("Migration complete.")

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(migrate())
