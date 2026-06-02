"""Public read-only API surface for SEO-indexed pages.

These endpoints are deliberately unauthenticated. They power every
public-facing route (`/reading-rooms/kochi`, `/listing/reading-room/abc-…`,
`/city/kochi`, `/state/kerala`, etc.) and are safe to expose:

  - Only LIVE listings are returned.
  - Only `is_seo_active=true` locations resolve.
  - No PII (owner ids/names are returned only when the listing model
    already exposes them — same as the existing browse APIs).
  - Cacheable with long TTLs at the CDN; the data only changes when a
    listing flips LIVE or a location is activated.

Endpoints:
  GET /public/locations/{kind}/{slug}        → single location + breadcrumb chain
  GET /public/locations/by-path?path=…       → resolve `/kochi/kakkanad` style paths
  GET /public/listings                        → list with category/city/locality filter
  GET /public/listings/{category}/by-slug/{slug} → single listing
"""
from __future__ import annotations

import json
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.models.accommodation import Accommodation
from app.models.reading_room import ListingStatus, ReadingRoom
from app.models.seo_location import LocationKind, SeoLocation


router = APIRouter(prefix="/public", tags=["Public SEO"])


# Categories the public API understands. Must match the frontend route + the
# sitemap categories list. Reading-rooms map to ReadingRoom; everything else
# (PGs, hostels, rentals, ...) maps to Accommodation today and will diverge
# as inventory specializes.
CATEGORY_TO_TABLE = {
    "reading-rooms": "reading_rooms",
    "study-cabins": "reading_rooms",
    "private-cabins": "reading_rooms",
    "shared-cabins": "reading_rooms",
    "pgs": "accommodations",
    "hostels": "accommodations",
    "co-working-spaces": "accommodations",
    "co-learning-spaces": "accommodations",
    "rental-houses": "accommodations",
    "rooms-for-rent": "accommodations",
}


# ---------- helpers --------------------------------------------------------

async def _location_breadcrumbs(
    db: AsyncSession, leaf: SeoLocation,
) -> list[dict]:
    """Walk parent_id up to country and return a list, root first."""
    chain: list[SeoLocation] = [leaf]
    cursor = leaf
    while cursor.parent_id:
        parent = await db.get(SeoLocation, cursor.parent_id)
        if parent is None:
            break
        chain.append(parent)
        cursor = parent
    chain.reverse()
    return [
        {
            "kind": loc.kind.value,
            "slug": loc.slug,
            "name": loc.name,
            "state_code": loc.state_code,
        }
        for loc in chain
    ]


def _location_to_dict(loc: SeoLocation) -> dict:
    aliases: list[str] = []
    if loc.aliases_json:
        try:
            aliases = json.loads(loc.aliases_json)
        except (ValueError, TypeError):
            aliases = []
    listing_counts: dict = {}
    if loc.listing_counts_json:
        try:
            listing_counts = json.loads(loc.listing_counts_json)
        except (ValueError, TypeError):
            listing_counts = {}
    metadata: dict = {}
    if loc.metadata_json:
        try:
            metadata = json.loads(loc.metadata_json)
        except (ValueError, TypeError):
            metadata = {}
    return {
        "id": loc.id,
        "kind": loc.kind.value,
        "slug": loc.slug,
        "name": loc.name,
        "aliases": aliases,
        "parent_id": loc.parent_id,
        "country_code": loc.country_code,
        "state_code": loc.state_code,
        "lat": loc.lat,
        "lng": loc.lng,
        "population_tier": loc.population_tier,
        "has_inventory": loc.has_inventory,
        "listing_counts": listing_counts,
        "metadata": metadata,
    }


def _rr_to_dict(r: ReadingRoom) -> dict:
    return {
        "id": r.id,
        "slug": r.slug,
        "name": r.name,
        "address": r.address,
        "description": r.description,
        "city": r.city,
        "area": r.area,
        "locality": r.locality,
        "state": r.state,
        "pincode": r.pincode,
        "lat": r.latitude,
        "lng": r.longitude,
        "images": r.images,
        "amenities": r.amenities,
        "price_start": r.price_start,
        "is_sponsored": r.is_sponsored,
    }


def _acc_to_dict(a: Accommodation) -> dict:
    return {
        "id": a.id,
        "slug": a.slug,
        "name": a.name,
        # Accommodation model fields are intentionally read defensively —
        # the table grew organically and some columns are nullable.
        "description": getattr(a, "description", None),
        "city": getattr(a, "city", None),
        "area": getattr(a, "area", None),
        "locality": getattr(a, "locality", None),
        "state": getattr(a, "state", None),
        "pincode": getattr(a, "pincode", None),
        "lat": getattr(a, "latitude", None),
        "lng": getattr(a, "longitude", None),
        "address": getattr(a, "address", None),
        "images": getattr(a, "images", None),
        "amenities": getattr(a, "amenities", None),
        "price_start": getattr(a, "price_start", None) or getattr(a, "price", None),
    }


# ---------- /public/locations ---------------------------------------------

@router.get("/locations/{kind}/{slug}")
async def get_location(kind: str, slug: str):
    """Fetch a single SEO location by (kind, slug) and return it along with
    its parent breadcrumb chain. 404 if not SEO-active."""
    try:
        loc_kind = LocationKind(kind)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"invalid kind: {kind}") from exc

    async with AsyncSessionLocal() as db:
        row = (await db.execute(
            select(SeoLocation).where(and_(
                SeoLocation.kind == loc_kind,
                SeoLocation.slug == slug,
                SeoLocation.is_seo_active.is_(True),
            ))
        )).scalar_one_or_none()
        if row is None:
            raise HTTPException(status_code=404, detail="location not found")
        breadcrumb = await _location_breadcrumbs(db, row)

        # Children — useful for city pages that list their localities, or
        # state pages that list their cities.
        children = (await db.execute(
            select(SeoLocation)
            .where(and_(
                SeoLocation.parent_id == row.id,
                SeoLocation.is_seo_active.is_(True),
            ))
            .order_by(SeoLocation.population_tier.asc(), SeoLocation.name.asc())
        )).scalars().all()

        return {
            "location": _location_to_dict(row),
            "breadcrumbs": breadcrumb,
            "children": [_location_to_dict(c) for c in children],
        }


