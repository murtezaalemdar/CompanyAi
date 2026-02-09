from app.config import settings
import os

print("=== Settings Debug ===")
print(f"OLLAMA_BASE_URL from settings: '{settings.OLLAMA_BASE_URL}'")
print(f"OLLAMA_BASE_URL from env: '{os.getenv('OLLAMA_BASE_URL')}'")
print(f"DATABASE_URL from settings: '{settings.DATABASE_URL}'")
print("======================")
