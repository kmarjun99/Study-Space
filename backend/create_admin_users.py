"""
Script to create admin and superadmin users in the database.
Run this from the backend directory: python create_admin_users.py
"""
import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from app.database import AsyncSessionLocal
from app.models.user import User, UserRole, VerificationStatus
from app.core.security import get_password_hash
from sqlalchemy.future import select


async def create_admin_users():
    """Create admin and superadmin users if they don't exist"""
    async with AsyncSessionLocal() as db:
        users_to_create = [
            {
                "email": "superadmin@studyspace.com",
                "password": "superadmin123",
                "role": UserRole.SUPER_ADMIN,
                "name": "Super Admin",
                "phone": "0000000000"
            },
            {
                "email": "admin@studyspace.com",
                "password": "admin123",
                "role": UserRole.ADMIN,
                "name": "Admin User",
                "phone": "9876543210"
            }
        ]

        created_count = 0
        existing_count = 0

        for user_data in users_to_create:
            # Check if user already exists
            result = await db.execute(
                select(User).where(User.email == user_data["email"])
            )
            existing_user = result.scalars().first()

            if existing_user:
                print(f"✓ User already exists: {user_data['email']}")
                existing_count += 1
            else:
                # Create new user
                new_user = User(
                    email=user_data["email"],
                    hashed_password=get_password_hash(user_data["password"]),
                    name=user_data["name"],
                    role=user_data["role"],
                    phone=user_data.get("phone", "0000000000"),
                    verification_status=VerificationStatus.VERIFIED
                )
                db.add(new_user)
                print(f"✓ Created user: {user_data['email']} (Password: {user_data['password']})")
                created_count += 1

        if created_count > 0:
            await db.commit()
            print(f"\n✅ Successfully created {created_count} new user(s)")
        
        if existing_count > 0:
            print(f"ℹ️  {existing_count} user(s) already existed")

        print("\n📋 Login Credentials:")
        print("=" * 60)
        for user_data in users_to_create:
            print(f"Email: {user_data['email']}")
            print(f"Password: {user_data['password']}")
            print(f"Role: {user_data['role'].value}")
            print("-" * 60)


if __name__ == "__main__":
    print("🚀 Creating admin users...\n")
    asyncio.run(create_admin_users())
    print("\n✨ Done!")
