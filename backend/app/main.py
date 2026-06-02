
from fastapi import FastAPI, Depends, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.core.config import settings
from app.database import engine, Base
# from app.database import engine, Base # Duplicate removed
from app.routers import auth, reading_rooms, cabins, bookings, accommodations, waitlist, ads, ad_categories, locations, admin_cities, users, reviews, inquiries, trust, payments, reset, invoices, boost, cache, subscriptions, favorites, razorpay, otp, venue_payments, messages, notifications, admin_migration, admin_system, upload, upload
from app.routers import owner_billing, webhooks_razorpay, tax_config as tax_config_router, settlements as settlements_router, listing_billing, tax_preview, super_admin_kyc, support_tickets
from app.models.inquiry import Inquiry  # Ensure table is created
from app.models.trust_flag import TrustFlag  # Ensure trust tables are created
from app.models.reminder import Reminder
from app.models.audit_log import AuditLog
from app.models.invoice import Invoice  # Invoice model for PDF generation
# Ensure new accounting tables are registered with Base.metadata.create_all
from app.models import (
    ChartOfAccounts, LedgerEntry, TaxConfig, TaxSnapshot, Party,
    WebhookEvent, InvoiceSeriesCounter, OwnerCharge,
    SupportTicket,
)
from app.middleware.security import (
    SecurityHeadersMiddleware,
    RateLimitMiddleware,
    InputValidationMiddleware,
    setup_cors
)
from typing import List
import traceback

app = FastAPI(title="mySpace Manager API")

# Security Middleware (Add before CORS)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RateLimitMiddleware, requests_per_minute=300)  # Increased for development
app.add_middleware(InputValidationMiddleware)


# CORS - Security: Only allow specific origins (NO wildcards).
# Defined ABOVE the exception handler so the handler can validate the
# request's Origin header against this list before echoing it on a 500.
origins = [
    # Development
    "http://localhost:3000",
    "http://localhost:5173",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
    # Production domains
    "https://studyspace-frontend.onrender.com",
    "https://studyspace-backend.onrender.com",
    "https://studyspaceapp.in",
    "https://www.studyspaceapp.in",
    "https://api.studyspaceapp.in",
    # GCP Cloud Run — stable URLs (project number: 1093245445801)
    "https://study-space-frontend-1093245445801.asia-south1.run.app",
    "https://study-space-backend-1093245445801.asia-south1.run.app",
    "https://study-space-frontend-krjaarqoxq-el.a.run.app",
    # Custom domain
    "https://myspaceapp.in",
    "https://www.myspaceapp.in",
]

# Append any extra origins from CORS_ORIGINS env var (comma-separated).
if settings.CORS_ORIGINS:
    extra = [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]
    origins.extend(extra)


# Global Exception Handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    print(f"Global Exception: {exc}")
    traceback.print_exc()

    # Build a structured chain of the exception + every __cause__ /
    # __context__ that led to it. SQLAlchemy's 7s2a error wraps the
    # original flush failure under .__cause__, and DevTools truncates
    # str(exc) when displayed in the console — but the original cause
    # is what actually points at the bug (constraint name, missing
    # column, etc.). Surfacing the chain here means every 500 carries
    # its own root-cause regardless of which route threw.
    chain: list[dict] = []
    seen: set[int] = set()
    cur: BaseException | None = exc
    while cur is not None and id(cur) not in seen and len(chain) < 6:
        seen.add(id(cur))
        chain.append({
            "type": type(cur).__name__,
            "module": type(cur).__module__,
            "message": str(cur),
        })
        # Prefer the chained "raise X from Y" cause; fall back to the
        # implicit __context__ that's set when an exception is raised
        # inside an except block.
        cur = cur.__cause__ or cur.__context__

    # CORS for 500s: only echo the request Origin if it's in our allow
    # list AND a credential-using cross-origin request. Previously this
    # set Access-Control-Allow-Origin: "*" + Allow-Credentials: "true",
    # which the browser REJECTS per the CORS spec — making the response
    # body unreadable to JavaScript. That's why every previous attempt
    # to read the error detail from the network showed an empty body.
    request_origin = request.headers.get("origin")
    response_headers: dict[str, str] = {}
    if request_origin and request_origin in origins:
        response_headers["Access-Control-Allow-Origin"] = request_origin
        response_headers["Access-Control-Allow-Credentials"] = "true"
        # Vary tells caches/CDNs that response varies by Origin.
        response_headers["Vary"] = "Origin"

    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal Server Error",
            "error": str(exc),
            "exception_chain": chain,
            "path": request.url.path,
        },
        headers=response_headers,
    )


