import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('192.168.0.12', username='root', password='435102')

print("=== Process List ===")
stdin, stdout, stderr = ssh.exec_command("ps aux | grep uvicorn")
print(stdout.read().decode())

ssh.close()
