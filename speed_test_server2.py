"""Server 2 — Optimizasyon sonrası hız testi"""
import paramiko, json, time

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('88.246.13.23', port=2013, username='root', password='Kc435102mn',
            timeout=30, allow_agent=False, look_for_keys=False)

def run(cmd, timeout=600):
    _, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    return stdout.read().decode().strip()

print("="*60)
print("  HIZ TESTİ — Optimizasyon Sonrası")
print("="*60)

# Önce GPU katman durumunu kontrol et
print("\n--- GPU Katman Durumu ---")
ps = run("curl -s http://localhost:11434/api/ps 2>/dev/null")
try:
    pd = json.loads(ps)
    for m in pd.get("models", []):
        size = m.get("size", 0)
        vram = m.get("size_vram", 0)
        pct = (vram/size*100) if size else 0
        print(f"  {m['name']}: VRAM {vram/1e9:.1f}GB / Toplam {size/1e9:.1f}GB ({pct:.0f}%)")
except:
    print(f"  {ps[:200]}")

# Backend üzerinden gerçek bir test (API ile — kullanıcıyla aynı akış)
print("\n--- Test 1: Kısa soru (Ollama direkt) ---")
start = time.time()
out = run('curl -s http://localhost:11434/api/chat -d \'{"model":"qwen2.5:72b","messages":[{"role":"user","content":"İnegöl nerededir? Kısa cevap ver."}],"stream":false,"options":{"num_predict":100,"num_thread":24,"num_ctx":4096,"temperature":0.3}}\' 2>/dev/null', timeout=600)
elapsed1 = time.time() - start
try:
    d = json.loads(out)
    resp = d.get("message", {}).get("content", "")[:200]
    eval_count = d.get("eval_count", 0)
    eval_dur = d.get("eval_duration", 0)
    tok_per_sec = eval_count / (eval_dur/1e9) if eval_dur > 0 else 0
    print(f"  Yanıt: {resp}")
    print(f"  Süre: {elapsed1:.1f}s")
    print(f"  Token: {eval_count}, Hız: {tok_per_sec:.1f} tok/s")
    print(f"  Prompt eval: {d.get('prompt_eval_duration',0)/1e9:.1f}s")
except Exception as e:
    print(f"  Hata: {e}")
    print(f"  {out[:300]}")

# Test 2 — Daha uzun bir soru
print("\n--- Test 2: Uzun soru (Ollama direkt) ---")
start = time.time()
out = run('curl -s http://localhost:11434/api/chat -d \'{"model":"qwen2.5:72b","messages":[{"role":"user","content":"Bugün İnegöl de hava nasıl?"}],"stream":false,"options":{"num_predict":256,"num_thread":24,"num_ctx":4096,"temperature":0.7}}\' 2>/dev/null', timeout=600)
elapsed2 = time.time() - start
try:
    d = json.loads(out)
    resp = d.get("message", {}).get("content", "")[:200]
    eval_count = d.get("eval_count", 0)
    eval_dur = d.get("eval_duration", 0)
    tok_per_sec = eval_count / (eval_dur/1e9) if eval_dur > 0 else 0
    print(f"  Yanıt: {resp}")
    print(f"  Süre: {elapsed2:.1f}s")
    print(f"  Token: {eval_count}, Hız: {tok_per_sec:.1f} tok/s")
    print(f"  Prompt eval: {d.get('prompt_eval_duration',0)/1e9:.1f}s")
except Exception as e:
    print(f"  Hata: {e}")
    print(f"  {out[:300]}")

# Test 3 — Backend API üzerinden (web search dahil olabilir)
print("\n--- Test 3: Backend API (gerçek akış) ---")
start = time.time()
out = run('curl -s -X POST http://localhost:8000/api/ask -H "Content-Type: application/json" -H "Authorization: Bearer test" -d \'{"question":"2+2 kaç eder?"}\' 2>/dev/null', timeout=600)
elapsed3 = time.time() - start
print(f"  Süre: {elapsed3:.1f}s")
print(f"  Yanıt: {out[:200]}")

print(f"\n{'='*60}")
print(f"  KARŞILAŞTIRMA")
print(f"  Önce (ekran görüntüsü): 205,211 ms (205 sn)")  
print(f"  Şimdi Test 1: {elapsed1*1000:.0f} ms ({elapsed1:.1f} sn)")
print(f"  Şimdi Test 2: {elapsed2*1000:.0f} ms ({elapsed2:.1f} sn)")
print(f"{'='*60}")

ssh.close()
