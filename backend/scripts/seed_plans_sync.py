"""
Simple sync SQLite script to seed boost plans
"""
import sqlite3
import uuid
from datetime import datetime

def main():
    conn = sqlite3.connect('study_space.db')
    cursor = conn.cursor()
    
    try:
        # Delete existing plans
        cursor.execute('DELETE FROM boost_plans')
        print("Cleared existing plans")
        
        # Insert new plans
        plans = [
            (str(uuid.uuid4()), 'Featured Listing - 7 Days', 'Get your property featured for 7 days (₹499 + GST)', 499.0, 7, 'both', 'featured_section', 1, 'active', 'super_admin', datetime.utcnow().isoformat()),
            (str(uuid.uuid4()), 'Premium Visibility - 30 Days', 'Maximum visibility for 30 days (₹1499 + GST)', 1499.0, 30, 'both', 'top_list', 5, 'active', 'super_admin', datetime.utcnow().isoformat()),
        ]
        
        for plan in plans:
            cursor.execute('''
                INSERT INTO boost_plans 
                (id, name, description, price, duration_days, applicable_to, placement, visibility_weight, status, created_by, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', plan)
        
        conn.commit()
        print(f"Created {len(plans)} active boost plans!")
        
        # Verify
        cursor.execute('SELECT name, status, applicable_to FROM boost_plans')
        rows = cursor.fetchall()
        print(f"\nPlans in database ({len(rows)}):")
        for row in rows:
            print(f"  - {row[0]}: status='{row[1]}', applicable_to='{row[2]}'")
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()

if __name__ == "__main__":
    main()
