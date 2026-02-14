import requests
import sys

# Test extend booking API directly
BASE_URL = "http://localhost:8000"

# First login to get token
print("=== Testing Extension API ===")

# Try to call extend endpoint without auth to see error
try:
    response = requests.post(
        f"{BASE_URL}/bookings/extend",
        params={
            "booking_id": "test-id",
            "new_end_date": "2026-04-21T00:00:00",
            "extension_amount": 7491
        }
    )
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text}")
except Exception as e:
    print(f"Request failed: {e}")
