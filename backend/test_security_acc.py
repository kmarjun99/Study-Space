import httpx
import asyncio

BASE_URL = "http://localhost:8000"

async def test_acc_security():
    async with httpx.AsyncClient() as client:
        # 1. Login as Admin
        resp = await client.post(f"{BASE_URL}/auth/login", data={"username": "admin@studyspace.com", "password": "admin123"})
        if resp.status_code != 200:
            print("Login failed")
            return
        token = resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        # 2. Create Accommodation
        acc_data = {
            "name": "Security Test Hostel",
            "type": "PG",
            "gender": "MALE",
            "address": "123 Secure St",
            "price": 5000,
            "sharing": "Single",
            "contactPhone": "1234567890",
            "city": "Hyderabad",
            "status": "LIVE" # Try sending status during creation
        }
        resp = await client.post(f"{BASE_URL}/accommodations/", json=acc_data, headers=headers)
        if resp.status_code != 200:
            print(f"Create failed: {resp.text}")
            return
        acc_id = resp.json()["id"]
        print(f"Accommodation created: {acc_id} (Status: {resp.json().get('status')})")
        
        # 3. Attempt Update to LIVE
        update_payload = {"status": "LIVE", "name": "Hacked Hostel Name"}
        resp = await client.put(f"{BASE_URL}/accommodations/{acc_id}", json=update_payload, headers=headers)
        
        if resp.status_code == 200:
            updated_acc = resp.json()
            if updated_acc["status"] == "LIVE":
                print("❌ FAILED: Owner successfully changed status to LIVE!")
            else:
                print(f"✅ PASSED: Status is {updated_acc['status']} (Expected: DRAFT)")
                if updated_acc["name"] == "Hacked Hostel Name":
                    print("   (Name update was allowed, as expected)")
        else:
            print(f"Update failed unexpectedly: {resp.status_code}")

if __name__ == "__main__":
    asyncio.run(test_acc_security())
