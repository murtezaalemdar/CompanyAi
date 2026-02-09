"""API üzerinden sohbet testi"""
import sys, json, urllib.request, urllib.parse

BASE = "http://localhost:8000/api"

# Login (OAuth2 form-data)
login_data = urllib.parse.urlencode({"username": "admin@company.ai", "password": "admin123"}).encode()
req = urllib.request.Request(f"{BASE}/auth/login", data=login_data, headers={"Content-Type": "application/x-www-form-urlencoded"})
with urllib.request.urlopen(req) as resp:
    token = json.loads(resp.read())["access_token"]
print(f"Login OK, token alindi")

# Test soruları
questions = [
    "Merhaba",
    "Nasılsın?",
    "Teşekkürler",
    "Sen kimsin?",
    "Bugün hava nasıl?",
]

for q in questions:
    data = json.dumps({"question": q}).encode()
    req = urllib.request.Request(
        f"{BASE}/ask",
        data=data,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"}
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        result = json.loads(resp.read())
    
    print(f"\n{'='*50}")
    print(f"SORU: {q}")
    print(f"CEVAP: {result['answer'][:200]}")
    print(f"MOD: {result['mode']} | SURE: {result['processing_time_ms']}ms")
    print(f"KAYNAK: {result.get('confidence', 'N/A')}")
