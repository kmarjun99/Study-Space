"""
Script to create OTP and PasswordReset tables in the database.
Run this after adding the new OTP models.
"""
import asyncio
import sys
from pathlib import Path

# Add backend directory to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from app.database import engine, Base
from app.models import OTP, PasswordReset  # Import to register with Base

async def create_tables():
    """Create all tables defined in models"""
    print("Creating OTP and PasswordReset tables...")
    
    async with engine.begin() as conn:
        # Create only OTP-related tables (will skip existing tables)
        await conn.run_sync(Base.metadata.create_all)
    
    print("✅ Tables created successfully!")
    print("   - otps")
    print("   - password_resets")

if __name__ == "__main__":
    asyncio.run(create_tables())
