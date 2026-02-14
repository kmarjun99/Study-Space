"""
Migration script to update ads table from 'category' enum to 'category_id' string.
Run with: python migrate_ads_table.py
"""
import asyncio
import sys
sys.path.insert(0, '.')

from app.database import AsyncSessionLocal, engine, Base
from sqlalchemy import text


async def migrate_ads_table():
    """Migrate ads table to use category_id instead of category enum."""
    async with engine.begin() as conn:
        # First, check current table structure
        result = await conn.execute(text("PRAGMA table_info(ads)"))
        columns = {row[1]: row[2] for row in result.fetchall()}
        print(f"Current ads table columns: {columns}")
        
        if 'category' in columns and 'category_id' not in columns:
            print("🔄 Migrating ads table: renaming 'category' to 'category_id'...")
            
            # SQLite doesn't support ALTER COLUMN, so we need to recreate the table
            # First, create a backup
            await conn.execute(text("""
                CREATE TABLE IF NOT EXISTS ads_backup AS SELECT * FROM ads
            """))
            print("   ✅ Created backup table")
            
            # Drop the original table
            await conn.execute(text("DROP TABLE IF EXISTS ads"))
            print("   ✅ Dropped old ads table")
            
            # Create new table with correct schema
            await conn.execute(text("""
                CREATE TABLE ads (
                    id VARCHAR PRIMARY KEY,
                    title VARCHAR NOT NULL,
                    description VARCHAR NOT NULL,
                    image_url VARCHAR NOT NULL,
                    cta_text VARCHAR NOT NULL,
                    link VARCHAR NOT NULL,
                    category_id VARCHAR,
                    target_audience VARCHAR DEFAULT 'ALL',
                    FOREIGN KEY (category_id) REFERENCES ad_categories(id)
                )
            """))
            print("   ✅ Created new ads table with category_id")
            
            # Copy data back (category becomes category_id, but values won't match UUIDs)
            # So we set category_id to NULL for now
            await conn.execute(text("""
                INSERT INTO ads (id, title, description, image_url, cta_text, link, category_id, target_audience)
                SELECT id, title, description, image_url, cta_text, link, NULL, target_audience
                FROM ads_backup
            """))
            print("   ✅ Migrated existing ads (category_id set to NULL)")
            
            # Drop backup
            await conn.execute(text("DROP TABLE ads_backup"))
            print("   ✅ Cleaned up backup table")
            
            print("\n🎉 Migration complete!")
            
        elif 'category_id' in columns:
            print("✅ Table already has 'category_id' column. No migration needed.")
        else:
            print("⚠️  Unexpected table structure. Creating table from scratch...")
            await conn.run_sync(Base.metadata.create_all)
            print("✅ Tables ensured.")


if __name__ == "__main__":
    asyncio.run(migrate_ads_table())
