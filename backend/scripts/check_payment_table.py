"""Check exact database schema vs model"""
import sqlite3

conn = sqlite3.connect('study_space.db')
c = conn.cursor()

print("=== payment_transactions table schema ===")
c.execute("PRAGMA table_info(payment_transactions)")
for col in c.fetchall():
    print(f"  {col[0]}: {col[1]} ({col[2]}) {'NOT NULL' if col[3] else 'NULL'}")

print("\n=== Required columns from model ===")
required = {
    'id': 'String PRIMARY KEY',
    'booking_id': 'String FK',
    'user_id': 'String FK',
    'payment_type': 'Enum',
    'method': 'Enum',
    'gateway': 'Enum',
    'masked_reference': 'String NULL',
    'amount': 'Float',
    'gateway_transaction_id': 'String NULL',
    'description': 'String NULL',
    'created_at': 'DateTime'
}

c.execute("PRAGMA table_info(payment_transactions)")
existing = {col[1]: col[2] for col in c.fetchall()}

print("\nComparison:")
for col_name, col_type in required.items():
    if col_name in existing:
        print(f"  ✓ {col_name}: {existing[col_name]}")
    else:
        print(f"  ✗ MISSING: {col_name} ({col_type})")
        
# Show sample data if any
print("\n=== Sample data ===")
c.execute("SELECT * FROM payment_transactions LIMIT 1")
row = c.fetchone()
if row:
    c.execute("PRAGMA table_info(payment_transactions)")
    cols = [col[1] for col in c.fetchall()]
    for i, val in enumerate(row):
        print(f"  {cols[i]}: {val}")
else:
    print("  No data in table")

conn.close()
