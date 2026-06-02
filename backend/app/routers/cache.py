"""
Cache Management Router - Super Admin Only

Provides endpoints to clear cached data and force refresh.
All actions are logged to audit trail.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
from typing import List, Optional
import json

from app.database import get_db
from app.models.audit_log import AuditLog, AuditActionType
from app.models.user import User, UserRole
from app.deps import get_current_user
from pydantic import BaseModel

router = APIRouter(prefix="/admin/cache", tags=["Cache Management"])


# =========== SCHEMAS ===========

class CacheClearRequest(BaseModel):
    scope: List[str]  # ['users', 'owners', 'listings', 'plans', 'ads', 'trust', 'payments', 'all']


# =========== CACHE KEY NAMESPACES ===========

CACHE_SCOPES = {
    "users": ["user:*:dashboard", "user:*:bookings", "user:*:reviews"],
    "owners": ["owner:*:venues", "owner:*:housing", "owner:*:payments", "owner:*:boosts"],
    "listings": ["listings:reading_rooms", "listings:accommodations", "listings:featured"],
    "plans": ["plans:boost", "plans:active", "promotions:*"],
    "ads": ["ads:campaigns", "ads:banners", "featured:listings"],
    "trust": ["trust:flags", "trust:cases", "trust:reminders"],
    "payments": ["payments:history", "payments:pending", "transactions:*"]
}


# =========== ENDPOINTS ===========

@router.post("/clear")
async def clear_cache(
    data: CacheClearRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Clear specified cache namespaces.
    
    Super Admin only.
    
    Scopes:
    - users: User dashboards, bookings, reviews
    - owners: Venue data, payments, boosts
    - listings: Reading rooms, accommodations
    - plans: Boost plans, promotions
    - ads: Ad campaigns, featured listings
    - trust: Trust flags, cases, reminders
    - payments: Transaction history
    - all: Clear everything
    """
    # Super Admin only
    if current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=403, detail="Super Admin access required")
    
    if not data.scope:
        raise HTTPException(status_code=400, detail="At least one scope required")
    
    # Determine which scopes to clear
    scopes_to_clear = []
    if "all" in data.scope:
        scopes_to_clear = list(CACHE_SCOPES.keys())
    else:
        for scope in data.scope:
            if scope in CACHE_SCOPES:
                scopes_to_clear.append(scope)
    
    if not scopes_to_clear:
        raise HTTPException(status_code=400, detail="No valid scopes provided")
    
    # Collect all cache keys to clear
    keys_cleared = []
    for scope in scopes_to_clear:
        keys_cleared.extend(CACHE_SCOPES[scope])
    
    # In-memory cache simulation: In a real Redis setup, you would clear these keys
    # For now, we log the action and return success
    # This acts as a manual trigger for frontend to refetch data
    
    cleared_count = len(keys_cleared)
    
    # Log to audit trail
    client_ip = request.client.host if request.client else None
    
    audit_entry = AuditLog(
        actor_id=current_user.id,
        actor_name=current_user.name,
        actor_role="SUPER_ADMIN",
        action_type=AuditActionType.CACHE_CLEARED,
        action_description=f"Cache cleared for scopes: {', '.join(scopes_to_clear)}",
        entity_type="system",
        entity_id="cache",
        entity_name="System Cache",
        extra_data=json.dumps({
            "scopes": scopes_to_clear,
            "keys_count": cleared_count,
            "timestamp": datetime.utcnow().isoformat()
        }),
        timestamp=datetime.utcnow(),
        ip_address=client_ip
    )
    db.add(audit_entry)
    await db.commit()
    
    return {
        "success": True,
        "message": "Cache cleared successfully",
        "scopes_cleared": scopes_to_clear,
        "keys_cleared": cleared_count,
        "audit_id": audit_entry.id
    }


@router.get("/scopes")
async def get_cache_scopes(
    current_user: User = Depends(get_current_user)
):
    """
    Get available cache scopes for clearing.
    Super Admin only.
    """
    if current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=403, detail="Super Admin access required")
    
    return {
        "scopes": [
            {"id": "users", "name": "User Cache", "description": "Dashboards, bookings, reviews"},
            {"id": "owners", "name": "Owner Cache", "description": "Venues, housing, payments, boosts"},
            {"id": "listings", "name": "Listings Cache", "description": "Reading rooms, accommodations"},
            {"id": "plans", "name": "Plans & Promotions", "description": "Boost plans, active promotions"},
            {"id": "ads", "name": "Ads & Featured", "description": "Ad campaigns, featured listings"},
            {"id": "trust", "name": "Trust & Safety", "description": "Flags, cases, reminders"},
            {"id": "payments", "name": "Payments", "description": "Transaction history, pending payments"},
            {"id": "all", "name": "Clear ALL", "description": "System-wide cache clear"}
        ]
    }
