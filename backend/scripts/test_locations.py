"""Quick test for locations API"""
import urllib.request
import json

# Test autocomplete for "ba" (should return Bangalore locations)
print("Testing autocomplete: q=ba")
print("-" * 40)
response = urllib.request.urlopen('http://localhost:8000/locations/autocomplete?q=ba')
data = json.loads(response.read())
for loc in data[:5]:
    print(f"  ✓ {loc['display_name']}")

print()

# Test autocomplete for "ker" (should return Kerala locations)
print("Testing autocomplete: q=ker")
print("-" * 40)
response = urllib.request.urlopen('http://localhost:8000/locations/autocomplete?q=ker')
data = json.loads(response.read())
for loc in data[:5]:
    print(f"  ✓ {loc['display_name']}")

print()
print("✅ Location API is working!")
