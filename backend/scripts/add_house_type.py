import asyncio
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import asyncpg
from app.core.config import settings

async def add_house_to_enum():
    """
    Add 'HOUSE' value to AccommodationType enum in PostgreSQL
    Using asyncpg directly to avoid transaction issues with ALTER TYPE
    """
    print("=" * 60)
    print("Adding HOUSE to AccommodationType enum")
    print("=" * 60)
    
    # Parse the DATABASE_URL to get connection parameters
    db_url = settings.DATABASE_URL.replace('postgresql+asyncpg://', 'postgresql://')
    
    try:
        # Connect directly with asyncpg (no transaction wrapper)
        conn = await asyncpg.connect(db_url, ssl='require')
        
        try:
            # Check if HOUSE already exists in the enum
            exists = await conn.fetchval("""
                SELECT EXISTS (
                    SELECT 1 FROM pg_enum 
                    WHERE enumlabel = 'HOUSE' 
                    AND enumtypid = (
                        SELECT oid FROM pg_type WHERE typname = 'accommodationtype'
                    )
                );
            """)
            
            if exists:
                print("\n✓ HOUSE value already exists in accommodationtype enum")
            else:
                print("\nAdding HOUSE value to accommodationtype enum...")
                # ALTER TYPE ADD VALUE must run outside a transaction
                # asyncpg connection.execute() runs in autocommit mode by default
                await conn.execute("ALTER TYPE accommodationtype ADD VALUE 'HOUSE'")
                print("✓ HOUSE value added successfully!")
            
            # Verify all enum values
            values = await conn.fetch("""
                SELECT enumlabel 
                FROM pg_enum 
                WHERE enumtypid = (
                    SELECT oid FROM pg_type WHERE typname = 'accommodationtype'
                )
                ORDER BY enumsortorder;
            """)
            enum_values = [row['enumlabel'] for row in values]
            print(f"\n✓ Current AccommodationType values: {enum_values}")
            
        finally:
            await conn.close()
            
    except Exception as e:
        print(f"\n✗ Error: {e}")
        print("\nNote: Migration will be skipped. Please check database connection.")
        print("The app will start but HOUSE type may not work until migration succeeds.")
        return
    
    print("\n" + "=" * 60)
    print("Migration completed successfully!")
    print("=" * 60)

if __name__ == '__main__':
    asyncio.run(add_house_to_enum())
