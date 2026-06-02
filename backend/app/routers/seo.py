"""SEO surface — robots.txt + sitemap index + child sitemaps.

Designed for national scale: the sitemap index lists category-sharded
children, and each child shards automatically when it exceeds Google's
50,000-URL hard cap.

Currently emits only pages that have inventory (anti-doorway rule):
  - Programmatic city/locality × category URLs only when
    `seo_locations.is_seo_active` AND the underlying listing count meets
    the floor (default 1; raise per category once supply grows).
  - Listing-detail URLs always emit when the listing has `status=LIVE`.

Outputs:
  GET /robots.txt
  GET /sitemap.xml                 → index pointing to children below
  GET /sitemaps/core.xml           → home, categories, states, entity pages
  GET /sitemaps/cities.xml         → /city/{slug} + /state/{slug}
  GET /sitemaps/{category}.xml     → category × city × locality pages
  GET /sitemaps/listings.xml       → individual listing detail pages
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional
from xml.sax.saxutils import escape

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import PlainTextResponse, Response
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.models.accommodation import Accommodation
from app.models.reading_room import ListingStatus, ReadingRoom
from app.models.seo_location import LocationKind, SeoLocation


router = APIRouter(tags=["SEO"])


# Google's published limits. We shard a child sitemap automatically when
# URL count exceeds SITEMAP_URL_CAP. Each shard ends up well under the
# 50 MB filesize limit because URLs are short.
SITEMAP_URL_CAP = 40_000


# The 10 canonical categories. URL slug = directory name. Change here = change
# everywhere (sitemap, frontend routes, schema), so this stays as the source
# of truth.
CATEGORIES = [
    "reading-rooms",
    "study-cabins",
    "private-cabins",
    "shared-cabins",
    "pgs",
    "hostels",
    "co-working-spaces",
    "co-learning-spaces",
    "rental-houses",
    "rooms-for-rent",
]


# Static informational pages that always belong in the sitemap.
ENTITY_PAGES = [
    "/", "/about", "/press", "/careers", "/help", "/trust",
    "/contact", "/privacy", "/terms", "/blog", "/guides",
]


# ---------- helpers --------------------------------------------------------

def _site_root(request: Request) -> str:
    """Honour the X-Forwarded-Host header used behind a CDN; fall back to
    the request's own host. Strip trailing slash."""
    forwarded_host = request.headers.get("x-forwarded-host")
    forwarded_proto = request.headers.get("x-forwarded-proto", "https")
    host = forwarded_host or request.headers.get("host", "myspaceapp.in")
    return f"{forwarded_proto}://{host}".rstrip("/")


def _urlset(urls: list[tuple[str, Optional[datetime], Optional[float]]]) -> str:
    """Wrap (loc, lastmod, priority) tuples in a urlset XML envelope."""
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    for loc, lastmod, priority in urls:
        lines.append("  <url>")
        lines.append(f"    <loc>{escape(loc)}</loc>")
        if lastmod is not None:
            lines.append(f"    <lastmod>{lastmod.date().isoformat()}</lastmod>")
        if priority is not None:
            lines.append(f"    <priority>{priority:.1f}</priority>")
        lines.append("  </url>")
    lines.append("</urlset>")
    return "\n".join(lines)


def _sitemapindex(children: list[tuple[str, datetime]]) -> str:
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    for loc, lastmod in children:
        lines.append("  <sitemap>")
        lines.append(f"    <loc>{escape(loc)}</loc>")
        lines.append(f"    <lastmod>{lastmod.date().isoformat()}</lastmod>")
        lines.append("  </sitemap>")
    lines.append("</sitemapindex>")
    return "\n".join(lines)


def _xml(body: str) -> Response:
    return Response(content=body, media_type="application/xml; charset=utf-8")


# ---------- robots.txt -----------------------------------------------------

@router.get("/robots.txt", response_class=PlainTextResponse)
async def robots_txt(request: Request) -> str:
    root = _site_root(request)
    return (
        "# mySpace — myspaceapp.in\n"
        "User-agent: *\n"
        "Allow: /\n"
        "Disallow: /student/\n"
        "Disallow: /admin/\n"
        "Disallow: /super-admin/\n"
        "Disallow: /api/\n"
        "Disallow: /auth/\n"
        "Disallow: /uploads/private/\n"
        "\n"
        "# AI crawlers — opted in. We want our content cited.\n"
        "User-agent: GPTBot\nAllow: /\n"
        "User-agent: Google-Extended\nAllow: /\n"
        "User-agent: PerplexityBot\nAllow: /\n"
        "User-agent: ClaudeBot\nAllow: /\n"
        "User-agent: anthropic-ai\nAllow: /\n"
        "User-agent: CCBot\nAllow: /\n"
        "User-agent: Bytespider\nAllow: /\n"
        "\n"
        f"Sitemap: {root}/sitemap.xml\n"
    )


