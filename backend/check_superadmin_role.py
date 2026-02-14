
from app.database import AsyncSessionLocal
from app.models.user import User, UserRole
from sqlalchemy.future import select
import asyncio


async def check_role():
    with open("role_check_result.txt", "w") as f:
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(User).where(User.email == "superadmin@studyspace.com"))
            user = result.scalars().first()
            if user:
                f.write(f"User: {user.email}\n")
                f.write(f"ID: {user.id}\n")
                f.write(f"Role: {user.role}\n")
                f.write(f"Is Super Admin Enum? {user.role == UserRole.SUPER_ADMIN}\n")
                f.write(f"Raw Role Value: {user.role.value if hasattr(user.role, 'value') else user.role}\n")
                
                # Check other admins too just in case
                result = await db.execute(select(User).where(User.role == UserRole.SUPER_ADMIN))
                super_admins = result.scalars().all()
                f.write(f"\nTotal Super Admins in DB: {len(super_admins)}\n")
                for sa in super_admins:
                    f.write(f" - {sa.email} ({sa.id})\n")
            else:
                f.write("superadmin@studyspace.com NOT FOUND\n")

if __name__ == "__main__":
    asyncio.run(check_role())
