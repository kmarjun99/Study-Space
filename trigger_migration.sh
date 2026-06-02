#!/bin/bash
# Script to manually trigger the database migration for HOUSE type support
# Run this after the backend has deployed

echo "🔄 Triggering manual database migration..."
echo ""

# You need to replace these with your actual credentials
read -p "Enter your email (admin account): " EMAIL
read -sp "Enter your password: " PASSWORD
echo ""

API_URL="https://study-space-ru65.onrender.com"

echo ""
echo "Step 1: Getting authentication token..."

# Login to get token
TOKEN_RESPONSE=$(curl -s -X POST "$API_URL/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\"}")

TOKEN=$(echo $TOKEN_RESPONSE | sed -n 's/.*"access_token":"\([^"]*\).*/\1/p')

if [ -z "$TOKEN" ]; then
  echo "❌ Failed to login. Please check your credentials."
  echo "Response: $TOKEN_RESPONSE"
  exit 1
fi

echo "✅ Successfully authenticated"
echo ""
echo "Step 2: Running migration..."
echo ""

# Trigger migration
MIGRATION_RESPONSE=$(curl -s -X POST "$API_URL/admin/migration/run-enum-migration" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json")

echo "Migration Response:"
echo "$MIGRATION_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$MIGRATION_RESPONSE"

echo ""
echo "✅ Migration request completed!"
echo ""
echo "If you see 'success: true' above, HOUSE type is now working!"
echo "Try creating a HOUSE accommodation in your app."
