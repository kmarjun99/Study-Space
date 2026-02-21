"""
Clean up test users and pending registrations
"""

import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
import os

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://user:password@localhost/studyspace")

async def cleanup_test_data():
    """Remove test users and expired pending registrations"""
    engine = create_async_engine(DATABASE_URL, echo=True)
    
    async with engine.begin() as conn:
        # Remove test users (update email as needed)
        test_emails = ['twitter6247m@gmail.com']  # Add more test emails here
        
        for email in test_emails:
            result = await conn.execute(
                text("DELETE FROM users WHERE email = :email"),
                {"email": email}
            )
            print(f"✅ Deleted user: {email} (rows affected: {result.rowcount})")
        
        # Clean up expired pending registrations
        result = await conn.execute(
            text("DELETE FROM pending_registrations WHERE expires_at < NOW()")
        )
        print(f"✅ Deleted {result.rowcount} expired pending registrations")
        
        # Show remaining pending registrations
        result = await conn.execute(
            text("SELECT email, created_at, expires_at FROM pending_registrations ORDER BY created_at DESC")
        )
        rows = result.fetchall()
        
        if rows:
            print("\n📋 Remaining pending registrations:")
            for row in rows:
                print(f"  - {row[0]} (created: {row[1]}, expires: {row[2]})")
        else:
            print("\n✅ No pending registrations")
    
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(cleanup_test_data())
