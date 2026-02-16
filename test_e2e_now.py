"""End-to-end test: login → ask question → get response"""
import requests, time, sys

BASE = "http://127.0.0.1:8000/api"

# 1. Login
print("1. Login...")
r = requests.post(f"{BASE}/auth/login", data={"username": "admin@company.ai", "password": "admin123"})
if r.status_code != 200:
    print(f"   Login failed: {r.status_code} - {r.text[:200]}")
    sys.exit(1)
token = r.json().get("access_token")
print(f"   OK (token: {token[:20]}...)")

headers = {"Authorization": f"Bearer {token}"}

# 2. Ask question (multimodal endpoint)
print("2. Asking 'merhaba' via /ask/multimodal...")
start = time.time()
try:
    r = requests.post(
        f"{BASE}/ask/multimodal",
        data={"question": "merhaba", "session_id": "test_e2e"},
        headers=headers,
        timeout=300,
    )
    elapsed = time.time() - start
    print(f"   HTTP: {r.status_code} ({elapsed:.1f}s)")
    if r.status_code == 200:
        d = r.json()
        answer = d.get("answer", d.get("response", ""))[:200]
        print(f"   Answer: {answer}")
    else:
        print(f"   Error: {r.text[:500]}")
except requests.Timeout:
    print(f"   TIMEOUT after {time.time()-start:.0f}s")
except Exception as e:
    print(f"   Exception: {e}")

# 3. Check RAM after
print("3. Done.")
