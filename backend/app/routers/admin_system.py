"""
Admin system management endpoints - migrations, seeding, diagnostics
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from sqlalchemy.future import select
from app.database import get_db, engine
from app.models.user import User, UserRole
from app.models.ad_category import AdCategory, CategoryStatus
from app.deps import get_current_user
import uuid
import re

router = APIRouter(prefix="/admin/system", tags=["admin-system"])


def slugify(text: str) -> str:
    """Convert text to URL-friendly slug."""
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[-\s]+', '-', text)
    return text


# 24 Initial Categories
INITIAL_CATEGORIES = [
    # Student-Focused
    {"name": "Education & Coaching", "group": "Student", "icon": "GraduationCap", "description": "Coaching centers, tuition, and academic support services"},
    {"name": "Online Courses & EdTech", "group": "Student", "icon": "Laptop", "description": "E-learning platforms, online certifications, and EdTech tools"},
    {"name": "Books & Stationery", "group": "Student", "icon": "BookOpen", "description": "Textbooks, notebooks, study materials, and stationery supplies"},
    {"name": "Competitive Exam Prep", "group": "Student", "icon": "Target", "description": "Preparation courses for UPSC, CAT, GRE, GATE, and other exams"},
    {"name": "Scholarships & Exams", "group": "Student", "icon": "Award", "description": "Scholarship programs, exam registrations, and educational grants"},
    {"name": "Gadgets & Accessories", "group": "Student", "icon": "Smartphone", "description": "Laptops, tablets, headphones, and student-friendly tech"},
    {"name": "Food & Cafes", "group": "Student", "icon": "Coffee", "description": "Restaurants, cafes, food delivery, and meal subscriptions"},
    {"name": "Transport & Mobility", "group": "Student", "icon": "Car", "description": "Ride-sharing, bike rentals, metro passes, and commute solutions"},
    {"name": "Internet & SIM Cards", "group": "Student", "icon": "Wifi", "description": "Broadband plans, mobile data, SIM cards, and connectivity offers"},
    {"name": "Health & Wellness", "group": "Student", "icon": "Heart", "description": "Gym memberships, mental health apps, healthcare services"},
    
    # Housing / Living
    {"name": "PG/Hostel Promotions", "group": "Housing", "icon": "Home", "description": "Paying guest accommodations, hostels, and co-living spaces"},
    {"name": "Furniture & Appliances", "group": "Housing", "icon": "Sofa", "description": "Rental furniture, appliances, and home setup essentials"},
    {"name": "Home Services", "group": "Housing", "icon": "Wrench", "description": "Plumbing, electrical, pest control, and maintenance services"},
    {"name": "Laundry Services", "group": "Housing", "icon": "Shirt", "description": "Laundry, dry cleaning, and ironing services"},
    {"name": "Cleaning Services", "group": "Housing", "icon": "Sparkles", "description": "House cleaning, deep cleaning, and sanitization services"},
    
    # Business
    {"name": "Business Tools & SaaS", "group": "Business", "icon": "Settings", "description": "Software tools, CRMs, and business management solutions"},
    {"name": "Accounting & GST", "group": "Business", "icon": "Calculator", "description": "Accounting software, GST filing services, and tax solutions"},
    {"name": "Payments & Banking", "group": "Business", "icon": "CreditCard", "description": "Payment gateways, business banking, and financial services"},
    {"name": "Marketing & Promotion", "group": "Business", "icon": "Megaphone", "description": "Digital marketing, social media, and advertising services"},
    {"name": "Insurance & Legal", "group": "Business", "icon": "Shield", "description": "Business insurance, legal compliance, and documentation"},
    
    # Platform
    {"name": "Featured Listings Promotion", "group": "Platform", "icon": "Star", "description": "Boost visibility for reading rooms and accommodations"},
    {"name": "StudySpace Offers", "group": "Platform", "icon": "Zap", "description": "Exclusive StudySpace platform deals and discounts"},
    {"name": "Partner Campaigns", "group": "Platform", "icon": "Handshake", "description": "Joint campaigns with StudySpace partner brands"},
    {"name": "Seasonal/Festival Campaigns", "group": "Platform", "icon": "PartyPopper", "description": "Diwali, New Year, Back-to-School, and seasonal promotions"},
]


@router.get("/migrate-ads-categories-quick")
async def migrate_ads_categories_quick(
    secret: str,
    db: AsyncSession = Depends(get_db)
):
    """
    🚨 EMERGENCY MIGRATION ENDPOINT - NO AUTH NEEDED
    
    Access via URL with secret:
    GET /admin/system/migrate-ads-categories-quick?secret=YOUR_SECRET
    
    This endpoint:
    1. Drops the foreign key constraint on ads.category_id
    2. Seeds 24 ad categories into the database
    
    Safe to run multiple times. Use secret=superadmin123 or your admin password.
    """
    # Simple secret validation - use your superadmin password
    if secret not in ["superadmin123", "admin123"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid secret. Use your superadmin password."
        )
    
    results = {
        "fk_dropped": False,
        "categories_added": 0,
        "categories_skipped": 0,
        "messages": []
    }
    
    try:
        # Step 1: Drop FK constraint
        async with engine.begin() as conn:
            # Check if constraint exists
            check_query = """
            SELECT constraint_name 
            FROM information_schema.table_constraints 
            WHERE table_name = 'ads' 
            AND constraint_name = 'ads_category_id_fkey'
            AND constraint_type = 'FOREIGN KEY';
            """
            
            result = await conn.execute(text(check_query))
            constraint_exists = result.fetchone()
            
            if constraint_exists:
                drop_query = "ALTER TABLE ads DROP CONSTRAINT IF EXISTS ads_category_id_fkey;"
                await conn.execute(text(drop_query))
                results["fk_dropped"] = True
                results["messages"].append("✅ Dropped foreign key constraint 'ads_category_id_fkey'")
            else:
                results["messages"].append("ℹ️  FK constraint already removed")
        
        # Step 2: Seed categories
        for i, cat_data in enumerate(INITIAL_CATEGORIES):
            # Check if category already exists
            result = await db.execute(
                select(AdCategory).where(AdCategory.name == cat_data["name"])
            )
            existing = result.scalars().first()
            
            if existing:
                results["categories_skipped"] += 1
            else:
                category = AdCategory(
                    id=str(uuid.uuid4()),
                    name=cat_data["name"],
                    slug=slugify(cat_data["name"]),
                    description=cat_data["description"],
                    icon=cat_data["icon"],
                    group=cat_data["group"],
                    applicable_to=["USER", "OWNER"],
                    status=CategoryStatus.ACTIVE,
                    display_order=str(i + 1).zfill(3)
                )
                db.add(category)
                results["categories_added"] += 1
        
        await db.commit()
        
        if results["categories_added"] > 0:
            results["messages"].append(f"✅ Added {results['categories_added']} new categories")
        if results["categories_skipped"] > 0:
            results["messages"].append(f"ℹ️  Skipped {results['categories_skipped']} existing categories")
        
        # Get total count
        total_result = await db.execute(select(AdCategory))
        total_categories = len(total_result.scalars().all())
        results["total_categories"] = total_categories
        results["messages"].append(f"📊 Total categories in database: {total_categories}")
        
        results["success"] = True
        results["messages"].append("🎉 Migration completed successfully! You can now create ads.")
        
        return results
        
    except Exception as e:
        results["success"] = False
        results["error"] = str(e)
        results["messages"].append(f"❌ Migration failed: {str(e)}")
        return results


@router.post("/migrate-ads-categories")
async def migrate_ads_categories(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    🚨 EMERGENCY MIGRATION ENDPOINT
    
    This endpoint:
    1. Drops the foreign key constraint on ads.category_id
    2. Seeds 24 ad categories into the database
    
    Super Admin only. Safe to run multiple times.
    """
    if current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Super Admin can run migrations"
        )
    
    results = {
        "fk_dropped": False,
        "categories_added": 0,
        "categories_skipped": 0,
        "messages": []
    }
    
    try:
        # Step 1: Drop FK constraint
        async with engine.begin() as conn:
            # Check if constraint exists
            check_query = """
            SELECT constraint_name 
            FROM information_schema.table_constraints 
            WHERE table_name = 'ads' 
            AND constraint_name = 'ads_category_id_fkey'
            AND constraint_type = 'FOREIGN KEY';
            """
            
            result = await conn.execute(text(check_query))
            constraint_exists = result.fetchone()
            
            if constraint_exists:
                drop_query = "ALTER TABLE ads DROP CONSTRAINT IF EXISTS ads_category_id_fkey;"
                await conn.execute(text(drop_query))
                results["fk_dropped"] = True
                results["messages"].append("✅ Dropped foreign key constraint 'ads_category_id_fkey'")
            else:
                results["messages"].append("ℹ️  FK constraint already removed")
        
        # Step 2: Seed categories
        for i, cat_data in enumerate(INITIAL_CATEGORIES):
            # Check if category already exists
            result = await db.execute(
                select(AdCategory).where(AdCategory.name == cat_data["name"])
            )
            existing = result.scalars().first()
            
            if existing:
                results["categories_skipped"] += 1
            else:
                category = AdCategory(
                    id=str(uuid.uuid4()),
                    name=cat_data["name"],
                    slug=slugify(cat_data["name"]),
                    description=cat_data["description"],
                    icon=cat_data["icon"],
                    group=cat_data["group"],
                    applicable_to=["USER", "OWNER"],
                    status=CategoryStatus.ACTIVE,
                    display_order=str(i + 1).zfill(3)
                )
                db.add(category)
                results["categories_added"] += 1
        
        await db.commit()
        
        if results["categories_added"] > 0:
            results["messages"].append(f"✅ Added {results['categories_added']} new categories")
        if results["categories_skipped"] > 0:
            results["messages"].append(f"ℹ️  Skipped {results['categories_skipped']} existing categories")
        
        # Get total count
        total_result = await db.execute(select(AdCategory))
        total_categories = len(total_result.scalars().all())
        results["total_categories"] = total_categories
        results["messages"].append(f"📊 Total categories in database: {total_categories}")
        
        results["success"] = True
        results["messages"].append("🎉 Migration completed successfully!")
        
        return results
        
    except Exception as e:
        results["success"] = False
        results["error"] = str(e)
        results["messages"].append(f"❌ Migration failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=results
        )


