import urllib.request
import json

try:
    r = urllib.request.urlopen('http://localhost:8000/subscriptions/plans', timeout=10)
    print('Status:', r.status)
    data = json.loads(r.read().decode())
    print('Subscription Plans returned:', len(data))
    for p in data:
        print(f"  - {p['name']}: price={p['price']}, is_active={p['is_active']}")
except urllib.error.HTTPError as e:
    print(f'HTTP Error: {e.code}')
    print(f'Response: {e.read().decode()}')
except Exception as e:
    print(f'Error: {e}')
