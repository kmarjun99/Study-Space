
from fastapi import FastAPI, Depends, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.database import engine, Base
# from app.database import engine, Base # Duplicate removed
from app.routers import auth, reading_rooms, cabins, bookings, accommodations, waitlist, ads, ad_categories, locations, admin_cities, users, reviews, inquiries, trust, payments, reset, invoices, boost, cache, subscriptions, favorites, razorpay, otp, venue_payments, messages, notifications
from app.models.inquiry import Inquiry  # Ensure table is created
from app.models.trust_flag import TrustFlag  # Ensure trust tables are created
from app.models.reminder import Reminder
from app.models.audit_log import AuditLog
from app.models.invoice import Invoice  # Invoice model for PDF generation
from app.middleware.security import (
    SecurityHeadersMiddleware,
    RateLimitMiddleware,
    InputValidationMiddleware,
    setup_cors
)
from typing import List
import traceback

app = FastAPI(title="StudySpace Manager API")

# Security Middleware (Add before CORS)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RateLimitMiddleware, requests_per_minute=300)  # Increased for development
app.add_middleware(InputValidationMiddleware)

# Global Exception Handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    print(f"Global Exception: {exc}")
    traceback.print_exc()
    # Add CORS headers to error responses
    origin = request.headers.get("origin", "*")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal Server Error", "error": str(exc)},
        headers={
            "Access-Control-Allow-Origin": origin,
            "Access-Control-Allow-Credentials": "true",
            "Access-Control-Allow-Methods": "*",
            "Access-Control-Allow-Headers": "*",
        }
    )



# CORS
origins = [
    "http://localhost:3000",
    "http://localhost:5173",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
    "http://localhost:3001",
    "http://localhost:3002",
    "http://127.0.0.1:3001",
    "http://127.0.0.1:3002",
    "http://192.168.29.177:3000",
    "http://192.168.29.177:5173",
    # Production domains
    "https://studyspace-frontend.onrender.com",
    "https://studyspace-backend.onrender.com",
    "https://studyspaceapp.in",
    "https://www.studyspaceapp.in",
    "https://api.studyspaceapp.in",
    "*"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Health check endpoint for Render
@app.get("/health")
async def health_check():
    """Health check endpoint for deployment platforms"""
    return {
        "status": "healthy",
        "service": "StudySpace API",
        "environment": settings.ENVIRONMENT if hasattr(settings, 'ENVIRONMENT') else "unknown"
    }

# Include Routers
app.include_router(auth.router)
app.include_router(reading_rooms.router)
app.include_router(cabins.router)
app.include_router(bookings.router)
app.include_router(accommodations.router)
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
app.include_router(notifications.router)  # Notifications system
app.include_router(cache.router)  # Cache Management (Super Admin)
# Database Tables Creation (For simple setup)
@app.on_event("startup")
async def startup():
    from sqlalchemy import text
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
        # Create pending_registrations table if it doesn't exist
        # This is needed for the OTP-first registration flow
        try:
            await conn.execute(text("""
                CREATE TABLE IF NOT EXISTS pending_registrations (
                    id VARCHAR PRIMARY KEY DEFAULT gen_random_uuid()::text,
                    email VARCHAR NOT NULL UNIQUE,
                    hashed_password VARCHAR NOT NULL,
                    name VARCHAR NOT NULL,
                    role VARCHAR NOT NULL,
                    phone VARCHAR,
                    avatar_url VARCHAR,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    expires_at TIMESTAMP WITH TIME ZONE NOT NULL
                );
            """))
            
            await conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_pending_registrations_email 
                ON pending_registrations(email);
            """))
            
            print("✅ pending_registrations table verified/created")
        except Exception as e:
            print(f"⚠️  Could not create pending_registrations table: {e}")
        
        # Clean up expired pending registrations
        try:
            result = await conn.execute(text("""
                DELETE FROM pending_registrations WHERE expires_at < NOW()
            """))
            deleted_count = result.rowcount
            if deleted_count > 0:
                print(f"🧹 Cleaned up {deleted_count} expired pending registrations")
        except Exception as e:
            print(f"⚠️  Could not clean up expired registrations: {e}")
    
    # Auto-create admin user if it doesn't exist
    from app.database import AsyncSessionLocal
    from app.models.user import User, UserRole, VerificationStatus
    from app.core.security import get_password_hash
    from sqlalchemy.future import select
    
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
                print("✅ Admin user created: admin@studyspace.com (Password: admin123)")
            else:
                print("ℹ️  Admin user already exists")
        except Exception as e:
            print(f"⚠️  Could not create admin user: {e}")

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
# Reload 2 
