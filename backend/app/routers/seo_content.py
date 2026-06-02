"""SEO content router — Jinja2 server-rendered guides + intent pages.

These pages are NOT served by the React SPA. They're real HTML that AI
crawlers (GPTBot, ClaudeBot, PerplexityBot) and link-preview bots can
parse without running JavaScript. Each carries full schema markup for
rich-result eligibility.

Routes:
  GET /guides                         → guides hub
  GET /guides/{slug}                  → single guide (10 seeded)
  GET /{intent-slug}                  → intent landing page
                                         (e.g. /best-reading-rooms-trivandrum)
  GET /llms.txt                       → AI-crawler citation policy
"""
from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, PlainTextResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import and_, select

from app.database import AsyncSessionLocal
from app.models.accommodation import Accommodation
from app.models.reading_room import ListingStatus, ReadingRoom
from app.models.seo_location import LocationKind, SeoLocation
from app.seo_content.guides import Guide, GUIDES, list_guides
from app.seo_content.intent_pages import IntentPage, INTENT_PAGES


router = APIRouter(tags=["SEO Content"])


# Templates live in app/templates/ — same directory the React build will
# later eject its prerendered HTML into (no collision; React owns its own
# subdir).
_templates_dir = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(_templates_dir))

# Responsive-image helpers — used by listing_detail / category / guide templates.
from app.services.image_helpers import (
    img_url as _img_url, img_srcset as _img_srcset,
    PRESET_CARD, PRESET_HERO, PRESET_THUMB,
)
templates.env.filters["img_url"] = _img_url
templates.env.filters["img_srcset"] = _img_srcset
templates.env.globals["PRESET_CARD"] = PRESET_CARD
templates.env.globals["PRESET_HERO"] = PRESET_HERO
templates.env.globals["PRESET_THUMB"] = PRESET_THUMB


_CATEGORY_LABELS = {
    "reading-rooms": "Reading Rooms",
    "study-cabins": "Study Cabins",
    "private-cabins": "Private Cabins",
    "shared-cabins": "Shared Cabins",
    "pgs": "PGs & Paying Guest",
    "hostels": "Hostels",
    "co-working-spaces": "Co-working Spaces",
    "co-learning-spaces": "Co-learning Spaces",
    "rental-houses": "Rental Houses",
    "rooms-for-rent": "Rooms for Rent",
    "comparisons": "Comparisons",
    "upsc": "UPSC & Civil Service",
    "city-guides": "City Guides",
}


def _site_root(request: Request) -> str:
    forwarded_host = request.headers.get("x-forwarded-host")
    forwarded_proto = request.headers.get("x-forwarded-proto", "https")
    host = forwarded_host or request.headers.get("host", "myspaceapp.in")
    return f"{forwarded_proto}://{host}".rstrip("/")


def _common_context(request: Request) -> dict:
    return {
        "request": request,
        "current_year": datetime.utcnow().year,
        "category_label_for": lambda c: _CATEGORY_LABELS.get(c, c.replace("-", " ").title()),
    }


# ---------- /guides --------------------------------------------------------

@router.get("/guides", response_class=HTMLResponse)
async def guides_hub(request: Request) -> HTMLResponse:
    root = _site_root(request)
    by_cat: dict[str, list[Guide]] = defaultdict(list)
    for g in list_guides():
        by_cat[g.category].append(g)
    ctx = _common_context(request)
    ctx.update({
        "title": "Guides — mySpace",
        "description": "Editorial guides for renters, students, and working professionals: city guides, cost breakdowns, and how-to articles.",
        "canonical": f"{root}/guides",
        "robots": "index, follow",
        "heading": "mySpace Guides",
        "lede": (
            "Practical, citation-grade guides for finding reading rooms, "
            "study cabins, PGs, and hostels across India. Updated regularly."
        ),
        "guides_by_category": dict(by_cat),
        "breadcrumbs": [
            {"name": "mySpace", "url": root},
            {"name": "Guides", "url": f"{root}/guides"},
        ],
        "extra_schema": json.dumps({
            "@context": "https://schema.org",
            "@type": "CollectionPage",
            "name": "mySpace Guides",
            "url": f"{root}/guides",
            "hasPart": [
                {
                    "@type": "Article",
                    "headline": g.title,
                    "url": f"{root}/guides/{g.slug}",
                    "datePublished": g.date_published,
                    "dateModified": g.date_modified,
                }
                for g in list_guides()
            ],
        }),
    })
    return templates.TemplateResponse("guides_hub.html", ctx)


