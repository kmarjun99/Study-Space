import asyncio
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy import text
from app.database import engine

async def add_house_to_enum():
    """
    Add 'HOUSE' value to AccommodationType enum in PostgreSQL
    """
    print("=" * 60)
    print("Adding HOUSE to AccommodationType enum")
    print("=" * 60)
    
    async with engine.begin() as conn:
        try:
            # Check if HOUSE already exists in the enum
            check_query = text("""
                SELECT EXISTS (
                    SELECT 1 FROM pg_enum 
                    WHERE enumlabel = 'HOUSE' 
                    AND enumtypid = (
                        SELECT oid FROM pg_type WHERE typname = 'accommodationtype'
                    )
                );
            """)
            result = await conn.execute(check_query)
            exists = result.scalar()
            
            if exists:
                print("\n✓ HOUSE value already exists in accommodationtype enum")
            else:
                print("\nAdding HOUSE value to accommodationtype enum...")
                # Add HOUSE to the enum
                alter_query = text("ALTER TYPE accommodationtype ADD VALUE 'HOUSE'")
                await conn.execute(alter_query)
                print("✓ HOUSE value added successfully!")
            
            # Verify all enum values
            verify_query = text("""
                SELECT enumlabel 
                FROM pg_enum 
                WHERE enumtypid = (
                    SELECT oid FROM pg_type WHERE typname = 'accommodationtype'
                )
                ORDER BY enumsortorder;
            """)
            result = await conn.execute(verify_query)
            values = [row[0] for row in result.fetchall()]
            print(f"\n✓ Current AccommodationType values: {values}")
            
        except Exception as e:
            print(f"\n✗ Error: {e}")
            print("\nNote: If the enum type doesn't exist, it will be created automatically")
            print("when you restart the backend with the updated models.")
            raise
    
    print("\n" + "=" * 60)
    print("Migration completed successfully!")
    print("=" * 60)
    print("\nThe HOUSE accommodation type is now available in the database.")

if __name__ == '__main__':
    asyncio.run(add_house_to_enum())
