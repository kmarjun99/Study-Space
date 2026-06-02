"""
Seed boost plans using SQLAlchemy models properly
"""
import asyncio
from sqlalchemy import select, delete
from app.database import AsyncSessionLocal
from app.models.boost_plan import BoostPlan, BoostPlanStatus, BoostApplicableTo, BoostPlacement

async def seed_boost_plans():
    async with AsyncSessionLocal() as db:
        try:
            # First, clear existing plans
            await db.execute(delete(BoostPlan))
            await db.commit()
            print("Cleared existing boost plans")
            
            # Create new plans using SQLAlchemy models
            plans = [
                BoostPlan(
                    name="Featured Listing - Basic",
                    description="Get your property featured for 7 days (₹499 + GST)",
                    price=499.0,
                    duration_days=7,
                    applicable_to=BoostApplicableTo.BOTH,
                    placement=BoostPlacement.FEATURED_SECTION,
                    visibility_weight=1,
                    status=BoostPlanStatus.ACTIVE,
                    created_by="super_admin"
                ),
                BoostPlan(
                    name="Premium Visibility - 30 Days",
                    description="Maximum visibility for 30 days (₹1499 + GST)",
                    price=1499.0,
                    duration_days=30,
                    applicable_to=BoostApplicableTo.BOTH,
                    placement=BoostPlacement.TOP_LIST,
                    visibility_weight=5,
                    status=BoostPlanStatus.ACTIVE,
                    created_by="super_admin"
                ),
            ]
            
            for plan in plans:
                db.add(plan)
            
            await db.commit()
            print(f"Created {len(plans)} boost plans successfully!")
            
            # Verify
            result = await db.execute(select(BoostPlan).where(BoostPlan.status == BoostPlanStatus.ACTIVE))
            active_plans = result.scalars().all()
            print(f"\nActive plans in database: {len(active_plans)}")
            for p in active_plans:
                print(f"  - {p.name} (status={p.status}, applicable_to={p.applicable_to})")
                
        except Exception as e:
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(seed_boost_plans())
