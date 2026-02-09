
from app.auth.jwt_handler import hash_password
from app.config import settings

print(f"SECRET_KEY length: {len(settings.SECRET_KEY)}")
print(f"Hashing 'admin123'...")
try:
    hash = hash_password("admin123")
    print(f"Success: {hash}")
except Exception as e:
    print(f"Error hashing 'admin123': {e}")

long_string = "production-min-32-chars-long-and-secure-secret-key-change-this"
print(f"Hashing long string ({len(long_string)} chars)...")
try:
    hash = hash_password(long_string)
    print(f"Success long: {hash}")
except Exception as e:
    print(f"Error hashing long string: {e}")

very_long = "x" * 73
print(f"Hashing very long string ({len(very_long)} chars)...")
try:
    hash = hash_password(very_long)
    print(f"Success very long: {hash}")
except Exception as e:
    print(f"Error hashing very long string: {e}")
