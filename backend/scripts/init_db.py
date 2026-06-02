#!/usr/bin/env python3
"""
Database initialization script - creates superuser and seeds initial data
Runs automatically when Docker container starts
"""

import asyncio
import json
import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import AsyncSessionLocal, engine, Base
from app.models.user import User, UserRole
from app.models.location import Location
from app.core.security import get_password_hash
from sqlalchemy.future import select
from sqlalchemy import text, func

CITIES_FILE = Path(__file__).parent.parent / "data" / "cities.json"


async def wait_for_db(max_retries=30, delay=2):
    """Wait for database to be ready"""
    print("Waiting for database to be ready...")
    for i in range(max_retries):
        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            print("✅ Database is ready!")
            return True
        except Exception as e:
            if i < max_retries - 1:
                print(f"Database not ready, retrying in {delay}s... ({i+1}/{max_retries})")
                await asyncio.sleep(delay)
            else:
                print(f"❌ Database connection failed after {max_retries} attempts")
                return False
    return False


async def create_tables():
    """Create all tables if they don't exist"""
    try:
        print("Creating database tables...")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        print("✅ Database tables created successfully")
        return True
    except Exception as e:
        print(f"❌ Error creating tables: {e}")
        return False


async def create_superuser():
    """Create default superuser if not exists"""
    try:
        async with AsyncSessionLocal() as db:
            # Check if superuser exists
            result = await db.execute(
                select(User).where(User.email == "superadmin@studyspace.com")
            )
            existing_user = result.scalars().first()
            
            if existing_user:
                print("ℹ️  Superuser already exists: superadmin@studyspace.com")
                return True
            
            # Create superuser
            print("Creating superuser...")
            superuser = User(
                email="superadmin@studyspace.com",
                hashed_password=get_password_hash("superadmin123"),
                name="Super Admin",
                role=UserRole.SUPER_ADMIN,
            )
            db.add(superuser)
            await db.commit()
            
            print("✅ Superuser created successfully!")
            print("=" * 50)
            print("Login Credentials:")
            print("Email: superadmin@studyspace.com")
            print("Password: superadmin123")
            print("=" * 50)
            print("⚠️  IMPORTANT: Change this password in production!")
            print("=" * 50)
            
            return True
            
    except Exception as e:
        print(f"❌ Error creating superuser: {e}")
        return False


async def seed_demo_users():
    """Seed additional demo users for testing"""
    try:
        async with AsyncSessionLocal() as db:
            demo_users = [
                {
                    "email": "admin@studyspace.com",
                    "password": "admin123",
                    "role": UserRole.ADMIN,
                    "name": "Admin User"
                },
                {
                    "email": "student1@studyspace.com",
                    "password": "student123",
                    "role": UserRole.STUDENT,
                    "name": "John Doe"
                },
            ]
            created_count = 0
            for user_data in demo_users:
                result = await db.execute(
                    select(User).where(User.email == user_data["email"])
                )
                if not result.scalars().first():
                    new_user = User(
                        email=user_data["email"],
                        hashed_password=get_password_hash(user_data["password"]),
                        name=user_data["name"],
                        role=user_data["role"],
                    )
                    db.add(new_user)
                    created_count += 1
            
            if created_count > 0:
                await db.commit()
                print(f"✅ Created {created_count} demo user(s)")
            else:
                print("ℹ️  Demo users already exist")
                
            return True
            
    except Exception as e:
        print(f"⚠️  Warning: Could not create demo users: {e}")
        return False


async def migrate_cabin_hold_columns():
    """Add hold-system columns to cabins table if missing (idempotent)."""
    try:
        async with engine.begin() as conn:
            for column, col_type in [
                ("held_by_user_id", "VARCHAR"),
                ("hold_expires_at", "VARCHAR"),
            ]:
                exists = await conn.scalar(
                    text(
                        "SELECT column_name FROM information_schema.columns "
                        "WHERE table_name='cabins' AND column_name=:col"
                    ),
                    {"col": column},
                )
                if not exists:
                    await conn.execute(
                        text(f"ALTER TABLE cabins ADD COLUMN {column} {col_type}")
                    )
                    print(f"✅ Added cabins.{column} column")
                else:
                    print(f"ℹ️  cabins.{column} already exists — skipping")
        return True
    except Exception as e:
        print(f"⚠️  Warning: Could not migrate cabin hold columns: {e}")
        return False


