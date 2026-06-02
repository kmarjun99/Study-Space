import asyncio
from app.database import AsyncSessionLocal
from app.models.user import User
from app.core.security import get_password_hash
from sqlalchemy import select

async def reset_password():
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.email == "superadmin@studyspace.com"))
        user = result.scalars().first()
        if user:
            print(f"Found user {user.email}")
            user.hashed_password = get_password_hash("superadmin123")
            await db.commit()
            print("Password reset to 'superadmin123'")
        else:
            print("User not found!")

if __name__ == "__main__":
    asyncio.run(reset_password())
