import asyncio
from sqlalchemy.future import select
from app.database import AsyncSessionLocal
from app.models.user import User

async def check_role():
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.email == "ajuvinod5873@gmail.com"))
        user = result.scalars().first()
        with open("role_check.txt", "w") as f:
            if user:
                f.write(f"User: {user.name}\n")
                f.write(f"Role: {user.role}\n")
                f.write(f"Role Value: {user.role.value if hasattr(user.role, 'value') else user.role}\n")
            else:
                f.write("User not found\n")

if __name__ == "__main__":
    asyncio.run(check_role())
