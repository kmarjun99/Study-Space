"""SEO geographic hierarchy (national scale).

One table represents the entire administrative hierarchy used to generate
programmatic SEO pages and sitemaps. Designed for ~500 cities and ~5,000
localities at maturity without schema change.

  country  (India)
    └── state    (Kerala, Karnataka, ...)
          └── city      (Trivandrum, Kochi, Bangalore, ...)
                └── locality   (Technopark, Kakkanad, Whitefield, ...)
                      └── landmark  (Infopark, Christ College, Cubbon Park, ...)

Each row is independently routable (every level produces a URL). Programmatic
page eligibility is computed from `listing_counts_json` so that thin pages
never publish — the same model supports a no-listings-yet city in stealth.

Hard rules:
  - Append/update only; never hard-delete (would break inbound SEO links).
    Set `is_seo_active = False` to retire a page; it then returns 410 Gone.
  - `slug` is unique site-wide for each kind (no two cities share a slug).
  - `parent_id` always points to the immediate parent (locality → city → state).
"""
import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean, Column, DateTime, Enum, Float, ForeignKey, Index, Integer,
    String, Text, UniqueConstraint,
)

from app.database import Base


class LocationKind(str, enum.Enum):
    COUNTRY = "country"
    STATE = "state"
    CITY = "city"
    LOCALITY = "locality"
    LANDMARK = "landmark"


class SeoLocation(Base):
    __tablename__ = "seo_locations"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    kind = Column(
        Enum(LocationKind, native_enum=False), nullable=False, index=True,
    )

    # Display name + URL slug. Slug is unique within (kind, parent_id) so two
    # cities in different states can share "salem" (TN) vs "salem" (KL) only
    # if they have different parents.
    name = Column(String(120), nullable=False)
    slug = Column(String(120), nullable=False, index=True)

    # JSON list of alternate names (e.g., ["TVM", "Thiruvananthapuram", "Anantapuri"]).
    # Used for query matching, not for URLs.
    aliases_json = Column(Text, nullable=True)

    parent_id = Column(
        String, ForeignKey("seo_locations.id"), nullable=True, index=True,
    )

    # Administrative identifiers. state_code follows ISO 3166-2:IN
    # (e.g., "KL", "KA", "TN", "DL"). country_code defaults "IN".
    country_code = Column(String(2), nullable=False, default="IN")
    state_code = Column(String(4), nullable=True, index=True)

    # Lat/lng powers "near me" pages and map renders. Required for cities and
    # localities; optional for states (country-level rows have none).
    lat = Column(Float, nullable=True)
    lng = Column(Float, nullable=True)

    # 1=tier-1 metro, 2=tier-2 city, 3=tier-3, 4=tier-4/rural. Used for content
    # template selection + sitemap priority weighting.
    population_tier = Column(Integer, nullable=True)

    # Editorial controls
    is_seo_active = Column(Boolean, nullable=False, default=False)
    has_inventory = Column(Boolean, nullable=False, default=False)

    # Computed nightly. JSON: {"reading_rooms": 47, "pgs": 12, ...}
    # Drives "only emit URL if listing_count >= threshold" rule.
    listing_counts_json = Column(Text, nullable=True)

    # Free-form admin notes + custom intro paragraph for the city/locality
    # page. JSON: {"intro": "...", "trivia": "...", "fun_fact": "..."}
    metadata_json = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow,
        nullable=False,
    )

    __table_args__ = (
        # Same slug allowed in different parents (Salem-KL vs Salem-TN) but
        # never within the same parent.
        UniqueConstraint("kind", "parent_id", "slug",
                         name="uq_seo_loc_kind_parent_slug"),
        # Common query patterns
        Index("ix_seo_loc_kind_active", "kind", "is_seo_active"),
        Index("ix_seo_loc_state_kind", "state_code", "kind"),
    )
