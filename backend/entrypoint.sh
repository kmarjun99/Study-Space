#!/bin/bash
set -e

echo "🔧 Running database initialization..."

# Run the initialization script
if python scripts/init_db.py; then
    echo "✅ Database initialization completed"
else
    echo "❌ Database initialization failed!"
    exit 1
fi

echo ""
echo "🔄 Running enum to VARCHAR migration..."

# Migrate enum columns to VARCHAR for flexibility
if python scripts/migrate_enums_to_varchar.py; then
    echo "✅ Migration completed successfully"
else
    echo "❌ Migration failed!"
    echo "⚠️  The app will start anyway, but HOUSE type may not work."
    echo "   Check the logs above for details."
fi

echo ""
echo "🔄 Running booking duration configuration migration..."

# Add flexible booking duration support
if python scripts/add_booking_duration_config.py; then
    echo "✅ Duration configuration migration completed"
else
    echo "❌ Duration migration failed!"
    echo "⚠️  The app will start anyway, but duration features may not work."
    echo "   Check the logs above for details."
fi

echo ""
echo "✅ All migrations complete, starting application..."

# Start the application
exec "$@"
