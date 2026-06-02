import httpx
import asyncio

BASE_URL = "http://localhost:8000"

async def test_security():
    async with httpx.AsyncClient() as client:
        # 1. Login as Admin
        resp = await client.post(f"{BASE_URL}/auth/login", data={"username": "admin@studyspace.com", "password": "admin123"})
        if resp.status_code != 200:
            print("Login failed")
            return
        token = resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        # 2. Create Room
        room_data = {
            "name": "Security Test Room",
            "address": "123 Secure St",
            "city": "Hyderabad",
            "priceStart": 5000,
            "status": "LIVE" # Try sending status during creation too
        }
        resp = await client.post(f"{BASE_URL}/reading-rooms/", json=room_data, headers=headers)
        if resp.status_code != 200:
            print(f"Create failed: {resp.text}")
            return
        room_id = resp.json()["id"]
        print(f"Room created: {room_id} (Status: {resp.json().get('status')})")
        
        # 3. Attempt Update to LIVE
        update_payload = {"status": "LIVE", "name": "Hacked Room Name"}
        resp = await client.put(f"{BASE_URL}/reading-rooms/{room_id}", json=update_payload, headers=headers)
        
        if resp.status_code == 200:
            updated_room = resp.json()
            if updated_room["status"] == "LIVE":
                print("❌ FAILED: Owner successfully changed status to LIVE!")
            else:
                print(f"✅ PASSED: Status is {updated_room['status']} (Expected: DRAFT)")
                if updated_room["name"] == "Hacked Room Name":
                    print("   (Name update was allowed, as expected)")
        else:
            print(f"Update failed unexpectedly: {resp.status_code}")

if __name__ == "__main__":
    asyncio.run(test_security())
