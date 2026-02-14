"""
Seed subscription plans for venue listings
"""
import sqlite3
import uuid
from datetime import datetime

def main():
    conn = sqlite3.connect('study_space.db')
    cursor = conn.cursor()
    
    try:
        # Check if table exists
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='subscription_plans'
        """)
        if not cursor.fetchone():
            print("Creating subscription_plans table...")
            cursor.execute("""
                CREATE TABLE subscription_plans (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT,
                    price REAL NOT NULL,
                    duration_days INTEGER NOT NULL,
                    features TEXT,
                    is_active BOOLEAN DEFAULT 1,
                    is_default BOOLEAN DEFAULT 0,
                    created_by TEXT,
                    created_at TEXT,
                    updated_at TEXT
                )
            """)
            conn.commit()
            print("✅ Created subscription_plans table")
        
        # Delete existing plans
        cursor.execute('DELETE FROM subscription_plans')
        print("Cleared existing subscription plans")
        
        # Insert new subscription plans
        plans = [
            (
                str(uuid.uuid4()), 
                'Basic Plan', 
                'Get your venue listed for 30 days', 
                499.0, 
                30, 
                '["Basic listing visibility", "Property showcase", "Contact information display", "30 days validity"]',
                1, 
                1,  # is_default
                'super_admin', 
                datetime.utcnow().isoformat(),
                datetime.utcnow().isoformat()
            ),
            (
                str(uuid.uuid4()), 
                'Standard Plan', 
                'Enhanced visibility for 60 days', 
                899.0, 
                60, 
                '["Enhanced listing visibility", "Property showcase", "Contact information display", "Priority in search results", "60 days validity"]',
                1, 
                0,
                'super_admin', 
                datetime.utcnow().isoformat(),
                datetime.utcnow().isoformat()
            ),
            (
                str(uuid.uuid4()), 
                'Premium Plan', 
                'Maximum visibility for 90 days', 
                1299.0, 
                90, 
                '["Maximum visibility", "Featured listing badge", "Top position in search", "Property showcase", "Contact information display", "90 days validity", "Analytics dashboard"]',
                1, 
                0,
                'super_admin', 
                datetime.utcnow().isoformat(),
                datetime.utcnow().isoformat()
            ),
        ]
        
        for plan in plans:
            cursor.execute('''
                INSERT INTO subscription_plans 
                (id, name, description, price, duration_days, features, is_active, is_default, created_by, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', plan)
        
        conn.commit()
        print(f"✅ Created {len(plans)} subscription plans!")
        
        # Verify
        cursor.execute('SELECT name, price, duration_days, is_active, is_default FROM subscription_plans ORDER BY price')
        rows = cursor.fetchall()
        print(f"\nSubscription Plans in database ({len(rows)}):")
        for row in rows:
            default_badge = " [DEFAULT]" if row[4] else ""
            print(f"  - {row[0]}: ₹{row[1]} for {row[2]} days (Active: {bool(row[3])}){default_badge}")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    main()
