"""
Admin-only endpoint to manually trigger database migrations
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.deps import get_current_user, get_db
from app.models.user import User, UserRole
import asyncpg
from app.core.config import settings

router = APIRouter(prefix="/admin/migration", tags=["admin-migration"])

async def require_admin(current_user: User = Depends(get_current_user)):
    """Require user to be admin or super admin"""
    if current_user.role not in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user

@router.post("/add-house-type")
async def add_house_type(
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Quick migration: Add HOUSE to accommodationtype enum.
    Use this if the enum still exists. Otherwise use run-enum-migration.
    """
    logs = []
    
    def log(msg: str):
        logs.append(msg)
        print(msg, flush=True)
    
    try:
        log("=" * 60)
        log("🏠 Adding HOUSE to AccommodationType enum")
        log(f"Triggered by: {current_user.email}")
        log("=" * 60)
        
        # Parse DATABASE_URL for asyncpg
        db_url = settings.DATABASE_URL
        if 'postgresql+asyncpg://' in db_url:
            db_url = db_url.replace('postgresql+asyncpg://', 'postgresql://')
        
        conn = await asyncpg.connect(db_url, ssl='require', timeout=60)
        
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
                log("✅ HOUSE value already exists in accommodationtype enum")
            else:
                log("🔄 Adding HOUSE value to accommodationtype enum...")
                await conn.execute("ALTER TYPE accommodationtype ADD VALUE 'HOUSE'")
                log("✅ HOUSE value added successfully!")
            
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
            log(f"✅ Current AccommodationType values: {enum_values}")
            
            log("=" * 60)
            log("✅ Migration completed successfully!")
            log("=" * 60)
            
            return {
                "success": True,
                "message": "HOUSE type added successfully!",
                "enum_values": enum_values,
                "logs": logs
            }
            
        finally:
            await conn.close()
            
    except asyncpg.exceptions.UndefinedObjectError:
        log("⚠️  accommodationtype enum doesn't exist - may already be VARCHAR")
        log("💡 Try running /admin/migration/run-enum-migration instead")
        return {
            "success": False,
            "message": "Enum type not found. Column may already be VARCHAR. Run full migration.",
            "logs": logs
        }
    except Exception as e:
        log(f"❌ Error: {str(e)}")
        import traceback
        log(traceback.format_exc())
        return {
            "success": False,
            "message": f"Migration failed: {str(e)}",
            "logs": logs
        }

@router.post("/run-enum-migration")
async def run_enum_migration(
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Manually trigger enum to VARCHAR migration for accommodations table.
    This converts native PostgreSQL enums to VARCHAR to support HOUSE type.
    """
    
    logs = []
    
    def log(msg: str):
        logs.append(msg)
        print(msg, flush=True)
    
    try:
        log("=" * 70)
        log("🔄 Starting manual enum migration")
        log(f"Triggered by: {current_user.email}")
        log("=" * 70)
        
        # Parse DATABASE_URL for asyncpg
        db_url = settings.DATABASE_URL
        if 'postgresql+asyncpg://' in db_url:
            db_url = db_url.replace('postgresql+asyncpg://', 'postgresql://')
        
        log("🔍 Connecting to database...")
        
        conn = await asyncpg.connect(db_url, ssl='require', timeout=60)
        
        try:
            log("✅ Database connection established!")
            
            # Check if accommodations table exists
            table_exists = await conn.fetchval("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'accommodations'
                );
            """)
            
            if not table_exists:
                log("❌ Accommodations table doesn't exist!")
                return {
                    "success": False,
                    "message": "Accommodations table not found",
                    "logs": logs
                }
            
            log("✅ Accommodations table found")
            
            # Migrate each column
            for column_name, varchar_type, not_null in [
                ('type', 'VARCHAR(20)', True),
                ('gender', 'VARCHAR(20)', True),
                ('status', 'VARCHAR(30)', False)
            ]:
                log(f"\n📋 Processing column: {column_name}")
                
                # Check current type
                current_type = await conn.fetchval(f"""
                    SELECT data_type 
                    FROM information_schema.columns 
                    WHERE table_name = 'accommodations' AND column_name = '{column_name}';
                """)
                
                log(f"   Current type: {current_type}")
                
                if current_type in ('character varying', 'varchar', 'text'):
                    log(f"   ✅ Already VARCHAR - skipping")
                    continue
                
                log(f"   🔄 Converting to {varchar_type}...")
                
                # Step 1: Add temporary column
                await conn.execute(f"""
                    ALTER TABLE accommodations 
                    ADD COLUMN IF NOT EXISTS {column_name}_new {varchar_type};
                """)
                log(f"   ✓ Created temp column {column_name}_new")
                
                # Step 2: Copy data
                await conn.execute(f"""
                    UPDATE accommodations 
                    SET {column_name}_new = {column_name}::text 
                    WHERE {column_name}_new IS NULL;
                """)
                row_count = await conn.fetchval('SELECT COUNT(*) FROM accommodations')
                log(f"   ✓ Copied {row_count} rows")
                
                # Step 3: Drop old column
                await conn.execute(f"""
                    ALTER TABLE accommodations 
                    DROP COLUMN {column_name} CASCADE;
                """)
                log(f"   ✓ Dropped old enum column")
                
                # Step 4: Rename temp to original
                await conn.execute(f"""
                    ALTER TABLE accommodations 
                    RENAME COLUMN {column_name}_new TO {column_name};
                """)
                log(f"   ✓ Renamed column")
                
                # Step 5: Add NOT NULL if needed
                if not_null:
                    await conn.execute(f"""
                        ALTER TABLE accommodations 
                        ALTER COLUMN {column_name} SET NOT NULL;
                    """)
                    log(f"   ✓ Added NOT NULL constraint")
                
                log(f"   ✅ {column_name} successfully migrated!")
            
            log("\n" + "=" * 70)
            log("✅ MIGRATION COMPLETED SUCCESSFULLY!")
            log("   HOUSE type is now fully supported")
            log("=" * 70)
            
            return {
                "success": True,
                "message": "All columns migrated successfully. HOUSE type now works!",
                "logs": logs
            }
            
        finally:
            await conn.close()
            log("🔌 Database connection closed")
            
    except Exception as e:
        log(f"\n❌ Migration failed: {str(e)}")
        import traceback
        log(traceback.format_exc())
        
        return {
            "success": False,
            "message": f"Migration failed: {str(e)}",
            "logs": logs
        }
