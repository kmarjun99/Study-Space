"""
Test boost plans API
"""
import requests

def test_api():
    try:
        # Test the boost plans endpoint
        response = requests.get("http://localhost:8000/boost/plans", timeout=10)
        print(f"Status Code: {response.status_code}")
        print(f"Response Headers: {dict(response.headers)}")
        print(f"Response Body: {response.text[:500] if response.text else 'EMPTY'}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"\nPlans returned: {len(data)}")
            for plan in data:
                print(f"  - {plan.get('name')}: status={plan.get('status')}")
        else:
            print(f"\nError: {response.text}")
            
    except requests.exceptions.ConnectionError as e:
        print(f"Connection Error: Backend not running? {e}")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_api()
