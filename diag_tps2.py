"""Profili yeniden uygula ve TPS ölç"""
import paramiko, json, time

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("88.246.13.23", port=2013, username="root", password="Kc435102mn", timeout=15)

# 1. Mevcut API config - getPerformanceProfile ile kontrol
print("Mevcut profil kontrol ediliyor...")
_, o, e = c.exec_command(
    "curl -s http://127.0.0.1:8000/api/admin/performance-profile "
    '-H "Authorization: Bearer $(curl -s -X POST http://127.0.0.1:8000/api/auth/login '
    "-d 'username=murteza.alemdar@karakoc.com.tr&password=Kc435102mn' "
    """-H 'Content-Type: application/x-www-form-urlencoded' | python3 -c 'import sys,json;print(json.load(sys.stdin).get("access_token",""))')" """,
    timeout=20,
)
out = o.read().decode().strip()
try:
    prof = json.loads(out)
    lc = prof.get("live_config", {})
    print(f"  num_gpu={lc.get('num_gpu')} num_ctx={lc.get('num_ctx')} num_batch={lc.get('num_batch')} num_thread={lc.get('num_thread')}")
except:
    print("  Profil parse edilemedi:", out[:200])

# 2. Warmup isteği - modelin yeni context ile yüklenmesini sağla
print("\nWarmup gönderiliyor (model 8K context ile yeniden yüklenecek)...")
_, o, e = c.exec_command(
    """curl -s http://127.0.0.1:11434/api/generate -d '{"model":"qwen2.5:72b","prompt":"test","stream":false,"options":{"num_predict":1,"num_ctx":8192}}'""",
    timeout=120,
)
print("  Warmup tamamlandı")

# 3. Biraz bekle
print("15 saniye bekleniyor...")
time.sleep(15)

# 4. GPU kontrol
_, o, e = c.exec_command(
    "nvidia-smi --query-gpu=index,memory.used,memory.total --format=csv,noheader",
    timeout=10,
)
print(f"\nGPU: {o.read().decode().strip()}")

# 5. Ollama ps
_, o, e = c.exec_command("curl -s http://127.0.0.1:11434/api/ps", timeout=10)
ps = json.loads(o.read().decode())
for m in ps.get("models", []):
    sz = m.get("size", 0) / 1e9
    vr = m.get("size_vram", 0) / 1e9
    name = m.get("name", "?")
    print(f"Model: {name}  total={sz:.1f}GB  vram={vr:.1f}GB  gpu_ratio={vr/sz*100:.0f}%")

# 6. TPS
print("\nTPS ölçülüyor...")
_, o, e = c.exec_command(
    """curl -s http://127.0.0.1:11434/api/generate -d '{"model":"qwen2.5:72b","prompt":"Merhaba, 1+1 ne eder?","stream":false,"options":{"num_predict":32,"num_ctx":8192}}'""",
    timeout=120,
)
data = json.loads(o.read().decode())
ec = data.get("eval_count", 0)
ed = data.get("eval_duration", 0)
pec = data.get("prompt_eval_count", 0)
ped = data.get("prompt_eval_duration", 0)
tps = ec / (ed / 1e9) if ed > 0 else 0
ptps = pec / (ped / 1e9) if ped > 0 else 0
print(f"Generation TPS: {tps:.1f}  (eval_count={ec}, eval_dur={ed/1e6:.0f}ms)")
print(f"Prompt TPS:     {ptps:.1f}  (prompt_count={pec})")

c.close()