@router.get("/health-check")
async def system_health_check(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Check system health - categories, constraints, etc.
    Super Admin only.
    """
    if current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Super Admin can access system health"
        )
    
    health = {
        "database": "connected",
        "categories": {},
        "constraints": {}
    }
    
    # Check categories
    result = await db.execute(select(AdCategory))
    categories = result.scalars().all()
    health["categories"]["total"] = len(categories)
    health["categories"]["active"] = len([c for c in categories if c.status == CategoryStatus.ACTIVE])
    
    # Check FK constraint
    async with engine.begin() as conn:
        check_query = """
        SELECT constraint_name 
        FROM information_schema.table_constraints 
        WHERE table_name = 'ads' 
        AND constraint_name = 'ads_category_id_fkey';
        """
        result = await conn.execute(text(check_query))
        fk_exists = result.fetchone() is not None
        health["constraints"]["ads_category_fk"] = "exists" if fk_exists else "removed"
    
    return health


@router.get("/reset-superadmin-quick")
async def reset_superadmin_quick(
    secret: str,
    db: AsyncSession = Depends(get_db)
):
    """
    🚨 EMERGENCY ENDPOINT - Reset or create superadmin user
    
    Access via URL with secret:
    GET /admin/system/reset-superadmin-quick?secret=YOUR_SECRET
    
    This endpoint:
    1. Checks if superadmin@studyspace.com exists
    2. If yes, resets password to superadmin123
    3. If no, creates the superadmin user
    
    Use secret=superadmin123 or admin123.
    """
    from app.core.security import get_password_hash
    from app.models.user import VerificationStatus
    
    if secret not in ["superadmin123", "admin123"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid secret."
        )
    
    result = await db.execute(
        select(User).where(User.email == "superadmin@studyspace.com")
    )
    user = result.scalars().first()
    
    if user:
        user.hashed_password = get_password_hash("superadmin123")
        user.role = UserRole.SUPER_ADMIN
        await db.commit()
        return {
            "success": True,
            "action": "reset",
            "message": "✅ Superadmin password reset to 'superadmin123'",
            "email": "superadmin@studyspace.com"
        }
    else:
        new_admin = User(
            email="superadmin@studyspace.com",
            hashed_password=get_password_hash("superadmin123"),
            name="Super Admin",
            role=UserRole.SUPER_ADMIN,
            phone="9876543210",
            verification_status=VerificationStatus.VERIFIED
        )
        db.add(new_admin)
        await db.commit()
        return {
            "success": True,
            "action": "created",
            "message": "✅ Superadmin user created with password 'superadmin123'",
            "email": "superadmin@studyspace.com"
        }