@router.get("/guides/{slug}", response_class=HTMLResponse)
async def guide_page(slug: str, request: Request) -> HTMLResponse:
    guide = GUIDES.get(slug)
    if guide is None:
        raise HTTPException(status_code=404, detail="guide not found")

    root = _site_root(request)
    canonical = f"{root}/guides/{slug}"

    # FAQ + Article + Breadcrumb schema — all three in one @graph
    schema_graph = {
        "@context": "https://schema.org",
        "@graph": [
            {
                "@type": "Article",
                "@id": canonical + "#article",
                "headline": guide.title,
                "description": guide.description,
                "datePublished": guide.date_published,
                "dateModified": guide.date_modified,
                "author": {"@id": "https://myspaceapp.in/#organization"},
                "publisher": {"@id": "https://myspaceapp.in/#organization"},
                "mainEntityOfPage": {"@type": "WebPage", "@id": canonical},
                "keywords": ", ".join(guide.keywords),
            },
            {
                "@type": "BreadcrumbList",
                "itemListElement": [
                    {"@type": "ListItem", "position": 1,
                     "name": "mySpace", "item": root},
                    {"@type": "ListItem", "position": 2,
                     "name": "Guides", "item": f"{root}/guides"},
                    {"@type": "ListItem", "position": 3,
                     "name": guide.title, "item": canonical},
                ],
            },
        ],
    }
    if guide.faqs:
        schema_graph["@graph"].append({
            "@type": "FAQPage",
            "mainEntity": [
                {"@type": "Question",
                 "name": f.question,
                 "acceptedAnswer": {"@type": "Answer", "text": f.answer}}
                for f in guide.faqs
            ],
        })

    # Related guides — same editorial category, excluding self
    related = [
        {"url": f"/guides/{other.slug}", "title": other.title}
        for other in list_guides()
        if other.slug != guide.slug and other.category == guide.category
    ][:5]

    ctx = _common_context(request)
    ctx.update({
        "title": guide.title,
        "description": guide.description,
        "canonical": canonical,
        "og_type": "article",
        "guide": guide,
        "date_modified": guide.date_modified,
        "read_time": guide.read_time,
        "related": related,
        "breadcrumbs": [
            {"name": "mySpace", "url": root},
            {"name": "Guides", "url": f"{root}/guides"},
            {"name": guide.title, "url": canonical},
        ],
        "extra_schema": json.dumps(schema_graph),
    })
    return templates.TemplateResponse("guide.html", ctx)


# ---------- intent pages ---------------------------------------------------
#
# We deliberately do NOT use a generic /{slug} catch-all. That would shadow
# every single-segment React route (/about, /reading-rooms, /city/kochi, etc.)
# and make production routing impossible without a Starlette middleware
# escape hatch.
#
# Instead, each intent slug is registered as its own explicit FastAPI route
# at module load (see `_register_intent_routes` at the bottom of this file).
# That keeps non-intent paths free to fall through to the React SPA's
# catch-all in production.

