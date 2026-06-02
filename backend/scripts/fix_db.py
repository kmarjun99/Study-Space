import sqlite3

try:
    conn = sqlite3.connect('study_space.db')
    cursor = conn.cursor()
    # Check if column exists
    cursor.execute("PRAGMA table_info(users)")
    columns = [info[1] for info in cursor.fetchall()]
    
    if 'verification_status' not in columns:
        print("Adding verification_status column...")
        cursor.execute("ALTER TABLE users ADD COLUMN verification_status VARCHAR DEFAULT 'NOT_REQUIRED'")
        conn.commit()
        print("Column verification_status added successfully.")
    else:
        print("Column verification_status already exists.")

    # Also check logic for current_lat/long if I added them recently?
    if 'current_lat' not in columns:
         cursor.execute("ALTER TABLE users ADD COLUMN current_lat FLOAT")
         print("Added current_lat")
    if 'current_long' not in columns:
         cursor.execute("ALTER TABLE users ADD COLUMN current_long FLOAT")
         print("Added current_long")
         
    conn.commit()
    conn.close()
except Exception as e:
    print(f"Error: {e}")
