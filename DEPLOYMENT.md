# MySpace — Production Routing & Deployment

This document is the source of truth for how `myspaceapp.in` resolves URLs in
production. It exists so the architecture decisions baked into the codebase
are reviewable in one place.

---

## TL;DR

**Single origin, single server.** FastAPI on `myspaceapp.in` owns every
URL. It dispatches in this order:

```
1. Explicit SEO routes  (Jinja2)           → real HTML for crawlers + users
2. Explicit API routes  (JSON)              → reads / writes
3. Explicit static                          → /assets/*, /uploads/*, favicon
4. SPA fallback (allowlist)                 → dist/index.html for app routes
5. Hard 404                                  → for everything else
```

There is **no Nginx in front** in the default deployment. If you put one in
front (recommended at scale), it should be a thin reverse proxy — all routing
intelligence stays in FastAPI.

---

## What gets served where

### Public SEO (Jinja2, server-rendered, indexable)

All these return real HTML with full `<title>`, `<meta>`, JSON-LD schema, and
internal links. Crawlers + AI bots see the same content as users.

```
GET /                                            (HomePage, React)*
GET /reading-rooms                               → category landing
GET /reading-rooms/:city                         → city × category
GET /reading-rooms/:city/:locality               → locality × category
GET /pgs, /pgs/:city, /pgs/:city/:locality
GET /hostels[, /:city, /:city/:locality]
GET /study-cabins, /private-cabins, /shared-cabins
GET /co-working-spaces, /co-learning-spaces
GET /rental-houses, /rooms-for-rent
                                                (each of the 10 categories
                                                 has 3 server-rendered URLs)

GET /listing/:category/:slug                    → server-rendered LocalBusiness

GET /city/:slug                                  (React, CityPage)*
GET /state/:slug                                 (React, StatePage)*

GET /guides                                     → guides hub
GET /guides/:slug                               → 10 long-form guides

GET /best-:cat-:place                           → intent landing pages
GET /24-hour-:cat-:place                        (82 pages auto-registered)
GET /ac-:cat-:place
GET /affordable-:cat-:place
GET /girls-:cat-:place
GET /boys-:cat-:place

GET /near-me                                    → geolocation intent landing

GET /about, /press, /careers, /contact,         (React, EntityPages)*
    /trust, /help, /privacy, /terms
```

