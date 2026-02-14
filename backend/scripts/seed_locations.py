"""
Seed script to populate locations table with Indian cities and localities.
Run with: python seed_locations.py
"""
import asyncio
import sys
sys.path.insert(0, '.')

from app.database import AsyncSessionLocal, engine, Base
from app.models.location import Location
import uuid


# 50+ Indian Cities with key localities
LOCATIONS_DATA = [
    # === TIER 1 CITIES ===
    
    # Delhi NCR
    {"state": "Delhi", "city": "New Delhi", "locality": None},
    {"state": "Delhi", "city": "New Delhi", "locality": "Connaught Place"},
    {"state": "Delhi", "city": "New Delhi", "locality": "Dwarka"},
    {"state": "Delhi", "city": "New Delhi", "locality": "Rohini"},
    {"state": "Delhi", "city": "New Delhi", "locality": "Karol Bagh"},
    {"state": "Delhi", "city": "New Delhi", "locality": "Laxmi Nagar"},
    {"state": "Haryana", "city": "Gurgaon", "locality": None},
    {"state": "Haryana", "city": "Gurgaon", "locality": "Cyber City"},
    {"state": "Uttar Pradesh", "city": "Noida", "locality": None},
    {"state": "Uttar Pradesh", "city": "Noida", "locality": "Sector 62"},
    
    # Mumbai
    {"state": "Maharashtra", "city": "Mumbai", "locality": None},
    {"state": "Maharashtra", "city": "Mumbai", "locality": "Andheri"},
    {"state": "Maharashtra", "city": "Mumbai", "locality": "Bandra"},
    {"state": "Maharashtra", "city": "Mumbai", "locality": "Powai"},
    {"state": "Maharashtra", "city": "Mumbai", "locality": "Dadar"},
    {"state": "Maharashtra", "city": "Mumbai", "locality": "Lower Parel"},
    {"state": "Maharashtra", "city": "Mumbai", "locality": "Thane"},
    {"state": "Maharashtra", "city": "Navi Mumbai", "locality": None},
    {"state": "Maharashtra", "city": "Navi Mumbai", "locality": "Vashi"},
    
    # Bangalore
    {"state": "Karnataka", "city": "Bangalore", "locality": None},
    {"state": "Karnataka", "city": "Bangalore", "locality": "Indiranagar"},
    {"state": "Karnataka", "city": "Bangalore", "locality": "Koramangala"},
    {"state": "Karnataka", "city": "Bangalore", "locality": "Whitefield"},
    {"state": "Karnataka", "city": "Bangalore", "locality": "HSR Layout"},
    {"state": "Karnataka", "city": "Bangalore", "locality": "Electronic City"},
    {"state": "Karnataka", "city": "Bangalore", "locality": "Marathahalli"},
    {"state": "Karnataka", "city": "Bangalore", "locality": "JP Nagar"},
    {"state": "Karnataka", "city": "Bangalore", "locality": "Jayanagar"},
    
    # Hyderabad
    {"state": "Telangana", "city": "Hyderabad", "locality": None},
    {"state": "Telangana", "city": "Hyderabad", "locality": "Hitech City"},
    {"state": "Telangana", "city": "Hyderabad", "locality": "Gachibowli"},
    {"state": "Telangana", "city": "Hyderabad", "locality": "Madhapur"},
    {"state": "Telangana", "city": "Hyderabad", "locality": "Kondapur"},
    {"state": "Telangana", "city": "Hyderabad", "locality": "Banjara Hills"},
    
    # Chennai
    {"state": "Tamil Nadu", "city": "Chennai", "locality": None},
    {"state": "Tamil Nadu", "city": "Chennai", "locality": "T Nagar"},
    {"state": "Tamil Nadu", "city": "Chennai", "locality": "Anna Nagar"},
    {"state": "Tamil Nadu", "city": "Chennai", "locality": "Velachery"},
    {"state": "Tamil Nadu", "city": "Chennai", "locality": "OMR"},
    {"state": "Tamil Nadu", "city": "Chennai", "locality": "Adyar"},
    
    # Kolkata
    {"state": "West Bengal", "city": "Kolkata", "locality": None},
    {"state": "West Bengal", "city": "Kolkata", "locality": "Salt Lake"},
    {"state": "West Bengal", "city": "Kolkata", "locality": "Park Street"},
    {"state": "West Bengal", "city": "Kolkata", "locality": "New Town"},
    {"state": "West Bengal", "city": "Kolkata", "locality": "Howrah"},
    
    # === TIER 2 CITIES ===
    
    # Pune
    {"state": "Maharashtra", "city": "Pune", "locality": None},
    {"state": "Maharashtra", "city": "Pune", "locality": "Koregaon Park"},
    {"state": "Maharashtra", "city": "Pune", "locality": "Hinjewadi"},
    {"state": "Maharashtra", "city": "Pune", "locality": "Kharadi"},
    {"state": "Maharashtra", "city": "Pune", "locality": "Viman Nagar"},
    
    # Ahmedabad
    {"state": "Gujarat", "city": "Ahmedabad", "locality": None},
    {"state": "Gujarat", "city": "Ahmedabad", "locality": "SG Highway"},
    {"state": "Gujarat", "city": "Ahmedabad", "locality": "Navrangpura"},
    
    # Jaipur
    {"state": "Rajasthan", "city": "Jaipur", "locality": None},
    {"state": "Rajasthan", "city": "Jaipur", "locality": "Malviya Nagar"},
    {"state": "Rajasthan", "city": "Jaipur", "locality": "C-Scheme"},
    
    # Lucknow
    {"state": "Uttar Pradesh", "city": "Lucknow", "locality": None},
    {"state": "Uttar Pradesh", "city": "Lucknow", "locality": "Gomti Nagar"},
    {"state": "Uttar Pradesh", "city": "Lucknow", "locality": "Hazratganj"},
    
    # === KERALA ===
    {"state": "Kerala", "city": "Thiruvananthapuram", "locality": None},
    {"state": "Kerala", "city": "Thiruvananthapuram", "locality": "Kazhakkoottam"},
    {"state": "Kerala", "city": "Thiruvananthapuram", "locality": "Technopark"},
    {"state": "Kerala", "city": "Kochi", "locality": None},
    {"state": "Kerala", "city": "Kochi", "locality": "Marine Drive"},
    {"state": "Kerala", "city": "Kochi", "locality": "Infopark"},
    {"state": "Kerala", "city": "Kochi", "locality": "Kakkanad"},
    {"state": "Kerala", "city": "Kozhikode", "locality": None},
    {"state": "Kerala", "city": "Thrissur", "locality": None},
    
    # === OTHER MAJOR CITIES ===
    {"state": "Chandigarh", "city": "Chandigarh", "locality": None},
    {"state": "Chandigarh", "city": "Chandigarh", "locality": "Sector 17"},
    {"state": "Punjab", "city": "Mohali", "locality": None},
    {"state": "Madhya Pradesh", "city": "Indore", "locality": None},
    {"state": "Madhya Pradesh", "city": "Bhopal", "locality": None},
    {"state": "Odisha", "city": "Bhubaneswar", "locality": None},
    {"state": "Andhra Pradesh", "city": "Visakhapatnam", "locality": None},
    {"state": "Andhra Pradesh", "city": "Vijayawada", "locality": None},
    {"state": "Goa", "city": "Panaji", "locality": None},
    {"state": "Assam", "city": "Guwahati", "locality": None},
    {"state": "Jharkhand", "city": "Ranchi", "locality": None},
    {"state": "Bihar", "city": "Patna", "locality": None},
    {"state": "Uttarakhand", "city": "Dehradun", "locality": None},
    {"state": "Tamil Nadu", "city": "Coimbatore", "locality": None},
    {"state": "Tamil Nadu", "city": "Madurai", "locality": None},
    {"state": "Karnataka", "city": "Mysore", "locality": None},
    {"state": "Karnataka", "city": "Mangalore", "locality": None},
    {"state": "Gujarat", "city": "Surat", "locality": None},
    {"state": "Gujarat", "city": "Vadodara", "locality": None},
    {"state": "Rajasthan", "city": "Udaipur", "locality": None},
    {"state": "Rajasthan", "city": "Jodhpur", "locality": None},
]


