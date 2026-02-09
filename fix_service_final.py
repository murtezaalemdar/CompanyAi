import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('192.168.0.12', username='root', password='435102')

# Update service file: use python -m uvicorn
print('=== Updating service file ===')
service_content = """[Unit]
Description=CompanyAI Backend
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/companyai
Environment=PATH=/usr/local/bin:/usr/bin:/bin
Environment=PYTHONPATH=/opt/companyai
ExecStart=/usr/bin/python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --loop asyncio
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
"""

# Write service file
cmd = f"cat > /etc/systemd/system/companyai-backend.service << 'EOF'\n{service_content}EOF"
stdin, stdout, stderr = ssh.exec_command(cmd)
stdout.read()

# Reload and restart
commands = [
    'systemctl daemon-reload',
    'systemctl restart companyai-backend',
    'sleep 3',
    'systemctl status companyai-backend --no-pager -l',
    'curl -v http://localhost:8000/api/health'
]
for cmd in commands:
    print(f'Exec: {cmd}')
    stdin, stdout, stderr = ssh.exec_command(cmd)
    out = stdout.read().decode()
    err = stderr.read().decode()
    if out: print(out[:500]) # Limit output
    if err: print(err[:500])

ssh.close()
print('\n✅ Done!')