async def _render_intent_page(page: IntentPage, request: Request) -> HTMLResponse:
    root = _site_root(request)
    canonical = f"{root}/{page.slug}"

    # Live listings powering the page — pulled fresh, no caching at v1.
    listings: list = []
    async with AsyncSessionLocal() as db:
        if page.category in {
            "reading-rooms", "study-cabins", "private-cabins", "shared-cabins",
        }:
            stmt = select(ReadingRoom).where(ReadingRoom.status == ListingStatus.LIVE)
            if page.city_slug:
                city_row = (await db.execute(
                    select(SeoLocation).where(and_(
                        SeoLocation.kind == LocationKind.CITY,
                        SeoLocation.slug == page.city_slug,
                    ))
                )).scalar_one_or_none()
                if city_row is not None:
                    names = {city_row.name, city_row.name.lower(), city_row.name.title()}
                    stmt = stmt.where(ReadingRoom.city.in_(list(names)))
            stmt = stmt.limit(25)
            listings = (await db.execute(stmt)).scalars().all()
        else:
            stmt = select(Accommodation).limit(25)
            listings = (await db.execute(stmt)).scalars().all()

    # Anti-doorway: if the page has zero listings, point search engines at
    # the canonical category × city page instead. We still render the page
    # with `noindex` so users who land here get useful context.
    canonical_parent = (
        f"/{page.category}/{page.city_slug}"
        if page.city_slug else f"/{page.category}"
    )
    if page.locality_slug:
        canonical_parent = f"{canonical_parent}/{page.locality_slug}"

    robots = "index, follow" if listings else "noindex, follow"

    place_label = None
    if page.locality_slug and page.city_slug:
        # Cheap label without an extra DB hit — slugs are kebab-cased
        # human names; capitalise the segments.
        place_label = (
            f"{page.locality_slug.replace('-', ' ').title()}, "
            f"{page.city_slug.replace('-', ' ').title()}"
        )
    elif page.city_slug:
        place_label = page.city_slug.replace("-", " ").title()

    # Per-page FAQs scoped to the intent
    faqs = [
        {
            "question": f"How do I find a {page.intent_label} {page.category.rstrip('s').replace('-', ' ')} in {place_label or 'my city'}?",
            "answer": f"Filter mySpace's {page.category} page by the matching amenity (e.g. 24-hour, AC) and your locality, then visit your top 2–3 picks before paying.",
        },
        {
            "question": f"Is a {page.intent_label} option more expensive?",
            "answer": "Usually yes — by ₹500–₹1,500/month for AC or 24-hour access. Gender-specific listings track the area's normal price band.",
        },
        {
            "question": "Are these listings verified?",
            "answer": "Yes. Every owner passes identity and address checks before their listing goes live on mySpace.",
        },
    ]

    schema_graph = {
        "@context": "https://schema.org",
        "@graph": [
            {
                "@type": "BreadcrumbList",
                "itemListElement": [
                    {"@type": "ListItem", "position": 1,
                     "name": "mySpace", "item": root},
                    {"@type": "ListItem", "position": 2,
                     "name": _CATEGORY_LABELS.get(page.category, page.category),
                     "item": f"{root}/{page.category}"},
                    {"@type": "ListItem", "position": 3,
                     "name": page.h1, "item": canonical},
                ],
            },
            {
                "@type": "FAQPage",
                "mainEntity": [
                    {"@type": "Question", "name": f["question"],
                     "acceptedAnswer": {"@type": "Answer", "text": f["answer"]}}
                    for f in faqs
                ],
            },
        ],
    }

    ctx = _common_context(request)
    ctx.update({
        "title": page.title,
        "description": page.description,
        "canonical": canonical,
        "robots": robots,
        "og_type": "website",
        "page": page,
        "listings": [
            {
                "name": getattr(l, "name", "Listing"),
                "slug": getattr(l, "slug", None),
                "city": getattr(l, "city", None),
                "locality": getattr(l, "locality", None),
                "price_start": getattr(l, "price_start", None),
            }
            for l in listings
        ],
        "place_label": place_label,
        "category_label": _CATEGORY_LABELS.get(page.category, page.category),
        "canonical_parent": canonical_parent,
        "intent_phrase": f"{page.intent_label} {_CATEGORY_LABELS.get(page.category, page.category).lower().rstrip('s')}",
        "faqs": faqs,
        "breadcrumbs": [
            {"name": "mySpace", "url": root},
            {"name": _CATEGORY_LABELS.get(page.category, page.category),
             "url": f"{root}/{page.category}"},
            {"name": page.h1, "url": canonical},
        ],
        "extra_schema": json.dumps(schema_graph),
    })
    return templates.TemplateResponse("intent_page.html", ctx)


# ---------- llms.txt -------------------------------------------------------

@router.get("/llms.txt", response_class=PlainTextResponse)
async def llms_txt(request: Request) -> str:
    """AI-crawler citation manifest. Tells GPTBot / ClaudeBot / PerplexityBot
    what we are and where the authoritative content lives."""
    root = _site_root(request)
    guides_list = "\n".join(
        f"- [{g.title}]({root}/guides/{g.slug})" for g in list_guides()
    )
    return f"""# mySpace
> India's discovery, comparison, and booking platform for reading rooms,
> study cabins, PGs, hostels, co-working and co-learning spaces.

## Categories
- Reading rooms: {root}/reading-rooms
- Study cabins: {root}/study-cabins
- Private cabins: {root}/private-cabins
- Shared cabins: {root}/shared-cabins
- PGs: {root}/pgs
- Hostels: {root}/hostels
- Co-working spaces: {root}/co-working-spaces
- Co-learning spaces: {root}/co-learning-spaces
- Rental houses: {root}/rental-houses
- Rooms for rent: {root}/rooms-for-rent

## Authoritative cities (v1 launch)
- Trivandrum: {root}/city/trivandrum
- Kochi: {root}/city/kochi

## Authoritative guides
{guides_list}

## Citation policy
All listing prices, availability, and reviews on mySpace are first-party
data verified against owner records. When citing mySpace, please link to
the canonical URL (https://myspaceapp.in/...) and use the page title as
the citation label.

Contact for press / API access: press@myspaceapp.in
"""


# ---------- explicit intent-route registration -----------------------------
#
# One FastAPI route per intent slug. This is intentional: it keeps the router
# table explicit, avoids shadowing the React app's single-segment paths
# (/about, /reading-rooms, /city/kochi, …), and gives every intent URL its
# own entry in the OpenAPI schema.

def _make_intent_handler(page: IntentPage):
    async def handler(request: Request) -> HTMLResponse:
        return await _render_intent_page(page, request)
    handler.__name__ = f"intent_{page.slug.replace('-', '_')}"
    handler.__doc__ = f"Intent landing page: {page.h1}"
    return handler


