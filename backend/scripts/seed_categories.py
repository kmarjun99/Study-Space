"""
Seed script to populate the ad_categories table with initial categories.
Run with: python seed_categories.py
"""
import asyncio
import sys
sys.path.insert(0, '.')

from app.database import AsyncSessionLocal, engine, Base
from app.models.ad_category import AdCategory, CategoryStatus
import uuid


# 24 Initial Categories organized by group
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
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async with AsyncSessionLocal() as session:
        # Check if categories already exist
        from sqlalchemy.future import select
        result = await session.execute(select(AdCategory))
        existing = result.scalars().all()
        
        if existing:
            print(f"⚠️  Found {len(existing)} existing categories. Skipping seed.")
            print("   To re-seed, delete existing categories first.")
            return
        
        print("🌱 Seeding ad categories...")
        
        for i, cat_data in enumerate(INITIAL_CATEGORIES):
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
        
        await session.commit()
        print(f"\n🎉 Successfully seeded {len(INITIAL_CATEGORIES)} categories!")


if __name__ == "__main__":
    asyncio.run(seed_categories())
