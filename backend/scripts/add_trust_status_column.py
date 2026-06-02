import sqlite3

# Add trust_status column to reading_rooms table
conn = sqlite3.connect('studyspace.db')
cursor = conn.cursor()

try:
    cursor.execute('ALTER TABLE reading_rooms ADD COLUMN trust_status VARCHAR(20) DEFAULT "CLEAR"')
    conn.commit()
    print('Added trust_status column to reading_rooms successfully')
except Exception as e:
    print(f'Error (might already exist): {e}')
finally:
    conn.close()
