import sqlite3

conn = sqlite3.connect('study_space.db')
cursor = conn.cursor()

# Check if invoices table exists
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='invoices'")
result = cursor.fetchone()

if result:
    print("✅ invoices table EXISTS")
    cursor.execute("PRAGMA table_info(invoices)")
    columns = cursor.fetchall()
    print("Columns:")
    for col in columns:
        print(f"  - {col[1]} ({col[2]})")
else:
    print("❌ invoices table DOES NOT EXIST")

conn.close()
