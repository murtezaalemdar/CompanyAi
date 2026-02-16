"""Server 2 TPS Teşhis Scripti"""
import paramiko, json

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("88.246.13.23", port=2013, username="root", password="Kc435102mn", timeout=15)

# 1. Ollama ps — model VRAM kullanımı
_, o, e = c.exec_command("curl -s http://127.0.0.1:11434/api/ps", timeout=10)
ps = json.loads(o.read().decode())
for m in ps.get("models", []):
    sz = m.get("size", 0) / 1e9
    vr = m.get("size_vram", 0) / 1e9
    name = m.get("name", "?")
    print(f"Model: {name}  total={sz:.1f}GB  vram={vr:.1f}GB  gpu_ratio={vr/sz*100:.0f}%")

# 2. Ollama servis environment
print()
_, o, e = c.exec_command("grep -i environment /etc/systemd/system/ollama.service", timeout=5)
env_out = o.read().decode().strip()
print("Ollama Env:", env_out if env_out else "(boş)")

# 3. TPS benchmark
print()
cmd = 'curl -s http://127.0.0.1:11434/api/generate -d \'{"model":"qwen2.5:72b","prompt":"Merhaba, 1+1 ne eder?","stream":false,"options":{"num_predict":32}}\''
_, o, e = c.exec_command(cmd, timeout=120)
raw = o.read().decode()
data = json.loads(raw)

ec = data.get("eval_count", 0)
ed = data.get("eval_duration", 0)
pec = data.get("prompt_eval_count", 0)
ped = data.get("prompt_eval_duration", 0)
td = data.get("total_duration", 0)

tps = ec / (ed / 1e9) if ed > 0 else 0
ptps = pec / (ped / 1e9) if ped > 0 else 0

print(f"Generation TPS: {tps:.1f} tok/s  (eval_count={ec}, eval_dur={ed/1e6:.0f}ms)")
print(f"Prompt TPS:     {ptps:.1f} tok/s  (prompt_count={pec}, prompt_dur={ped/1e6:.0f}ms)")
print(f"Total duration: {td/1e6:.0f}ms")

c.close()
