"""On-the-fly image transform — resize + format-convert + cache.

Endpoint shape: GET /img/{source}?w=400&h=300&fmt=webp&q=80
  - `source`   : path under uploads/ (e.g. listings/abc/photo.jpg) or absolute https URL
  - `w`        : target width in CSS pixels (height proportional unless h is set)
  - `h`        : target height; if both w and h are given, the image is fitted
                 into the box and centre-cropped to avoid letterboxing
  - `fmt`      : 'webp' | 'avif' | 'jpg' | 'png' — defaults to 'webp'
  - `q`        : quality 1–95, default 80 (sweet spot for photos)

Cache: transformed bytes are written to `uploads/.cache/{sha1}.{fmt}` keyed by
the full transform spec. First request transforms; subsequent requests
read from cache. The cache is best-effort — wiping `uploads/.cache/` is
always safe.

Production swap: the same URL shape is what Cloudflare Images, imgix, and
Cloudinary expose with their own query parameters. Front a CDN that does
the transform at the edge, point `/img/` at the upstream, and this
in-process implementation can be retired. See DEPLOYMENT.md.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Literal, Optional

from PIL import Image, ImageOps


_log = logging.getLogger("studyspace.image")

# Resolve uploads/ relative to this file (backend/app/services/...).
_UPLOADS = (Path(__file__).resolve().parent.parent.parent / "uploads").resolve()
_CACHE = _UPLOADS / ".cache"
_CACHE.mkdir(parents=True, exist_ok=True)


# Format negotiation. Pillow handles webp natively; avif support depends on
# the host's libaom build. We probe once at import time so we can be honest
# about what we can serve.
_AVIF_SUPPORTED: bool
try:
    Image.new("RGB", (1, 1)).save(BytesIO(), format="AVIF")
    _AVIF_SUPPORTED = True
except Exception:  # pragma: no cover — varies by host
    _AVIF_SUPPORTED = False
    _log.info("AVIF encoder not available; falling back to webp/jpg for /img/*")


Fmt = Literal["webp", "avif", "jpg", "jpeg", "png"]


@dataclass
class TransformSpec:
    source: str            # uploads-relative path or external URL
    width: Optional[int]
    height: Optional[int]
    fmt: Fmt
    quality: int

    def cache_key(self) -> str:
        h = hashlib.sha1(
            f"{self.source}|w={self.width}|h={self.height}|f={self.fmt}|q={self.quality}".encode(),
        ).hexdigest()
        return f"{h}.{self.fmt}"


# Pillow is CPU-bound; offload to the default executor so we don't block the
# event loop on bigger images.
async def _to_thread(fn, *args, **kwargs):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, lambda: fn(*args, **kwargs))


def _resolve_source(path: str) -> Path:
    """Resolve `path` under uploads/ and guard against traversal."""
    # Drop a leading "uploads/" prefix if the caller included it — both
    # /img/uploads/abc.jpg and /img/abc.jpg should mean the same file.
    if path.startswith("uploads/"):
        path = path[len("uploads/"):]
    candidate = (_UPLOADS / path).resolve()
    if not str(candidate).startswith(str(_UPLOADS)):
        raise FileNotFoundError(path)  # treat traversal as not-found, not 500
    if not candidate.is_file():
        raise FileNotFoundError(path)
    return candidate


def _open_source(src_path: Path) -> Image.Image:
    img = Image.open(src_path)
    # EXIF orientation handling — phones love to lie about rotation.
    img = ImageOps.exif_transpose(img)
    return img


def _fit(img: Image.Image, w: Optional[int], h: Optional[int]) -> Image.Image:
    if w is None and h is None:
        return img
    if w is not None and h is None:
        ratio = w / img.width
        return img.resize((w, max(1, round(img.height * ratio))), Image.LANCZOS)
    if h is not None and w is None:
        ratio = h / img.height
        return img.resize((max(1, round(img.width * ratio)), h), Image.LANCZOS)
    # Both — fit to box, then centre-crop excess so we never distort.
    assert w is not None and h is not None
    return ImageOps.fit(img, (w, h), Image.LANCZOS)


_CONTENT_TYPES: dict[str, str] = {
    "webp": "image/webp",
    "avif": "image/avif",
    "jpg":  "image/jpeg",
    "jpeg": "image/jpeg",
    "png":  "image/png",
}


def _save_bytes(img: Image.Image, fmt: Fmt, quality: int) -> bytes:
    buf = BytesIO()
    if fmt in ("jpg", "jpeg"):
        if img.mode in ("RGBA", "LA", "P"):
            # JPEG can't carry alpha; flatten onto white.
            bg = Image.new("RGB", img.size, (255, 255, 255))
            bg.paste(img, mask=img.split()[-1] if img.mode == "RGBA" else None)
            img = bg
        img.save(buf, format="JPEG", quality=quality, optimize=True, progressive=True)
    elif fmt == "webp":
        img.save(buf, format="WEBP", quality=quality, method=6)
    elif fmt == "avif":
        img.save(buf, format="AVIF", quality=quality)
    elif fmt == "png":
        img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def _transform_sync(spec: TransformSpec) -> tuple[bytes, str]:
    src = _resolve_source(spec.source)
    img = _open_source(src)
    img = _fit(img, spec.width, spec.height)
    payload = _save_bytes(img, spec.fmt, spec.quality)
    return payload, _CONTENT_TYPES[spec.fmt]


async def transform(spec: TransformSpec) -> tuple[bytes, str]:
    """Returns (bytes, content_type). Cached on disk by cache_key."""
    cache_path = _CACHE / spec.cache_key()
    if cache_path.is_file():
        return cache_path.read_bytes(), _CONTENT_TYPES[spec.fmt]
    payload, ctype = await _to_thread(_transform_sync, spec)
    # Best-effort write — corrupt cache is just slower, never wrong.
    try:
        cache_path.write_bytes(payload)
    except OSError as exc:
        _log.warning("Cache write failed for %s: %s", cache_path, exc)
    return payload, ctype


def normalise_format(fmt: Optional[str]) -> Fmt:
    """Pick the served format, falling back when AVIF isn't available."""
    fmt = (fmt or "webp").lower()
    if fmt == "avif" and not _AVIF_SUPPORTED:
        return "webp"
    if fmt in ("webp", "avif", "jpg", "jpeg", "png"):
        return fmt  # type: ignore[return-value]
    return "webp"


def avif_supported() -> bool:
    return _AVIF_SUPPORTED
