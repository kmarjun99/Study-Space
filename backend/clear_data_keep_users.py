import asyncio
from sqlalchemy import text
from app.database import engine, Base

async def clear_data_keep_users():
    async with engine.begin() as conn:
        print("Disabling foreign keys...")
        await conn.execute(text("PRAGMA foreign_keys = OFF;"))
        
        tables_to_clear = [
            "waitlist",
            "bookings",
            "reviews",
            "inquiries",
            "cabins",
            "reading_rooms",
            "accommodations", 
            "payment_transactions",
            "notifications",
            "favorites",
            "boost_requests",
            "boost_plans",
            "trust_flags",
            "audit_logs",
            "invoices",
            "refunds",
            "reminders",
            "messages",
            "ads",
            "ad_categories",
            "otps",
            "locations", # Maybe clear locations too? Or keep master data? User said "clear whole data".
            # "subscription_plans", # Might want to keep these? Usually config.
            # "cities", # Master data?
        ]
        
        # Checking for tables that exist
        # We can just try to delete from them.
        
        print("Clearing tables...")
        for table in tables_to_clear:
            try:
                await conn.execute(text(f"DELETE FROM {table};"))
                print(f"Cleared {table}")
            except Exception as e:
                print(f"Error clearing {table}: {e}")
                
        # Also clear specific user-related but not user tables if needed?
        # User said "keep only users data".
        
        print("Enabling foreign keys...")
        await conn.execute(text("PRAGMA foreign_keys = ON;"))
        print("Database cleared (except users).")

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(clear_data_keep_users())
