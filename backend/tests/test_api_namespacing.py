"""Regression tests for the /api/* namespace migration.

After moving /owner/* and /super-admin/* and the intelligence routers under
/api/*, we need to assert three things:

  1. The new /api/* URLs resolve (not 404).
  2. The OLD URLs no longer return JSON — they either 404 outright or fall
     through to the SPA fallback (which serves HTML, not JSON).
  3. Public SEO routes are untouched.

These tests exercise the FastAPI app via httpx so we hit the real ASGI
routing, including all the prefix-stacking through include_router().
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app


@pytest.mark.asyncio
async def test_api_owner_insights_is_reachable():
    """/api/owner/insights resolves (401 = endpoint reached + needs auth)."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r = await ac.get("/api/owner/insights")
    # Endpoint exists and requires auth; never 404.
    assert r.status_code in (200, 401), (
        f"/api/owner/insights returned {r.status_code} — endpoint missing?"
    )


@pytest.mark.asyncio
async def test_api_owner_charges_is_reachable():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r = await ac.get("/api/owner/charges")
    assert r.status_code in (200, 401)


@pytest.mark.asyncio
async def test_api_super_admin_routes_reachable():
    """All key /api/super-admin/* endpoints resolve."""
    paths = [
        "/api/super-admin/dashboard",
        "/api/super-admin/segments",
        "/api/super-admin/campaigns",
        "/api/super-admin/notification-rules",
        "/api/super-admin/experiments",
        "/api/super-admin/cohorts/weekly",
        "/api/super-admin/recommendation-attribution/funnel",
        "/api/super-admin/ledger",
        "/api/super-admin/owners/kyc",
    ]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        for p in paths:
            r = await ac.get(p)
            assert r.status_code in (200, 401, 403), (
                f"{p} returned {r.status_code} — expected 200/401/403"
            )


def test_api_public_endpoints_are_registered():
    """/api/public/* must be in the app's route table. We can't make a live
    HTTP call here because the routes hit a DB whose tables aren't created
    in the test runner — but registration alone is enough to prove the
    namespace migration worked."""
    registered = {r.path for r in app.routes if hasattr(r, "path")}
    expected = {
        "/api/public/categories",
        "/api/public/locations/{kind}/{slug}",
        "/api/public/listings",
        "/api/public/listings/{category}/by-slug/{slug}",
    }
    missing = expected - registered
    assert not missing, f"Missing /api/public routes: {missing}"
    # And the OLD /public/* paths must NOT be registered anymore.
    leaked = {p for p in registered if p.startswith("/public/")}
    assert not leaked, f"Old /public/* routes still present: {leaked}"


@pytest.mark.asyncio
async def test_api_events_endpoint_resolves():
    """/api/events accepts POST (intelligence event firehose)."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 422 = pydantic validation failure on empty body, which proves the
        # endpoint was reached.
        r = await ac.post("/api/events", json={})
    assert r.status_code in (200, 401, 422), (
        f"/api/events returned {r.status_code} — endpoint missing?"
    )


@pytest.mark.asyncio
async def test_old_owner_paths_no_longer_serve_json():
    """The old /owner/insights / /owner/charges paths must NOT return JSON
    anymore — they should either 404 or fall through to the SPA fallback
    (text/html). This is the core assertion of the namespace migration."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        for p in ["/owner/insights", "/owner/charges"]:
            r = await ac.get(p)
            # If the old route still claimed the URL, it would be 401 (auth).
            # After the move, /owner/* is a SPA prefix → SPA fallback handler
            # serves either HTML (200, when dist/ exists) or a helpful 503
            # (when dist/ doesn't exist in test env).
            assert r.status_code in (200, 404, 503), (
                f"{p} returned {r.status_code} — expected SPA fallback"
            )
            ctype = r.headers.get("content-type", "")
            assert "application/json" not in ctype or r.status_code == 503, (
                f"{p} still returns JSON ({ctype}) — old API route not moved"
            )


@pytest.mark.asyncio
async def test_old_super_admin_paths_no_longer_serve_json():
    """Same migration assertion for /super-admin/*."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        for p in ["/super-admin/segments", "/super-admin/dashboard",
                  "/super-admin/notification-rules", "/super-admin/experiments"]:
            r = await ac.get(p)
            assert r.status_code in (200, 404, 503)
            ctype = r.headers.get("content-type", "")
            assert "application/json" not in ctype or r.status_code == 503, (
                f"{p} still returns JSON — old API route not moved"
            )


@pytest.mark.asyncio
async def test_old_public_paths_404():
    """/public/* is gone — it was only ever consumed by our React frontend.
    Anyone who hits the old path gets a clean 404."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r = await ac.get("/public/categories")
    # Should NOT be 200 — old endpoint removed.
    assert r.status_code in (404, 405), (
        f"/public/categories still returns {r.status_code} — old route not removed"
    )


@pytest.mark.asyncio
async def test_guides_hub_still_serves_html():
    """The /guides hub is fully data-independent — pure in-memory dict +
    Jinja2. If THIS breaks, the SEO surface is broken; the namespace
    migration would have nothing to do with it."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r = await ac.get("/guides")
    assert r.status_code == 200
    assert "text/html" in r.headers.get("content-type", "")


def test_seo_db_dependent_routes_are_registered():
    """For DB-touching SEO routes (/reading-rooms/{city}, etc.), assert
    that the routes are still registered in the app — the same
    introspection approach as for /api/public/*."""
    registered = {r.path for r in app.routes if hasattr(r, "path")}
    expected = {
        "/reading-rooms/{city_slug}",
        "/reading-rooms/{city_slug}/{locality_slug}",
        "/pgs/{city_slug}",
        "/listing/{category}/{slug}",
    }
    missing = expected - registered
    assert not missing, f"SEO routes missing from registration: {missing}"


@pytest.mark.asyncio
async def test_sitemap_robots_llms_still_work():
    """SEO infrastructure at the root path must NOT have moved."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        for p in ["/robots.txt", "/sitemap.xml", "/llms.txt"]:
            r = await ac.get(p)
            assert r.status_code == 200, f"{p} returned {r.status_code}"


@pytest.mark.asyncio
async def test_no_collision_api_with_spa_prefix():
    """A request to /api/owner/foo (a sub-path that doesn't exist on the
    backend) must still 404 with JSON — NOT fall through to the SPA. This
    confirms the SPA fallback is below /api/* in the route table."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r = await ac.get("/api/owner/this-endpoint-does-not-exist")
    assert r.status_code == 404
    # JSON detail, not HTML SPA shell
    assert "text/html" not in r.headers.get("content-type", ""), (
        "Unknown /api/* path leaked through to the SPA fallback"
    )
