"""Image transform endpoint.

URL pattern: GET /img/{path:path}?w&h&fmt&q

  /img/listings/abc/photo.jpg                → original-sized webp
  /img/listings/abc/photo.jpg?w=400          → 400-wide webp
  /img/listings/abc/photo.jpg?w=400&fmt=avif → 400-wide avif (if available)
  /img/listings/abc/photo.jpg?w=400&h=300    → 400×300 centre-cropped

Long Cache-Control because the URL is fully content-addressable — any
change to the source needs a new file name on disk, which produces a new
URL. (Existing `/uploads/...` URLs without query params still work via the
StaticFiles mount; they're un-transformed originals.)
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import Response

from app.services.image_transform_service import (
    TransformSpec, normalise_format, transform,
)


router = APIRouter(tags=["Image Transform"])


_MAX_DIM = 4096  # don't accept w/h above this to avoid DoS via huge upscales


@router.get("/img/{path:path}")
async def transform_image(
    path: str,
    request: Request,
    w: Optional[int] = Query(None, ge=1, le=_MAX_DIM),
    h: Optional[int] = Query(None, ge=1, le=_MAX_DIM),
    fmt: Optional[str] = Query(None),
    q: int = Query(80, ge=1, le=95),
) -> Response:
    # Content negotiation — if the client sent Accept: image/avif, prefer it
    # over webp when no explicit fmt was passed. Clients that explicitly ask
    # for a format always get what they asked for.
    if fmt is None:
        accept = request.headers.get("accept", "")
        if "image/avif" in accept:
            fmt = "avif"
        elif "image/webp" in accept:
            fmt = "webp"
        else:
            fmt = "webp"

    spec = TransformSpec(
        source=path,
        width=w,
        height=h,
        fmt=normalise_format(fmt),
        quality=q,
    )
    try:
        body, ctype = await transform(spec)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="image not found")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"transform failed: {exc}")

    headers = {
        # URL is content-addressable — body changes only when source or query
        # param changes, so 1 year is safe.
        "Cache-Control": "public, max-age=31536000, immutable",
        "Vary": "Accept",
    }
    return Response(content=body, media_type=ctype, headers=headers)
