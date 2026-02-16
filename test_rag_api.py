"""Test RAG API on Server 2"""
import paramiko, json

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('88.246.13.23', port=2013, username='root', password='Kc435102mn', timeout=30)

# Login first (OAuth2 form data)
cmd = "curl -s -X POST http://localhost:8000/api/auth/login -d 'username=admin@company.ai&password=admin123'"
_, stdout, _ = ssh.exec_command(cmd, timeout=30)
stdout.channel.settimeout(30)
login_raw = stdout.read().decode()
print(f"LOGIN RAW: {login_raw[:200]}")
login_result = json.loads(login_raw)
token = login_result.get('access_token', '')
print(f"TOKEN: {token[:30]}..." if token else "NO TOKEN!")

test_questions = [
    "sirket hakkinda bilgi ver",
    "katalogumuzdaki urunler neler",
    "uretim surecimiz nasil isliyor",
]

for q in test_questions:
    payload = json.dumps({"question": q, "department": "Genel", "session_id": "test-rag-check"})
    cmd = f"curl -s -X POST http://localhost:8000/api/ask -H 'Content-Type: application/json' -H 'Authorization: Bearer {token}' -d '{payload}'"
    _, stdout, stderr = ssh.exec_command(cmd, timeout=120)
    stdout.channel.settimeout(120)
    result = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    print(f"\n{'='*60}")
    print(f"SORU: {q}")
    print(f"RAW RESPONSE ({len(result)} chars): {result[:1000]}")
    if err:
        print(f"STDERR: {err[:300]}")
    try:
        data = json.loads(result)
        answer = data.get('answer', '')[:300]
        sources = data.get('sources', [])
        mode = data.get('mode', '?')
        intent = data.get('intent', '?')
        print(f"INTENT: {intent} | MODE: {mode}")
        print(f"SOURCES: {sources}")
        print(f"CEVAP: {answer}")
    except Exception as ex:
        print(f"JSON PARSE ERROR: {ex}")

ssh.close()
print("\n\nTEST TAMAMLANDI")
