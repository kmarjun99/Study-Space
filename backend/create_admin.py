import asyncio

async def create_admin():
    from app.database import engine, AsyncSessionLocal, Base
    from app.models.user import User, UserRole, VerificationStatus
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async with AsyncSessionLocal() as session:
        # Check if admin exists
        from sqlalchemy.future import select
        # result = await session.execute(select(User).where(User.role == UserRole.ADMIN))
        # existing = result.scalars().first()
        
        # if existing:
        #    print(f"Admin user already exists: {existing.email}")
        #    return
        
        # Create a new super admin user
        from app.core.security import get_password_hash
        
        # Check if superadmin exists
        result_super = await session.execute(select(User).where(User.email == "superadmin@studyspace.com"))
        existing_super = result_super.scalars().first()
        
        if existing_super:
            print(f"Super Admin user already exists: {existing_super.email}")
            # Reset password just in case
            existing_super.hashed_password = get_password_hash("admin123")
            await session.commit()
            print(f"✅ Reset password for {existing_super.email} to: admin123")
            return

        super_admin = User(
            email="superadmin@studyspace.com",
            name="Super Admin",
            hashed_password=get_password_hash("admin123"),
            role=UserRole.SUPER_ADMIN,
            phone="+91 9999999999",
            verification_status=VerificationStatus.VERIFIED
        )
        
        session.add(super_admin)
        await session.commit()
        print(f"✅ Created super admin user: {super_admin.email} with password: admin123")
        print(f"   User ID: {super_admin.id}")

asyncio.run(create_admin())
