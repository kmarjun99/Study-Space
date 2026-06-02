#!/usr/bin/env python3
"""
Migration: Convert PostgreSQL native enums to VARCHAR
This fixes issues with adding new enum values like HOUSE to AccommodationType
"""
import asyncio
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import asyncpg
from app.core.config import settings


async def migrate_column(conn, column_name: str, varchar_type: str, not_null: bool):
    """Migrate a single enum column to VARCHAR"""
    try:
        # Check current column type
        current_type = await conn.fetchval(f"""
            SELECT data_type 
            FROM information_schema.columns 
            WHERE table_name = 'accommodations' AND column_name = '{column_name}';
        """)
        
        print(f"\n   Column '{column_name}': {current_type}", flush=True)
        
        if current_type in ('character varying', 'varchar', 'text'):
            print(f"   ✅ Already VARCHAR - skipping", flush=True)
            return
        
        print(f"   🔄 Converting to {varchar_type}...", flush=True)
        
        # Step 1: Add temporary column
        await conn.execute(f"""
            ALTER TABLE accommodations 
            ADD COLUMN IF NOT EXISTS {column_name}_new {varchar_type};
        """)
        print(f"   ✓ Created temporary column {column_name}_new", flush=True)
        
        # Step 2: Copy data with explicit cast
        await conn.execute(f"""
            UPDATE accommodations 
            SET {column_name}_new = {column_name}::text 
            WHERE {column_name}_new IS NULL;
        """)
        row_count = await conn.fetchval(f'SELECT COUNT(*) FROM accommodations')
        print(f"   ✓ Copied {row_count} rows", flush=True)
        
        # Step 3: Drop old column (this also removes enum type reference)
        await conn.execute(f"""
            ALTER TABLE accommodations 
            DROP COLUMN {column_name} CASCADE;
        """)
        print(f"   ✓ Dropped old enum column", flush=True)
        
        # Step 4: Rename temp column to original name
        await conn.execute(f"""
            ALTER TABLE accommodations 
            RENAME COLUMN {column_name}_new TO {column_name};
        """)
        print(f"   ✓ Renamed column", flush=True)
        
        # Step 5: Add NOT NULL constraint if needed
        if not_null:
            await conn.execute(f"""
                ALTER TABLE accommodations 
                ALTER COLUMN {column_name} SET NOT NULL;
            """)
            print(f"   ✓ Added NOT NULL constraint", flush=True)
        
        print(f"   ✅ {column_name} successfully migrated to {varchar_type}", flush=True)
        
    except Exception as e:
        print(f"   ❌ Failed to migrate {column_name}: {e}", flush=True)
        import traceback
        print(traceback.format_exc(), flush=True)
        raise


async def migrate_enums_to_varchar():
    """
    Convert enum columns to VARCHAR to support dynamic enum values
    """
    print("=" * 70, flush=True)
    print("🔄 Migrating enum columns from native PostgreSQL enums to VARCHAR", flush=True)
    print("=" * 70, flush=True)
    print(f"\n🔍 DATABASE_URL configured: {settings.DATABASE_URL[:50]}...", flush=True)
    
    # Parse DATABASE_URL for asyncpg (handle both formats)
    db_url = settings.DATABASE_URL
    if 'postgresql+asyncpg://' in db_url:
        db_url = db_url.replace('postgresql+asyncpg://', 'postgresql://')
    
    print(f"🔍 Connecting to database...", flush=True)
    
    conn = None
    try:
        conn = await asyncpg.connect(db_url, ssl='require', timeout=60)
        print("✅ Database connection established!", flush=True)
        
        # Check if accommodations table exists
        table_exists = await conn.fetchval("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'accommodations'
            );
        """)
        
        if not table_exists:
            print("⚠️  Accommodations table doesn't exist yet. Skipping migration.", flush=True)
            return
        
        print("\n✅ Accommodations table found. Starting migration...", flush=True)
        
        # Migrate type column
        await migrate_column(conn, 'type', 'VARCHAR(20)', True)
        
        # Migrate gender column
        await migrate_column(conn, 'gender', 'VARCHAR(20)', True)
        
        # Migrate status column
        await migrate_column(conn, 'status', 'VARCHAR(30)', False)
        
        print("\n✅ All columns migrated successfully!", flush=True)
        print("   HOUSE, PG, and HOSTEL types are now fully supported.", flush=True)
        
    except asyncpg.InvalidCatalogNameError as e:
        print(f"\n❌ Database does not exist: {e}", flush=True)
        raise
    except asyncpg.InvalidPasswordError as e:
        print(f"\n❌ Authentication failed: {e}", flush=True)
        raise
    except asyncpg.CannotConnectNowError as e:
        print(f"\n❌ Database not ready: {e}", flush=True)
        raise
    except Exception as e:
        print(f"\n❌ Migration error: {e}", flush=True)
        import traceback
        print(traceback.format_exc(), flush=True)
        print("\n⚠️  Migration failed. The app will continue but HOUSE type won't work.", flush=True)
        print("    Please check the database connection and permissions.", flush=True)
        raise  # Re-raise to make the error visible
    finally:
        if conn:
            await conn.close()
            print("🔌 Database connection closed.", flush=True)
    
    print("\n" + "=" * 70, flush=True)


if __name__ == '__main__':
    asyncio.run(migrate_enums_to_varchar())
