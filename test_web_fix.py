"""Web arama düzeltmesi + Rich Data (hava durumu kartı) test scripti"""
import requests
import json

BASE = "http://192.168.0.12:8000/api"

# Login
resp = requests.post(f"{BASE}/auth/login", data={"username": "admin@company.ai", "password": "admin123"})
token = resp.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}

# Test: hava durumu sorusu (web arama gerektiren)
print("=" * 60)
print("TEST: Hava durumu sorusu (web arama + rich_data testi)")
print("=" * 60)

resp = requests.post(f"{BASE}/ask/multimodal", headers=headers, data={
    "question": "bugün inegölde hava nasıl",
}, timeout=120)

print(f"Status: {resp.status_code}")
data = resp.json()
print(f"Keys: {list(data.keys())}")
print(f"Answer: {data.get('answer', data.get('response', 'N/A'))[:400]}")
print()

# Rich data kontrolü
rich = data.get("rich_data")
if rich and rich.get("type") == "weather":
    print("✅ RICH DATA: Hava durumu kartı verisi geldi!")
    print(f"   Konum: {rich.get('location')}")
    print(f"   Sıcaklık: {rich.get('temperature')}°{rich.get('unit', 'C')}")
    print(f"   Durum: {rich.get('condition_icon')} {rich.get('condition')}")
    print(f"   Nem: {rich.get('humidity')}")
    print(f"   Rüzgar: {rich.get('wind')}")
    print(f"   Yağış: {rich.get('precipitation')}")
    forecast = rich.get("forecast", [])
    if forecast:
        print(f"   Haftalık tahmin ({len(forecast)} gün):")
        for day in forecast:
            print(f"     {day['day']}: {day['icon']} {day.get('high','?')}°/{day.get('low','?')}° — {day.get('condition','')}")
else:
    print("⚠️ Rich data yok veya weather tipi değil")
    print(f"   rich_data: {rich}")

print()
answer = data.get("answer", "").lower()
if "erişimim yok" in answer or "internete erişim" in answer:
    print("❌ HATA: LLM hala 'internete erişimim yok' diyor!")
else:
    print("✅ LLM web arama sonuçlarını kullandı!")
