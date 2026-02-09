import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('192.168.0.12', username='root', password='435102')

# Check error logs
print('=== Checking journalctl logs ===')
stdin, stdout, stderr = ssh.exec_command('journalctl -u companyai-backend -n 50 --no-pager')
print(stdout.read().decode())

# Try running manually
print('\n=== Trying to run manually ===')
stdin, stdout, stderr = ssh.exec_command('cd /opt/companyai && python3 -c "from app.main import app; print(app)"')
out = stdout.read().decode()
err = stderr.read().decode()
print(f'Out: {out}')
print(f'Err: {err}')

ssh.close()
