import traceback
import sys

print("1. Testing direct app.database.Base...")
from app.database import Base
print("   OK")

print("2. Testing app.models.reading_room...")
try:
    import app.models.reading_room as rr
    print(f"   Module loaded: {rr}")
except Exception as e:
    print(f"   FAILED: {e}")
    traceback.print_exc()
    sys.exit(1)
