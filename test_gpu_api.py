"""Server 2 — API yanıtını kontrol et"""
import paramiko, json

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('88.246.13.23', port=2013, username='root', password='Kc435102mn',
            timeout=30, allow_agent=False, look_for_keys=False)

def run(cmd, timeout=30):
    _, stdout, _ = ssh.exec_command(cmd, timeout=timeout)
    return stdout.read().decode().strip()

# psutil check
print("psutil:", run("/opt/companyai/venv/bin/python3 -c 'import psutil; print(psutil.__version__)' 2>&1"))

# Backend durumu
print("Backend:", run("systemctl is-active companyai-backend"))

# Login + API test
login = run("""curl -s -X POST http://localhost:8000/api/auth/login -H 'Content-Type: application/json' -d '{"email":"murteza.alemdar@karakoc.com","password":"Kc435102mn"}' 2>/dev/null""")
try:
    token = json.loads(login).get('access_token', '')
    if not token:
        # Farklı şifre dene
        login = run("""curl -s -X POST http://localhost:8000/api/auth/login -H 'Content-Type: application/json' -d '{"email":"murteza.alemdar@karakoc.com","password":"admin123"}' 2>/dev/null""")
        token = json.loads(login).get('access_token', '')
    
    if token:
        result = run(f"curl -s http://localhost:8000/api/admin/stats/system-resources -H 'Authorization: Bearer {token}' 2>/dev/null")
        d = json.loads(result)
        print(f"\nCPU: {d.get('cpu_percent')}%")
        print(f"Memory: {d.get('memory_percent')}%")
        print(f"Disk: {d.get('disk_percent')}%")
        print(f"GPU: {json.dumps(d.get('gpu'), indent=2)}")
        print(f"Ollama GPU: {json.dumps(d.get('ollama_gpu'), indent=2)}")
    else:
        print(f"Login hatası: {login[:200]}")
except Exception as e:
    print(f"Hata: {e}")
    print(f"Login yanıt: {login[:200]}")

ssh.close()
