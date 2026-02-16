"""CompanyAI TPS (Tokens Per Second) Ölçüm Aracı — Paramiko ile"""
import json
import sys
import time

try:
    import paramiko
except ImportError:
    print("paramiko yükleniyor...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "paramiko", "-q"])
    import paramiko

SERVERS = [
    {
        "name": "Server 1 (CPU-only, Xeon 4316)",
        "host": "192.168.0.12",
        "port": 22,
        "key_file": "keys/companyai_key",
        "password": None,
    },
    {
        "name": "Server 2 (RTX 4080 GPU)",
        "host": "88.246.13.23",
        "port": 2013,
        "key_file": None,
        "password": "Kc435102mn",
    },
]

PROMPT = "Merhaba, nasılsın?"
TIMEOUT = 600  # saniye — CPU-only 72B için yeterli

results = []

for srv in SERVERS:
    print(f"\n{'='*60}")
    print(f"  {srv['name']} — {srv['host']}:{srv['port']}")
    print(f"{'='*60}")

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        connect_kwargs = {
            "hostname": srv["host"],
            "port": srv["port"],
            "username": "root",
            "timeout": 15,
        }
        if srv["key_file"]:
            connect_kwargs["key_filename"] = srv["key_file"]
        if srv["password"]:
            connect_kwargs["password"] = srv["password"]

        client.connect(**connect_kwargs)
        print("  SSH bağlantısı OK")

        # Ollama generate API çağrısı
        json_payload = json.dumps({
            "model": "qwen2.5:72b",
            "prompt": PROMPT,
            "stream": False
        })
        cmd = f"curl -s --max-time {TIMEOUT} http://localhost:11434/api/generate -d '{json_payload}'"

        print(f"  Ollama'ya istek gönderiliyor (timeout={TIMEOUT}s)...")
        t0 = time.time()
        stdin, stdout, stderr = client.exec_command(cmd, timeout=TIMEOUT)
        raw = stdout.read().decode("utf-8", errors="replace")
        elapsed = time.time() - t0
        err = stderr.read().decode("utf-8", errors="replace")

        if err.strip():
            print(f"  stderr: {err[:200]}")

        if not raw.strip():
            print(f"  Boş yanıt (süre: {elapsed:.1f}s)")
            continue

        data = json.loads(raw)

        if "error" in data:
            print(f"  Ollama hatası: {data['error']}")
            continue

        eval_count = data.get("eval_count", 0)
        eval_duration_ns = data.get("eval_duration", 1)
        prompt_eval_count = data.get("prompt_eval_count", 0)
        prompt_eval_dur_ns = data.get("prompt_eval_duration", 1)
        total_dur_ns = data.get("total_duration", 0)

        eval_sec = eval_duration_ns / 1e9
        prompt_sec = prompt_eval_dur_ns / 1e9
        total_sec = total_dur_ns / 1e9

        gen_tps = eval_count / eval_sec if eval_sec > 0 else 0
        prompt_tps = prompt_eval_count / prompt_sec if prompt_sec > 0 else 0

        print(f"  Model: {data.get('model', '?')}")
        print(f"  Prompt tokens: {prompt_eval_count}")
        print(f"  Prompt eval: {prompt_sec:.2f}s ({prompt_tps:.2f} tok/s)")
        print(f"  Generation tokens: {eval_count}")
        print(f"  Generation time: {eval_sec:.2f}s")
        print(f"  ★ Generation TPS: {gen_tps:.2f} tok/s")
        print(f"  Total duration: {total_sec:.2f}s")
        print(f"  Response preview: {data.get('response', '')[:150]}...")

        results.append({
            "server": srv["name"],
            "gen_tps": gen_tps,
            "prompt_tps": prompt_tps,
            "eval_count": eval_count,
            "total_sec": total_sec,
        })

    except paramiko.AuthenticationException:
        print("  AUTH HATASI — Anahtar veya şifre geçersiz")
    except Exception as e:
        print(f"  Hata: {type(e).__name__}: {e}")
    finally:
        client.close()

print(f"\n{'='*60}")
print("  ÖZET")
print(f"{'='*60}")
if results:
    for r in results:
        print(f"  {r['server']}: {r['gen_tps']:.2f} tok/s  ({r['eval_count']} token, {r['total_sec']:.1f}s)")
else:
    print("  Hiçbir sunucudan TPS verisi alınamadı.")
