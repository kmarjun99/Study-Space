"""
Reading Room Duration Pricing Configuration Endpoint
Allows owners to configure flexible booking durations and set custom prices
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import Dict, List
from pydantic import BaseModel

from app.database import get_db
from app.models.reading_room import ReadingRoom
from app.models.user import User, UserRole
from app.deps import get_current_user
from app.services.booking_validator import booking_validator, BookingDurationType
import json

router = APIRouter(prefix="/reading-rooms", tags=["duration-pricing"])

class DurationPriceConfig(BaseModel):
    """Duration pricing configuration"""
    allowed_booking_durations: List[str]
    duration_prices: Dict[str, float]
    
    class Config:
        schema_extra = {
            "example": {
                "allowed_booking_durations": ["1_DAY", "1_WEEK", "1_MONTH", "3_MONTHS"],
                "duration_prices": {
                    "1_DAY": 150,
                    "1_WEEK": 900,
                    "1_MONTH": 3000,
                    "3_MONTHS": 8500,
                    "6_MONTHS": None  # Not offered
                }
            }
        }

class DurationPriceResponse(BaseModel):
    """Duration pricing response"""
    reading_room_id: str
    allowed_booking_durations: List[str]
    duration_prices: Dict[str, float]
    available_duration_types: List[str]

@router.get("/{room_id}/duration-config", response_model=DurationPriceResponse)
async def get_duration_config(
    room_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get current duration pricing configuration for a reading room"""
    
    result = await db.execute(select(ReadingRoom).where(ReadingRoom.id == room_id))
    room = result.scalars().first()
    if not room:
        raise HTTPException(status_code=404, detail="Reading room not found")
    
    # Only owner or admin can view detailed config
    if room.owner_id != current_user.id and current_user.role not in [UserRole.SUPER_ADMIN, UserRole.ADMIN]:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    allowed_durations = booking_validator.parse_allowed_durations(room.allowed_booking_durations)
    duration_prices = booking_validator.parse_duration_prices(room.duration_prices)
    
    return {
        "reading_room_id": room_id,
        "allowed_booking_durations": allowed_durations,
        "duration_prices": duration_prices,
        "available_duration_types": BookingDurationType.ALL
    }

@router.put("/{room_id}/duration-config", response_model=DurationPriceResponse)
async def update_duration_config(
    room_id: str,
    config: DurationPriceConfig,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update duration pricing configuration for a reading room.
    Owner can enable/disable duration types and set custom prices.
    """
    
    result = await db.execute(select(ReadingRoom).where(ReadingRoom.id == room_id))
    room = result.scalars().first()
    if not room:
        raise HTTPException(status_code=404, detail="Reading room not found")
    
    # Only owner can update
    if room.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only venue owner can update pricing")
    
    # Validate allowed durations
    for duration_type in config.allowed_booking_durations:
        if duration_type not in BookingDurationType.ALL:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid duration type: {duration_type}. Valid types: {BookingDurationType.ALL}"
            )
    
    # Validate that prices are set for all allowed durations
    for duration_type in config.allowed_booking_durations:
        price = config.duration_prices.get(duration_type)
        if price is None or price <= 0:
            raise HTTPException(
                status_code=400,
                detail=f"Price must be set and greater than 0 for enabled duration: {duration_type}"
            )
    
    # Validate all prices using booking validator
    validated_prices = booking_validator.validate_duration_prices_schema(config.duration_prices)
    
    # Update reading room
    room.allowed_booking_durations = json.dumps(config.allowed_booking_durations)
    room.duration_prices = json.dumps(validated_prices)
    
    await db.commit()
    await db.refresh(room)
    
    return {
        "reading_room_id": room_id,
        "allowed_booking_durations": config.allowed_booking_durations,
        "duration_prices": validated_prices,
        "available_duration_types": BookingDurationType.ALL
    }

# Include this router in main.py
# from app.routers import duration_pricing
# app.include_router(duration_pricing.router)
