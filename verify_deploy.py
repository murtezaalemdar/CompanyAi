"""Health check - her iki sunucu v3.9.3 kontrolü"""
import paramiko
import json

servers = [
    {"name": "Server 1", "host": "192.168.0.12", "port": 22, "key": "keys/companyai_key", "password": "435102"},
    {"name": "Server 2", "host": "88.246.13.23", "port": 2013, "key": "keys/server2_key", "password": "Kc435102mn"},
]

for s in servers:
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            ssh.connect(
                s["host"], port=s["port"], username="root",
                key_filename=s["key"], timeout=15,
                allow_agent=False, look_for_keys=False
            )
        except Exception:
            ssh.connect(
                s["host"], port=s["port"], username="root",
                password=s.get("password", ""),
                timeout=15, allow_agent=False, look_for_keys=False
            )
        stdin, stdout, stderr = ssh.exec_command(
            "curl -s http://localhost:8000/api/health 2>/dev/null || echo ERROR"
        )
        health = stdout.read().decode().strip()
        try:
            data = json.loads(health)
            version = data.get("version", "?")
            status = data.get("status", "?")
            print(f"  {s['name']}: v{version} — {status}")
        except Exception:
            print(f"  {s['name']}: {health[:120]}")
        ssh.close()
    except Exception as e:
        print(f"  {s['name']}: HATA — {e}")
