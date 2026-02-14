#!/usr/bin/env python3
"""
Database initialization script - creates superuser and seeds initial data
Runs automatically when Docker container starts
"""

import asyncio
import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import AsyncSessionLocal, engine, Base
from app.models.user import User, UserRole
from app.core.security import get_password_hash
from sqlalchemy.future import select
from sqlalchemy import text


async def wait_for_db(max_retries=30, delay=2):
    """Wait for database to be ready"""
    print("Waiting for database to be ready...")
    for i in range(max_retries):
        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            print("✅ Database is ready!")
            return True
        except Exception as e:
            if i < max_retries - 1:
                print(f"Database not ready, retrying in {delay}s... ({i+1}/{max_retries})")
                await asyncio.sleep(delay)
            else:
                print(f"❌ Database connection failed after {max_retries} attempts")
                return False
    return False


async def create_tables():
    """Create all tables if they don't exist"""
    try:
        print("Creating database tables...")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        print("✅ Database tables created successfully")
        return True
    except Exception as e:
        print(f"❌ Error creating tables: {e}")
        return False


async def create_superuser():
    """Create default superuser if not exists"""
    try:
        async with AsyncSessionLocal() as db:
            # Check if superuser exists
            result = await db.execute(
                select(User).where(User.email == "superadmin@studyspace.com")
            )
            existing_user = result.scalars().first()
            
            if existing_user:
                print("ℹ️  Superuser already exists: superadmin@studyspace.com")
                return True
            
            # Create superuser
            print("Creating superuser...")
            superuser = User(
                email="superadmin@studyspace.com",
                hashed_password=get_password_hash("superadmin123"),
                name="Super Admin",
                role=UserRole.SUPER_ADMIN,
            )
            db.add(superuser)
            await db.commit()
            
            print("✅ Superuser created successfully!")
            print("=" * 50)
            print("Login Credentials:")
            print("Email: superadmin@studyspace.com")
            print("Password: superadmin123")
            print("=" * 50)
            print("⚠️  IMPORTANT: Change this password in production!")
            print("=" * 50)
            
            return True
            
    except Exception as e:
        print(f"❌ Error creating superuser: {e}")
        return False


async def seed_demo_users():
    """Seed additional demo users for testing"""
    try:
        async with AsyncSessionLocal() as db:
            demo_users = [
                {
                    "email": "admin@studyspace.com",
                    "password": "admin123",
                    "role": UserRole.ADMIN,
                    "name": "Admin User"
                },
                {
                    "email": "student1@studyspace.com",
                    "password": "student123",
                    "role": UserRole.STUDENT,
                    "name": "John Doe"
                },
            ]
            
            created_count = 0
            for user_data in demo_users:
                result = await db.execute(
                    select(User).where(User.email == user_data["email"])
                )
                if not result.scalars().first():
                    new_user = User(
                        email=user_data["email"],
                        hashed_password=get_password_hash(user_data["password"]),
                        name=user_data["name"],
                        role=user_data["role"],
                    )
                    db.add(new_user)
                    created_count += 1
            
            if created_count > 0:
                await db.commit()
                print(f"✅ Created {created_count} demo user(s)")
            else:
                print("ℹ️  Demo users already exist")
                
            return True
            
    except Exception as e:
        print(f"⚠️  Warning: Could not create demo users: {e}")
        return False


async def main():
    """Main initialization function"""
    print("\n" + "=" * 50)
    print("🚀 Starting Database Initialization")
    print("=" * 50 + "\n")
    
    # Wait for database
    if not await wait_for_db():
        print("\n❌ Database initialization failed - database not accessible")
        sys.exit(1)
    
    # Create tables
    if not await create_tables():
        print("\n❌ Database initialization failed - could not create tables")
        sys.exit(1)
    
    # Create superuser
    if not await create_superuser():
        print("\n❌ Database initialization failed - could not create superuser")
        sys.exit(1)
    
    # Seed demo users (optional, don't fail if this doesn't work)
    await seed_demo_users()
    
    print("\n" + "=" * 50)
    print("✅ Database Initialization Complete!")
    print("=" * 50 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