app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Health check endpoint for Render / Cloud Run.
#
# Includes BUILD_SHA so operators can compare what's running against the
# latest commit on the branch. Cloud Build sets COMMIT_SHA at build time
# (we wire it into the image as an env var BUILD_SHA in cloudbuild.yaml),
# so `curl /health | grep build_sha` is the one-shot way to confirm a
# deploy actually replaced the running container. The default "unknown"
# leaks no information when run locally.
import os as _os
_BUILD_SHA = _os.getenv("BUILD_SHA", "unknown")
_BUILD_TIME = _os.getenv("BUILD_TIME", "unknown")

@app.get("/health")
async def health_check():
    """Health check endpoint for deployment platforms"""
    return {
        "status": "healthy",
        "service": "mySpace API",
        "environment": settings.ENVIRONMENT if hasattr(settings, 'ENVIRONMENT') else "unknown",
        "build_sha": _BUILD_SHA,
        "build_time": _BUILD_TIME,
    }

# Include Routers
app.include_router(auth.router)

# SEO content router MUST be mounted before reading_rooms / accommodations,
# because both legacy routers expose /{id} patterns that would otherwise
# shadow the SEO content routes /reading-rooms/{city_slug} and
# /pgs/{city_slug}. FastAPI matches by registration order; the first match
# wins. The shared `/reading-rooms`-prefixed shape is intentional — search
# engines + AI crawlers expect the category in the URL.
from app.routers import seo_content as seo_content_router
app.include_router(seo_content_router.router)

app.include_router(reading_rooms.router)
app.include_router(cabins.router)
app.include_router(bookings.router)
app.include_router(accommodations.router)

# Same routers ALSO mounted under /api/* so the React app can hit them
# without colliding with the Jinja2 SEO routes that own /reading-rooms/{city},
# /pgs/{city}, etc. for browser-facing URLs. Both registrations point at the
# same handler functions — no duplication of business logic.
app.include_router(reading_rooms.router, prefix="/api")
app.include_router(cabins.router, prefix="/api")
app.include_router(bookings.router, prefix="/api")
app.include_router(accommodations.router, prefix="/api")
app.include_router(waitlist.router)
app.include_router(ads.router)
app.include_router(ad_categories.router)  # Dynamic Ad Categories
app.include_router(locations.router)  # Location Search & Autocomplete
app.include_router(admin_cities.router)
# Trigger Reload
app.include_router(users.router)
app.include_router(reviews.router)
app.include_router(favorites.router)
app.include_router(inquiries.router)
app.include_router(trust.router)  # Trust & Safety
app.include_router(payments.router)  # Payments & Refunds
app.include_router(razorpay.router)  # Razorpay Payment Gateway
app.include_router(otp.router)  # OTP & Password Reset
app.include_router(reset.router)  # Admin Database Reset
app.include_router(invoices.router)  # Invoice PDF Generation
app.include_router(boost.router)  # Boost Plans & Requests
app.include_router(subscriptions.router)  # Subscription Plans for Venue Listings
app.include_router(venue_payments.router)  # Venue Subscription Payments
app.include_router(messages.router)  # Messaging between users and owners
# Also expose under /api/* so production deployments whose load balancer only
# proxies /api/* to the backend (and serves the SPA from the frontend service
# for everything else) reach the same handlers. The root mount above stays for
# backward compatibility with existing callers.
app.include_router(messages.router, prefix="/api")
app.include_router(notifications.router)  # Notifications system
app.include_router(upload.router)  # File uploads (images)
app.include_router(cache.router)  # Cache Management (Super Admin)
app.include_router(admin_migration.router)  # Admin Migration Tools
app.include_router(admin_system.router)  # System Migrations & Diagnostics