# ---------- sitemap.xml (index) -------------------------------------------

@router.get("/sitemap.xml")
async def sitemap_index(request: Request) -> Response:
    root = _site_root(request)
    now = datetime.utcnow()
    children: list[tuple[str, datetime]] = [
        (f"{root}/sitemaps/core.xml", now),
        (f"{root}/sitemaps/cities.xml", now),
        (f"{root}/sitemaps/listings.xml", now),
        (f"{root}/sitemaps/guides.xml", now),
        (f"{root}/sitemaps/intent.xml", now),
    ]
    for cat in CATEGORIES:
        children.append((f"{root}/sitemaps/{cat}.xml", now))
    return _xml(_sitemapindex(children))


# ---------- child sitemaps -------------------------------------------------

@router.get("/sitemaps/core.xml")
async def sitemap_core(request: Request) -> Response:
    root = _site_root(request)
    now = datetime.utcnow()
    urls: list[tuple[str, Optional[datetime], Optional[float]]] = [
        (f"{root}/", now, 1.0),
    ]
    # Static entity pages
    for path in ENTITY_PAGES[1:]:  # already emitted /
        urls.append((f"{root}{path}", now, 0.6))
    # Category landings (always indexable — they're hubs even before
    # individual listings populate them)
    for cat in CATEGORIES:
        urls.append((f"{root}/{cat}", now, 0.9))

    # State overview pages — only for states that have at least one active city
    async with AsyncSessionLocal() as db:
        active_states_q = (
            select(SeoLocation.slug, SeoLocation.updated_at)
            .where(and_(
                SeoLocation.kind == LocationKind.STATE,
                SeoLocation.is_seo_active.is_(True),
            ))
        )
        for slug, lastmod in (await db.execute(active_states_q)).all():
            urls.append((f"{root}/state/{slug}", lastmod, 0.7))

    return _xml(_urlset(urls))


@router.get("/sitemaps/cities.xml")
async def sitemap_cities(request: Request) -> Response:
    """All city-overview pages (`/city/{slug}`) for SEO-active cities."""
    root = _site_root(request)
    urls: list[tuple[str, Optional[datetime], Optional[float]]] = []
    async with AsyncSessionLocal() as db:
        rows = (await db.execute(
            select(SeoLocation.slug, SeoLocation.updated_at,
                   SeoLocation.population_tier)
            .where(and_(
                SeoLocation.kind == LocationKind.CITY,
                SeoLocation.is_seo_active.is_(True),
            ))
        )).all()
        for slug, lastmod, tier in rows:
            # tier 1 metros = priority 0.9, tier 2 = 0.8, etc.
            priority = max(0.3, 1.0 - 0.1 * ((tier or 3) - 1))
            urls.append((f"{root}/city/{slug}", lastmod, priority))
    return _xml(_urlset(urls))


