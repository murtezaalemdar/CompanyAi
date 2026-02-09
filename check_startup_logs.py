import paramiko
import time

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('192.168.0.12', username='root', password='435102')

commands = [
    ("Service Status", "systemctl status companyai-backend --no-pager"),
    ("Recent Logs", "journalctl -u companyai-backend -n 50 --no-pager"),
    ("Test API", "curl -s http://localhost:8000/api/health")
]

for name, cmd in commands:
    print(f"\n=== {name} ===")
    stdin, stdout, stderr = ssh.exec_command(cmd)
    out = stdout.read().decode()
    if out:
        print(out[:5000]) # Limit
    else:
        err = stderr.read().decode()
        if err: print("Stderr:", err)

ssh.close()
