
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

long_secret = "production-min-32-chars-long-and-secure-secret-key-change-this"

try:
    print(f"Hashing 'admin123'...")
    res = hash_password("admin123")
    print(f"Success: {res}")
except Exception as e:
    print(f"Error: {e}")

try:
    print(f"Hashing long secret ({len(long_secret)} chars)...")
    res = hash_password(long_secret)
    print(f"Success long: {res}")
except Exception as e:
    print(f"Error long: {e}")

very_long = "a" * 73
try:
    print(f"Hashing 73 chars...")
    res = hash_password(very_long)
    print(f"Success 73: {res}")
except Exception as e:
    print(f"Error 73: {e}")
