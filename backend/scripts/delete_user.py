"""
Delete User from Database
Usage: python delete_user.py
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.database import async_session_maker
from app.models.user import User


async def list_users():
    """List all users in the database"""
    async with async_session_maker() as session:
        result = await session.execute(select(User))
        users = result.scalars().all()
        
        if not users:
            print("❌ No users found in database")
            return []
        
        print("\n" + "="*80)
        print("📋 USERS IN DATABASE")
        print("="*80)
        print(f"{'#':<4} {'ID':<38} {'Email':<35} {'Name':<20} {'Role':<15}")
        print("-"*80)
        
        for idx, user in enumerate(users, 1):
            print(f"{idx:<4} {user.id:<38} {user.email:<35} {user.name:<20} {user.role:<15}")
        
        print("="*80 + "\n")
        return users


async def delete_user_by_email(email: str):
    """Delete user by email address"""
    async with async_session_maker() as session:
        result = await session.execute(select(User).where(User.email == email))
        user = result.scalars().first()
        
        if not user:
            print(f"❌ User with email '{email}' not found")
            return False
        
        print(f"\n⚠️  Found user:")
        print(f"   ID: {user.id}")
        print(f"   Email: {user.email}")
        print(f"   Name: {user.name}")
        print(f"   Role: {user.role}")
        
        confirm = input(f"\n⚠️  Are you sure you want to DELETE this user? (yes/no): ")
        
        if confirm.lower() == 'yes':
            await session.delete(user)
            await session.commit()
            print(f"✅ User '{email}' deleted successfully!")
            return True
        else:
            print("❌ Deletion cancelled")
            return False


async def delete_user_by_id(user_id: str):
    """Delete user by ID"""
    async with async_session_maker() as session:
        result = await session.execute(select(User).where(User.id == user_id))
        user = result.scalars().first()
        
        if not user:
            print(f"❌ User with ID '{user_id}' not found")
            return False
        
        print(f"\n⚠️  Found user:")
        print(f"   ID: {user.id}")
        print(f"   Email: {user.email}")
        print(f"   Name: {user.name}")
        print(f"   Role: {user.role}")
        
        confirm = input(f"\n⚠️  Are you sure you want to DELETE this user? (yes/no): ")
        
        if confirm.lower() == 'yes':
            await session.delete(user)
            await session.commit()
            print(f"✅ User '{user.email}' deleted successfully!")
            return True
        else:
            print("❌ Deletion cancelled")
            return False


async def delete_all_users():
    """Delete ALL users (DANGEROUS!)"""
    async with async_session_maker() as session:
        result = await session.execute(select(User))
        users = result.scalars().all()
        
        if not users:
            print("❌ No users found in database")
            return False
        
        print(f"\n⚠️  WARNING: This will delete ALL {len(users)} users from the database!")
        for user in users:
            print(f"   - {user.email} ({user.name})")
        
        confirm = input(f"\n⚠️  Type 'DELETE ALL USERS' to confirm: ")
        
        if confirm == 'DELETE ALL USERS':
            for user in users:
                await session.delete(user)
            await session.commit()
            print(f"✅ All {len(users)} users deleted successfully!")
            return True
        else:
            print("❌ Deletion cancelled")
            return False


async def main():
    print("\n" + "="*80)
    print("🗑️  DELETE USER FROM DATABASE")
    print("="*80)
    
    # Show all users
    users = await list_users()
    
    if not users:
        return
    
    print("Choose an option:")
    print("1. Delete user by email")
    print("2. Delete user by ID")
    print("3. Delete user by number (from list above)")
    print("4. Delete ALL users (⚠️  DANGEROUS)")
    print("5. Exit")
    
    choice = input("\nEnter your choice (1-5): ")
    
    if choice == "1":
        email = input("Enter user email: ")
        await delete_user_by_email(email)
        
    elif choice == "2":
        user_id = input("Enter user ID: ")
        await delete_user_by_id(user_id)
        
    elif choice == "3":
        try:
            num = int(input("Enter user number from list: "))
            if 1 <= num <= len(users):
                user = users[num - 1]
                await delete_user_by_email(user.email)
            else:
                print("❌ Invalid number")
        except ValueError:
            print("❌ Please enter a valid number")
    
    elif choice == "4":
        await delete_all_users()
        
    elif choice == "5":
        print("👋 Exiting...")
        
    else:
        print("❌ Invalid choice")


if __name__ == "__main__":
    asyncio.run(main())
