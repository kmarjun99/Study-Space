#!/usr/bin/env python3
"""
Fix Ad Images with Blob URLs
This script updates ads in the database that have blob: URLs with a default placeholder.
"""

import os
import sys
from sqlalchemy import create_engine, text

# Get database URL from environment or use default
DATABASE_URL = os.getenv('DATABASE_URL')

if not DATABASE_URL:
    print("❌ DATABASE_URL environment variable not set")
    print("Usage: export DATABASE_URL='your-database-url' && python fix_blob_ad_images.py")
    sys.exit(1)

# Default placeholder image for ads
DEFAULT_AD_IMAGE = "https://images.unsplash.com/photo-1557804506-669a67965ba0?auto=format&fit=crop&w=800&q=80"

def fix_blob_urls():
    """Update ads with blob URLs to use placeholder image"""
    engine = create_engine(DATABASE_URL)
    
    with engine.connect() as conn:
        # Start transaction
        trans = conn.begin()
        
        try:
            # Find all ads with blob URLs
            result = conn.execute(text("""
                SELECT id, title, image_url 
                FROM ads 
                WHERE image_url LIKE 'blob:%'
            """))
            
            blob_ads = result.fetchall()
            
            if not blob_ads:
                print("✅ No ads with blob URLs found!")
                return
            
            print(f"Found {len(blob_ads)} ads with blob URLs:\n")
            
            for ad in blob_ads:
                print(f"  • {ad.title} (ID: {ad.id})")
                print(f"    Old: {ad.image_url[:60]}...")
            
            print(f"\n⚠️  These ads will be updated with a placeholder image:")
            print(f"  {DEFAULT_AD_IMAGE}")
            
            response = input("\nProceed with update? (yes/no): ").lower().strip()
            
            if response != 'yes':
                print("❌ Operation cancelled")
                trans.rollback()
                return
            
            # Update all blob URLs
            update_result = conn.execute(
                text("""
                    UPDATE ads 
                    SET image_url = :placeholder 
                    WHERE image_url LIKE 'blob:%'
                """),
                {"placeholder": DEFAULT_AD_IMAGE}
            )
            
            trans.commit()
            
            print(f"\n✅ Successfully updated {update_result.rowcount} ads!")
            print("\n📝 Next steps:")
            print("  1. Log in to Super Admin panel")
            print("  2. Go to 'Ad Campaigns' section")
            print("  3. Edit each ad and add proper image URLs from:")
            print("     • https://imgur.com/upload")
            print("     • https://unsplash.com")
            print("     • Or any direct image URL")
            
        except Exception as e:
            trans.rollback()
            print(f"\n❌ Error: {e}")
            sys.exit(1)

if __name__ == "__main__":
    print("=" * 60)
    print("🔧 Fix Ad Images with Blob URLs")
    print("=" * 60)
    fix_blob_urls()
