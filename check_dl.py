import subprocess
r = subprocess.run(
    ['ssh', '-i', 'keys/companyai_key', 'root@192.168.0.12',
     "python3 -c 'f=open(\"/tmp/ollama_pull.log\",\"rb\"); d=f.read(); f.close(); lines=[l for l in d.split(b\"\\r\") if l.strip()]; print(lines[-1][-120:])'"],
    capture_output=True, timeout=15
)
out = r.stdout.decode('utf-8', 'ignore').strip()
print(out if out else "No output")
if r.stderr:
    print(r.stderr.decode('utf-8','ignore')[:200])
