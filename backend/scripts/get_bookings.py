import sqlite3

conn = sqlite3.connect('study_space.db')
cursor = conn.cursor()
cursor.execute("SELECT id, user_id, end_date, amount FROM bookings LIMIT 5")
for row in cursor.fetchall():
    print(f"ID: {row[0]}")
    print(f"User: {row[1]}")
    print(f"End Date: {row[2]}")
    print(f"Amount: {row[3]}")
    print("---")
conn.close()
