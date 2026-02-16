"""Server2 Ollama Chat Test + Log Analizi"""
import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('88.246.13.23', port=2013, username='root', password='Kc435102mn', timeout=15)

# Test 1: Ollama chat doğrudan test
print("=== TEST 1: qwen2.5:72b-q3 ile /api/chat testi ===")
test_script = r"""
import json, urllib.request
payload = json.dumps({"model": "qwen2.5:72b-q3", "messages": [{"role": "user", "content": "say hi"}], "stream": False}).encode()
req = urllib.request.Request("http://127.0.0.1:11434/api/chat", data=payload, headers={"Content-Type": "application/json"})
try:
    resp = urllib.request.urlopen(req, timeout=120)
    print("STATUS:", resp.status)
    data = json.loads(resp.read())
    print("OK:", data.get("message",{}).get("content","")[:200])
except Exception as e:
    print("ERROR:", str(e))
    if hasattr(e, "read"):
        print("BODY:", e.read().decode()[:500])
"""
# Write script to remote, then run
ssh.exec_command("cat > /tmp/test_chat.py << 'PYEOF'\n" + test_script + "\nPYEOF")
import time; time.sleep(1)
stdin, stdout, stderr = ssh.exec_command("python3 /tmp/test_chat.py", timeout=180)
out = stdout.read().decode()
err = stderr.read().decode()
print(out)
if err: print("[STDERR]", err)

# Test 2: Backend chat/multimodal logları
print("\n=== TEST 2: Backend chat/error logları (son 6 saat) ===")
stdin2, stdout2, stderr2 = ssh.exec_command(
    'journalctl -u companyai-backend --no-pager --since "6 hours ago" 2>&1 | grep -iE "multimodal|ollama|500|error|traceback|llm|exception" | tail -30',
    timeout=30
)
print(stdout2.read().decode())

# Test 3: Ollama loglarında hata var mı?
print("\n=== TEST 3: Ollama error logları (son 6 saat) ===")
stdin3, stdout3, stderr3 = ssh.exec_command(
    'journalctl -u ollama --no-pager --since "6 hours ago" 2>&1 | grep -iE "error|500|panic|fatal|fail" | tail -20',
    timeout=30
)
print(stdout3.read().decode())

# Test 4: generate endpoint testi (chat yerine)
print("\n=== TEST 4: /api/generate testi ===")
gen_script = r"""
import json, urllib.request
payload = json.dumps({"model": "qwen2.5:72b-q3", "prompt": "say hi", "stream": False}).encode()
req = urllib.request.Request("http://127.0.0.1:11434/api/generate", data=payload, headers={"Content-Type": "application/json"})
try:
    resp = urllib.request.urlopen(req, timeout=120)
    print("STATUS:", resp.status)
    data = json.loads(resp.read())
    print("OK:", data.get("response","")[:200])
except Exception as e:
    print("ERROR:", str(e))
    if hasattr(e, "read"):
        print("BODY:", e.read().decode()[:500])
"""
ssh.exec_command("cat > /tmp/test_gen.py << 'PYEOF'\n" + gen_script + "\nPYEOF")
time.sleep(1)
stdin4, stdout4, stderr4 = ssh.exec_command("python3 /tmp/test_gen.py", timeout=180)
out4 = stdout4.read().decode()
err4 = stderr4.read().decode()
print(out4)
if err4: print("[STDERR]", err4)

ssh.close()
print("\n✅ Test tamamlandı.")
