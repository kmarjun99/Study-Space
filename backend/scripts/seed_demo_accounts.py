"""Seed two known-credential demo accounts so login works without OTP.

Idempotent: existing accounts get their password reset to the canonical
demo value so the credentials in this file always work.

Run:
    python backend/scripts/seed_demo_accounts.py
"""
from __future__ import annotations

import asyncio
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select
from app.core.security import get_password_hash
from app.database import AsyncSessionLocal
from app.models.user import User, UserRole, VerificationStatus


DEMO_ACCOUNTS = [
    {
        "email": "demo.student@myspaceapp.in",
        "password": "Student@123",
        "name": "Demo Student",
        "role": UserRole.STUDENT,
        "phone": "+919000000001",
    },
    {
        "email": "demo.owner@myspaceapp.in",
        "password": "Owner@123",
        "name": "Demo Owner",
        "role": UserRole.ADMIN,        # owners use the ADMIN role in this codebase
        "phone": "+919000000002",
    },
]


async def run() -> None:
    async with AsyncSessionLocal() as db:
        for acct in DEMO_ACCOUNTS:
            existing = (await db.execute(
                select(User).where(User.email == acct["email"])
            )).scalar_one_or_none()
            if existing is not None:
                # Reset password + role so the credentials below always work.
                existing.hashed_password = get_password_hash(acct["password"])
                existing.role = acct["role"]
                existing.name = acct["name"]
                existing.phone = acct["phone"]
                existing.verification_status = VerificationStatus.VERIFIED
                action = "updated"
            else:
                db.add(User(
                    id=str(uuid.uuid4()),
                    email=acct["email"],
                    hashed_password=get_password_hash(acct["password"]),
                    name=acct["name"],
                    role=acct["role"],
                    phone=acct["phone"],
                    verification_status=VerificationStatus.VERIFIED,
                ))
                action = "created"
            print(f"  ✓ {action}: {acct['email']:38s} role={acct['role'].value}")
        await db.commit()

    print()
    print("=" * 68)
    print("DEMO LOGIN CREDENTIALS")
    print("=" * 68)
    for a in DEMO_ACCOUNTS:
        print(f"  {a['role'].value:11s}  email: {a['email']}")
        print(f"               password: {a['password']}")
    print("=" * 68)


if __name__ == "__main__":
    asyncio.run(run())
