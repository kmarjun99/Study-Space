from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func
from typing import List, Dict

from app.database import get_db
from app.models.reading_room import ReadingRoom, Cabin, CabinStatus
from app.models.accommodation import Accommodation
from app.models.booking import Booking
from app.models.city import CitySettings
from app.models.user import User
from app.schemas.city import CityStats, CityUpdate, CityDetail, AreaStats
from app.deps import get_current_admin

router = APIRouter(prefix="/admin/cities", tags=["admin-cities"])

@router.get("/", response_model=List[CityStats])
async def get_all_cities(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    # 1. Fetch Settings
    settings_result = await db.execute(select(CitySettings))
    settings_map = {s.city_name.lower(): s.is_active for s in settings_result.scalars().all()}

    # 2. Fetch Data
    rooms_result = await db.execute(select(ReadingRoom))
    rooms = rooms_result.scalars().all()

    acc_result = await db.execute(select(Accommodation))
    accommodations = acc_result.scalars().all()

    # Cabins need to be linked to rooms to know the city
    # We can fetch all cabins and map them, or just count them per room
    cabins_result = await db.execute(select(Cabin))
    cabins = cabins_result.scalars().all()
    
    # Map cabins to room_id
    cabins_by_room = {}
    for c in cabins:
        cabins_by_room[c.reading_room_id] = cabins_by_room.get(c.reading_room_id, 0) + 1

    # Bookings (active)
    # Simple count for now, filtering by end_date >= today ideally
    # For MVP, we'll just count all bookings as a proxy or fetch active
    # bookings_result = await db.execute(select(Booking).where(Booking.status == 'ACTIVE'))
    # bookings = bookings_result.scalars().all()
    
    # 3. Aggregate
    cities: Dict[str, dict] = {}

    def get_city_key(name: str):
        return name.strip().title() if name else "Unknown"

    for room in rooms:
        c_name = get_city_key(room.city)
        if c_name not in cities:
            cities[c_name] = {
                "name": c_name,
                "reading_rooms": 0,
                "accommodations": 0,
                "cabins": 0,
                "bookings": 0
            }
        cities[c_name]["reading_rooms"] += 1
        cities[c_name]["cabins"] += cabins_by_room.get(room.id, 0)

    for acc in accommodations:
        c_name = get_city_key(acc.city)
        if c_name not in cities:
            cities[c_name] = {
                "name": c_name,
                "reading_rooms": 0,
                "accommodations": 0,
                "cabins": 0,
                "bookings": 0
            }
        cities[c_name]["accommodations"] += 1

    # 4. Construct Response
    response = []
    for c_name, data in cities.items():
        is_active = settings_map.get(c_name.lower(), True) # Default Active
        
        total_venues = data["reading_rooms"] + data["accommodations"]
        total_cabins = data["cabins"]
        
        # Occupancy rate calculation (mock logic or real)
        # Real: (Active Bookings / Total Cabins) * 100
        # For now, 0
        occupancy = 0.0

        response.append(CityStats(
            name=c_name,
            is_active=is_active,
            total_venues=total_venues,
            total_cabins=total_cabins,
            total_accommodations=data["accommodations"],
            active_bookings=data["bookings"],
            occupancy_rate=occupancy
        ))

    return sorted(response, key=lambda x: x.name)

@router.put("/{city_name}/status", response_model=CityStats)
async def update_city_status(
    city_name: str,
    update: CityUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    # Upsert setting
    normalized_name = city_name.strip().title() # Key storage format? 
    # Actually Model uses `city_name` generic.
    # We should stick to exact string or normalized. 
    # Let's clean it up: Title Case for display, but lookup insensitive?
    # Ideally store as Title Case.
    
    result = await db.execute(select(CitySettings).where(CitySettings.city_name == normalized_name))
    setting = result.scalars().first()

    if not setting:
        setting = CitySettings(city_name=normalized_name, is_active=update.is_active)
        db.add(setting)
    else:
        setting.is_active = update.is_active
    
    await db.commit()
    await db.refresh(setting)

    # Return stats (reuse aggregation or minimal return?)
    # Schema expects CityStats. We must populate it.
    # We can just return the updated status with 0 stats if UI updates optimistically,
    # or re-fetch.
    # Let's re-fetch just for this city or construct dummy.
    # Construction is faster given we don't want to re-agg all.
    return CityStats(
        name=normalized_name,
        is_active=update.is_active,
        total_venues=0, # UI should preserve existing
        total_cabins=0,
        total_accommodations=0,
        active_bookings=0,
        occupancy_rate=0
    )

@router.get("/{city_name}", response_model=CityDetail)
async def get_city_details(
    city_name: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    target_city = city_name.strip().title()
    
    # Fetch Rooms and Accs for this city
    # In-memory filter again or DB filter
    # DB filter is better for Detail view
    
    rooms_res = await db.execute(select(ReadingRoom)) # Filter in python to match get_city_key logic exactly
    all_rooms = rooms_res.scalars().all()
    rooms = [r for r in all_rooms if (r.city or "").strip().title() == target_city]

    acc_res = await db.execute(select(Accommodation))
    all_acc = acc_res.scalars().all()
    accs = [a for a in all_acc if (a.city or "").strip().title() == target_city]

    # Aggregate Areas
    areas: Dict[str, AreaStats] = {}
    
    owners_set = set()

    for r in rooms:
        area_name = (r.area or "Unknown").strip()
        if area_name not in areas:
            areas[area_name] = AreaStats(name=area_name, venue_count=0, cabin_count=0)
        
        areas[area_name].venue_count += 1
        # Count cabins? Query for this room?
        # We need a join. Or separate query `select(Cabin).where(reading_room_id.in_([ids]))`
        owners_set.add(r.owner_id) # ID, resolve name later? Schema says str. ID is fine or name.

    for a in accs:
        area_name = (a.area or "Unknown").strip()
        if area_name not in areas:
            areas[area_name] = AreaStats(name=area_name, venue_count=0, cabin_count=0)
        areas[area_name].venue_count += 1
        owners_set.add(a.owner_id)

    # Fetch cabins for these rooms
    if rooms:
        room_ids = [r.id for r in rooms]
        cabins_res = await db.execute(select(Cabin).where(Cabin.reading_room_id.in_(room_ids)))
        cabins = cabins_res.scalars().all()
        
        # Map to area
        room_area_map = {r.id: (r.area or "Unknown").strip() for r in rooms}
        for c in cabins:
            aname = room_area_map.get(c.reading_room_id)
            if aname in areas:
                areas[aname].cabin_count += 1

    # Settings
    set_res = await db.execute(select(CitySettings).where(CitySettings.city_name == target_city))
    setting = set_res.scalars().first()
    is_active = setting.is_active if setting else True

    return CityDetail(
        name=target_city,
        is_active=is_active,
        total_venues=len(rooms) + len(accs),
        total_cabins=sum(a.cabin_count for a in areas.values()),
        total_accommodations=len(accs),
        active_bookings=0,
        occupancy_rate=0.0,
        areas=list(areas.values()),
        owners=list(owners_set)
    )
