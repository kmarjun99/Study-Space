"""Intent landing pages — long-tail keyword capture.

These are generated programmatically from a config of (modifier × category ×
location) triples. Each produces a real page with:
  - H1 matching the search query
  - One-paragraph TL;DR
  - Live listing grid (when inventory exists)
  - Internal links to the canonical category × city page
  - FAQs scoped to the intent

Anti-doorway: when no listings exist, the page redirects (302) to the
canonical city × category page rather than rendering empty.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class IntentPage:
    slug: str
    title: str
    h1: str
    description: str
    tldr: str
    intent_label: str       # human-readable modifier ("24-hour", "girls', "near Infopark")
    category: str           # canonical category slug
    city_slug: Optional[str]
    locality_slug: Optional[str]
    landmark: Optional[str]
    keywords: list[str]


# ---------------------------------------------------------------- generator

_MODIFIERS = [
    # (slug_fragment, label, intent_focus_paragraph_template)
    ("best",
     "best",
     "Top-rated {label} based on reviews, location, and amenities. We filter for owner verification, listing freshness, and rating ≥ 4 to surface the strongest options."),
    ("24-hour",
     "24-hour",
     "{label} that stay open 24×7 — ideal for late-night UPSC/PSC prep and shift-workers. Always confirm 24h access with the owner before paying for the month."),
    ("ac",
     "AC",
     "{label} with full air conditioning, ideal for summer prep months. AC adds ₹500–₹1,500/month over the base seat fee."),
    ("affordable",
     "affordable",
     "{label} under ₹2,500/month (₹10,000/month for PG). All listings are filtered for the budget band and verified for owner identity."),
    ("girls",
     "girls'",
     "{label} for girls and women only — segregated accommodation with women-only floors or buildings, dedicated security, and curfews if applicable."),
    ("boys",
     "boys'",
     "{label} for boys and men only — segregated accommodation, ideal for college-age aspirants in coaching-heavy clusters."),
]


def _make_intent(
    *, modifier_slug: str, modifier_label: str, modifier_paragraph: str,
    category_slug: str, category_label: str, category_singular: str,
    city_slug: Optional[str] = None, city_name: Optional[str] = None,
    locality_slug: Optional[str] = None, locality_name: Optional[str] = None,
) -> IntentPage:
    place = (
        f"{locality_name}, {city_name}" if locality_name and city_name
        else city_name or "India"
    )
    h1 = f"{modifier_label.title()} {category_label} in {place}"
    title = f"{h1} — mySpace"
    slug_parts = [modifier_slug, category_slug]
    if locality_slug:
        slug_parts.append(locality_slug)
    elif city_slug:
        slug_parts.append(city_slug)
    slug = "-".join(slug_parts)

    return IntentPage(
        slug=slug,
        title=title,
        h1=h1,
        description=(
            f"Find {modifier_label} {category_label.lower()} in {place} on mySpace. "
            f"Verified listings, transparent pricing, online booking."
        )[:160],
        tldr=modifier_paragraph.format(label=f"{category_label.lower()} in {place}"),
        intent_label=modifier_label,
        category=category_slug,
        city_slug=city_slug,
        locality_slug=locality_slug,
        landmark=None,
        keywords=[
            f"{modifier_label} {category_label.lower()} {place.lower()}",
            f"{modifier_label} {category_singular.lower()} {place.lower()}",
        ],
    )


# Curated coverage — high-intent (modifier × category × place) triples.
# Designed for v1 launch markets (Trivandrum, Kochi); the same generator
# scales to every category × city combination by feeding it the seo_locations
# table at build time.

_V1_COVERAGE: list[tuple] = [
    # (category_slug, category_label, category_singular,
    #  applicable_modifier_slugs, places)
    # places: list of (city_slug, city_name, locality_slug_or_None, locality_name_or_None)
    ("reading-rooms", "Reading Rooms", "Reading Room",
     ["best", "24-hour", "ac", "affordable"],
     [("trivandrum", "Trivandrum", None, None),
      ("kochi", "Kochi", None, None),
      ("trivandrum", "Trivandrum", "pattom", "Pattom"),
      ("trivandrum", "Trivandrum", "technopark", "Technopark"),
      ("kochi", "Kochi", "kakkanad", "Kakkanad"),
      ("kochi", "Kochi", "edappally", "Edappally")]),
    ("study-cabins", "Study Cabins", "Study Cabin",
     ["best", "24-hour", "ac"],
     [("trivandrum", "Trivandrum", None, None),
      ("kochi", "Kochi", None, None)]),
    ("private-cabins", "Private Cabins", "Private Cabin",
     ["best", "24-hour"],
     [("trivandrum", "Trivandrum", None, None),
      ("kochi", "Kochi", None, None)]),
    ("pgs", "PGs", "PG",
     ["best", "affordable", "girls", "boys"],
     [("trivandrum", "Trivandrum", None, None),
      ("kochi", "Kochi", None, None),
      ("trivandrum", "Trivandrum", "kazhakkoottam", "Kazhakkoottam"),
      ("kochi", "Kochi", "kakkanad", "Kakkanad")]),
    ("hostels", "Hostels", "Hostel",
     ["best", "affordable", "girls", "boys"],
     [("trivandrum", "Trivandrum", None, None),
      ("kochi", "Kochi", None, None),
      ("trivandrum", "Trivandrum", "kariavattom", "Kariavattom"),
      ("kochi", "Kochi", "kakkanad", "Kakkanad")]),
    ("co-working-spaces", "Co-working Spaces", "Co-working Space",
     ["best", "24-hour"],
     [("trivandrum", "Trivandrum", None, None),
      ("kochi", "Kochi", None, None)]),
    ("co-learning-spaces", "Co-learning Spaces", "Co-learning Space",
     ["best", "ac"],
     [("trivandrum", "Trivandrum", None, None),
      ("kochi", "Kochi", None, None)]),
    ("rental-houses", "Rental Houses", "Rental House",
     ["affordable"],
     [("trivandrum", "Trivandrum", None, None),
      ("kochi", "Kochi", None, None)]),
    ("rooms-for-rent", "Rooms for Rent", "Room for Rent",
     ["affordable", "girls", "boys"],
     [("trivandrum", "Trivandrum", None, None),
      ("kochi", "Kochi", None, None)]),
]


def _build_v1() -> dict[str, IntentPage]:
    out: dict[str, IntentPage] = {}
    modifier_map = {m[0]: m for m in _MODIFIERS}
    for (cat_slug, cat_label, cat_singular, mod_slugs, places) in _V1_COVERAGE:
        for mod_slug in mod_slugs:
            mod_tuple = modifier_map.get(mod_slug)
            if mod_tuple is None:
                continue
            _, mod_label, mod_para = mod_tuple
            for (city_slug, city_name, loc_slug, loc_name) in places:
                ip = _make_intent(
                    modifier_slug=mod_slug,
                    modifier_label=mod_label,
                    modifier_paragraph=mod_para,
                    category_slug=cat_slug,
                    category_label=cat_label,
                    category_singular=cat_singular,
                    city_slug=city_slug, city_name=city_name,
                    locality_slug=loc_slug, locality_name=loc_name,
                )
                out[ip.slug] = ip
    return out


INTENT_PAGES: dict[str, IntentPage] = _build_v1()


def list_intent_pages() -> list[IntentPage]:
    return sorted(INTENT_PAGES.values(), key=lambda p: p.slug)


def get_intent_page(slug: str) -> Optional[IntentPage]:
    return INTENT_PAGES.get(slug)