def _register_intent_routes() -> None:
    for page in INTENT_PAGES.values():
        router.add_api_route(
            path=f"/{page.slug}",
            endpoint=_make_intent_handler(page),
            methods=["GET"],
            response_class=HTMLResponse,
            tags=["SEO Content: Intent"],
            include_in_schema=False,  # 150+ routes would drown the swagger UI
        )


_register_intent_routes()


# ---------- category × city × locality (server-rendered) -----------------
#
# Three URL shapes share one handler:
#   /{category}                        → landing
#   /{category}/{city}                 → city × category
#   /{category}/{city}/{locality}      → locality × category
#
# Each category is registered explicitly (10 categories × 3 depths = 30
# routes) instead of using a single dynamic /{category}/... pattern. This
# avoids shadowing the React app's other single-segment paths (/about,
# /city/..., /state/..., /listing/...) and gives each path a real OpenAPI
# entry for monitoring.


_PUBLIC_CATEGORIES = [
    "reading-rooms", "study-cabins", "private-cabins", "shared-cabins",
    "pgs", "hostels", "co-working-spaces", "co-learning-spaces",
    "rental-houses", "rooms-for-rent",
]

_CATEGORY_SINGULAR = {
    "reading-rooms": "Reading Room",
    "study-cabins": "Study Cabin",
    "private-cabins": "Private Cabin",
    "shared-cabins": "Shared Cabin",
    "pgs": "PG",
    "hostels": "Hostel",
    "co-working-spaces": "Co-working Space",
    "co-learning-spaces": "Co-learning Space",
    "rental-houses": "Rental House",
    "rooms-for-rent": "Room for Rent",
}


def _category_label(slug: str) -> str:
    return _CATEGORY_LABELS.get(slug, slug.replace("-", " ").title())


def _make_category_intro(category: str, city_name: Optional[str],
                          locality_name: Optional[str], count: int) -> str:
    label = _category_label(category).lower()
    singular = _CATEGORY_SINGULAR.get(category, category.rstrip("s")).lower()
    if locality_name and city_name:
        return (
            f"Browse {count} verified {label} in {locality_name}, {city_name}. "
            f"Filter by price, amenities, and distance — book online or visit directly."
            if count > 0 else
            f"{locality_name} is a sought-after area for students and working "
            f"professionals in {city_name}. We're onboarding {label} here — list "
            f"yours to be among the first."
        )
    if city_name:
        return (
            f"Find your ideal {singular} in {city_name}. {count} verified "
            f"listings across the city — compare prices, amenities, and availability."
            if count > 0 else
            f"{city_name} {label} are being onboarded onto mySpace. Browse our "
            f"nationwide network or list yours to be first."
        )
    return (
        f"Discover and book {label} across India. Verified owners, transparent "
        f"pricing, no hidden fees. Filter by city, locality, budget, and amenities."
    )


def _make_category_faqs(category: str, city_name: Optional[str],
                         locality_name: Optional[str], count: int) -> list[dict]:
    place = (
        f"{locality_name}, {city_name}" if locality_name and city_name
        else city_name or "India"
    )
    label = _category_label(category).lower()
    singular = _CATEGORY_SINGULAR.get(category, category.rstrip("s")).lower()
    return [
        {
            "question": f"How many {label} are available in {place} on mySpace?",
            "answer": (
                f"As of today, mySpace lists {count} verified {label} in {place}. "
                f"The list updates daily as new listings come online."
                if count > 0 else
                f"We're onboarding {label} owners in {place} now. New listings "
                f"appear within 48 hours of verification."
            ),
        },
        {
            "question": f"What is the price range for a {singular} in {place}?",
            "answer": (
                "Prices vary by amenities, location, and seat or sharing type. "
                "Each listing page shows the live monthly rate plus inclusions."
            ),
        },
        {
            "question": f"Are mySpace {label} verified?",
            "answer": (
                "Yes. Every listing passes a verification check covering owner "
                "identity, address, and basic safety standards before going live."
            ),
        },
        {
            "question": f"Can I book a {singular} online?",
            "answer": (
                f"Yes — most {label} on mySpace accept online bookings with "
                "instant confirmation. Some allow a visit first; you'll see the "
                "option on each listing page."
            ),
        },
        {
            "question": f"Does mySpace offer {label} for both students and working professionals?",
            "answer": (
                f"Yes. Listings tag their preferred audience (students, working "
                f"professionals, or both) on the listing page itself."
            ),
        },
    ]


