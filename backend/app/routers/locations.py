"""
Locations Router - Autocomplete search and location management.
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import or_, func
from app.database import get_db
from app.models.location import Location
from app.models.user import User, UserRole
from app.deps import get_current_user
from pydantic import BaseModel
from datetime import datetime


router = APIRouter(prefix="/locations", tags=["locations"])


# ============================================================
# SCHEMAS
# ============================================================

class LocationBase(BaseModel):
    country: str = "India"
    state: str
    city: str
    locality: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class LocationCreate(LocationBase):
    pass


class LocationResponse(BaseModel):
    id: str
    country: str
    state: str
    city: str
    locality: Optional[str] = None
    display_name: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    usage_count: int = 0
    is_active: bool = True
    
    class Config:
        from_attributes = True


class AutocompleteResult(BaseModel):
    id: str
    display_name: str
    city: str
    state: str
    locality: Optional[str] = None


# ============================================================
# PUBLIC ENDPOINTS
# ============================================================

@router.get("/autocomplete", response_model=List[AutocompleteResult])
async def autocomplete_locations(
    q: str = Query(..., min_length=2, description="Search query (min 2 chars)"),
    limit: int = Query(10, le=20),
    db: AsyncSession = Depends(get_db)
):
    """
    Fast autocomplete for location search.
    Works after 2 characters - searches city, state, and locality.
    Returns most popular matches first.
    """
    search_term = q.lower().strip()
    
    query = (
        select(Location)
        .where(
            Location.is_active == True,
            or_(
                Location.city_normalized.ilike(f"%{search_term}%"),
                Location.locality_normalized.ilike(f"%{search_term}%"),
                Location.search_text.ilike(f"%{search_term}%")
            )
        )
        .order_by(Location.usage_count.desc(), Location.city)
        .limit(limit)
    )
    
    result = await db.execute(query)
    locations = result.scalars().all()
    
    return [
        AutocompleteResult(
            id=loc.id,
            display_name=loc.display_name,
            city=loc.city,
            state=loc.state,
            locality=loc.locality
        )
        for loc in locations
    ]


@router.get("/states", response_model=List[str])
async def get_states(
    db: AsyncSession = Depends(get_db)
):
    """Get list of all unique states with active locations."""
    query = (
        select(Location.state)
        .where(Location.is_active == True)
        .distinct()
        .order_by(Location.state)
    )
    result = await db.execute(query)
    states = result.scalars().all()
    return states


@router.get("/cities", response_model=List[str])
async def get_cities(
    state: str = Query(..., description="State to filter cities"),
    db: AsyncSession = Depends(get_db)
):
    """Get list of cities for a given state."""
    query = (
        select(Location.city)
        .where(
            Location.is_active == True,
            func.lower(Location.state) == state.lower().strip()
        )
        .distinct()
        .order_by(Location.city)
    )
    result = await db.execute(query)
    cities = result.scalars().all()
    return cities


@router.get("/localities", response_model=List[AutocompleteResult])
async def get_localities(
    state: str = Query(..., description="State"),
    city: str = Query(..., description="City"),
    db: AsyncSession = Depends(get_db)
):
    """Get localities for a given state and city. Only returns locations with specific localities."""
    query = (
        select(Location)
        .where(
            Location.is_active == True,
            func.lower(Location.state) == state.lower().strip(),
            Location.city_normalized == city.lower().strip(),
            Location.locality.isnot(None),
            Location.locality != ''
        )
        .order_by(Location.locality)
    )
    result = await db.execute(query)
    locations = result.scalars().all()
    
    return [
        AutocompleteResult(
            id=loc.id,
            display_name=loc.display_name,
            city=loc.city,
            state=loc.state,
            locality=loc.locality
        )
        for loc in locations
    ]


@router.get("/", response_model=List[LocationResponse])
async def list_locations(
    city: Optional[str] = None,
    state: Optional[str] = None,
    active_only: bool = True,
    db: AsyncSession = Depends(get_db)
):
    """List all locations, optionally filtered by city or state."""
    query = select(Location).order_by(Location.state, Location.city, Location.locality)
    
    if active_only:
        query = query.where(Location.is_active == True)
    
    if city:
        query = query.where(Location.city_normalized == city.lower().strip())
    
    if state:
        query = query.where(func.lower(Location.state) == state.lower().strip())
    
    result = await db.execute(query)
    locations = result.scalars().all()
    
    return [
        LocationResponse(
            id=loc.id,
            country=loc.country,
            state=loc.state,
            city=loc.city,
            locality=loc.locality,
            display_name=loc.display_name,
            latitude=loc.latitude,
            longitude=loc.longitude,
            usage_count=loc.usage_count,
            is_active=loc.is_active
        )
        for loc in locations
    ]


@router.get("/{location_id}", response_model=LocationResponse)
async def get_location(
    location_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Get a specific location by ID."""
    result = await db.execute(
        select(Location).where(Location.id == location_id)
    )
    location = result.scalars().first()
    
    if not location:
        raise HTTPException(status_code=404, detail="Location not found")
    
    return LocationResponse(
        id=location.id,
        country=location.country,
        state=location.state,
        city=location.city,
        locality=location.locality,
        display_name=location.display_name,
        latitude=location.latitude,
        longitude=location.longitude,
        usage_count=location.usage_count,
        is_active=location.is_active
    )


