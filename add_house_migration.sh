#!/bin/bash
# Quick script to add HOUSE type to the database
# Run this after backend deployment

echo "🏠 Adding HOUSE type to accommodation enum..."
echo ""

API_URL="https://study-space-ru65.onrender.com"

# Get your credentials
read -p "Enter your admin email: " EMAIL
read -sp "Enter your password: " PASSWORD
echo ""
echo ""

echo "Step 1: Logging in..."
TOKEN_RESPONSE=$(curl -s -X POST "$API_URL/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\"}")

TOKEN=$(echo $TOKEN_RESPONSE | grep -o '"access_token":"[^"]*' | cut -d'"' -f4)

if [ -z "$TOKEN" ]; then
  echo "❌ Login failed. Please check your credentials."
  echo "Response: $TOKEN_RESPONSE"
  exit 1
fi

echo "✅ Logged in successfully"
echo ""
echo "Step 2: Running migration to add HOUSE type..."
echo ""

# Trigger migration
MIGRATION_RESPONSE=$(curl -s -X POST "$API_URL/admin/migration/add-house-type" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json")

echo "Migration Response:"
echo "$MIGRATION_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$MIGRATION_RESPONSE"

echo ""
echo "✅ Done! Check above for success status."
echo ""
echo "If successful, you can now create HOUSE accommodations!"