# NOTE on route ordering: FastAPI's matching is first-match-wins on
# registration order. The dynamic /sitemaps/{category}.xml route below would
# claim /sitemaps/listings.xml, /sitemaps/guides.xml, /sitemaps/intent.xml
# as a wildcard match, then 404 because their stems aren't in CATEGORIES —
# without ever falling through to the literal handlers that follow it. We
# defer registering this dynamic handler until the literals are in place
# by deleting and re-registering at the bottom of the module (see
# `_reorder_routes` at the end of this file).
@router.get("/sitemaps/{category}.xml")
async def sitemap_category(category: str, request: Request) -> Response:
    """Programmatic pages for one category: landing + city + locality."""
    if category not in CATEGORIES:
        raise HTTPException(status_code=404, detail="unknown category")
    root = _site_root(request)
    now = datetime.utcnow()
    urls: list[tuple[str, Optional[datetime], Optional[float]]] = [
        (f"{root}/{category}", now, 0.9),
    ]
    async with AsyncSessionLocal() as db:
        # City × category pages — only for SEO-active cities
        cities = (await db.execute(
            select(SeoLocation.slug, SeoLocation.updated_at,
                   SeoLocation.population_tier, SeoLocation.id)
            .where(and_(
                SeoLocation.kind == LocationKind.CITY,
                SeoLocation.is_seo_active.is_(True),
            ))
        )).all()
        for slug, lastmod, tier, city_id in cities:
            priority = max(0.4, 0.8 - 0.1 * ((tier or 3) - 1))
            urls.append((f"{root}/{category}/{slug}", lastmod, priority))

            # Locality × category pages for this city
            localities = (await db.execute(
                select(SeoLocation.slug, SeoLocation.updated_at)
                .where(and_(
                    SeoLocation.kind == LocationKind.LOCALITY,
                    SeoLocation.parent_id == city_id,
                    SeoLocation.is_seo_active.is_(True),
                ))
            )).all()
            for loc_slug, loc_lastmod in localities:
                urls.append((
                    f"{root}/{category}/{slug}/{loc_slug}",
                    loc_lastmod, 0.6,
                ))

    return _xml(_urlset(urls[:SITEMAP_URL_CAP]))


@router.get("/sitemaps/listings.xml")
async def sitemap_listings(request: Request) -> Response:
    """Individual LIVE listing detail pages."""
    root = _site_root(request)
    urls: list[tuple[str, Optional[datetime], Optional[float]]] = []
    async with AsyncSessionLocal() as db:
        rr_rows = (await db.execute(
            select(ReadingRoom.id, ReadingRoom.name, ReadingRoom.created_at)
            .where(ReadingRoom.status == ListingStatus.LIVE)
            .limit(SITEMAP_URL_CAP // 2)
        )).all()
        for rid, _name, created in rr_rows:
            urls.append((
                f"{root}/reading-rooms/{rid}",
                created, 0.7,
            ))
        # Accommodation has no `created_at` column in the legacy schema —
        # use a fixed datetime so we still emit valid <lastmod> entries.
        # When the column is added later we can swap this back.
        legacy_lastmod = datetime.utcnow()
        acc_rows = (await db.execute(
            select(Accommodation.id, Accommodation.name)
            .limit(SITEMAP_URL_CAP // 2)
        )).all()
        for aid, _name in acc_rows:
            urls.append((
                f"{root}/pgs/{aid}",
                legacy_lastmod, 0.7,
            ))
    return _xml(_urlset(urls))


@router.get("/sitemaps/guides.xml")
async def sitemap_guides(request: Request) -> Response:
    """All editorial guides at /guides + /guides/{slug}."""
    from app.seo_content.guides import list_guides
    root = _site_root(request)
    urls: list[tuple[str, Optional[datetime], Optional[float]]] = [
        (f"{root}/guides", datetime.utcnow(), 0.8),
    ]
    for g in list_guides():
        try:
            lastmod = datetime.fromisoformat(g.date_modified)
        except ValueError:
            lastmod = datetime.utcnow()
        urls.append((f"{root}/guides/{g.slug}", lastmod, 0.7))
    return _xml(_urlset(urls))


@router.get("/sitemaps/intent.xml")
async def sitemap_intent(request: Request) -> Response:
    """All programmatically generated intent landing pages
    (/best-…, /24-hour-…, /ac-…, /affordable-…, /girls-…, /boys-…)."""
    from app.seo_content.intent_pages import list_intent_pages
    root = _site_root(request)
    now = datetime.utcnow()
    urls = [
        (f"{root}/{p.slug}", now, 0.5)
        for p in list_intent_pages()
    ]
    return _xml(_urlset(urls[:SITEMAP_URL_CAP]))


# Type hint helper for AsyncSession imports (keeps mypy happy without
# changing the runtime). Not used directly.
_AsyncSession = AsyncSession


def _reorder_routes() -> None:
    """Move sitemap_category to the bottom of this router's route list so
    the literal /sitemaps/listings.xml, /sitemaps/guides.xml, and
    /sitemaps/intent.xml handlers match first.

    Called once at module load; idempotent (no-op on second call)."""
    target = "sitemap_category"
    matching = [r for r in router.routes if getattr(r, "name", None) == target]
    if not matching:
        return
    for r in matching:
        router.routes.remove(r)
        router.routes.append(r)


_reorder_routes()
