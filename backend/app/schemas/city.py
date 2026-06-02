from pydantic import BaseModel
from typing import List, Optional

class CityStats(BaseModel):
    name: str
    is_active: bool
    total_venues: int
    total_cabins: int
    total_accommodations: int
    active_bookings: int # Placeholder for Phase 1
    occupancy_rate: float # Placeholder

class CityUpdate(BaseModel):
    is_active: bool

class AreaStats(BaseModel):
    name: str
    venue_count: int
    cabin_count: int

class CityDetail(CityStats):
    areas: List[AreaStats] = []
    owners: List[str] = [] # List of owner names/emails
