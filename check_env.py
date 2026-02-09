import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('192.168.0.12', username='root', password='435102')

# Check .env file
print('=== .env content ===')
stdin, stdout, stderr = ssh.exec_command('cat /opt/companyai/.env')
print(stdout.read().decode())

# Check full error
print('\n=== Full error ===')
stdin, stdout, stderr = ssh.exec_command('cd /opt/companyai && python3 -c "from app.config import settings; print(settings)" 2>&1')
print(stdout.read().decode())

ssh.close()
