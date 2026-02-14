# Backend Admin Reset Router
# POST /admin/reset-database - Clears all data except Super Admin accounts

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.database import get_db
from datetime import datetime
import logging

router = APIRouter(prefix="/admin", tags=["Admin Reset"])

logger = logging.getLogger(__name__)

@router.post("/reset-database")
async def reset_database(db: AsyncSession = Depends(get_db)):
    """
    DANGER: Completely resets the database.
    - Deletes ALL data except Super Admin users
    - Use with extreme caution
    - Requires Super Admin authentication (TODO: add proper auth check)
    """
    
    reset_log = []
    start_time = datetime.now()
    
    try:
        # Order matters due to foreign key constraints
        # Delete child tables first, then parent tables
        
        tables_to_truncate = [
            # Child tables first (have foreign keys)
            ("bookings", "DELETE FROM bookings"),
            ("reviews", "DELETE FROM reviews"),
            ("waitlist_entries", "DELETE FROM waitlist_entries"),
            ("cabins", "DELETE FROM cabins"),
            ("inquiries", "DELETE FROM inquiries"),
            ("refunds", "DELETE FROM refunds"),
            ("payment_transactions", "DELETE FROM payment_transactions"),
            ("trust_flags", "DELETE FROM trust_flags"),
            ("reminders", "DELETE FROM reminders"),
            ("audit_logs", "DELETE FROM audit_logs"),
            
            # Parent tables (after children are deleted)
            ("reading_rooms", "DELETE FROM reading_rooms"),
            ("accommodations", "DELETE FROM accommodations"),
            ("ads", "DELETE FROM ads"),
            ("city_settings", "DELETE FROM city_settings"),
            
            # Users - keep Super Admin only
            ("users", "DELETE FROM users WHERE role != 'SUPER_ADMIN'"),
        ]
        
        for table_name, sql in tables_to_truncate:
            try:
                result = await db.execute(text(sql))
                rows_deleted = result.rowcount
                reset_log.append(f"✓ {table_name}: {rows_deleted} rows deleted")
                logger.info(f"Reset: Deleted {rows_deleted} rows from {table_name}")
            except Exception as e:
                # Table might not exist yet
                reset_log.append(f"⚠ {table_name}: {str(e)}")
                logger.warning(f"Reset warning for {table_name}: {str(e)}")
        
        await db.commit()
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        logger.info(f"=== DATABASE RESET COMPLETE === Duration: {duration}s")
        
        return {
            "success": True,
            "message": "Database reset complete. Super Admin accounts preserved.",
            "details": reset_log,
            "duration_seconds": duration,
            "timestamp": end_time.isoformat()
        }
        
    except Exception as e:
        await db.rollback()
        logger.error(f"Database reset failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Reset failed: {str(e)}")


@router.get("/reset-status")
async def get_reset_status(db: AsyncSession = Depends(get_db)):
    """Check current database state - counts of all tables"""
    
    tables = [
        "users", "reading_rooms", "cabins", "accommodations", 
        "bookings", "reviews", "waitlist_entries", "inquiries",
        "refunds", "payment_transactions", "trust_flags", "ads"
    ]
    
    counts = {}
    for table in tables:
        try:
            result = await db.execute(text(f"SELECT COUNT(*) FROM {table}"))
            counts[table] = result.scalar()
        except:
            counts[table] = "N/A"
    
    return {
        "counts": counts,
        "timestamp": datetime.now().isoformat()
    }