async def seed_locations():
    """Seed the database with initial locations."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async with AsyncSessionLocal() as session:
        # Check if locations already exist
        from sqlalchemy.future import select
        result = await session.execute(select(Location))
        existing = result.scalars().all()
        
        if existing:
            print(f"⚠️  Found {len(existing)} existing locations. Skipping seed.")
            print("   To re-seed, delete existing locations first.")
            return
        
        print("🌱 Seeding locations...")
        
        for data in LOCATIONS_DATA:
            location = Location(
                id=str(uuid.uuid4()),
                country="India",
                state=data["state"],
                city=data["city"],
                locality=data.get("locality"),
                city_normalized=Location.normalize(data["city"]),
                locality_normalized=Location.normalize(data.get("locality")) if data.get("locality") else None,
                search_text=Location.create_search_text(data["city"], data["state"], data.get("locality")),
                is_active=True,
                usage_count=0
            )
            session.add(location)
            
            display = f"{data['locality']}, {data['city']}" if data.get("locality") else f"{data['city']}, {data['state']}"
            print(f"   ✅ Added: {display}")
        
        await session.commit()
        print(f"\n🎉 Successfully seeded {len(LOCATIONS_DATA)} locations!")


if __name__ == "__main__":
    asyncio.run(seed_locations())
