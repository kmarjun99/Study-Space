"""SPA fallback + production static-asset serving.

Mounted LAST in main.py — every preceding router gets first crack at matching.
What's left after all the explicit routes have had their turn falls into the
classification this module does:

  ┌────────────────────────────────────────────────────────────────────┐
  │ A. Path starts with an SPA prefix (/student/, /admin/, /login, …) │
  │    → serve frontend/dist/index.html (React BrowserRouter takes over)│
  │                                                                    │
  │ B. Path starts with /assets/, /uploads/, /static/, /images/, …    │
  │    → static file from dist/ or uploads/ (404 if not on disk)      │
  │                                                                    │
  │ C. Anything else                                                  │
  │    → 404 (unknown public-SEO URL — do NOT shadow it with the SPA) │
  └────────────────────────────────────────────────────────────────────┘

The strict separation between (A) and (C) is the point: returning the SPA
shell for `/reading-rooms/foo` would let Google index thousands of empty
shells. Returning 404 forces unknown SEO URLs to fail loudly so we can
either add a redirect or activate the missing programmatic page.

Dev-mode behaviour: when `frontend/dist/` doesn't exist yet (you're running
the React dev server on :3000 and FastAPI on :8000 as separate processes),
the catch-all logs a helpful warning and 404s with a hint instead of 500'ing.
"""
from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse


router = APIRouter(tags=["SPA"])
_log = logging.getLogger("studyspace.spa")


# Resolve the React build output relative to this file. In production, this
# directory is populated by `npm run build` and shipped alongside the backend.
_FRONTEND_DIST = (
    Path(__file__).resolve().parent.parent.parent.parent
    / "frontend" / "dist"
).resolve()


# Path prefixes that resolve to the React SPA. Any URL under one of these
# is served the SPA shell; React Router takes over client-side. This list
# is the single source of truth — keep it in sync with App.tsx's <Routes>.
SPA_PREFIXES: tuple[str, ...] = (
    "/student/",
    "/admin/",
    "/super-admin/",
    "/owner/",
    "/dashboard/",
    "/auth",
    "/login",
    "/register",
    "/mock-payment",
    # Bare path also resolves; matched as `path == prefix.rstrip("/")` below.
)


# Static asset directories that must be reachable directly. /assets/* is the
# Vite-fingerprinted JS + CSS; the others are public images already in the
# tree.
_STATIC_FILES_AT_ROOT: tuple[str, ...] = (
    "logo_stacked.png", "profile_favicon.png", "studyspace_logo.png",
    "favicon.ico", "manifest.webmanifest",
)


def _spa_index_html() -> Path:
    return _FRONTEND_DIST / "index.html"


def _is_spa_path(path: str) -> bool:
    """Return True iff path should be served by the React SPA."""
    return any(
        path == p.rstrip("/") or path.startswith(p) or path.startswith(p + "/")
        for p in SPA_PREFIXES
    )


# ---------- /assets/<fingerprinted-js-or-css> ----------------------------

@router.get("/assets/{file_path:path}")
async def serve_vite_assets(file_path: str) -> FileResponse:
    """Vite's hashed JS/CSS bundles. Long-cache headers — the hash in the
    filename invalidates on every build."""
    target = (_FRONTEND_DIST / "assets" / file_path).resolve()
    # Path traversal guard
    if not str(target).startswith(str(_FRONTEND_DIST / "assets")):
        raise HTTPException(status_code=404)
    if not target.is_file():
        raise HTTPException(status_code=404)
    return FileResponse(
        target,
        headers={
            # Vite asset names are content-hashed → safe to cache forever.
            "Cache-Control": "public, max-age=31536000, immutable",
        },
    )


# ---------- a few root-level static assets the SPA + Jinja templates link to

@router.get("/{filename:path}", include_in_schema=False)
async def root_static_or_spa_or_404(filename: str, request: Request):
    """Final catch-all. Order of resolution:
       1. Root-level static file (favicon, logos)        → FileResponse
       2. Known SPA prefix                                 → index.html
       3. Anything else                                    → 404
    """
    # (1) Known root-level static asset
    if filename in _STATIC_FILES_AT_ROOT:
        target = (_FRONTEND_DIST / filename).resolve()
        if target.is_file() and str(target).startswith(str(_FRONTEND_DIST)):
            return FileResponse(target)
        # Fall through to 404 if the file was promised but is missing

    full_path = "/" + filename  # e.g. "student/dashboard" → "/student/dashboard"

    # (2) React SPA shell for app routes
    if _is_spa_path(full_path):
        index = _spa_index_html()
        if not index.is_file():
            _log.warning(
                "SPA index.html not found at %s — run `npm run build` in "
                "frontend/ or serve the React dev server separately.",
                index,
            )
            raise HTTPException(
                status_code=503,
                detail=(
                    "Frontend build missing. Run `npm run build` in frontend/ "
                    "to produce dist/index.html, or run the dev server on "
                    "port 3000 and proxy to it."
                ),
            )
        # The SPA shell must not be cached aggressively — when we redeploy,
        # the embedded asset URLs change. The hashed assets themselves are
        # cached for a year by /assets above.
        return FileResponse(
            index,
            media_type="text/html; charset=utf-8",
            headers={"Cache-Control": "no-cache, must-revalidate"},
        )

    # (3) Unknown public-SEO URL — let it 404 with no SPA shadow. This is
    #     deliberate: returning SPA HTML here would let Google index thousands
    #     of empty React shells under non-existent slugs.
    raise HTTPException(status_code=404, detail="not found")
