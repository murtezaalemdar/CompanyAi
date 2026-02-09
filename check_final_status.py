import paramiko
import time

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('192.168.0.12', username='root', password='435102')

commands = [
    ("Frontend (Nginx)", "curl -s -I http://localhost | head -1"),
    ("Backend via Proxy", "curl -s http://localhost/api/health"),
    ("Backend Direct", "curl -s http://localhost:8000/api/health"),
    ("Ollama (Port 11434)", "curl -s http://localhost:11434/api/tags | head -c 100")
]

for name, cmd in commands:
    print(f"\n=== {name} ===")
    stdin, stdout, stderr = ssh.exec_command(cmd)
    out = stdout.read().decode().strip()
    if out:
        print(out)
    else:
        print("Empty response or error")
        error = stderr.read().decode()
        if error: print("Stderr:", error)

ssh.close()
