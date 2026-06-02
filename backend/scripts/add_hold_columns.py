"""Add missing columns to cabins table"""
import asyncio
from sqlalchemy import text

async def migrate():
    from app.database import engine
    
    async with engine.begin() as conn:
        # Add held_by_user_id column
        try:
            await conn.execute(text("ALTER TABLE cabins ADD COLUMN held_by_user_id VARCHAR"))
            print("✅ Added held_by_user_id column")
        except Exception as e:
            print(f"⚠️ held_by_user_id: {e}")
        
        # Add hold_expires_at column
        try:
            await conn.execute(text("ALTER TABLE cabins ADD COLUMN hold_expires_at VARCHAR"))
            print("✅ Added hold_expires_at column")
        except Exception as e:
            print(f"⚠️ hold_expires_at: {e}")

if __name__ == "__main__":
    asyncio.run(migrate())
