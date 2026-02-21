"""
Create pending_registrations table for OTP-verified registration flow
"""

import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
import os

# Get database URL
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://user:password@localhost/studyspace")

async def create_pending_registrations_table():
    """Create pending_registrations table"""
    engine = create_async_engine(DATABASE_URL, echo=True)
    
    async with engine.begin() as conn:
        # Create pending_registrations table
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS pending_registrations (
                id VARCHAR PRIMARY KEY,
                email VARCHAR NOT NULL UNIQUE,
                hashed_password VARCHAR NOT NULL,
                name VARCHAR NOT NULL,
                role VARCHAR NOT NULL,
                phone VARCHAR,
                avatar_url VARCHAR,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP WITH TIME ZONE NOT NULL
            );
        """))
        
        # Create index on email
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_pending_registrations_email 
            ON pending_registrations(email);
        """))
        
        print("✅ pending_registrations table created successfully!")
    
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(create_pending_registrations_table())