async def seed_locations():
    """Seed locations table from cities.json — skips if already populated."""
    try:
        if not CITIES_FILE.exists():
            print("⚠️  cities.json not found, skipping location seeding.")
            return True

        async with AsyncSessionLocal() as db:
            count_result = await db.execute(select(func.count()).select_from(Location))
            existing = count_result.scalar()

            if existing > 0:
                print(f"ℹ️  Locations already seeded ({existing} records). Skipping.")
                return True

            print("📍 Seeding locations from cities.json...")
            with open(CITIES_FILE, "r", encoding="utf-8") as f:
                cities = json.load(f)

            BATCH_SIZE = 500
            inserted = 0
            batch = []

            for city in cities:
                city_name = (city.get("city_name") or "").strip()
                state = (city.get("state") or "").strip()
                if not city_name or not state:
                    continue

                batch.append(Location(
                    country="India",
                    state=state,
                    city=city_name,
                    locality=None,
                    city_normalized=Location.normalize(city_name),
                    locality_normalized=None,
                    search_text=Location.create_search_text(city_name, state),
                    latitude=city.get("latitude"),
                    longitude=city.get("longitude"),
                    is_active=True,
                ))
                inserted += 1

                if len(batch) >= BATCH_SIZE:
                    db.add_all(batch)
                    await db.commit()
                    batch = []

            if batch:
                db.add_all(batch)
                await db.commit()

            print(f"✅ Seeded {inserted} locations successfully!")
            return True

    except Exception as e:
        print(f"⚠️  Warning: Could not seed locations: {e}")
        return False


async def _run_additive_migrations():
    """Run every standalone additive-column migration script in sequence.

    Each script's `run()` is idempotent (existence-checks every column before
    issuing ALTER TABLE), so re-running on every container boot is safe and
    cheap. A failure in one script is logged but does NOT abort the others —
    we'd rather have most columns added than block startup on a single
    rough script.
    """
    # Imported lazily so a missing module (e.g. a partial deploy) doesn't
    # break the import of init_db.py itself.
    migrations = [
        ("accounting / GST / KYC columns", "scripts.migrate_add_accounting_columns"),
        ("intelligence columns",           "scripts.migrate_intelligence_columns"),
        ("recommendation attribution",     "scripts.migrate_add_reco_attribution"),
        ("notification_rule_id column",    "scripts.migrate_add_notification_rule_id"),
        ("dispatch_attempts column",       "scripts.migrate_add_dispatch_attempts"),
        ("listing slugs",                  "scripts.migrate_add_listing_slugs"),
    ]
    for label, module_path in migrations:
        try:
            import importlib
            mod = importlib.import_module(module_path)
            run_fn = getattr(mod, "run", None)
            if run_fn is None:
                print(f"⚠️  {label}: module {module_path} has no run() — skipping")
                continue
            print(f"▶️  Running migration: {label}")
            await run_fn()
            print(f"✅ {label} done")
        except Exception as e:
            print(f"⚠️  {label} failed (continuing): {e}")


async def _run_seeds():
    """Seed reference data the accounting layer assumes is present.

    Each seed is idempotent (skip-existing pattern) and is safe to re-run on
    every container boot. Without these the super-admin Tax Config page is
    empty AND every `LedgerService.post_entries` call references account codes
    that don't exist in `chart_of_accounts`. We surface a loud line per seed
    so an operator scanning the boot log can verify the system is configured.
    """
    seeds = [
        ("chart of accounts (14 ledger account codes)",
         "scripts.seed_chart_of_accounts"),
        ("tax_config defaults (accounting.enabled, GST rates, feature flags)",
         "scripts.seed_tax_config"),
    ]
    for label, module_path in seeds:
        try:
            import importlib
            mod = importlib.import_module(module_path)
            run_fn = getattr(mod, "run", None)
            if run_fn is None:
                print(f"⚠️  {label}: module {module_path} has no run() — skipping")
                continue
            print(f"▶️  Seeding: {label}")
            await run_fn()
            print(f"✅ {label} done")
        except Exception as e:
            # Don't crash boot on seed failure — empty tables degrade the UI
            # (Quick Add becomes the only path) but won't break running queries.
            print(f"⚠️  {label} failed (continuing): {e}")


async def main():
    """Main initialization function"""
    print("\n" + "=" * 50)
    print("🚀 Starting Database Initialization")
    print("=" * 50 + "\n")
    
    # Wait for database
    if not await wait_for_db():
        print("\n❌ Database initialization failed - database not accessible")
        sys.exit(1)
    
    # Create tables
    if not await create_tables():
        print("\n❌ Database initialization failed - could not create tables")
        sys.exit(1)

    # Run incremental column migrations (safe to re-run — each script checks
    # for column existence before issuing ALTER TABLE). `create_all` above only
    # creates missing TABLES, never adds missing COLUMNS to existing tables,
    # so without these the prod DB drifts behind the ORM and ANY query against
    # a table whose model gained a column will 500.
    await migrate_cabin_hold_columns()
    await _run_additive_migrations()

    # Create superuser
    if not await create_superuser():
        print("\n❌ Database initialization failed - could not create superuser")
        sys.exit(1)
    
    # Seed demo users (optional, don't fail if this doesn't work)
    await seed_demo_users()

    # Seed locations from cities.json (skips if already done)
    await seed_locations()

    # Seed accounting reference data (chart_of_accounts + tax_config defaults).
    # Idempotent; safe to run on every container boot.
    await _run_seeds()

    print("\n" + "=" * 50)
    print("✅ Database Initialization Complete!")
    print("=" * 50 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