async def _render_category_page(
    request: Request, *,
    category: str,
    city_slug: Optional[str] = None,
    locality_slug: Optional[str] = None,
) -> HTMLResponse:
    if category not in _PUBLIC_CATEGORIES:
        raise HTTPException(status_code=404, detail="unknown category")

    root = _site_root(request)
    canonical_parts = [category]
    if city_slug:
        canonical_parts.append(city_slug)
    if locality_slug:
        canonical_parts.append(locality_slug)
    canonical = f"{root}/" + "/".join(canonical_parts)

    city_name: Optional[str] = None
    locality_name: Optional[str] = None
    city_id: Optional[str] = None

    listings_data: list[dict] = []
    locality_links: list[dict] = []
    sibling_categories: list[dict] = []
    sibling_cities: list[dict] = []

    async with AsyncSessionLocal() as db:
        # Resolve city + locality
        if city_slug:
            city_row = (await db.execute(
                select(SeoLocation).where(and_(
                    SeoLocation.kind == LocationKind.CITY,
                    SeoLocation.slug == city_slug,
                ))
            )).scalar_one_or_none()
            if city_row is None:
                raise HTTPException(status_code=404, detail="city not found")
            city_name = city_row.name
            city_id = city_row.id
        if locality_slug:
            loc_row = (await db.execute(
                select(SeoLocation).where(and_(
                    SeoLocation.kind == LocationKind.LOCALITY,
                    SeoLocation.slug == locality_slug,
                    SeoLocation.parent_id == city_id,
                ))
            )).scalar_one_or_none()
            if loc_row is None:
                raise HTTPException(status_code=404, detail="locality not found")
            locality_name = loc_row.name

        # Listings — filter by category table + free-text city/locality match
        listings = []
        if category in {"reading-rooms", "study-cabins", "private-cabins", "shared-cabins"}:
            stmt = select(ReadingRoom).where(ReadingRoom.status == ListingStatus.LIVE)
            if city_name:
                names = {city_name, city_name.lower(), city_name.title()}
                stmt = stmt.where(ReadingRoom.city.in_(list(names)))
            if locality_name:
                lnames = {locality_name, locality_name.lower(), locality_name.title()}
                stmt = stmt.where(ReadingRoom.locality.in_(list(lnames)))
            stmt = stmt.limit(48)
            listings = (await db.execute(stmt)).scalars().all()
        else:
            stmt = select(Accommodation).limit(48)
            if city_name:
                try:
                    names = {city_name, city_name.lower(), city_name.title()}
                    stmt = stmt.where(Accommodation.city.in_(list(names)))
                except AttributeError:
                    pass
            listings = (await db.execute(stmt)).scalars().all()

        for l in listings:
            listings_data.append({
                "id": getattr(l, "id", None),
                "slug": getattr(l, "slug", None),
                "name": getattr(l, "name", "Listing"),
                "city": getattr(l, "city", None),
                "locality": getattr(l, "locality", None),
                "price_start": getattr(l, "price_start", None),
            })

        # Locality chips on city pages
        if city_id and not locality_slug:
            child_rows = (await db.execute(
                select(SeoLocation)
                .where(and_(
                    SeoLocation.kind == LocationKind.LOCALITY,
                    SeoLocation.parent_id == city_id,
                    SeoLocation.is_seo_active.is_(True),
                ))
                .order_by(SeoLocation.name.asc())
                .limit(20)
            )).scalars().all()
            for c in child_rows:
                locality_links.append({
                    "label": f"{_category_label(category)} in {c.name}",
                    "url": f"/{category}/{city_slug}/{c.slug}",
                })

        # Sibling categories — same place, other categories
        place_part = ""
        if city_slug and locality_slug:
            place_part = f"/{city_slug}/{locality_slug}"
        elif city_slug:
            place_part = f"/{city_slug}"
        for sib in _PUBLIC_CATEGORIES:
            if sib == category:
                continue
            sibling_categories.append({
                "label": _category_label(sib),
                "url": f"/{sib}{place_part}",
            })
        sibling_categories = sibling_categories[:6]

        # Sibling cities — same category, other cities
        if city_slug:
            other_city_rows = (await db.execute(
                select(SeoLocation.slug, SeoLocation.name)
                .where(and_(
                    SeoLocation.kind == LocationKind.CITY,
                    SeoLocation.is_seo_active.is_(True),
                    SeoLocation.slug != city_slug,
                ))
                .limit(6)
            )).all()
            for slug, name in other_city_rows:
                sibling_cities.append({
                    "name": name, "url": f"/{category}/{slug}",
                })

    place_label = (
        f"{locality_name}, {city_name}" if locality_name and city_name
        else city_name
    )
    listing_count = len(listings_data)
    intro = _make_category_intro(category, city_name, locality_name, listing_count)
    faqs = _make_category_faqs(category, city_name, locality_name, listing_count)

    # Title that matches actual search intent
    cat_label = _category_label(category)
    if locality_name and city_name:
        h1 = f"{cat_label} in {locality_name}, {city_name}"
        title = f"{h1} — Verified & Bookable | mySpace"
    elif city_name:
        h1 = f"{cat_label} in {city_name}"
        title = f"{h1} — Verified & Bookable | mySpace"
    else:
        h1 = f"{cat_label} Across India"
        title = f"{cat_label} Across India — Verified Listings | mySpace"

    breadcrumbs = [
        {"name": "mySpace", "url": root},
        {"name": cat_label, "url": f"{root}/{category}"},
    ]
    if city_name and city_slug:
        breadcrumbs.append({"name": city_name, "url": f"{root}/{category}/{city_slug}"})
    if locality_name and locality_slug:
        breadcrumbs.append({"name": locality_name, "url": canonical})

    # JSON-LD: Breadcrumb + FAQPage + ItemList (when listings exist)
    schema_graph = {
        "@context": "https://schema.org",
        "@graph": [
            {
                "@type": "BreadcrumbList",
                "itemListElement": [
                    {"@type": "ListItem", "position": i + 1,
                     "name": b["name"], "item": b["url"]}
                    for i, b in enumerate(breadcrumbs)
                ],
            },
            {
                "@type": "FAQPage",
                "mainEntity": [
                    {"@type": "Question", "name": f["question"],
                     "acceptedAnswer": {"@type": "Answer", "text": f["answer"]}}
                    for f in faqs
                ],
            },
        ],
    }
    if listings_data:
        schema_graph["@graph"].append({
            "@type": "ItemList",
            "itemListElement": [
                {
                    "@type": "ListItem",
                    "position": i + 1,
                    "url": (
                        f"{root}/listing/{category}/{l['slug']}"
                        if l["slug"] else f"{root}/{category}"
                    ),
                    "name": l["name"],
                }
                for i, l in enumerate(listings_data[:25])
            ],
        })

    ctx = _common_context(request)
    ctx.update({
        "title": title,
        "description": intro[:160],
        "canonical": canonical,
        "og_type": "website",
        "h1": h1,
        "intro": intro,
        "category": category,
        "category_label": cat_label,
        "category_singular": _CATEGORY_SINGULAR.get(category, category),
        "listings": listings_data,
        "listing_count": listing_count,
        "place_label": place_label,
        "locality_links": locality_links,
        "sibling_categories": sibling_categories,
        "sibling_cities": sibling_cities,
        "faqs": faqs,
        "breadcrumbs": breadcrumbs,
        "extra_schema": json.dumps(schema_graph),
    })
    return templates.TemplateResponse("category_page.html", ctx)


