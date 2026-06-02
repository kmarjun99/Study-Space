/**
 * Frontend-side equivalents of backend/app/services/image_helpers.py.
 *
 * Same URL shape (`/img/{path}?w&h&fmt&q`) so the backend transform service
 * can pick up any URL the React code emits.
 *
 * External URLs (https://…) are returned unchanged — we don't try to proxy
 * them through /img unless the caller explicitly opts in.
 */

export type ImageFormat = 'webp' | 'avif' | 'jpg' | 'png';

export interface ImageOpts {
    w?: number;
    h?: number;
    fmt?: ImageFormat;
    q?: number;       // default 80
}

/** Strip /uploads prefix; return path suitable for `/img/...`. */
function normaliseSourcePath(path: string): string {
    let p = path.replace(/^\/+/, '');
    if (p.startsWith('uploads/')) p = p.slice('uploads/'.length);
    return p;
}

/** Build a single `/img/...` URL with the given transform params. */
export function imageUrl(source: string, opts: ImageOpts = {}): string {
    if (!source) return '';
    if (/^https?:\/\//.test(source)) return source;        // external, untouched
    // `data:` and `blob:` URLs are inline images the browser already knows
    // how to render — never proxy them through the `/img/` transform pipeline.
    // Doing so prepends `/img/` to the (multi-kilobyte) base64 payload and the
    // server rejects the >2KB URL with 414 URI Too Long. This typically shows
    // up when an upload preview (FileReader.readAsDataURL) is bound to an
    // <img src> before the real upload completes, or when stale rows in the
    // database accidentally have a data URL stored as `imageUrl`.
    if (/^(data|blob):/i.test(source)) return source;
    const params: string[] = [];
    if (opts.w !== undefined) params.push(`w=${opts.w}`);
    if (opts.h !== undefined) params.push(`h=${opts.h}`);
    if (opts.fmt)             params.push(`fmt=${opts.fmt}`);
    if (opts.q !== undefined && opts.q !== 80) params.push(`q=${opts.q}`);
    const qs = params.length ? `?${params.join('&')}` : '';
    return `/img/${normaliseSourcePath(source)}${qs}`;
}

/** Build a `srcset` value with width descriptors. */
export function imageSrcSet(
    source: string,
    widths: number[],
    fmt?: ImageFormat,
): string {
    // Pass-through for empty, external, and inline data/blob URLs — none of
    // these benefit from a srcset (or would crash trying to build one).
    if (!source || /^(https?|data|blob):/i.test(source)) return source;
    return widths
        .map(w => `${imageUrl(source, { w, fmt })} ${w}w`)
        .join(', ');
}

// Width presets that match the backend's PRESET_THUMB / PRESET_CARD / PRESET_HERO
export const IMAGE_PRESETS = {
    thumb: [240, 480, 720],
    card:  [320, 640, 960],
    hero:  [400, 800, 1200, 1600],
} as const;

/**
 * Strip out the first image from a comma-separated URL string and return it
 * normalised. Listings store images as a comma-separated string in the
 * legacy schema; this helper centralises that parsing in one place.
 */
export function firstImage(images: string | null | undefined): string {
    if (!images) return '';
    return images.split(',')[0]?.trim() || '';
}

/** All images in a comma-separated string, trimmed and empty-filtered. */
export function allImages(images: string | null | undefined): string[] {
    if (!images) return [];
    return images.split(',').map(s => s.trim()).filter(Boolean);
}
