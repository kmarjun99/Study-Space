"""Template helpers for responsive images.

Registered as Jinja2 filters in routers/seo_content.py so guides + listing
detail + intent + category templates can write:

  {{ "listings/abc/photo.jpg" | img_srcset(widths=[400, 800, 1200]) }}

…and get a complete `srcset="..."` value back. Templates can also use
`img_url(path, w=400)` for a single src URL.
"""
from __future__ import annotations

from typing import Iterable, Optional


def img_url(path: str, w: Optional[int] = None, h: Optional[int] = None,
            fmt: Optional[str] = None, q: int = 80) -> str:
    """Generate a single /img URL with optional transform params.

    `path` may be:
      - "/uploads/listings/abc.jpg"  → stripped to "listings/abc.jpg"
      - "listings/abc.jpg"           → used as-is
      - "https://example.com/x.jpg"  → returned untouched (external source)
    """
    if not path:
        return ""
    if path.startswith(("http://", "https://")):
        return path
    # Normalise — drop leading slash + optional uploads/ prefix.
    cleaned = path.lstrip("/")
    if cleaned.startswith("uploads/"):
        cleaned = cleaned[len("uploads/"):]
    params = []
    if w is not None: params.append(f"w={w}")
    if h is not None: params.append(f"h={h}")
    if fmt:           params.append(f"fmt={fmt}")
    if q != 80:       params.append(f"q={q}")
    qstring = ("?" + "&".join(params)) if params else ""
    return f"/img/{cleaned}{qstring}"


def img_srcset(path: str, widths: Iterable[int],
               fmt: Optional[str] = None, q: int = 80) -> str:
    """Build a `srcset` value with width descriptors.

      img_srcset("a.jpg", widths=[400, 800, 1200])
      → "/img/a.jpg?w=400 400w, /img/a.jpg?w=800 800w, /img/a.jpg?w=1200 1200w"
    """
    if not path or path.startswith(("http://", "https://")):
        # External sources can't be transformed by us; fall back to a single src.
        return f"{path} 800w"
    parts = []
    for w in widths:
        url = img_url(path, w=w, fmt=fmt, q=q)
        parts.append(f"{url} {w}w")
    return ", ".join(parts)


# Common breakpoint presets so templates don't have to think.
PRESET_THUMB = [240, 480, 720]            # listing-card thumbnails
PRESET_CARD  = [320, 640, 960]            # category-page cards
PRESET_HERO  = [400, 800, 1200, 1600]     # listing-detail hero
PRESET_OG    = [1200]                      # social share image
