"""Server 2 - Düzeltme doğrulama testi."""
import paramiko
import json

HOST = "88.246.13.23"
PORT = 2013
USER = "root"
PWD  = "Kc435102mn"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, port=PORT, username=USER, password=PWD, timeout=15)

def run(cmd, timeout=60):
    _, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    return stdout.read().decode('utf-8', errors='replace').strip()

print("=" * 60)
print("  DÜZELTME DOĞRULAMA TESTİ")
print("=" * 60)

# 1. Ollama env
print("\n1. Ollama Environment:")
env = run("cat /etc/default/ollama")
print(f"   {env}")

# 2. Ollama ps - model yüklü mü, VRAM=0 mı
print("\n2. Ollama PS (model durumu):")
ps = run("curl -s http://127.0.0.1:11434/api/ps")
ps_data = json.loads(ps) if ps else {}
for m in ps_data.get("models", []):
    vram_gb = m.get("size_vram", 0) / (1024**3)
    size_gb = m.get("size", 0) / (1024**3)
    print(f"   Model: {m['name']}")
    print(f"   Toplam: {size_gb:.1f}GB, VRAM: {vram_gb:.1f}GB ({'GPU kullanmıyor ✅' if vram_gb < 0.1 else '⚠️ GPU kullanıyor!'})")

# 3. Backend health
print("\n3. Backend Health:")
health = run("curl -s http://127.0.0.1:8000/health")
print(f"   {health}")

# 4. GPU kullanımı
print("\n4. GPU Kullanımı:")
gpu = run("nvidia-smi --query-compute-apps=pid,name,used_memory --format=csv,noheader 2>/dev/null")
if gpu:
    for line in gpu.split('\n'):
        parts = line.strip().split(', ')
        pid = parts[0] if len(parts) > 0 else '?'
        name = parts[1] if len(parts) > 1 else '?'
        mem = parts[2] if len(parts) > 2 else '?'
        is_ollama = 'ollama' in name.lower()
        print(f"   PID {pid}: {name} ({mem}) {'⚠️ OLLAMA!' if is_ollama else '✅'}")
else:
    print("   GPU prosesi yok ✅")

# 5. Backend loglarında son hata var mı
print("\n5. Backend Son Hatalar:")
errors = run("journalctl -u companyai-backend --since '5 min ago' --no-pager 2>/dev/null | grep -i 'error\\|500' | tail -5")
if errors:
    print(f"   ⚠️ Hatalar bulundu:\n   {errors}")
else:
    print("   ✅ Son 5 dakikada hata yok")

# 6. Ollama direkt chat testi
print("\n6. Ollama Chat Testi:")
chat = run('curl -s -w "\\nHTTP:%{http_code}" -X POST http://127.0.0.1:11434/api/chat -d \'{"model":"qwen2.5:72b-q3","messages":[{"role":"user","content":"Say hello"}],"stream":false,"options":{"num_predict":10}}\' --max-time 120', timeout=130)
if "HTTP:200" in chat:
    print("   ✅ Ollama chat çalışıyor (CPU-only)")
else:
    print(f"   ❌ Sonuç: {chat[:200]}")

print("\n" + "=" * 60)
print("  DOĞRULAMA TAMAMLANDI")
print("=" * 60)
ssh.close()
