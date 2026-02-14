
import asyncio
import httpx

async def test_locations():
    # Corrected Base URL
    async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
        print("Testing /locations/states...")
        try:
            r = await client.get("/locations/states")
            print(f"Status: {r.status_code}")
            print(f"Response: {r.text[:200]}")
        except Exception as e:
            print(f"Error: {e}")

        print("\nTesting /locations/cities (state='Telangana')...")
        try:
            r = await client.get("/locations/cities", params={"state": "Telangana"})
            print(f"Status: {r.status_code}")
            print(f"Response: {r.text[:200]}")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_locations())