# =====================================================================
# /api/* NAMESPACE — all backend API routers below are mounted under
# /api/* so they don't collide with the SPA prefixes /owner/*,
# /super-admin/*, /admin/*, /student/* and friends. The Jinja2 SEO
# content router (registered earlier, before reading_rooms) is the
# canonical owner of /owner/insights, /reading-rooms/kochi, etc. for
# *browser* requests. The /api/* equivalents return JSON.
#
# Why no redirects: a browser hitting /owner/insights now falls through
# to the SPA fallback → React loads → React's service calls
# /api/owner/insights for data. That's the correct architecture.
# External JSON consumers that used the old paths must be updated.
# =====================================================================

# ---- Transaction Flow: owner billing + GST-aware webhooks + tax config ----
app.include_router(owner_billing.router, prefix="/api")
app.include_router(webhooks_razorpay.router)  # Razorpay webhooks — external, do NOT namespace
app.include_router(tax_config_router.router, prefix="/api")
app.include_router(settlements_router.router, prefix="/api")
app.include_router(listing_billing.router, prefix="/api")
app.include_router(tax_preview.router, prefix="/api")
app.include_router(super_admin_kyc.router, prefix="/api")
# Owner self-service KYC submission (the counterpart to super_admin_kyc's
# review queue). Mounted under /api so the SPA reaches /api/owner/kyc.
from app.routers import owner_kyc as owner_kyc_router
app.include_router(owner_kyc_router.router, prefix="/api")
app.include_router(support_tickets.router, prefix="/api")
from app.routers import ledger as ledger_router
app.include_router(ledger_router.router, prefix="/api")

# Phase 1 intelligence: event firehose + consent management.
from app.routers import events as events_router, consent as consent_router
app.include_router(events_router.router, prefix="/api")
app.include_router(consent_router.router, prefix="/api")

# Phase 2 intelligence: derived profile + intent.
from app.routers import intelligence as intelligence_router
app.include_router(intelligence_router.router, prefix="/api")

# Phase 3 intelligence: rule-based recommendations.
from app.routers import recommendations as recommendations_router
app.include_router(recommendations_router.router, prefix="/api")

# Phase 4A intelligence: rule-based segments.
from app.routers import segments as segments_router
app.include_router(segments_router.router, prefix="/api")

# Phase 4B intelligence: campaigns + attribution.
from app.routers import campaigns as campaigns_router
app.include_router(campaigns_router.router, prefix="/api")

# Phase 4C intelligence: notification automation.
from app.routers import notification_rules as notification_rules_router
app.include_router(notification_rules_router.router, prefix="/api")

# Phase 4D intelligence: recommendation attribution.
from app.routers import recommendation_attribution as reco_attribution_router
app.include_router(reco_attribution_router.router, prefix="/api")

# Phase 5 intelligence: owner insights + super-admin dashboard.
from app.routers import owner_insights as owner_insights_router
from app.routers import admin_dashboard as admin_dashboard_router
app.include_router(owner_insights_router.router, prefix="/api")
app.include_router(admin_dashboard_router.router, prefix="/api")

# Phase 6 intelligence: experiments + cohorts + ML feature export.
from app.routers import experiments as experiments_router
app.include_router(experiments_router.router, prefix="/api")

# SEO surface — robots.txt + sitemap index + child sitemaps.
# Do NOT namespace under /api — these live at the root by convention
# (Google + AI crawlers look for /robots.txt and /sitemap.xml).
from app.routers import seo as seo_router
app.include_router(seo_router.router)

