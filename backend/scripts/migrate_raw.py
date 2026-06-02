
import sqlite3
import os

DB_PATH = "backend/study_space.db"

def migrate():
    if not os.path.exists(DB_PATH):
        print(f"Database file {DB_PATH} not found!")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    print("Checking if columns exist in conversations table...")

    # Check columns
    cursor.execute("PRAGMA table_info(conversations)")
    columns = [info[1] for info in cursor.fetchall()]

    if "accommodation_id" in columns:
        print("column 'accommodation_id' already exists.")
    else:
        print("Adding 'accommodation_id' column...")
        try:
            cursor.execute("ALTER TABLE conversations ADD COLUMN accommodation_id TEXT")
            print("Added 'accommodation_id' column.")
        except Exception as e:
            print(f"Failed to add accommodation_id: {e}")

    if "venue_type" in columns:
        print("column 'venue_type' already exists.")
    else:
        print("Adding 'venue_type' column...")
        try:
            cursor.execute("ALTER TABLE conversations ADD COLUMN venue_type TEXT")
            print("Added 'venue_type' column.")
        except Exception as e:
            print(f"Failed to add venue_type: {e}")

    conn.commit()
    conn.close()
    print("Migration complete.")

if __name__ == "__main__":
    migrate()
