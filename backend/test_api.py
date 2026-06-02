import requests
import json

# Step 1: Login to get token
login_url = "http://localhost:8000/auth/login"
login_data = {
    "username": "admin@studyspace.com",
    "password": "admin123"
}

print("Step 1: Logging in...")
try:
    login_resp = requests.post(login_url, data=login_data)
    print(f"Login Status: {login_resp.status_code}")
    
    if login_resp.status_code != 200:
        print(f"Login failed: {login_resp.text}")
        # Try to register a new admin
        print("\nLet's check what users exist...")
        exit(1)
    
    token = login_resp.json().get("access_token")
    print(f"Token obtained: {token[:50]}...")
    
except Exception as e:
    print(f"Login error: {e}")
    exit(1)

# Step 2: Create reading room with auth token
create_url = "http://localhost:8000/reading-rooms/"
headers = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {token}"
}

payload = {
    "name": "Test Room",
    "address": "Test Address",
    "description": "A nice place",
    "image_url": "http://example.com/image.jpg",
    "images": '["http://example.com/image.jpg"]',
    "city": "Trivandrum",
    "state": "Kerala",
    "pincode": "695001",
    "price_start": 30000,
    "amenities": "WiFi,AC",
    "contact_phone": "+91 9999999999",
    "latitude": 8.5241,
    "longitude": 76.9366
}

print("\nStep 2: Creating reading room...")
print(f"URL: {create_url}")
print(f"Payload: {json.dumps(payload, indent=2)}")

try:
    create_resp = requests.post(create_url, json=payload, headers=headers)
    print(f"\nStatus Code: {create_resp.status_code}")
    print(f"Response Headers: {dict(create_resp.headers)}")
    print(f"Response Body: {create_resp.text}")
except Exception as e:
    print(f"Error: {e}")
