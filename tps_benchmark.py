#!/usr/bin/env python3
"""TPS Benchmark — Ollama modelleri için"""
import subprocess, json, time

def benchmark(model, prompt, label):
    print(f"\n{'='*50}")
    print(f"Model: {model} | {label}")
    print(f"{'='*50}")
    t0 = time.time()
    try:
        r = subprocess.run(
            ["curl", "-s", "http://localhost:11434/api/chat", "-d",
             json.dumps({
                 "model": model,
                 "messages": [{"role":"user","content": prompt}],
                 "stream": False,
                 "options": {"num_predict": 100}
             })],
            capture_output=True, text=True, timeout=300
        )
        wall = time.time() - t0
        d = json.loads(r.stdout)
        
        e = d.get("eval_count", 0)
        dur = d.get("eval_duration", 0)
        pd = d.get("prompt_eval_duration", 0)
        td = d.get("total_duration", 0)
        
        tps = e / (dur / 1e9) if dur else 0
        
        print(f"  Tokens uretildi : {e}")
        print(f"  Token uretim    : {dur/1e9:.1f}s")
        print(f"  TPS             : {tps:.2f} tok/s")
        print(f"  Prompt eval     : {pd/1e9:.1f}s")
        print(f"  Toplam sure     : {td/1e9:.1f}s")
        print(f"  Wall clock      : {wall:.1f}s")
        
        # Yanit
        msg = d.get("message", {}).get("content", "")
        print(f"  Yanit ({len(msg)} chr) : {msg[:120]}...")
        return tps
    except Exception as ex:
        print(f"  HATA: {ex}")
        return 0

# Test 1: Kisa soru
tps1 = benchmark("qwen2.5:72b", "Merhaba, nasilsin?", "Kisa soru")

# Test 2: Bilgi sorusu
tps2 = benchmark("qwen2.5:72b", "Turkiye'nin baskenti neresidir?", "Bilgi sorusu")

# Test 3: gpt-oss:20b (varsa)
tps3 = benchmark("gpt-oss:20b", "Merhaba, nasilsin?", "Kisa soru (20B)")

print(f"\n{'='*50}")
print(f"SONUC: qwen2.5:72b ortalama TPS = {(tps1+tps2)/2:.2f} tok/s")
print(f"SONUC: gpt-oss:20b TPS = {tps3:.2f} tok/s")
print(f"{'='*50}")