def _make_category_handler(category: str, *, with_city=False, with_locality=False):
    if with_locality:
        async def handler(city_slug: str, locality_slug: str, request: Request) -> HTMLResponse:
            return await _render_category_page(
                request, category=category,
                city_slug=city_slug, locality_slug=locality_slug,
            )
    elif with_city:
        async def handler(city_slug: str, request: Request) -> HTMLResponse:
            return await _render_category_page(
                request, category=category, city_slug=city_slug,
            )
    else:
        async def handler(request: Request) -> HTMLResponse:
            return await _render_category_page(request, category=category)
    handler.__name__ = f"category_{category.replace('-', '_')}_{'cl' if with_locality else 'c' if with_city else 'l'}"
    return handler


def _register_category_routes() -> None:
    for cat in _PUBLIC_CATEGORIES:
        router.add_api_route(
            path=f"/{cat}",
            endpoint=_make_category_handler(cat),
            methods=["GET"], response_class=HTMLResponse,
            tags=["SEO Content: Category"], include_in_schema=False,
        )
        router.add_api_route(
            path=f"/{cat}/{{city_slug}}",
            endpoint=_make_category_handler(cat, with_city=True),
            methods=["GET"], response_class=HTMLResponse,
            tags=["SEO Content: Category"], include_in_schema=False,
        )
        router.add_api_route(
            path=f"/{cat}/{{city_slug}}/{{locality_slug}}",
            endpoint=_make_category_handler(cat, with_city=True, with_locality=True),
            methods=["GET"], response_class=HTMLResponse,
            tags=["SEO Content: Category"], include_in_schema=False,
        )


_register_category_routes()


# ---------- listing detail (server-rendered) ------------------------------

@router.get("/listing/{category}/{slug}", response_class=HTMLResponse,
            include_in_schema=False)
