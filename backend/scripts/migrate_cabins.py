import sqlite3

def migrate_cabins_table():
    """Add missing columns to cabins table"""
    conn = sqlite3.connect('study_space.db')
    cursor = conn.cursor()
    
    print("=" * 50)
    print("Cabins Table Migration")
    print("=" * 50)
    
    # Check current columns
    cursor.execute('PRAGMA table_info(cabins)')
    columns = [c[1] for c in cursor.fetchall()]
    print(f"\nCurrent cabins columns: {columns}")
    
    # Add zone column if missing
    if 'zone' not in columns:
        print("\nAdding 'zone' column to cabins...")
        cursor.execute('ALTER TABLE cabins ADD COLUMN zone VARCHAR(20)')
        print("✓ zone column added")
    else:
        print("\n✓ zone column already exists")
    
    # Add row_label column if missing
    if 'row_label' not in columns:
        print("\nAdding 'row_label' column to cabins...")
        cursor.execute('ALTER TABLE cabins ADD COLUMN row_label VARCHAR(10)')
        print("✓ row_label column added")
    else:
        print("\n✓ row_label column already exists")
    
    conn.commit()
    
    # Verify
    cursor.execute('PRAGMA table_info(cabins)')
    columns_after = [c[1] for c in cursor.fetchall()]
    print(f"\nCabins columns after migration: {columns_after}")
    
    conn.close()
    
    print("\n" + "=" * 50)
    print("Migration complete!")
    print("=" * 50)
    print("\nPlease restart the backend server for changes to take effect.")

if __name__ == '__main__':
    migrate_cabins_table()
