import sqlite3

conn = sqlite3.connect('study_space.db')
cursor = conn.cursor()

# Check all tables
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
tables = cursor.fetchall()
print("All tables in database:")
for table in tables:
    print(f"  - {table[0]}")

# Check if payment_transactions table exists
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='payment_transactions'")
result = cursor.fetchone()
if result:
    print("\n✅ payment_transactions table EXISTS")
    # Check its columns
    cursor.execute("PRAGMA table_info(payment_transactions)")
    columns = cursor.fetchall()
    print("Columns:")
    for col in columns:
        print(f"  - {col[1]} ({col[2]})")
else:
    print("\n❌ payment_transactions table DOES NOT EXIST")

conn.close()