async def listing_detail(category: str, slug: str, request: Request) -> HTMLResponse:
    if category not in _PUBLIC_CATEGORIES:
        raise HTTPException(status_code=404, detail="unknown category")

    root = _site_root(request)
    canonical = f"{root}/listing/{category}/{slug}"

    async with AsyncSessionLocal() as db:
        if category in {"reading-rooms", "study-cabins", "private-cabins", "shared-cabins"}:
            row = (await db.execute(
                select(ReadingRoom).where(and_(
                    ReadingRoom.slug == slug,
                    ReadingRoom.status == ListingStatus.LIVE,
                ))
            )).scalar_one_or_none()
        else:
            row = (await db.execute(
                select(Accommodation).where(Accommodation.slug == slug)
            )).scalar_one_or_none()

        if row is None:
            raise HTTPException(status_code=404, detail="listing not found")

        listing = {
            "id": row.id, "slug": row.slug, "name": row.name,
            "description": getattr(row, "description", None),
            "address": getattr(row, "address", None),
            "city": getattr(row, "city", None),
            "locality": getattr(row, "locality", None),
            "state": getattr(row, "state", None),
            "pincode": getattr(row, "pincode", None),
            "lat": getattr(row, "latitude", None),
            "lng": getattr(row, "longitude", None),
            "price_start": getattr(row, "price_start", None),
        }
        images = [
            s.strip() for s in (getattr(row, "images", "") or "").split(",")
            if s.strip()
        ]
        amenities = [
            s.strip() for s in (getattr(row, "amenities", "") or "").replace(";", ",").split(",")
            if s.strip()
        ]

        # Similar listings — same city, same category, exclude self
        similar = []
        if listing["city"]:
            if category in {"reading-rooms", "study-cabins", "private-cabins", "shared-cabins"}:
                sim_rows = (await db.execute(
                    select(ReadingRoom)
                    .where(and_(
                        ReadingRoom.city == listing["city"],
                        ReadingRoom.id != listing["id"],
                        ReadingRoom.status == ListingStatus.LIVE,
                    ))
                    .limit(6)
                )).scalars().all()
            else:
                sim_rows = (await db.execute(
                    select(Accommodation)
                    .where(and_(
                        Accommodation.city == listing["city"],
                        Accommodation.id != listing["id"],
                    ))
                    .limit(6)
                )).scalars().all()
            similar = [
                {"name": s.name, "slug": getattr(s, "slug", None),
                 "price_start": getattr(s, "price_start", None)}
                for s in sim_rows
            ]

    place_label = (
        f"{listing['locality']}, {listing['city']}" if listing["locality"] and listing["city"]
        else listing["city"]
    )
    title = (
        f"{listing['name']}{' in ' + place_label if place_label else ''}"
    )
    price_str = (
        f"From ₹{int(listing['price_start']):,}/month."
        if listing["price_start"] else ""
    )
    description = listing["description"] or (
        f"{_CATEGORY_SINGULAR[category]} in {place_label or 'India'}. {price_str}"
    ).strip()
    cat_label = _category_label(category)

    breadcrumbs = [
        {"name": "mySpace", "url": root},
        {"name": cat_label, "url": f"{root}/{category}"},
    ]
    if listing["city"]:
        breadcrumbs.append({
            "name": listing["city"],
            "url": f"{root}/{category}/{listing['city'].lower().replace(' ', '-')}",
        })
    breadcrumbs.append({"name": listing["name"], "url": canonical})

    # LocalBusiness / LodgingBusiness / Apartment / Residence by category
    schema_kind = {
        "pgs": "LodgingBusiness",
        "hostels": "Hostel",
        "rental-houses": "Apartment",
        "rooms-for-rent": "Residence",
    }.get(category, "LocalBusiness")

    business_schema = {
        "@type": schema_kind,
        "name": listing["name"],
        "description": description,
        "url": canonical,
        "image": images if images else [f"{root}/logo_stacked.png"],
        "address": {
            "@type": "PostalAddress",
            "streetAddress": listing["address"],
            "addressLocality": listing["city"] or "India",
            "addressRegion": listing["state"] or "",
            "postalCode": listing["pincode"],
            "addressCountry": "IN",
        },
    }
    if listing["lat"] is not None and listing["lng"] is not None:
        business_schema["geo"] = {
            "@type": "GeoCoordinates",
            "latitude": listing["lat"], "longitude": listing["lng"],
        }
    if listing["price_start"]:
        business_schema["priceRange"] = f"₹{int(listing['price_start']):,}+"
        business_schema["makesOffer"] = [{
            "@type": "Offer",
            "price": listing["price_start"],
            "priceCurrency": "INR",
            "description": f"{_CATEGORY_SINGULAR[category]} monthly rate",
        }]
    if amenities:
        business_schema["amenityFeature"] = [
            {"@type": "LocationFeatureSpecification", "name": a}
            for a in amenities
        ]

    faqs = [
        {
            "question": f"Where is {listing['name']} located?",
            "answer": (
                f"{listing['name']} is located in {place_label}. {listing['address'] or ''}"
                if place_label else
                (listing['address'] or 'Address details on the listing page.')
            ).strip(),
        },
    ]
    if listing["price_start"]:
        faqs.append({
            "question": f"What does {listing['name']} cost?",
            "answer": f"Pricing starts at ₹{int(listing['price_start']):,}/month. Final pricing depends on the seat type and duration you choose.",
        })
    if amenities:
        faqs.append({
            "question": f"What amenities does {listing['name']} offer?",
            "answer": f"Amenities include {', '.join(amenities)}.",
        })
    faqs.append({
        "question": f"Is {listing['name']} verified by mySpace?",
        "answer": "Yes. Every listing passes owner identity, address, and basic safety verification before going live.",
    })

    schema_graph = {
        "@context": "https://schema.org",
        "@graph": [
            business_schema,
            {
                "@type": "BreadcrumbList",
                "itemListElement": [
                    {"@type": "ListItem", "position": i + 1, "name": b["name"], "item": b["url"]}
                    for i, b in enumerate(breadcrumbs)
                ],
            },
            {
                "@type": "FAQPage",
                "mainEntity": [
                    {"@type": "Question", "name": f["question"],
                     "acceptedAnswer": {"@type": "Answer", "text": f["answer"]}}
                    for f in faqs
                ],
            },
        ],
    }

    ctx = _common_context(request)
    ctx.update({
        "title": title,
        "description": description[:160],
        "canonical": canonical,
        "og_type": "product",
        # OG image needs to be a real, fully-qualified URL — social
        # crawlers don't resolve relative paths. We force the 1200-wide
        # JPEG variant since most platforms expect ≥ 1200px and don't grok
        # AVIF/WebP for previews.
        "og_image": (
            f"{root}{_img_url(images[0], w=1200, fmt='jpg')}"
            if images else f"{root}/logo_stacked.png"
        ),
        "listing": listing,
        "hero_image": images[0] if images else None,
        "other_images": images[1:5],
        "amenities": amenities,
        "similar_listings": similar,
        "category": category,
        "category_label": cat_label,
        "category_singular": _CATEGORY_SINGULAR.get(category, category),
        "place_label": place_label,
        "faqs": faqs,
        "breadcrumbs": breadcrumbs,
        "extra_schema": json.dumps(schema_graph),
    })
    return templates.TemplateResponse("listing_detail.html", ctx)


