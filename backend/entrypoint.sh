#!/bin/bash
set -e

echo "🔧 Running database initialization..."

# Run the initialization script
python scripts/init_db.py

echo "✅ Initialization complete, starting application..."

# Start the application
exec "$@"
