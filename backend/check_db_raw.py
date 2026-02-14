import sqlite3
import os

db_path = "study_space.db"

def check():
    if not os.path.exists(db_path):
        print("DB File NOT found!")
        return

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    
    # Count Inquiries
    try:
        cur.execute("SELECT count(*) FROM inquiries")
        count = cur.fetchone()[0]
        print(f"Total Inquiries (Raw): {count}")
        
        cur.execute("SELECT id, student_id, question FROM inquiries")
        rows = cur.fetchall()
        for r in rows:
            print(f" - {r}")
            
        cur.execute("SELECT id, name, email FROM users ORDER BY created_at DESC LIMIT 5")
        users = cur.fetchall()
        print("Recent Users:")
        for u in users:
            print(f" - {u}")
            
        cur.execute("SELECT id, name, email FROM users WHERE email='ajuvinod5873@gmail.com'")
        user = cur.fetchone()
        if user:
            print(f"User Ajay: {user}")
        else:
            print("User Ajay NOT found in Raw DB")
            
    except Exception as e:
        print(f"Error: {e}")
        
    conn.close()

if __name__ == "__main__":
    check()
