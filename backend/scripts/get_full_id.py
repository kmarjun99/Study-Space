import sqlite3

conn = sqlite3.connect('study_space.db')
cursor = conn.cursor()
cursor.execute("SELECT id FROM bookings LIMIT 3")
for row in cursor.fetchall():
    print(f"Full ID: {row[0]}")
conn.close()
