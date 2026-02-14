"""
Debug async SQLAlchemy query
"""
import asyncio
import sys
sys.path.insert(0, '.')

from sqlalchemy import select
from app.database import AsyncSessionLocal, engine
from app.models.boost_plan import BoostPlan

async def test_query():
    print("Testing async SQLAlchemy query...")
    
    async with AsyncSessionLocal() as db:
        try:
            # Test simple query - get all
            print("Query 1: SELECT * FROM boost_plans")
            result = await db.execute(select(BoostPlan))
            all_plans = result.scalars().all()
            print(f"  Found {len(all_plans)} plans")
            for p in all_plans:
                print(f"    - {p.name}: status={p.status}, type={type(p.status)}")
            
            # Test with status filter
            print("\nQuery 2: SELECT * FROM boost_plans WHERE status = 'active'")
            result2 = await db.execute(select(BoostPlan).where(BoostPlan.status == "active"))
            active_plans = result2.scalars().all()
            print(f"  Found {len(active_plans)} active plans")
            
        except Exception as e:
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_query())
