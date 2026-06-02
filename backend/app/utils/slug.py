"""URL slug generation.

Deterministic, ASCII-only slugs from listing names + city context. Designed
so the same listing always slugifies to the same string (idempotent backfill).

Rules:
  - Lowercase, ASCII only (Unicode normalised to NFKD, accents stripped).
  - Whitespace + punctuation collapsed to single hyphens.
  - No leading/trailing hyphens.
  - At most `MAX_LEN` characters; truncated at the last hyphen.
  - City + locality suffixes appended for SEO + uniqueness.
  - Optional integer suffix `-2`, `-3`, … on collision (handled by caller).
"""
from __future__ import annotations

import re
import unicodedata
from typing import Optional


MAX_LEN = 100
_NON_ALNUM = re.compile(r"[^a-z0-9]+")
_MULTI_HYPHEN = re.compile(r"-{2,}")


def slugify(value: str) -> str:
    """Lowercase, ASCII, hyphen-separated. Single piece — no suffix logic."""
    if not value:
        return ""
    normalized = unicodedata.normalize("NFKD", value)
    ascii_only = normalized.encode("ascii", "ignore").decode("ascii")
    lowered = ascii_only.lower()
    hyphenated = _NON_ALNUM.sub("-", lowered)
    cleaned = _MULTI_HYPHEN.sub("-", hyphenated).strip("-")
    return cleaned


def listing_slug(
    name: str,
    *,
    locality: Optional[str] = None,
    city: Optional[str] = None,
) -> str:
    """Generate a listing slug of the form `name-locality-city`.

    Example:
        listing_slug("ABC Reading Room", locality="Kakkanad", city="Kochi")
        → "abc-reading-room-kakkanad-kochi"

    Any of the three pieces may be None — empty pieces are dropped, not left
    as dangling hyphens. The result is truncated to MAX_LEN at the last
    safe hyphen so we never break a word in half.
    """
    parts = [slugify(p) for p in (name, locality, city) if p]
    raw = "-".join(p for p in parts if p)
    raw = _MULTI_HYPHEN.sub("-", raw).strip("-")
    if len(raw) <= MAX_LEN:
        return raw
    truncated = raw[:MAX_LEN]
    last_hyphen = truncated.rfind("-")
    return truncated[:last_hyphen] if last_hyphen > 0 else truncated


def collision_suffix(base: str, n: int) -> str:
    """Append `-2`, `-3`, … to disambiguate collisions. n=1 returns base."""
    if n <= 1:
        return base
    return f"{base}-{n}"