\* React-rendered pages. In production they hit the SPA fallback (#4) and
hydrate client-side. Google can render JS so these get indexed; AI crawlers
(GPTBot / ClaudeBot / PerplexityBot) cannot, so the **most important**
pages (`/reading-rooms/kochi`, `/listing/...`, `/guides/*`) are all
**also** server-rendered via Jinja2 and win the route match in production.

### SEO infrastructure

```
GET /robots.txt                                  → text
GET /llms.txt                                    → text — AI crawler manifest
GET /sitemap.xml                                 → sitemap index
GET /sitemaps/core.xml                           → home + categories + entity
GET /sitemaps/cities.xml                         → city overview pages
GET /sitemaps/listings.xml                       → listing detail URLs
GET /sitemaps/guides.xml                         → 11 guide URLs
GET /sitemaps/intent.xml                         → 82 intent landing URLs
GET /sitemaps/{category}.xml                     → per-category URLs (10 shards)
```

### API (JSON)

```
GET  /auth/me                                    legacy auth
POST /auth/login, /auth/register                 etc.

# Public reads (no auth)
GET  /public/categories
GET  /public/locations/{kind}/{slug}
GET  /public/listings, /public/listings/{cat}/by-slug/{slug}

# Authed reads/writes
GET  /reading-rooms/                             list (LIVE only for anon)
POST /reading-rooms/                             create (admin)
GET  /reading-rooms/{uuid}                       legacy detail by id
                                                  (NOTE: shadowed by
                                                  /reading-rooms/{city_slug}
                                                  in production — see below)

# Intelligence layer
GET  /super-admin/segments[/...]
GET  /super-admin/campaigns[/...]
GET  /super-admin/notification-rules[/...]
GET  /super-admin/attribution/funnel
GET  /super-admin/dashboard
GET  /super-admin/experiments[/...]
GET  /super-admin/cohorts/weekly
GET  /super-admin/ml/features.csv
GET  /owner/insights
GET  /owner/charges[/...]
GET  /owner/settlements[/...]
GET  /owner/listings[/...]

# Money / payment
POST /razorpay/create-order, /razorpay/verify
POST /webhooks/razorpay
```

### SPA (React shell)

Only these prefixes get served the React build's `dist/index.html`. The
list lives at [`backend/app/routers/spa_fallback.py`](backend/app/routers/spa_fallback.py).
Keep it in sync with `<Routes>` in `frontend/src/App.tsx`.

```
/student/*           student dashboard, bookings, messages, profile
/admin/*             owner-admin dashboard
/super-admin/*       platform-admin dashboard
/owner/*             owner-facing settings + insights UI
/dashboard/*         generic dashboard alias
/auth, /login,       authentication flows
  /register
/mock-payment        demo gateway
```

### Hard 404 (the deliberate part)

Anything that doesn't match (1)–(4) returns **404, not the SPA shell.**
This is intentional. If we served the SPA shell for `/reading-rooms/foobar`,
Google would index thousands of empty React shells. Returning a real 404
forces unknown public-SEO URLs to fail loudly so we can either add a
redirect or activate the missing programmatic page.

---

## Known route collisions (legacy API ↔ SPA URL)

A handful of backend APIs share URLs with SPA routes. These were registered
**before** the SEO refactor and predate the namespacing convention.

| URL | Currently returns | SPA expectation | Cost of fix |
|---|---|---|---|
| `/owner/insights` | JSON (401 if anon) | SPA shell | Move API to `/api/owner/insights` |
| `/owner/charges`, `/owner/settlements`, `/owner/listings` | JSON | SPA shell | Same |
| `/owner/payment-history`, `/owner/flags` | JSON | SPA shell | Same |
| `/super-admin/segments`, `/super-admin/campaigns`, etc. | JSON | SPA shell | Same |

**Practical impact:** a logged-in browser hitting these URLs receives raw
JSON instead of the React page. The SPA's `<Link>`-based navigation works
fine because it doesn't do full page loads — the JS is already in memory.
The user-facing bug is only triggered by deep-linking or refresh.

**Recommended fix:** namespace all backend APIs under `/api/*` and update
the frontend services. This is a future PR; the current routing is
functional for v1.

**Workaround for now:** the SPA's auth interceptor in `frontend/src/services/api.ts`
catches 401s and redirects to `/login`. So an anonymous user hitting
`/owner/insights` lands at `/login` with the intended URL preserved as a
`?next=` param after we wire that.

---

## How requests flow in production

```
        ┌──────────────┐
        │  Cloudflare  │  edge caching (optional)
        └──────┬───────┘
               │ HTTPS
               ▼
        ┌──────────────┐
        │   FastAPI    │  uvicorn workers
        │    :8000     │  + uvicorn[standard] (gunicorn in prod)
        └──────┬───────┘
               │
   ┌───────────┼───────────┬──────────────┐
   ▼           ▼           ▼              ▼
Jinja2       Pydantic    StaticFiles    SQLAlchemy
templates    handlers    (dist, uploads) (Postgres in prod)
```

`vite` is **not** running in production. The React app is built once with
`npm run build` and the resulting `frontend/dist/` is served by FastAPI as
static files. Run-time JS execution happens only in the user's browser.

---

## Deployment commands

```bash
# 1. Backend — install + migrations
cd backend
pip install -r requirements.txt
python scripts/seed_chart_of_accounts.py
python scripts/seed_tax_config.py
python scripts/seed_seo_locations.py
python scripts/migrate_add_accounting_columns.py
python scripts/migrate_add_listing_slugs.py
python scripts/migrate_add_notification_rule_id.py
python scripts/migrate_add_reco_attribution.py
python scripts/migrate_intelligence_columns.py

# 2. Frontend — build static assets
cd ../frontend
npm ci --legacy-peer-deps
npm run build
# Produces frontend/dist/{index.html, assets/*.js, assets/*.css}

# 3. Start backend (it serves both the API and the dist/)
cd ../backend
gunicorn app.main:app -k uvicorn.workers.UvicornWorker -w 4 -b 0.0.0.0:8000
```

The single `gunicorn` process serves everything. If you put Cloudflare or
Nginx in front, configure it only for HTTPS termination + edge caching —
do not split the URL space across multiple origins, that breaks the route
precedence.

---

## Optional: Cloudflare CDN edge caching

Recommended cache policies:

```
/assets/*                Cache: 1 year, immutable (Vite hashes invalidate)
/uploads/*               Cache: 1 day, stale-while-revalidate
/robots.txt              Cache: 1 hour
/sitemap*.xml            Cache: 1 day
/llms.txt                Cache: 1 hour
/guides, /guides/*       Cache: 1 day (updates infrequent)
/reading-rooms, /pgs,    Cache: 1 hour (listings change)
  /hostels, ...
/listing/*               Cache: 30 minutes
/                        Cache: 1 hour
/api/*, /auth/*,         Cache: BYPASS
  /webhooks/*,
  /razorpay/*
/student/*, /admin/*,    Cache: BYPASS (per-user state)
  /super-admin/*,
  /owner/*, /dashboard/*
```

Cloudflare Workers can additionally inject a bot-vs-human distinction if we
ever want to dynamic-render React pages for AI crawlers — not needed today
because the SEO-critical pages are already Jinja2-rendered.

---

## Image transform pipeline (`/img/*`)

Listings are stored as plain files under `backend/uploads/`. To avoid
shipping 4 MB phone photos to mobile users, every `<img>` in the SEO and
React surfaces routes through `/img/{path}?w=...&h=...&fmt=...&q=...`.

```
GET /uploads/listings/abc/photo.jpg            → original, untransformed
GET /img/listings/abc/photo.jpg                → 800w WebP (default)
GET /img/listings/abc/photo.jpg?w=400&fmt=avif → 400w AVIF (if encoder available)
GET /img/listings/abc/photo.jpg?w=400&h=400    → 400x400 centre-cropped WebP
```

**Caching**: every URL is content-addressable. Cache-Control is
`max-age=31536000, immutable`. Transformed bytes are cached on disk at
`uploads/.cache/{sha1}.{fmt}`; wiping that directory is always safe.

**Format negotiation**: when `?fmt=` is omitted, the handler reads the
client's `Accept` header. Modern browsers send `image/avif`; older ones
get WebP; legacy clients fall through to `<img src=...>` which is a
proper JPEG.

### Swapping to Cloudflare Images / imgix / Cloudinary

The same URL shape is what every commercial CDN exposes. To swap the
in-process Pillow implementation for an external CDN, do **only** these
three things:

1. Upload all of `backend/uploads/` into the CDN bucket (one-time).
2. Replace the `/img/*` route handler with a transparent proxy that
   forwards to the CDN URL pattern:
   ```python
   @router.get("/img/{path:path}")
   async def transform_image(path: str, w: int = None, fmt: str = None, ...):
       cdn_url = f"https://images.myspaceapp.in/{path}?w={w}&format={fmt}"
       return RedirectResponse(url=cdn_url, status_code=308)
   ```
3. Delete `uploads/.cache/` and `image_transform_service.py`.

The frontend `imageUtils.ts` and backend `image_helpers.py` keep
generating the same `/img/...` URLs — no template or component changes
needed.

---

## Optional: Nginx reverse proxy

If you prefer Nginx in front of FastAPI:

```nginx
server {
    listen 443 ssl http2;
    server_name myspaceapp.in;

    # HTTPS — terminate here
    ssl_certificate     /etc/letsencrypt/live/myspaceapp.in/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/myspaceapp.in/privkey.pem;

    # Static — serve from disk directly (don't proxy these)
    location /assets/ {
        alias /srv/myspace/frontend/dist/assets/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
    location /uploads/ {
        alias /srv/myspace/backend/uploads/;
        expires 1d;
    }

    # Everything else → FastAPI
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_read_timeout 90s;
    }
}
```

Nginx serves `/assets/` and `/uploads/` directly to take that load off
FastAPI. Everything else proxies to FastAPI where the routing precedence
above kicks in.

---

## Verification (run after every deploy)

```bash
# 1. Real HTML for SEO routes
curl -sS https://myspaceapp.in/reading-rooms/kochi \
    | grep -E '<title>|FAQPage|BreadcrumbList'
# expect 3+ matches

# 2. SPA shell for app routes
curl -sS https://myspaceapp.in/student/dashboard | grep 'id="root"'
# expect 1 match

# 3. Hard 404 for unknown SEO URLs
curl -sS -o /dev/null -w '%{http_code}\n' \
    https://myspaceapp.in/reading-rooms/this-is-not-a-real-city
# expect: 404

# 4. SEO infrastructure
curl -sS -o /dev/null -w '%{http_code}\n' https://myspaceapp.in/robots.txt
curl -sS -o /dev/null -w '%{http_code}\n' https://myspaceapp.in/sitemap.xml
curl -sS -o /dev/null -w '%{http_code}\n' https://myspaceapp.in/llms.txt
# expect: 200 200 200

# 5. AI crawler sample (no JS)
curl -sS -H 'User-Agent: GPTBot' https://myspaceapp.in/guides/best-reading-rooms-in-kerala \
    | wc -l
# expect: 200+ lines (real content, not the React shell which is ~70 lines)
```

---

## What is NOT in this setup

- **No HashRouter** — `myspaceapp.in/#/path` is gone. All URLs are clean
  `BrowserRouter` paths.
- **No build-time prerender** — React-rendered pages
  (`/city/:slug`, `/state/:slug`, entity pages, `/`) still hydrate on the
  client. AI-critical pages are Jinja2; non-critical ones are React.
- **No Vite dev server in production** — `npm run build` is the only
  frontend build step. `npm run dev` is local-only.
- **No bot-vs-human dynamic rendering** — we serve the same Jinja2 HTML to
  every client for SEO routes.
