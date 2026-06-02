import asyncio

async def verify_admin_password():
    from app.database import engine, AsyncSessionLocal
    from app.models.user import User
    from app.core.security import verify_password
    from sqlalchemy.future import select
    
    async with AsyncSessionLocal() as session:
        # Check super admin
        result = await session.execute(select(User).where(User.email == "superadmin@studyspace.com"))
        user = result.scalars().first()
        
        if not user:
            print("❌ Super Admin not found in DB!")
            return
            
        print(f"User found: {user.email}")
        print(f"Stored Hash: {user.hashed_password[:20]}...")
        
        is_valid = verify_password("admin123", user.hashed_password)
        print(f"Password 'admin123' valid? {is_valid}")

asyncio.run(verify_admin_password())
