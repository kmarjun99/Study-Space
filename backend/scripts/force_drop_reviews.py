import sqlite3
import os

DB_FILE = "study_space.db"

def fix_db():
    if not os.path.exists(DB_FILE):
        print(f"{DB_FILE} not found.")
        return

    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        # Check if table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='reviews';")
        if cursor.fetchone():
            print("Table 'reviews' exists. Dropping it...")
            cursor.execute("DROP TABLE reviews;")
            conn.commit()
            print("Table 'reviews' dropped successfully.")
        else:
            print("Table 'reviews' does not exist.")
            
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    fix_db()