# ============================================================
# SUPER ADMIN ENDPOINTS
# ============================================================

@router.post("/", response_model=LocationResponse)
async def create_location(
    location: LocationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new location. Super Admin only."""
    if current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Super Admin can create locations"
        )
    
    # Check for duplicate
    existing = await db.execute(
        select(Location).where(
            Location.city_normalized == location.city.lower().strip(),
            Location.locality_normalized == (location.locality.lower().strip() if location.locality else None)
        )
    )
    if existing.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Location '{location.city}' with locality '{location.locality}' already exists"
        )
    
    new_location = Location(
        country=location.country,
        state=location.state,
        city=location.city,
        locality=location.locality,
        city_normalized=Location.normalize(location.city),
        locality_normalized=Location.normalize(location.locality) if location.locality else None,
        search_text=Location.create_search_text(location.city, location.state, location.locality),
        latitude=location.latitude,
        longitude=location.longitude,
        is_active=True,
        usage_count=0
    )
    
    db.add(new_location)
    await db.commit()
    await db.refresh(new_location)
    
    return LocationResponse(
        id=new_location.id,
        country=new_location.country,
        state=new_location.state,
        city=new_location.city,
        locality=new_location.locality,
        display_name=new_location.display_name,
        latitude=new_location.latitude,
        longitude=new_location.longitude,
        usage_count=new_location.usage_count,
        is_active=new_location.is_active
    )


@router.put("/{location_id}/increment-usage")
async def increment_usage(
    location_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Increment usage count when a location is selected. Called by frontend."""
    result = await db.execute(
        select(Location).where(Location.id == location_id)
    )
    location = result.scalars().first()
    
    if not location:
        raise HTTPException(status_code=404, detail="Location not found")
    
    location.usage_count = (location.usage_count or 0) + 1
    await db.commit()
    
    return {"message": "Usage count incremented", "count": location.usage_count}


class LocationUpdate(BaseModel):
    state: Optional[str] = None
    city: Optional[str] = None
    locality: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    is_active: Optional[bool] = None


@router.put("/{location_id}", response_model=LocationResponse)
async def update_location(
    location_id: str,
    updates: LocationUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update a location. Super Admin only."""
    if current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Super Admin can update locations"
        )
    
    result = await db.execute(
        select(Location).where(Location.id == location_id)
    )
    location = result.scalars().first()
    
    if not location:
        raise HTTPException(status_code=404, detail="Location not found")
    
    update_data = updates.model_dump(exclude_unset=True)
    
    for key, value in update_data.items():
        setattr(location, key, value)
    
    # Recalculate normalized fields if city or locality changed
    if 'city' in update_data or 'locality' in update_data:
        location.city_normalized = Location.normalize(location.city)
        location.locality_normalized = Location.normalize(location.locality) if location.locality else None
        location.search_text = Location.create_search_text(location.city, location.state, location.locality)
    
    await db.commit()
    await db.refresh(location)
    
    return LocationResponse(
        id=location.id,
        country=location.country,
        state=location.state,
        city=location.city,
        locality=location.locality,
        display_name=location.display_name,
        latitude=location.latitude,
        longitude=location.longitude,
        usage_count=location.usage_count,
        is_active=location.is_active
    )


@router.delete("/{location_id}")
async def delete_location(
    location_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete a location (soft delete - sets is_active to False). Super Admin only."""
    if current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Super Admin can delete locations"
        )
    
    result = await db.execute(
        select(Location).where(Location.id == location_id)
    )
    location = result.scalars().first()
    
    if not location:
        raise HTTPException(status_code=404, detail="Location not found")
    
    # Soft delete
    location.is_active = False
    await db.commit()
    
    return {"message": f"Location '{location.display_name}' has been deactivated"}

