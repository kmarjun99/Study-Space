from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from typing import List
from app.database import get_db
from app.models.favorite import Favorite
from app.models.accommodation import Accommodation
from app.models.reading_room import ReadingRoom
from app.models.user import User
from app.deps import get_current_user
from pydantic import BaseModel

router = APIRouter(prefix="/favorites", tags=["Favorites"])


class FavoriteCreate(BaseModel):
    accommodation_id: str | None = None
    reading_room_id: str | None = None


class FavoriteResponse(BaseModel):
    id: str
    user_id: str
    accommodation_id: str | None
    reading_room_id: str | None
    created_at: str
    
    # Include item details
    item_name: str | None = None
    item_type: str | None = None
    item_image: str | None = None
    item_price: float | None = None
    item_city: str | None = None

    class Config:
        from_attributes = True


@router.post("/", response_model=FavoriteResponse)
async def add_favorite(
    favorite: FavoriteCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Add an accommodation or reading room to favorites."""
    
    # Validate that exactly one ID is provided
    if not favorite.accommodation_id and not favorite.reading_room_id:
        raise HTTPException(status_code=400, detail="Must provide accommodation_id or reading_room_id")
    
    if favorite.accommodation_id and favorite.reading_room_id:
        raise HTTPException(status_code=400, detail="Cannot favorite both accommodation and reading room at once")
    
    # Check if already favorited
    existing = await db.execute(
        select(Favorite).where(
            Favorite.user_id == current_user.id,
            Favorite.accommodation_id == favorite.accommodation_id if favorite.accommodation_id else Favorite.reading_room_id == favorite.reading_room_id
        )
    )
    
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Already in favorites")
    
    # Create favorite
    new_favorite = Favorite(
        user_id=current_user.id,
        accommodation_id=favorite.accommodation_id,
        reading_room_id=favorite.reading_room_id
    )
    
    db.add(new_favorite)
    await db.commit()
    await db.refresh(new_favorite)
    
    # Fetch item details
    item_name, item_type, item_image, item_price, item_city = None, None, None, None, None
    
    if favorite.accommodation_id:
        acc = await db.get(Accommodation, favorite.accommodation_id)
        if acc:
            item_name = acc.name
            item_type = "accommodation"
            item_image = acc.images.strip('"[]').split('","')[0] if acc.images else None
            item_price = acc.price
            item_city = acc.city
    
    if favorite.reading_room_id:
        room = await db.get(ReadingRoom, favorite.reading_room_id)
        if room:
            item_name = room.name
            item_type = "reading_room"
            item_image = room.images.strip('"[]').split('","')[0] if room.images else None
            item_price = room.price_start
            item_city = room.city
    
    return FavoriteResponse(
        id=new_favorite.id,
        user_id=new_favorite.user_id,
        accommodation_id=new_favorite.accommodation_id,
        reading_room_id=new_favorite.reading_room_id,
        created_at=new_favorite.created_at.isoformat(),
        item_name=item_name,
        item_type=item_type,
        item_image=item_image,
        item_price=item_price,
        item_city=item_city
    )


@router.get("/", response_model=List[FavoriteResponse])
async def get_favorites(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all favorites for the current user."""
    
    result = await db.execute(
        select(Favorite).where(Favorite.user_id == current_user.id).order_by(Favorite.created_at.desc())
    )
    favorites = result.scalars().all()
    
    # Enrich with item details
    response = []
    for fav in favorites:
        item_name, item_type, item_image, item_price, item_city = None, None, None, None, None
        
        if fav.accommodation_id:
            acc = await db.get(Accommodation, fav.accommodation_id)
            if acc:
                item_name = acc.name
                item_type = "accommodation"
                item_image = acc.images.strip('"[]').split('","')[0] if acc.images else None
                item_price = acc.price
                item_city = acc.city
        
        if fav.reading_room_id:
            room = await db.get(ReadingRoom, fav.reading_room_id)
            if room:
                item_name = room.name
                item_type = "reading_room"
                item_image = room.images.strip('"[]').split('","')[0] if room.images else None
                item_price = room.price_start
                item_city = room.city
        
        response.append(FavoriteResponse(
            id=fav.id,
            user_id=fav.user_id,
            accommodation_id=fav.accommodation_id,
            reading_room_id=fav.reading_room_id,
            created_at=fav.created_at.isoformat(),
            item_name=item_name,
            item_type=item_type,
            item_image=item_image,
            item_price=item_price,
            item_city=item_city
        ))
    
    return response


@router.delete("/{favorite_id}")
async def remove_favorite(
    favorite_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Remove a favorite."""
    
    result = await db.execute(
        select(Favorite).where(
            Favorite.id == favorite_id,
            Favorite.user_id == current_user.id
        )
    )
    favorite = result.scalar_one_or_none()
    
    if not favorite:
        raise HTTPException(status_code=404, detail="Favorite not found")
    
    await db.delete(favorite)
    await db.commit()
    
    return {"message": "Removed from favorites"}


@router.get("/check")
async def check_favorite(
    accommodation_id: str | None = None,
    reading_room_id: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Check if an item is favorited."""
    
    if not accommodation_id and not reading_room_id:
        raise HTTPException(status_code=400, detail="Must provide accommodation_id or reading_room_id")
    
    result = await db.execute(
        select(Favorite).where(
            Favorite.user_id == current_user.id,
            Favorite.accommodation_id == accommodation_id if accommodation_id else Favorite.reading_room_id == reading_room_id
        )
    )
    
    favorite = result.scalar_one_or_none()
    
    return {
        "is_favorited": favorite is not None,
        "favorite_id": favorite.id if favorite else None
    }
