
import asyncio
import sys
import os

# Add the current directory to sys.path so we can import app modules
# Assuming this script is run from backend/ directory
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database import AsyncSessionLocal
from app.models.user import User, UserRole
from app.core.security import get_password_hash
from sqlalchemy.future import select

async def seed_users():
    async with AsyncSessionLocal() as db:
        users = [
            # Super Admin
            {
                "email": "superadmin@studyspace.com",
                "password": "superadmin123",
                "role": UserRole.SUPER_ADMIN,
                "name": "Super Admin"
            },
            # Admin (General)
            {
                "email": "admin@studyspace.com",
                "password": "admin123",
                "role": UserRole.ADMIN,
                "name": "Admin User"
            },
            # Student
            {
                "email": "student1@studyspace.com",
                "password": "student123",
                "role": UserRole.STUDENT,
                "name": "John Doe"
            },
             # Central Library Owner
            {
                "email": "centrallibrary@studyspace.com",
                "password": "admin123",
                "role": UserRole.ADMIN,
                "name": "Central Library"
            },
            # Study Nook Owner
            {
                "email": "studynook@studyspace.com",
                "password": "admin123",
                "role": UserRole.ADMIN,
                "name": "Study Nook"
            }
        ]

        print("Checking for demo users...")
        for user_data in users:
            try:
                result = await db.execute(select(User).where(User.email == user_data["email"]))
                existing_user = result.scalars().first()
                if not existing_user:
                    print(f"Creating user: {user_data['email']}")
                    new_user = User(
                        email=user_data["email"],
                        hashed_password=get_password_hash(user_data["password"]),
                        name=user_data["name"],
                        role=user_data["role"],
                        # avatar_url=user_data.get("avatar_url"), # Optional
                        # phone=user_data.get("phone"), # Optional
                    )
                    db.add(new_user)
                else:
                    print(f"User already exists: {user_data['email']}")
            except Exception as e:
                print(f"Error checking/creating user {user_data['email']}: {e}")
        
        try:
            await db.commit()
            print("Seeding complete successfully.")
        except Exception as e:
            print(f"Error committing changes: {e}")

if __name__ == "__main__":
    # Ensure Windows compatibility for asyncio loop if needed, though usually standard run is fine for scripts
    asyncio.run(seed_users())
