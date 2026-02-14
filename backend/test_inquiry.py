import httpx
import asyncio
import random
import string

BASE_URL = "http://localhost:8000"

def random_string(length=8):
    return ''.join(random.choices(string.ascii_letters, k=length))

async def test_inquiry_flow():
    async with httpx.AsyncClient() as client:
        # 1. Register Student
        email = f"student_{random_string()}@example.com"
        password = "password123"
        print(f"Registering {email}...")
        resp = await client.post(f"{BASE_URL}/auth/register", json={
            "email": email,
            "password": password,
            "name": "Test Student",
            "role": "STUDENT",
            "phone": "9999999999"
        })
        if resp.status_code != 200:
            print(f"Registration failed: {resp.text}")
            return
            
        # 2. Login
        resp = await client.post(f"{BASE_URL}/auth/login", data={"username": email, "password": password})
        token = resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        # 3. Get Accommodation
        # We need an accommodation ID. 
        # Since I can't browse, I'll try to find one via public list or just create one if I was admin.
        # But I'm student.
        # I'll rely on setup: Fetch accommodations (even unverified excluded, maybe I can't see them).
        # I'll use a hack: Query DB via side-channel or assume "Security Test Hostel" exists?
        
        # Or better: Login as Admin first, get/create accommodation ID, then switch to Student.
        
        # 2b. Login Admin to get Acc ID
        resp_admin = await client.post(f"{BASE_URL}/auth/login", data={"username": "admin@studyspace.com", "password": "admin123"})
        if resp_admin.status_code == 200:
            token_admin = resp_admin.json()["access_token"]
            headers_admin = {"Authorization": f"Bearer {token_admin}"}
            resp_accs = await client.get(f"{BASE_URL}/accommodations/my", headers=headers_admin)
            accs = resp_accs.json()
            if accs:
                acc_id = accs[0]["id"]
                print(f"Using Accommodation: {acc_id}")
            else:
                print("No accommodations found for admin. creating one...")
                # Create one
                create_data = {
                    "name": "Inquiry Test Hostel", "type": "PG", "gender": "MALE", "address": "Test St", "price": 5000,
                    "contactPhone": "1234567890", "city": "Hyderabad", "sharing": "Single"
                }
                resp_create = await client.post(f"{BASE_URL}/accommodations/", json=create_data, headers=headers_admin)
                acc_id = resp_create.json()["id"]
                print(f"Created Acc: {acc_id}")
        else:
            print("Admin login failed. Cannot setup test data.")
            return

        # 4. Send Inquiry as Student
        print("Sending Inquiry...")
        inquiry_data = {
            "accommodation_id": acc_id,
            "type": "QUESTION",
            "question": "Is wifi good?",
            "student_name": "Test Student",
            "student_phone": "9876543210"
        }
        
        resp_inq = await client.post(f"{BASE_URL}/inquiries/", json=inquiry_data, headers=headers)
        if resp_inq.status_code == 200:
            print("✅ Inquiry Sent Successfully!")
            print(resp_inq.json())
        else:
            print(f"❌ Inquiry Failed: {resp_inq.status_code}")
            print(resp_inq.text)
            
        # 5. Verify Student 'My Inquiries'
        print("\nChecking Student's Sent Inquiries...")
        resp_my = await client.get(f"{BASE_URL}/inquiries/my", headers=headers)
        if resp_my.status_code == 200:
            my_inqs = resp_my.json()
            print(f"Student has {len(my_inqs)} inquiries.")
            if len(my_inqs) > 0:
                print(f"Latest: {my_inqs[0]['question']}")
            else:
                print("❌ ERROR: Inquiry not found in /my")
        else:
            print(f"❌ Failed to get /my: {resp_my.status_code}")

        # 6. Verify Admin 'Received Inquiries'
        print("\nChecking Admin's Received Inquiries...")
        resp_received = await client.get(f"{BASE_URL}/inquiries/received", headers=headers_admin)
        if resp_received.status_code == 200:
            rec_inqs = resp_received.json()
            print(f"Admin has {len(rec_inqs)} received inquiries.")
            # Check if our new inquiry is there
            found = any(i['question'] == "Is wifi good?" for i in rec_inqs)
            if found:
                print("✅ Found newly created inquiry in Admin inbox.")
            else:
                print("❌ Inquiry not found in Admin inbox.")
        else:
            print(f"❌ Failed to get /received: {resp_received.status_code}")

if __name__ == "__main__":
    asyncio.run(test_inquiry_flow())