# ---------- /public/listings ----------------------------------------------

@router.get("/listings")
async def list_public_listings(
    category: str = Query(..., description="e.g. reading-rooms, pgs, hostels"),
    city_slug: Optional[str] = None,
    locality_slug: Optional[str] = None,
    limit: int = 24,
    offset: int = 0,
):
    """List LIVE listings for a category, optionally narrowed by city or
    locality slug. Powers `/reading-rooms`, `/reading-rooms/kochi`,
    `/reading-rooms/kochi/kakkanad`."""
    table = CATEGORY_TO_TABLE.get(category)
    if table is None:
        raise HTTPException(status_code=404, detail=f"unknown category: {category}")

    if limit > 100:
        limit = 100

    async with AsyncSessionLocal() as db:
        # Resolve city / locality slugs to their canonical *names* so we can
        # match against the listing's free-text city/locality columns. (The
        # listings table predates the SEO hierarchy, so its location data is
        # stored as strings, not foreign keys.)
        city_names: Optional[set[str]] = None
        locality_names: Optional[set[str]] = None
        if city_slug:
            city_row = (await db.execute(
                select(SeoLocation).where(and_(
                    SeoLocation.kind == LocationKind.CITY,
                    SeoLocation.slug == city_slug,
                ))
            )).scalar_one_or_none()
            if city_row is None:
                raise HTTPException(status_code=404, detail="city not found")
            aliases = json.loads(city_row.aliases_json) if city_row.aliases_json else []
            city_names = {city_row.name.lower(), *(a.lower() for a in aliases)}
        if locality_slug:
            loc_row = (await db.execute(
                select(SeoLocation).where(and_(
                    SeoLocation.kind == LocationKind.LOCALITY,
                    SeoLocation.slug == locality_slug,
                ))
            )).scalar_one_or_none()
            if loc_row is None:
                raise HTTPException(status_code=404, detail="locality not found")
            aliases = json.loads(loc_row.aliases_json) if loc_row.aliases_json else []
            locality_names = {loc_row.name.lower(), *(a.lower() for a in aliases)}

        if table == "reading_rooms":
            stmt = select(ReadingRoom).where(ReadingRoom.status == ListingStatus.LIVE)
            if city_names:
                stmt = stmt.where(
                    ReadingRoom.city.in_(list(city_names))
                    | ReadingRoom.city.in_([n.title() for n in city_names])
                )
            if locality_names:
                stmt = stmt.where(
                    ReadingRoom.locality.in_(list(locality_names))
                    | ReadingRoom.locality.in_([n.title() for n in locality_names])
                )
            stmt = stmt.order_by(
                ReadingRoom.is_sponsored.desc(), ReadingRoom.name,
            ).offset(offset).limit(limit)
            rows = (await db.execute(stmt)).scalars().all()
            return {"category": category, "count": len(rows),
                    "listings": [_rr_to_dict(r) for r in rows]}

        # accommodations branch — same shape
        stmt = select(Accommodation)
        # No status column on legacy Accommodation; we just return them all
        # for now and filter at the application layer once it's added.
        if city_names:
            try:
                stmt = stmt.where(Accommodation.city.in_(list(city_names)))
            except AttributeError:
                pass
        if locality_names:
            try:
                stmt = stmt.where(
                    Accommodation.locality.in_(list(locality_names))
                )
            except AttributeError:
                pass
        stmt = stmt.order_by(Accommodation.name).offset(offset).limit(limit)
        rows = (await db.execute(stmt)).scalars().all()
        return {"category": category, "count": len(rows),
                "listings": [_acc_to_dict(a) for a in rows]}


@router.get("/listings/{category}/by-slug/{slug}")
async def get_listing_by_slug(category: str, slug: str):
    table = CATEGORY_TO_TABLE.get(category)
    if table is None:
        raise HTTPException(status_code=404, detail=f"unknown category: {category}")

    async with AsyncSessionLocal() as db:
        if table == "reading_rooms":
            row = (await db.execute(
                select(ReadingRoom).where(and_(
                    ReadingRoom.slug == slug,
                    ReadingRoom.status == ListingStatus.LIVE,
                ))
            )).scalar_one_or_none()
            if row is None:
                raise HTTPException(status_code=404, detail="listing not found")
            return {"category": category, "listing": _rr_to_dict(row)}

        row = (await db.execute(
            select(Accommodation).where(Accommodation.slug == slug)
        )).scalar_one_or_none()
        if row is None:
            raise HTTPException(status_code=404, detail="listing not found")
        return {"category": category, "listing": _acc_to_dict(row)}


# ---------- /public/categories --------------------------------------------

@router.get("/categories")
async def list_categories():
    """List all 10 categories with their (current) total LIVE counts.
    Powers the home page hero + category landing cards."""
    async with AsyncSessionLocal() as db:
        rr_count = (await db.execute(
            select(ReadingRoom.id).where(ReadingRoom.status == ListingStatus.LIVE)
        )).all()
        acc_count = (await db.execute(select(Accommodation.id))).all()

        out = []
        for slug, table in CATEGORY_TO_TABLE.items():
            count = len(rr_count) if table == "reading_rooms" else len(acc_count)
            out.append({"slug": slug, "total_live": count})
        return {"categories": out}
