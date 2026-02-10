"""Deploy sonrası hızlı test script'i"""
import paramiko
import json
import time

HOST = "192.168.0.12"
KEY_PATH = "keys/companyai_key"

def ssh_cmd(cmd, timeout=300):
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    pkey = paramiko.Ed25519Key.from_private_key_file(KEY_PATH)
    ssh.connect(HOST, username="root", pkey=pkey)
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    ssh.close()
    return out, err

# 1. Health check
print("=== 1. Health Check ===")
out, _ = ssh_cmd("curl -s http://127.0.0.1:8000/api/health")
print(out)

# 2. Login
print("\n=== 2. Login Test ===")
out, _ = ssh_cmd("curl -s -X POST http://127.0.0.1:8000/api/auth/login -d 'username=admin@company.ai&password=admin123'")
login_resp = json.loads(out)
token = login_resp["access_token"]
print(f"Token alındı: {token[:30]}...")

# 3. Web arama testi — bilgi sorusu (Google yapılandırılmamış → DuckDuckGo fallback)
print("\n=== 3. Web Arama Testi (bilgi intent) ===")
out, _ = ssh_cmd(f"curl -s -X POST http://127.0.0.1:8000/api/ask/multimodal -H 'Authorization: Bearer {token}' -F 'question=Turkiye baskenti neresi araştır'")
try:
    resp = json.loads(out)
    answer = resp.get('answer', '?')
    web_searched = resp.get('web_searched', False)
    sources = resp.get('sources', [])
    print(f"Yanıt: {answer[:300]}")
    print(f"Web arandı mı: {web_searched}")
    print(f"Kaynaklar: {sources}")
    print(f"Süre: {resp.get('processing_time_ms')}ms")
except Exception as e:
    print(f"Parse hatası: {e}")
    print(f"Raw: {out[:500]}")

# 4. Google API durumu kontrolü
print("\n=== 4. Google API Yapılandırma Durumu ===")
out, _ = ssh_cmd("grep -c 'GOOGLE_API_KEY' /opt/companyai/.env 2>/dev/null || echo 'Google env tanımsız'")
print(f"Durum: {out}")

# 5. İsim hatırlama (önceki session fix çalışıyor mu?)
print("\n=== 5. İsim Hatırlama (önceki fix kontrolü) ===")
out, _ = ssh_cmd(f"curl -s -X POST http://127.0.0.1:8000/api/ask/multimodal -H 'Authorization: Bearer {token}' -F 'question=Benim adım Murteza'")
resp1 = json.loads(out)
print(f"Tanıtma: {resp1.get('answer', '?')[:100]}")

time.sleep(1)
out, _ = ssh_cmd(f"curl -s -X POST http://127.0.0.1:8000/api/ask/multimodal -H 'Authorization: Bearer {token}' -F 'question=Benim ismim ne?'")
resp2 = json.loads(out)
answer2 = resp2.get('answer', '?')
print(f"Hatırlama: {answer2[:100]}")
has_name = "murteza" in answer2.lower()
print(f"İsim hatırlandı mı: {'✅ EVET' if has_name else '⚠️ HAYIR'}")

# 6. Backend logları — web search modülü aktif mi?
print("\n=== 6. Web Search Modülü Log Kontrolü ===")
out, _ = ssh_cmd("journalctl -u companyai-backend --since '5 min ago' --no-pager | grep -i 'web_search\\|google\\|ddg\\|duckduck' | tail -5")
print(out or "Web search logu bulunamadı (henüz arama yapılmamış olabilir)")

print("\n=== TEST TAMAMLANDI ===")

