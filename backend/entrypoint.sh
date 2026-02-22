#!/bin/bash
set -e

echo "🔧 Running database initialization..."

# Run the initialization script
python scripts/init_db.py

echo "🔧 Running database migrations..."

# Add HOUSE to AccommodationType enum
python scripts/add_house_type.py

echo "✅ Initialization complete, starting application..."

# Start the application
exec "$@"
