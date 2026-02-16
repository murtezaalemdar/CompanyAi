import requests, json, time
print('Testing Ollama...')
start = time.time()
try:
    r = requests.post('http://127.0.0.1:11434/api/chat', json={'model':'qwen2.5:72b','messages':[{'role':'user','content':'hi'}],'stream':False}, timeout=300)
    elapsed = time.time() - start
    print(f'HTTP: {r.status_code} ({elapsed:.1f}s)')
    if r.status_code == 200:
        d = r.json()
        print(f'OK: {d.get("message",{}).get("content","")[:200]}')
    else:
        print(f'Error: {r.text[:500]}')
except Exception as e:
    elapsed = time.time() - start
    print(f'Exception ({elapsed:.1f}s): {e}')
