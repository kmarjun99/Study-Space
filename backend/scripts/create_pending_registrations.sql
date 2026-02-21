-- Create pending_registrations table for OTP-verified registration flow
-- Run this SQL on your Render PostgreSQL database

CREATE TABLE IF NOT EXISTS pending_registrations (
    id VARCHAR PRIMARY KEY DEFAULT gen_random_uuid()::text,
    email VARCHAR NOT NULL UNIQUE,
    hashed_password VARCHAR NOT NULL,
    name VARCHAR NOT NULL,
    role VARCHAR NOT NULL,
    phone VARCHAR,
    avatar_url VARCHAR,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL
);

-- Create index on email for faster lookups
CREATE INDEX IF NOT EXISTS idx_pending_registrations_email 
ON pending_registrations(email);

-- Verify the table was created
SELECT 'pending_registrations table created successfully!' AS status;
SELECT COUNT(*) as table_exists FROM information_schema.tables 
WHERE table_name = 'pending_registrations';
