"""Deploy sonrası hızlı test script'i"""
import paramiko
import json
import time

HOST = "192.168.0.12"
KEY_PATH = "keys/companyai_key"

def ssh_cmd(cmd):
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    pkey = paramiko.Ed25519Key.from_private_key_file(KEY_PATH)
    ssh.connect(HOST, username="root", pkey=pkey)
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=300)
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

# 3. Yeni session oluştur (temiz başlangıç)
print("\n=== 3. Yeni Session Oluştur ===")
out, _ = ssh_cmd(f"curl -s -X POST http://127.0.0.1:8000/api/memory/sessions/new -H 'Authorization: Bearer {token}'")
session_resp = json.loads(out)
print(f"Yeni session: {session_resp}")
session_id = session_resp.get("session_id")

# 4. İsim tanıtma (multimodal — dosyasız)
print("\n=== 4. İsim Tanıtma (multimodal endp.) ===")
out, _ = ssh_cmd(f"curl -s -X POST http://127.0.0.1:8000/api/ask/multimodal -H 'Authorization: Bearer {token}' -F 'question=Benim adım Murteza'")
resp = json.loads(out)
print(f"Yanıt: {resp.get('answer', '?')[:200]}")
print(f"Süre: {resp.get('processing_time_ms')}ms")

# 5. İsmimi hatırlıyor mu? (multimodal — dosyasız)
print("\n=== 5. İsim Hatırlama Testi ===")
time.sleep(1)
out, _ = ssh_cmd(f"curl -s -X POST http://127.0.0.1:8000/api/ask/multimodal -H 'Authorization: Bearer {token}' -F 'question=Benim ismim ne?'")
resp = json.loads(out)
answer = resp.get('answer', '?')
print(f"Yanıt: {answer[:200]}")
print(f"Süre: {resp.get('processing_time_ms')}ms")
has_name = "murteza" in answer.lower() or "Murteza" in answer
print(f"İsim hatırlandı mı: {'✅ EVET' if has_name else '⚠️ HAYIR'}")

# 6. Session mesajlarını kontrol et
print("\n=== 6. Session Mesajları Kontrolü ===")
out, _ = ssh_cmd(f"curl -s http://127.0.0.1:8000/api/memory/sessions/{session_id}/messages -H 'Authorization: Bearer {token}'")
msg_resp = json.loads(out)
messages = msg_resp.get("messages", [])
print(f"Mesaj sayısı: {len(messages)}")
for m in messages:
    print(f"  Q: {m.get('question', '')[:60]}")
    print(f"  A: {m.get('answer', '')[:60]}")

# 7. Session listesi
print("\n=== 7. Session Listesi ===")
out, _ = ssh_cmd(f"curl -s http://127.0.0.1:8000/api/memory/sessions -H 'Authorization: Bearer {token}'")
sess_resp = json.loads(out)
sessions = sess_resp.get("sessions", [])
print(f"Toplam session: {len(sessions)}")
for s in sessions[:3]:
    print(f"  [{s.get('id')}] {s.get('title', '?')[:40]} (active={s.get('is_active')})")

# 8. Session switch testi
if len(sessions) > 1:
    other = [s for s in sessions if s["id"] != session_id]
    if other:
        print(f"\n=== 8. Session Switch Testi (→ {other[0]['id']}) ===")
        out, _ = ssh_cmd(f"curl -s -X POST http://127.0.0.1:8000/api/memory/sessions/{other[0]['id']}/switch -H 'Authorization: Bearer {token}'")
        switch_resp = json.loads(out)
        print(f"Switch başarılı: {switch_resp.get('success')}")
        print(f"Mesaj sayısı: {len(switch_resp.get('messages', []))}")
else:
    print("\n=== 8. Session Switch: Tek session var, atlıyorum ===")

# 9. Correlation ID kontrolü
print("\n=== 9. X-Request-ID Kontrolü ===")
out, _ = ssh_cmd("curl -sI http://127.0.0.1:8000/api/health 2>&1 | grep -i x-request-id")
print(out or "Header bulunamadı")

print("\n=== TEST TAMAMLANDI ===")

