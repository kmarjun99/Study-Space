"""
Script to seed ad_categories table in production.
Run this ONCE after deployment: python seed_production_categories.py
"""
import asyncio
import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from app.database import AsyncSessionLocal, engine, Base
from app.models.ad_category import AdCategory, CategoryStatus
import uuid


# Initial Categories organized by group
INITIAL_CATEGORIES = [
    # 🎓 Student-Focused (10 categories)
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
    
    # 🏠 Housing / Living (5 categories)
    {"name": "PG/Hostel Promotions", "group": "Housing", "icon": "Home", "description": "Paying guest accommodations, hostels, and co-living spaces"},
    {"name": "Furniture & Appliances", "group": "Housing", "icon": "Sofa", "description": "Rental furniture, appliances, and home setup essentials"},
    {"name": "Home Services", "group": "Housing", "icon": "Wrench", "description": "Plumbing, electrical, pest control, and maintenance services"},
    {"name": "Laundry Services", "group": "Housing", "icon": "Shirt", "description": "Laundry, dry cleaning, and ironing services"},
    {"name": "Cleaning Services", "group": "Housing", "icon": "Sparkles", "description": "House cleaning, deep cleaning, and sanitization services"},
    
    # 💼 Owner / Business (5 categories)
    {"name": "Business Tools & SaaS", "group": "Business", "icon": "Settings", "description": "Software tools, CRMs, and business management solutions"},
    {"name": "Accounting & GST", "group": "Business", "icon": "Calculator", "description": "Accounting software, GST filing services, and tax solutions"},
    {"name": "Payments & Banking", "group": "Business", "icon": "CreditCard", "description": "Payment gateways, business banking, and financial services"},
    {"name": "Marketing & Promotion", "group": "Business", "icon": "Megaphone", "description": "Digital marketing, social media, and advertising services"},
    {"name": "Insurance & Legal", "group": "Business", "icon": "Shield", "description": "Business insurance, legal compliance, and documentation"},
    
    # ⭐ Platform-Specific (4 categories)
    {"name": "Featured Listings Promotion", "group": "Platform", "icon": "Star", "description": "Boost visibility for reading rooms and accommodations"},
    {"name": "StudySpace Offers", "group": "Platform", "icon": "Zap", "description": "Exclusive StudySpace platform deals and discounts"},
    {"name": "Partner Campaigns", "group": "Platform", "icon": "Handshake", "description": "Joint campaigns with StudySpace partner brands"},
    {"name": "Seasonal/Festival Campaigns", "group": "Platform", "icon": "PartyPopper", "description": "Diwali, New Year, Back-to-School, and seasonal promotions"},
]


def slugify(text: str) -> str:
    """Convert text to URL-friendly slug."""
    import re
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[-\s]+', '-', text)
    return text


async def seed_categories():
    """Seed the database with initial ad categories."""
    print("🚀 Starting category seeding for production...\n")
    
    # Ensure tables exist
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        print("✅ Database tables verified\n")
    
    async with AsyncSessionLocal() as session:
        # Check if categories already exist
        from sqlalchemy.future import select
        result = await session.execute(select(AdCategory))
        existing = result.scalars().all()
        
        if existing:
            print(f"⚠️  Found {len(existing)} existing categories.")
            print("   Existing categories will be skipped.\n")
            
            # Show existing
            for cat in existing[:5]:
                print(f"   - {cat.name} ({cat.group})")
            if len(existing) > 5:
                print(f"   ... and {len(existing) - 5} more")
            print()
        
        print("🌱 Adding new categories...\n")
        
        added_count = 0
        skipped_count = 0
        
        for i, cat_data in enumerate(INITIAL_CATEGORIES):
            # Check if this category name already exists
            result = await session.execute(
                select(AdCategory).where(AdCategory.name == cat_data["name"])
            )
            if result.scalars().first():
                skipped_count += 1
                continue
            
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
            session.add(category)
            print(f"   ✅ Added: {cat_data['name']} ({cat_data['group']})")
            added_count += 1
        
        if added_count > 0:
            await session.commit()
            print(f"\n🎉 Successfully seeded {added_count} new categories!")
        else:
            print(f"\nℹ️  All categories already exist. No new categories added.")
        
        if skipped_count > 0:
            print(f"   Skipped {skipped_count} existing categories.")


async def verify_categories():
    """Verify that categories were seeded correctly."""
    print("\n" + "="*60)
    print("📊 VERIFICATION: Current Categories in Database")
    print("="*60 + "\n")
    
    async with AsyncSessionLocal() as session:
        from sqlalchemy.future import select
        result = await session.execute(
            select(AdCategory).order_by(AdCategory.group, AdCategory.display_order)
        )
        categories = result.scalars().all()
        
        if not categories:
            print("⚠️  No categories found in database!")
            return
        
        current_group = None
        for cat in categories:
            if cat.group != current_group:
                current_group = cat.group
                print(f"\n{cat.group} Categories:")
                print("-" * 40)
            print(f"  • {cat.name}")
            print(f"    ID: {cat.id}")
            print(f"    Status: {cat.status.value}")
        
        print(f"\n{'='*60}")
        print(f"Total: {len(categories)} categories")
        print(f"{'='*60}\n")


if __name__ == "__main__":
    print("\n" + "="*60)
    print("  AD CATEGORIES SEED SCRIPT - PRODUCTION")
    print("="*60 + "\n")
    
    try:
        asyncio.run(seed_categories())
        asyncio.run(verify_categories())
        print("\n✨ All done! You can now create ads with categories.\n")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
