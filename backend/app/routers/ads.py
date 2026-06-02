
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.database import get_db
from app.models.ad import Ad, TargetAudience
from app.models.ad_category import AdCategory, CategoryStatus
from app.models.user import User, UserRole
from app.deps import get_current_user
from pydantic import BaseModel

router = APIRouter(prefix="/ads", tags=["ads"])


class AdBase(BaseModel):
    title: str
    description: str
    image_url: str
    cta_text: str
    link: str
    category_id: Optional[str] = None
    target_audience: TargetAudience = TargetAudience.ALL
    is_active: bool = True
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None


class AdCreate(AdBase):
    pass


class AdUpdate(BaseModel):
    """Partial update schema - all fields optional"""
    title: Optional[str] = None
    description: Optional[str] = None
    image_url: Optional[str] = None
    cta_text: Optional[str] = None
    link: Optional[str] = None
    category_id: Optional[str] = None
    target_audience: Optional[TargetAudience] = None
    is_active: Optional[bool] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None


class AdResponse(BaseModel):
    id: str
    title: str
    description: str
    image_url: str
    cta_text: str
    link: str
    category_id: Optional[str] = None
    target_audience: TargetAudience
    is_active: bool = True
    created_at: Optional[datetime] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    impression_count: int = 0
    click_count: int = 0
    
    class Config:
        from_attributes = True


# Public endpoint to fetch active ads
@router.get("/", response_model=List[AdResponse])
async def get_ads(
    audience: TargetAudience = None,
    include_inactive: bool = False,
    db: AsyncSession = Depends(get_db)
):
    query = select(Ad)
    
    # Filter by audience if specified
    if audience:
        query = query.where((Ad.target_audience == audience) | (Ad.target_audience == TargetAudience.ALL))
    
    # Only show active ads by default (for public)
    if not include_inactive:
        query = query.where(Ad.is_active == True)
        # Also filter by date range if set
        now = datetime.utcnow()
        query = query.where(
            ((Ad.start_date == None) | (Ad.start_date <= now)) &
            ((Ad.end_date == None) | (Ad.end_date >= now))
        )
    
    result = await db.execute(query)
    return result.scalars().all()


# Get single ad by ID
@router.get("/{ad_id}", response_model=AdResponse)
async def get_ad(ad_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Ad).where(Ad.id == ad_id))
    ad = result.scalars().first()
    if not ad:
        raise HTTPException(status_code=404, detail="Ad not found")
    return ad


# Track impression (when ad is viewed)
@router.post("/{ad_id}/impression")
async def track_impression(ad_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Ad).where(Ad.id == ad_id))
    ad = result.scalars().first()
    if ad:
        ad.impression_count = (ad.impression_count or 0) + 1
        await db.commit()
    return {"success": True}


# Track click (when ad is clicked)
@router.post("/{ad_id}/click")
async def track_click(ad_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Ad).where(Ad.id == ad_id))
    ad = result.scalars().first()
    if ad:
        ad.click_count = (ad.click_count or 0) + 1
        await db.commit()
    return {"success": True}


# Admin or Super Admin: Create Ad
@router.post("/", response_model=AdResponse)
async def create_ad(
    ad: AdCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role not in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Admin or Super Admin can create ads"
        )
    
    new_ad = Ad(**ad.model_dump())
    db.add(new_ad)
    await db.commit()
    await db.refresh(new_ad)
    return new_ad


# Admin or Super Admin: Update Ad
@router.put("/{ad_id}", response_model=AdResponse)
async def update_ad(
    ad_id: str,
    ad_update: AdUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role not in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
        raise HTTPException(status_code=403, detail="Only Admin or Super Admin can edit ads")
    
    result = await db.execute(select(Ad).where(Ad.id == ad_id))
    ad = result.scalars().first()
    if not ad:
        raise HTTPException(status_code=404, detail="Ad not found")
    
    # Update only provided fields
    update_data = ad_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(ad, field, value)
    
    await db.commit()
    await db.refresh(ad)
    return ad


# Admin or Super Admin: Toggle ad active status
@router.patch("/{ad_id}/toggle")
async def toggle_ad(
    ad_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role not in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    result = await db.execute(select(Ad).where(Ad.id == ad_id))
    ad = result.scalars().first()
    if not ad:
        raise HTTPException(status_code=404, detail="Ad not found")
    
    ad.is_active = not ad.is_active
    await db.commit()
    return {"id": ad.id, "is_active": ad.is_active}


# Admin or Super Admin: Delete Ad
@router.delete("/{ad_id}")
async def delete_ad(
    ad_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role not in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
        raise HTTPException(status_code=403, detail="Not authorized")
        
    result = await db.execute(select(Ad).where(Ad.id == ad_id))
    ad = result.scalars().first()
    if not ad:
        raise HTTPException(status_code=404, detail="Ad not found")
        
    await db.delete(ad)
    await db.commit()
    return {"message": "Ad deleted"}


# Super Admin: Fix blob URLs in ads (replaces them with placeholder)
@router.post("/fix-blob-urls")
async def fix_blob_urls(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Fix ads that have blob: URLs by replacing them with a placeholder image.
    This happens when users accidentally upload files instead of providing direct URLs.
    """
    if current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Super Admin can fix blob URLs"
        )
    
    # Default placeholder image
    PLACEHOLDER_IMAGE = "https://images.unsplash.com/photo-1557804506-669a67965ba0?auto=format&fit=crop&w=800&q=80"
    
    # Find all ads with blob URLs
    result = await db.execute(select(Ad).where(Ad.image_url.like('blob:%')))
    blob_ads = result.scalars().all()
    
    if not blob_ads:
        return {
            "message": "No ads with blob URLs found",
            "fixed_count": 0,
            "ads_fixed": []
        }
    
    fixed_ads = []
    for ad in blob_ads:
        old_url = ad.image_url
        ad.image_url = PLACEHOLDER_IMAGE
        fixed_ads.append({
            "id": ad.id,
            "title": ad.title,
            "old_url": old_url[:60] + "..." if len(old_url) > 60 else old_url,
            "new_url": PLACEHOLDER_IMAGE
        })
    
    await db.commit()
    
    return {
        "message": f"Successfully fixed {len(fixed_ads)} ads",
        "fixed_count": len(fixed_ads),
        "ads_fixed": fixed_ads,
        "next_steps": "Please edit each ad and add a proper image URL from Imgur, Unsplash, or any direct image URL"
    }