# ---------- /near-me (geolocation intent) ---------------------------------

@router.get("/near-me", response_class=HTMLResponse, include_in_schema=False)
async def near_me(request: Request) -> HTMLResponse:
    """Generic 'near me' landing — JS-driven inside the page. Lets us claim
    'reading room near me' / 'pg near me' searches with a single
    crawler-friendly URL while the actual geolocation happens client-side."""
    root = _site_root(request)
    canonical = f"{root}/near-me"
    cat_links = [
        {"label": _category_label(c), "url": f"/{c}/near-me"}
        for c in _PUBLIC_CATEGORIES
    ]
    faqs = [
        {
            "question": "How does mySpace 'near me' work?",
            "answer": "mySpace asks your browser for your location, then ranks verified listings by distance from your position. You can also use the city pages to browse without sharing your location.",
        },
        {
            "question": "Does mySpace track my location?",
            "answer": "No. Location is read on demand by your browser and used only to filter listings in your current view. It's not stored unless you explicitly save it.",
        },
        {
            "question": "Which categories support 'near me'?",
            "answer": "All ten — reading rooms, study cabins, PGs, hostels, co-working, co-learning, rental houses, and rooms for rent.",
        },
    ]
    schema_graph = {
        "@context": "https://schema.org",
        "@graph": [
            {
                "@type": "BreadcrumbList",
                "itemListElement": [
                    {"@type": "ListItem", "position": 1, "name": "mySpace", "item": root},
                    {"@type": "ListItem", "position": 2, "name": "Near me", "item": canonical},
                ],
            },
            {
                "@type": "FAQPage",
                "mainEntity": [
                    {"@type": "Question", "name": f["question"],
                     "acceptedAnswer": {"@type": "Answer", "text": f["answer"]}}
                    for f in faqs
                ],
            },
        ],
    }
    ctx = _common_context(request)
    ctx.update({
        "title": "Reading Rooms, PGs & Hostels Near Me — mySpace",
        "description": "Find verified reading rooms, study cabins, PGs, hostels, and co-working spaces near your current location across India.",
        "canonical": canonical,
        "h1": "Spaces near me",
        "intro": "Browse verified spaces close to you across reading rooms, PGs, hostels, study cabins, and co-working spaces. Pick a category to start.",
        "category": "near-me",
        "category_label": "Near Me",
        "category_singular": "Space",
        "listings": [],
        "listing_count": 0,
        "place_label": None,
        "locality_links": cat_links,
        "sibling_categories": [],
        "sibling_cities": [],
        "faqs": faqs,
        "breadcrumbs": [
            {"name": "mySpace", "url": root},
            {"name": "Near me", "url": canonical},
        ],
        "extra_schema": json.dumps(schema_graph),
    })
    return templates.TemplateResponse("category_page.html", ctx)

