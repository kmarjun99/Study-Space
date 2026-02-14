"""
Script to create the missing 'cabins' table in the database.
Run this from the backend directory: python create_cabins_table.py
"""
import sqlite3
import os

# Find the database file
db_path = './study_space.db'
if not os.path.exists(db_path):
    db_path = './app/study_space.db'  # Alternative location

if not os.path.exists(db_path):
    print(f"ERROR: Could not find database file")
    exit(1)

print(f"Using database: {db_path}")

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Check if cabins table exists
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='cabins'")
if cursor.fetchone():
    print("Cabins table already exists!")
else:
    print("Creating cabins table...")
    
    create_sql = """
    CREATE TABLE cabins (
        id VARCHAR PRIMARY KEY,
        reading_room_id VARCHAR NOT NULL,
        number VARCHAR NOT NULL,
        floor INTEGER NOT NULL,
        amenities VARCHAR,
        price FLOAT NOT NULL,
        status VARCHAR DEFAULT 'AVAILABLE',
        current_occupant_id VARCHAR,
        zone VARCHAR,
        row_label VARCHAR,
        FOREIGN KEY (reading_room_id) REFERENCES reading_rooms(id),
        FOREIGN KEY (current_occupant_id) REFERENCES users(id)
    )
    """
    
    cursor.execute(create_sql)
    conn.commit()
    print("Cabins table created successfully!")

# Verify
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()
print(f"\nCurrent tables: {[t[0] for t in tables]}")

# Show cabins table schema
cursor.execute("PRAGMA table_info(cabins)")
columns = cursor.fetchall()
print(f"\nCabins table columns:")
for col in columns:
    print(f"  - {col[1]} ({col[2]})")

conn.close()
print("\nDone!")
