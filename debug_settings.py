import sys
import os

# Add /opt/companyai to path to make sure we can import app
sys.path.append("/opt/companyai")

try:
    from app.config import settings
    print(f"OLLAMA_BASE_URL: {settings.OLLAMA_BASE_URL}")
    print(f"LLM_MODEL: {settings.LLM_MODEL}")
except Exception as e:
    print(f"Error: {e}")
