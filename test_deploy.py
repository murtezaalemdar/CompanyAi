"""Deploy sonrası hızlı test script'i"""
import paramiko
import json

HOST = "192.168.0.12"
KEY_PATH = "keys/companyai_key"

def ssh_cmd(cmd):
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    pkey = paramiko.Ed25519Key.from_private_key_file(KEY_PATH)
    ssh.connect(HOST, username="root", pkey=pkey)
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=30)
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    ssh.close()
    return out, err

# 1. Health check
print("=== 1. Health Check ===")
out, _ = ssh_cmd("curl -s http://127.0.0.1:8000/api/health")
print(out)

# 2. Login test (access + refresh token)
print("\n=== 2. Login Test ===")
out, _ = ssh_cmd("curl -s -X POST http://127.0.0.1:8000/api/auth/login -d 'username=admin@company.ai&password=admin123'")
login_resp = json.loads(out)
print(f"access_token: {login_resp.get('access_token', 'YOK')[:30]}...")
print(f"refresh_token: {login_resp.get('refresh_token', 'YOK')[:30]}...")
print(f"token_type: {login_resp.get('token_type', 'YOK')}")
token = login_resp["access_token"]
refresh = login_resp.get("refresh_token", "")

# 3. Refresh token test
if refresh:
    print("\n=== 3. Refresh Token Test ===")
    payload = json.dumps({"refresh_token": refresh})
    cmd = f"curl -s -X POST http://127.0.0.1:8000/api/auth/refresh -H 'Content-Type: application/json' -d '{payload}'"
    out, _ = ssh_cmd(cmd)
    try:
        ref_resp = json.loads(out)
        print(f"new access_token: {ref_resp.get('access_token', 'YOK')[:30]}...")
        print(f"new refresh_token: {ref_resp.get('refresh_token', 'YOK')[:30]}...")
    except:
        print(f"Refresh response: {out}")

# 4. Authenticated chat test
print("\n=== 4. Chat (Ask) Test ===")
ask_payload = json.dumps({"question": "Merhaba, nasılsın?"})
cmd = f"curl -s -X POST http://127.0.0.1:8000/api/ask -H 'Authorization: Bearer {token}' -H 'Content-Type: application/json' -d '{ask_payload}'"
out, _ = ssh_cmd(cmd)
try:
    ask_resp = json.loads(out)
    answer = ask_resp.get("answer", ask_resp.get("detail", "?"))
    print(f"Cevap: {answer[:200]}")
except:
    print(f"Ask response: {out[:300]}")

# 5. Correlation ID check
print("\n=== 5. Correlation ID (X-Request-ID) Test ===")
out, _ = ssh_cmd("curl -sI http://127.0.0.1:8000/api/health 2>&1 | grep -i x-request-id || echo 'X-Request-ID header BULUNAMADI'")
print(out)

# 6. Rate limit header check
print("\n=== 6. Rate Limit Header Test ===")
out, _ = ssh_cmd("curl -sI http://127.0.0.1:8000/api/health 2>&1 | grep -i 'x-ratelimit\\|retry-after' || echo 'Rate limit headers yok (normal - health exempt olabilir)'")
print(out)

print("\n=== TEST TAMAMLANDI ===")
