
import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('192.168.0.12', username='root', password='435102')

cmds = [
    # Update .env
    "sed -i 's/5432/5433/g' /opt/companyai/.env",
    # Restart backend
    "systemctl restart companyai-backend",
    "sleep 3",
    "systemctl status companyai-backend --no-pager -l"
]

for cmd in cmds:
    print(f"Exec: {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd)
    out = stdout.read().decode()
    err = stderr.read().decode()
    if out: print(out)
    if err: print(err)

# Test API
print('=== Testing API ===')
stdin, stdout, stderr = ssh.exec_command('curl -s http://localhost:8000/api/health')
print(stdout.read().decode())

ssh.close()
