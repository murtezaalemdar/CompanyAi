import asyncio
import httpx
import sys

# Backend ile AYNI ayarlar
BASE_URL = "http://127.0.0.1:11434"
TIMEOUT = 5.0

async def check_connection():
    print(f"--- TEST BAŞLIYOR ---")
    print(f"Hedef: {BASE_URL}/api/tags")
    
    # 1. httpx (Async) Testi - Backend'in kullandığı yöntem
    print("\n1. httpx AsyncClient Testi:")
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT, trust_env=False) as client:
            response = await client.get(f"{BASE_URL}/api/tags")
            print(f"   DURUM: BAŞARILI ✅")
            print(f"   Status Code: {response.status_code}")
            print(f"   Body: {response.text[:100]}...")
    except Exception as e:
        print(f"   DURUM: BAŞARISIZ ❌")
        print(f"   Hata: {type(e).__name__}: {e}")

    # 2. Standart requests kütüphanesi ile kontrol (Karılaştırma için)
    print("\n2. urllib Testi (Senkron):")
    try:
        import urllib.request
        with urllib.request.urlopen(f"{BASE_URL}/api/tags", timeout=TIMEOUT) as response:
            print(f"   DURUM: BAŞARILI ✅")
            print(f"   Status Code: {response.getcode()}")
    except Exception as e:
        print(f"   DURUM: BAŞARISIZ ❌")
        print(f"   Hata: {e}")

if __name__ == "__main__":
    asyncio.run(check_connection())
