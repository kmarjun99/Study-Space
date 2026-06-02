
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.database import get_db
from app.models.ad_category import AdCategory, CategoryStatus
from app.models.user import User, UserRole
from app.deps import get_current_user
from pydantic import BaseModel
from datetime import datetime
import re


router = APIRouter(prefix="/ad-categories", tags=["ad-categories"])


def slugify(text: str) -> str:
    """Convert text to URL-friendly slug."""
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[-\s]+', '-', text)
    return text


class AdCategoryBase(BaseModel):
    name: str
    description: Optional[str] = None
    icon: Optional[str] = None
    group: Optional[str] = None
    applicable_to: Optional[List[str]] = ["USER", "OWNER"]


class AdCategoryCreate(AdCategoryBase):
    pass


class AdCategoryUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    icon: Optional[str] = None
    group: Optional[str] = None
    applicable_to: Optional[List[str]] = None
    status: Optional[str] = None


class AdCategoryResponse(AdCategoryBase):
    id: str
    slug: str
    status: str
    display_order: str
    created_at: datetime
    
    class Config:
        from_attributes = True


# ============================================================
# PUBLIC ENDPOINT - List all active categories
# ============================================================
@router.get("/", response_model=List[AdCategoryResponse])
async def get_ad_categories(
    include_inactive: bool = False,
    db: AsyncSession = Depends(get_db)
):
    """
    Get all ad categories. By default only returns ACTIVE categories.
    Super Admin can pass include_inactive=true to see all.
    """
    query = select(AdCategory).order_by(AdCategory.group, AdCategory.display_order, AdCategory.name)
    
    if not include_inactive:
        query = query.where(AdCategory.status == CategoryStatus.ACTIVE)
    
    result = await db.execute(query)
    return result.scalars().all()


# ============================================================
# SUPER ADMIN ONLY - Create category
# ============================================================
@router.post("/", response_model=AdCategoryResponse)
async def create_ad_category(
    category: AdCategoryCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new ad category. Super Admin only."""
    if current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Super Admin can create ad categories"
        )
    
    # Check if category with same name exists
    existing = await db.execute(
        select(AdCategory).where(AdCategory.name == category.name)
    )
    if existing.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Category '{category.name}' already exists"
        )
    
    new_category = AdCategory(
        name=category.name,
        slug=slugify(category.name),
        description=category.description,
        icon=category.icon,
        group=category.group,
        applicable_to=category.applicable_to,
        status=CategoryStatus.ACTIVE
    )
    
    db.add(new_category)
    await db.commit()
    await db.refresh(new_category)
    return new_category


# ============================================================
# SUPER ADMIN ONLY - Update category
# ============================================================
@router.put("/{category_id}", response_model=AdCategoryResponse)
async def update_ad_category(
    category_id: str,
    updates: AdCategoryUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update an ad category. Super Admin only."""
    if current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Super Admin can update ad categories"
        )
    
    result = await db.execute(
        select(AdCategory).where(AdCategory.id == category_id)
    )
    category = result.scalars().first()
    
    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found"
        )
    
    # Apply updates
    update_data = updates.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if field == "status":
            value = CategoryStatus(value)
        if field == "name" and value:
            setattr(category, "slug", slugify(value))
        setattr(category, field, value)
    
    await db.commit()
    await db.refresh(category)
    return category


# ============================================================
# SUPER ADMIN ONLY - Delete (soft delete) category
# ============================================================
@router.delete("/{category_id}")
async def delete_ad_category(
    category_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Soft delete an ad category (set status to INACTIVE).
    Super Admin only. Existing ads with this category remain unchanged.
    """
    if current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Super Admin can delete ad categories"
        )
    
    result = await db.execute(
        select(AdCategory).where(AdCategory.id == category_id)
    )
    category = result.scalars().first()
    
    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found"
        )
    
    category.status = CategoryStatus.INACTIVE
    await db.commit()
    
    return {"message": f"Category '{category.name}' has been deactivated"}
