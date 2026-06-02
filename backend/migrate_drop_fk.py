"""
Emergency migration: Drop foreign key constraint on ads.category_id
This allows ads to be created without requiring valid category references.

Run ONCE on production: python migrate_drop_fk.py
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.database import engine
from sqlalchemy import text


async def drop_foreign_key():
    """Drop the foreign key constraint ads_category_id_fkey"""
    print("🔧 Starting FK constraint migration...\n")
    
    async with engine.begin() as conn:
        # Check if the constraint exists
        check_query = """
        SELECT constraint_name 
        FROM information_schema.table_constraints 
        WHERE table_name = 'ads' 
        AND constraint_name = 'ads_category_id_fkey'
        AND constraint_type = 'FOREIGN KEY';
        """
        
        result = await conn.execute(text(check_query))
        constraint_exists = result.fetchone()
        
        if constraint_exists:
            print("✓ Found foreign key constraint 'ads_category_id_fkey'")
            print("  Dropping constraint...\n")
            
            # Drop the foreign key constraint
            drop_query = """
            ALTER TABLE ads DROP CONSTRAINT IF EXISTS ads_category_id_fkey;
            """
            
            await conn.execute(text(drop_query))
            print("✅ Successfully dropped foreign key constraint!")
            print("   Ads can now be created with any category_id value.\n")
        else:
            print("ℹ️  Foreign key constraint 'ads_category_id_fkey' not found.")
            print("   It may have already been dropped.\n")
        
        # Verify the constraint is gone
        result = await conn.execute(text(check_query))
        if not result.fetchone():
            print("✓ Verified: FK constraint has been removed.\n")
        
        print("="*60)
        print("Next Steps:")
        print("="*60)
        print("1. Run: python seed_production_categories.py")
        print("   This will populate 24 ad categories")
        print("")
        print("2. Test creating an ad in the UI")
        print("   https://studyspace-frontend.onrender.com/#/super-admin/ads")
        print("="*60)


if __name__ == "__main__":
    print("\n" + "="*60)
    print("  DROP FK CONSTRAINT MIGRATION")
    print("="*60 + "\n")
    
    try:
        asyncio.run(drop_foreign_key())
        print("\n✨ Migration completed successfully!\n")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
