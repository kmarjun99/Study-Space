"""Add all missing columns to payment_transactions table"""
import sqlite3

conn = sqlite3.connect('study_space.db')
c = conn.cursor()

# Get existing columns
c.execute("PRAGMA table_info(payment_transactions)")
existing = [col[1] for col in c.fetchall()]
print("Existing columns:", existing)

# Define all columns that should exist (from model)
required_columns = {
    'payment_type': 'VARCHAR DEFAULT "INITIAL"',
    'masked_reference': 'VARCHAR',
    'description': 'VARCHAR',
    'gateway_transaction_id': 'VARCHAR'
}

# Add missing columns
for col_name, col_type in required_columns.items():
    if col_name not in existing:
        try:
            sql = f'ALTER TABLE payment_transactions ADD COLUMN {col_name} {col_type}'
            c.execute(sql)
            print(f"✓ Added: {col_name}")
        except Exception as e:
            print(f"✗ Failed to add {col_name}: {e}")
    else:
        print(f"- Already exists: {col_name}")

conn.commit()
conn.close()
print("\nDone! Restart the backend server.")
