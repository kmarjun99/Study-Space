"""
Script to check and seed boost plans
"""
import sqlite3

def main():
    conn = sqlite3.connect('study_space.db')
    cursor = conn.cursor()
    
    # Check if table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cursor.fetchall()]
    print("All tables:", tables)
    
    # Check for boost tables
    boost_tables = [t for t in tables if 'boost' in t.lower()]
    print("\nBoost-related tables:", boost_tables)
    
    if 'boost_plans' in tables:
        cursor.execute("SELECT id, name, status, applicable_to FROM boost_plans")
        plans = cursor.fetchall()
        print(f"\nBoost Plans ({len(plans)}):")
        for plan in plans:
            print(f"  - {plan[1]} (status: {plan[2]}, applicable_to: {plan[3]})")
            
        # If no active plans, create one
        if not any(p[2] == 'active' for p in plans):
            print("\nNo active plans found! Creating a sample active plan...")
            import uuid
            from datetime import datetime
            
            cursor.execute("""
                INSERT INTO boost_plans (id, name, description, price, duration_days, applicable_to, placement, visibility_weight, status, created_by, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                str(uuid.uuid4()),
                "Featured Listing - Basic",
                "Get your property featured for 7 days",
                499.0,
                7,
                "both",
                "featured_section",
                1,
                "active",
                "super_admin",
                datetime.utcnow().isoformat()
            ))
            
            cursor.execute("""
                INSERT INTO boost_plans (id, name, description, price, duration_days, applicable_to, placement, visibility_weight, status, created_by, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                str(uuid.uuid4()),
                "Premium Visibility - 30 Days",
                "Maximum visibility for 30 days",
                1499.0,
                30,
                "both",
                "top_list",
                5,
                "active",
                "super_admin",
                datetime.utcnow().isoformat()
            ))
            
            conn.commit()
            print("Created 2 active boost plans!")
    else:
        print("\n⚠️ boost_plans table does not exist!")
        print("The server needs to restart to create the table.")
    
    conn.close()

if __name__ == "__main__":
    main()
