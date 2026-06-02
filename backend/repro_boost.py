
import urllib.request
import urllib.parse
import json
import sys

BASE_URL = "http://localhost:8000"

def login(email, password):
    url = f"{BASE_URL}/auth/login"
    data = urllib.parse.urlencode({"username": email, "password": password}).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    
    try:
        with urllib.request.urlopen(req) as response:
            if response.status == 200:
                body = response.read().decode("utf-8")
                token_data = json.loads(body)
                print("Login successful!")
                return token_data.get("access_token")
            else:
                print(f"Login failed: {response.status}")
                return None
    except urllib.error.HTTPError as e:
        print(f"Login failed: {e.code} {e.reason}")
        print(e.read().decode("utf-8"))
        return None
    except Exception as e:
        print(f"Error: {e}")
        return None

def create_boost_plan(token):
    url = f"{BASE_URL}/boost/plans"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    payload = {
        "name": "Basic",
        "description": "Get Featured",
        "price": 499,
        "duration_days": 7,
        "applicable_to": "both", 
        "placement": "featured_section",
        "status": "active"
    }
    
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    
    print(f"Sending Payload: {json.dumps(payload, indent=2)}")
    
    try:
        with urllib.request.urlopen(req) as response:
            print(f"Status Code: {response.status}")
            body = response.read().decode("utf-8")
            print(f"Response Body: {body}")
    except urllib.error.HTTPError as e:
        print(f"Request failed: {e.code} {e.reason}")
        print(e.read().decode("utf-8"))
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    with open("repro_output_utf8.txt", "w", encoding="utf-8") as f:
        sys.stdout = f
        print("Logging in as Super Admin...")
        token = login("superadmin@studyspace.com", "superadmin123")
        if token:
            print("Creating Boost Plan...")
            create_boost_plan(token)
