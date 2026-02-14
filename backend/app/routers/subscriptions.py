"""
Subscriptions Router - CRUD for subscription plans
"""
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from pydantic import BaseModel
from app.database import get_db
from app.models.subscription_plan import SubscriptionPlan
from app.models.user import User, UserRole
from app.deps import get_current_user, get_current_admin, get_current_user_optional


router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])


# ============================================================
# SCHEMAS
# ============================================================

class SubscriptionPlanCreate(BaseModel):
    name: str
    description: Optional[str] = None
    price: float
    duration_days: int = 30
    features: Optional[List[str]] = []
    is_active: bool = True
    is_default: bool = False


class SubscriptionPlanUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None
    duration_days: Optional[int] = None
    features: Optional[List[str]] = None
    is_active: Optional[bool] = None
    is_default: Optional[bool] = None


class SubscriptionPlanResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    price: float
    duration_days: int
    features: List[str]
    is_active: bool
    is_default: bool
    created_by: str
    created_at: datetime
    
    class Config:
        from_attributes = True


# ============================================================
# ENDPOINTS
# ============================================================

@router.get("/plans", response_model=List[SubscriptionPlanResponse])
async def get_subscription_plans(
    include_inactive: bool = False,
    db: AsyncSession = Depends(get_db)
):
    """
    Get all subscription plans.
    By default returns only active plans. Super Admin can see all.
    """
    query = select(SubscriptionPlan).order_by(SubscriptionPlan.price)
    
    if not include_inactive:
        query = query.where(SubscriptionPlan.is_active == True)
    
    result = await db.execute(query)
    plans = result.scalars().all()
    
    return [
        SubscriptionPlanResponse(
            id=p.id,
            name=p.name,
            description=p.description,
            price=p.price,
            duration_days=p.duration_days,
            features=p.features or [],
            is_active=p.is_active,
            is_default=p.is_default,
            created_by=p.created_by,
            created_at=p.created_at
        )
        for p in plans
    ]


@router.post("/plans", response_model=SubscriptionPlanResponse)
async def create_subscription_plan(
    plan: SubscriptionPlanCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Create a new subscription plan. Super Admin only."""
    if current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=403, detail="Only Super Admin can create subscription plans")
    
    # If this is set as default, unset other defaults
    if plan.is_default:
        existing = await db.execute(select(SubscriptionPlan).where(SubscriptionPlan.is_default == True))
        for existing_plan in existing.scalars().all():
            existing_plan.is_default = False
    
    new_plan = SubscriptionPlan(
        name=plan.name,
        description=plan.description,
        price=plan.price,
        duration_days=plan.duration_days,
        features=plan.features or [],
        is_active=plan.is_active,
        is_default=plan.is_default,
        created_by=current_user.id
    )
    
    db.add(new_plan)
    await db.commit()
    await db.refresh(new_plan)
    
    return SubscriptionPlanResponse(
        id=new_plan.id,
        name=new_plan.name,
        description=new_plan.description,
        price=new_plan.price,
        duration_days=new_plan.duration_days,
        features=new_plan.features or [],
        is_active=new_plan.is_active,
        is_default=new_plan.is_default,
        created_by=new_plan.created_by,
        created_at=new_plan.created_at
    )


@router.put("/plans/{plan_id}", response_model=SubscriptionPlanResponse)
async def update_subscription_plan(
    plan_id: str,
    updates: SubscriptionPlanUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Update a subscription plan. Super Admin only."""
    if current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=403, detail="Only Super Admin can update subscription plans")
    
    result = await db.execute(select(SubscriptionPlan).where(SubscriptionPlan.id == plan_id))
    plan = result.scalars().first()
    if not plan:
        raise HTTPException(status_code=404, detail="Subscription plan not found")
    
    # If setting as default, unset other defaults
    if updates.is_default:
        existing = await db.execute(select(SubscriptionPlan).where(SubscriptionPlan.is_default == True))
        for existing_plan in existing.scalars().all():
            if existing_plan.id != plan_id:
                existing_plan.is_default = False
    
    update_data = updates.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(plan, key, value)
    
    await db.commit()
    await db.refresh(plan)
    
    return SubscriptionPlanResponse(
        id=plan.id,
        name=plan.name,
        description=plan.description,
        price=plan.price,
        duration_days=plan.duration_days,
        features=plan.features or [],
        is_active=plan.is_active,
        is_default=plan.is_default,
        created_by=plan.created_by,
        created_at=plan.created_at
    )


@router.delete("/plans/{plan_id}")
async def delete_subscription_plan(
    plan_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """Delete a subscription plan. Super Admin only."""
    if current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=403, detail="Only Super Admin can delete subscription plans")
    
    result = await db.execute(select(SubscriptionPlan).where(SubscriptionPlan.id == plan_id))
    plan = result.scalars().first()
    if not plan:
        raise HTTPException(status_code=404, detail="Subscription plan not found")
    
    await db.delete(plan)
    await db.commit()
    
    return {"message": "Subscription plan deleted successfully"}
