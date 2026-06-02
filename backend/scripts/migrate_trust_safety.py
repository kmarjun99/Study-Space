"""
Database migration script to add Trust & Safety columns and tables.
Run this to fix the 'no such column: trust_status' error.
"""
import sqlite3

def migrate_database():
    conn = sqlite3.connect('study_space.db')  # Correct filename with underscore
    cursor = conn.cursor()
    
    print("=" * 50)
    print("Trust & Safety Database Migration")
    print("=" * 50)
    
    # 1. Check current reading_rooms columns
    cursor.execute('PRAGMA table_info(reading_rooms)')
    columns = [c[1] for c in cursor.fetchall()]
    print(f"\nCurrent reading_rooms columns: {columns}")
    
    # 2. Add trust_status column if missing
    if 'trust_status' not in columns:
        print("\nAdding trust_status column to reading_rooms...")
        cursor.execute('ALTER TABLE reading_rooms ADD COLUMN trust_status VARCHAR(20) DEFAULT "CLEAR"')
        print("✓ trust_status column added")
    else:
        print("\n✓ trust_status column already exists")
    
    # 3. Check if trust_flags table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='trust_flags'")
    if not cursor.fetchone():
        print("\nCreating trust_flags table...")
        cursor.execute('''
            CREATE TABLE trust_flags (
                id VARCHAR(36) PRIMARY KEY,
                entity_type VARCHAR(50) NOT NULL,
                entity_id VARCHAR(36) NOT NULL,
                entity_name VARCHAR(255),
                flag_type VARCHAR(50) NOT NULL,
                custom_reason TEXT,
                raised_by VARCHAR(36) NOT NULL,
                raised_by_name VARCHAR(255),
                status VARCHAR(20) DEFAULT 'active',
                resolution_notes TEXT,
                resolved_by VARCHAR(36),
                resolved_by_name VARCHAR(255),
                owner_notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP,
                resolved_at TIMESTAMP,
                resubmitted_at TIMESTAMP
            )
        ''')
        print("✓ trust_flags table created")
    else:
        print("\n✓ trust_flags table already exists")
    
    # 4. Check if reminders table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='reminders'")
    if not cursor.fetchone():
        print("\nCreating reminders table...")
        cursor.execute('''
            CREATE TABLE reminders (
                id VARCHAR(36) PRIMARY KEY,
                user_id VARCHAR(36) NOT NULL,
                user_name VARCHAR(255),
                user_email VARCHAR(255),
                reminder_type VARCHAR(50) NOT NULL,
                missing_fields TEXT,
                message TEXT,
                sent_by VARCHAR(36) NOT NULL,
                sent_by_name VARCHAR(255),
                status VARCHAR(20) DEFAULT 'pending',
                blocks_listings BOOLEAN DEFAULT 1,
                blocks_payments BOOLEAN DEFAULT 1,
                blocks_bookings BOOLEAN DEFAULT 0,
                sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                acknowledged_at TIMESTAMP,
                completed_at TIMESTAMP,
                email_sent BOOLEAN DEFAULT 0,
                email_sent_at TIMESTAMP
            )
        ''')
        print("✓ reminders table created")
    else:
        print("\n✓ reminders table already exists")
    
    # 5. Check if audit_logs table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='audit_logs'")
    if not cursor.fetchone():
        print("\nCreating audit_logs table...")
        cursor.execute('''
            CREATE TABLE audit_logs (
                id VARCHAR(36) PRIMARY KEY,
                actor_id VARCHAR(36) NOT NULL,
                actor_name VARCHAR(255),
                actor_role VARCHAR(50) NOT NULL,
                action_type VARCHAR(50) NOT NULL,
                action_description TEXT,
                entity_type VARCHAR(50),
                entity_id VARCHAR(36),
                entity_name VARCHAR(255),
                extra_data TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        print("✓ audit_logs table created")
    else:
        print("\n✓ audit_logs table already exists")
    
    conn.commit()
    conn.close()
    
    print("\n" + "=" * 50)
    print("Migration complete!")
    print("=" * 50)
    print("\nPlease restart the backend server for changes to take effect.")

if __name__ == '__main__':
    migrate_database()
