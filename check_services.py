import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('192.168.0.12', username='root', password='435102')

print("=== Check Ollama Service ===")
stdin, stdout, stderr = ssh.exec_command('systemctl status ollama --no-pager')
print(stdout.read().decode())

print("=== Check Ollama API (11434) ===")
stdin, stdout, stderr = ssh.exec_command('curl -s http://localhost:11434/api/tags')
print(stdout.read().decode())

print("=== Check Backend API (8000) Verbose ===")
stdin, stdout, stderr = ssh.exec_command('curl -v http://localhost:8000/api/health 2>&1')
print(stdout.read().decode())   

ssh.close()
