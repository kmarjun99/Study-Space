import asyncio
import logging
from app.database import engine, Base, AsyncSessionLocal


from app.models.user import User, UserRole, VerificationStatus
from app.models.reading_room import ReadingRoom, Cabin, CabinStatus
from app.models.accommodation import Accommodation, AccommodationType, Gender
from app.models.booking import Booking
from app.models.review import Review # Imported from correct location
from app.core.security import get_password_hash
from sqlalchemy.future import select

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from app.models.ad import Ad, TargetAudience
from app.models.ad_category import AdCategory

async def seed_data():
    # Don't drop tables - we already have seeded data
    # async with engine.begin() as conn:
    #     await conn.run_sync(Base.metadata.drop_all)
    #     await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as db:
        # Check if users already exist
        existing_admin_result = await db.execute(
            select(User).where(User.email == "admin@studyspace.com")
        )
        existing_admin = existing_admin_result.scalar_one_or_none()
        
        if existing_admin:
            logger.info("Users already exist, fetching existing users")
            admin = existing_admin
            
            room1_result = await db.execute(
                select(User).where(User.email == "centrallibrary@studyspace.com")
            )
            room1_admin = room1_result.scalar_one()
            
            room2_result = await db.execute(
                select(User).where(User.email == "studynook@studyspace.com")
            )
            room2_admin = room2_result.scalar_one()
            
            student1_result = await db.execute(
                select(User).where(User.email == "student1@studyspace.com")
            )
            student1 = student1_result.scalar_one()
            
            student2_result = await db.execute(
                select(User).where(User.email == "student2@studyspace.com")
            )
            student2 = student2_result.scalar_one_or_none()
            
            if not student2:
                # Create student2 if doesn't exist
                student2 = User(
                    email="student2@studyspace.com",
                    hashed_password=get_password_hash("student123"),
                    name="Jane Smith",
                    role=UserRole.STUDENT,
                    phone="9876543212",
                    verification_status=VerificationStatus.NOT_REQUIRED
                )
                db.add(student2)
                await db.commit()
                await db.refresh(student2)
        else:
            logger.info("Creating new users")
            # Create Super Admin
            super_admin = User(
                email="superadmin@studyspace.com",
                hashed_password=get_password_hash("superadmin123"),
                name="Platform Owner",
                role=UserRole.SUPER_ADMIN,
                phone="0000000000"
            )
            # Create Users

            admin = User(
                email="admin@studyspace.com",
                hashed_password=get_password_hash("admin123"),
                name="Admin User",
                role=UserRole.ADMIN,
                phone="9876543210",
                verification_status=VerificationStatus.VERIFIED
            )
            student1 = User(
                email="student1@studyspace.com",
                hashed_password=get_password_hash("student123"),
                name="John Doe",
                role=UserRole.STUDENT,
                phone="9876543211",
                verification_status=VerificationStatus.NOT_REQUIRED
            )
            student2 = User(
                email="student2@studyspace.com",
                hashed_password=get_password_hash("student123"),
                name="Jane Smith",
                role=UserRole.STUDENT,
                phone="9876543212",
                verification_status=VerificationStatus.NOT_REQUIRED
            )
            
            room1_admin = User(
                email="centrallibrary@studyspace.com",
                hashed_password=get_password_hash("admin123"),
                name="Central Library Admin",
                role=UserRole.ADMIN,
                phone="9998887776",
                verification_status=VerificationStatus.VERIFIED
            )

            room2_admin = User(
                email="studynook@studyspace.com",
                hashed_password=get_password_hash("admin123"),
                name="Study Nook Manager",
                role=UserRole.ADMIN,
                phone="9998887775",
                verification_status=VerificationStatus.PENDING # Keep one pending for dashboard demo
            )
            
            db.add_all([admin, room1_admin, room2_admin, student1, student2, super_admin])
            await db.commit()
            await db.refresh(admin)
            await db.refresh(room1_admin)
            await db.refresh(room2_admin)
            await db.refresh(student1)
            await db.refresh(student2)


        # Create Reading Rooms
        room1 = ReadingRoom(
            owner_id=room1_admin.id,
            name="Central Library Reading Room",
            address="123 Main St, City Center",
            description="Quiet and spacious reading room with AC.",
            images='["https://images.unsplash.com/photo-1541829070764-84a7d30dd3f3"]',
            amenities="AC,WiFi,Water",
            contact_phone="9998887776",
            price_start=500.0,
            city="Trivandrum", 
            locality="Palayam", 
            state="Kerala", 
            pincode="695001"
        )
        
        room2 = ReadingRoom(
            owner_id=room2_admin.id,
            name="Study Nook",
            address="456 Market Road",
            description="Cozy space for focused study.",
            images='["https://images.unsplash.com/photo-1497366216548-37526070297c"]',
            amenities="WiFi,Coffee",
            contact_phone="9998887775",
            price_start=300.0,
            city="Trivandrum",
            locality="Pattom",
            state="Kerala",
            pincode="695004"
        )
        
        db.add_all([room1, room2])
        await db.commit()
        await db.refresh(room1)
        await db.refresh(room2)

        # Create Cabins for Room 1
        cabins = []
        for i in range(1, 11):
            cabin = Cabin(
                reading_room_id=room1.id,
                number=f"A{i}",
                floor=1,
                price=500.0,
                status=CabinStatus.OCCUPIED if i % 3 == 0 else CabinStatus.AVAILABLE,
                amenities="AC,Desk"
            )
            if cabin.status == CabinStatus.OCCUPIED:
                cabin.current_occupant_id = student1.id if i == 3 else student2.id
            cabins.append(cabin)
        
        db.add_all(cabins)


        # Create Accommodations
        acc1 = Accommodation(
            owner_id=admin.id,
            name="Sunrise PG",
            type=AccommodationType.PG,
            gender=Gender.MALE,
            address="789 Park Lane",
            price=8000.0,
            sharing="Double",
            amenities="WiFi,Food,Laundry",
            images='["https://images.unsplash.com/photo-1555854877-bab0e564b8d5"]',
            rating=4.5,
            city="Trivandrum", locality="Kowdiar", state="Kerala", pincode="695003"
        )

        acc2 = Accommodation(
            owner_id=admin.id,
            name="Girls Hostel Elite",
            type=AccommodationType.HOSTEL,
            gender=Gender.FEMALE,
            address="101 College Road",
            price=6000.0,
            sharing="Triple",
            amenities="WiFi,Security,Mess",
            images='["https://images.unsplash.com/photo-1522771753035-711036f827eb"]',
            rating=4.8,
            city="Trivandrum", locality="Vazhuthacaud", state="Kerala", pincode="695014"
        )
        
        db.add_all([acc1, acc2])
        await db.commit()

        # Get some categories for ads
        food_cat = await db.execute(
            select(AdCategory).where(AdCategory.slug == "food-cafes")
        )
        food_category = food_cat.scalar_one_or_none()
        
        lifestyle_cat = await db.execute(
            select(AdCategory).where(AdCategory.slug == "gadgets-accessories")
        )
        lifestyle_category = lifestyle_cat.scalar_one_or_none()

        # Create Ads
        ad1 = Ad(
            title="Fuel Your Study Session",
            description="Get 20% off on your first order with Zomato. Use code STUDY20.",
            image_url="https://images.unsplash.com/photo-1565299624946-b28f40a0ae38?auto=format&fit=crop&q=80&w=600",
            cta_text="Order Now",
            link="#",
            category_id=food_category.id if food_category else None,
            target_audience=TargetAudience.STUDENT
        )
        
        ad2 = Ad(
            title="Premium Office Furniture",
            description="Upgrade your reading room with ergonomic chairs.",
            image_url="https://images.unsplash.com/photo-1524758631624-e2822e304c36?auto=format&fit=crop&q=80&w=600",
            cta_text="View Catalog",
            link="#",
            category_id=lifestyle_category.id if lifestyle_category else None,
            target_audience=TargetAudience.ADMIN
        )

        db.add_all([ad1, ad2])
        
        await db.commit()

        logger.info("Seeding completed successfully!")

if __name__ == "__main__":
    asyncio.run(seed_data())
