import sqlite3

# Try both database files
for db_name in ['study_space.db', 'studyspace.db']:
    try:
        conn = sqlite3.connect(db_name)
        cursor = conn.cursor()
        
        # Get tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        print(f"\n{db_name} tables: {[t[0] for t in tables]}")
        
        # Get bookings if the table exists
        if any('booking' in t[0].lower() for t in tables):
            cursor.execute("SELECT id, user_id, end_date FROM bookings LIMIT 3")
            bookings = cursor.fetchall()
            print(f"Bookings: {bookings}")
        
        conn.close()
    except Exception as e:
        print(f"{db_name} error: {e}")