# Public read-only API for SEO-indexed pages (no auth).
# Namespaced under /api so the React SEO frontend calls /api/public/*.
from app.routers import public as public_router
app.include_router(public_router.router, prefix="/api")

# SEO content router was registered above (before reading_rooms) so its
# /reading-rooms/{city_slug} routes match before the legacy /{room_id} route.

# On-the-fly image transform (resize + WebP/AVIF + on-disk cache).
# Reachable at /img/{path}?w=...&h=...&fmt=...&q=...
from app.routers import img as img_router
app.include_router(img_router.router)

# Mount static files for uploads (original-size files; transforms are at /img)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# SPA fallback router — MUST be registered LAST. Serves the React build's
# index.html for known SPA prefixes (/student/, /admin/, /super-admin/,
# /owner/, /dashboard/, /auth, /login, /register, /mock-payment), serves
# Vite's fingerprinted assets from /assets/*, and returns a hard 404 for
# anything else so unknown public-SEO URLs don't get shadowed by an empty
# React shell. See routers/spa_fallback.py for the full classification
# table.
from app.routers import spa_fallback as spa_fallback_router
app.include_router(spa_fallback_router.router)

# Database Tables Creation (For simple setup)
@app.on_event("startup")
async def startup():
    """Initialize database and create tables on startup"""
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        print("✅ Database tables created/verified")
    except Exception as e:
        print(f"⚠️  Database connection failed: {e}")
        print("ℹ️  App will start but database operations will fail until DATABASE_URL is configured")
        return  # Exit startup gracefully if DB not available
    
    # Run booking duration migration
    try:
        from sqlalchemy import text
        from app.database import AsyncSessionLocal
        
        print("🔄 Running booking duration configuration migration...")
        async with AsyncSessionLocal() as db:
            # Add columns to reading_rooms
            await db.execute(text("""
                ALTER TABLE reading_rooms 
                ADD COLUMN IF NOT EXISTS allowed_booking_durations TEXT DEFAULT '["1_MONTH"]'
            """))
            
            await db.execute(text("""
                ALTER TABLE reading_rooms 
                ADD COLUMN IF NOT EXISTS duration_prices TEXT DEFAULT NULL
            """))
            
            # Add duration_type to bookings
            await db.execute(text("""
                ALTER TABLE bookings 
                ADD COLUMN IF NOT EXISTS duration_type VARCHAR(20) DEFAULT '1_MONTH'
            """))
            
            # Set default duration configuration for existing venues using their base price
            # This query sets 1_MONTH as enabled with price_start as the default price
            await db.execute(text("""
                UPDATE reading_rooms 
                SET 
                    allowed_booking_durations = '["1_MONTH"]',
                    duration_prices = json_build_object('1_MONTH', COALESCE(price_start, 3000))::text
                WHERE duration_prices IS NULL OR duration_prices = 'null'
            """))
            
            await db.commit()
            print("✅ Booking duration migration completed!")
    except Exception as e:
        print(f"⚠️  Duration migration warning: {e}")
        # Continue even if migration fails (columns might already exist)
    
    # Auto-create admin user if it doesn't exist
    from app.database import AsyncSessionLocal
    from app.models.user import User, UserRole, VerificationStatus
    from app.core.security import get_password_hash
    from sqlalchemy.future import select
    
    try:
        async with AsyncSessionLocal() as db:
            try:
                # Check if admin user exists
                result = await db.execute(
                    select(User).where(User.email == "admin@studyspace.com")
                )
                admin_user = result.scalars().first()
                
                if not admin_user:
                    # Create admin user
                    new_admin = User(
                        email="superadmin@studyspace.com",
                        hashed_password=get_password_hash("superadmin123"),
                        name="Super Admin",
                        role=UserRole.SUPER_ADMIN,
                        phone="9876543210",
                        verification_status=VerificationStatus.VERIFIED
                    )
                    db.add(new_admin)
                    await db.commit()
                    print("✅ Admin user created: superadmin@studyspace.com")
                else:
                    print("ℹ️  Admin user already exists")
            except Exception as e:
                print(f"⚠️  Could not create admin user: {e}")
    except Exception as e:
        print(f"⚠️  Database session failed: {e}")
    
    # Start APScheduler (accounting jobs: cabin hold expiry, monthly fees,
    # dunning, ledger integrity check). Safe to call multiple times.
    try:
        from app.services.scheduler import start_scheduler
        start_scheduler()
        print("✅ APScheduler started (accounting jobs registered)")
    except Exception as sched_err:
        print(f"⚠️  Scheduler failed to start: {sched_err}")

    # Auto-fix HELD bookings on startup (Financial reports fix)
    try:
        async with AsyncSessionLocal() as db:
            try:
                from app.models.booking import Booking, BookingStatus, PaymentStatus
                from app.models.payment_transaction import PaymentTransaction, PaymentMethod, PaymentGateway, PaymentType
                from app.models.reading_room import Cabin, CabinStatus
                
                # Find all HELD bookings
                result = await db.execute(
                    select(Booking).where(Booking.status == BookingStatus.HELD)
                )
                held_bookings = result.scalars().all()
                
                if held_bookings:
                    print(f"🔧 Found {len(held_bookings)} HELD booking(s) to fix...")
                    
                    for booking in held_bookings:
                        # Update booking status
                        booking.status = BookingStatus.ACTIVE
                        booking.payment_status = PaymentStatus.PAID
                        if not booking.transaction_id:
                            booking.transaction_id = f"auto_fix_{booking.id[:8]}"
                        
                        # Check if PaymentTransaction already exists
                        tx_result = await db.execute(
                            select(PaymentTransaction).where(
                                PaymentTransaction.booking_id == booking.id
                            )
                        )
                        existing_tx = tx_result.scalar_one_or_none()
                        
                        if not existing_tx:
                            # Create PaymentTransaction record
                            payment_tx = PaymentTransaction(
                                booking_id=booking.id,
                                user_id=booking.user_id,
                                payment_type=PaymentType.INITIAL,
                                method=PaymentMethod.UPI,
                                gateway=PaymentGateway.RAZORPAY,
                                amount=booking.amount,
                                gateway_transaction_id=booking.transaction_id,
                                description="Auto-fixed on startup"
                            )
                            db.add(payment_tx)
                        
                        # Update cabin status
                        if booking.cabin_id:
                            cabin_result = await db.execute(
                                select(Cabin).where(Cabin.id == booking.cabin_id)
                            )
                            cabin = cabin_result.scalar_one_or_none()
                            if cabin:
                                cabin.status = CabinStatus.OCCUPIED
                                cabin.current_occupant_id = booking.user_id
                    
                    await db.commit()
                    print(f"✅ Fixed {len(held_bookings)} HELD booking(s) - Financial reports updated!")
            except Exception as e:
                print(f"⚠️  Could not fix HELD bookings: {e}")
    except Exception as e:
        print(f"⚠️  Database session failed during HELD bookings fix: {e}")

from app.core.socket_manager import manager

@app.websocket("/ws/cabins")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            # We can process incoming messages if needed
            # await manager.broadcast(f"Client says: {data}")
    except WebSocketDisconnect:
        manager.disconnect(websocket)

@app.websocket("/ws/messages/{user_id}")
async def message_websocket_endpoint(websocket: WebSocket, user_id: str):
    """WebSocket endpoint for real-time messaging"""
    await manager.connect_user(user_id, websocket)
    try:
        while True:
            # Keep connection alive and receive any client messages
            data = await websocket.receive_text()
            # Could handle ping/pong or other client messages here
    except WebSocketDisconnect:
        manager.disconnect_user(user_id, websocket)

# Reload 2 
