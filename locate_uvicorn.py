import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('192.168.0.12', username='root', password='435102')

print("=== which uvicorn ===")
stdin, stdout, stderr = ssh.exec_command("which uvicorn")
print(stdout.read().decode())

print("=== whereis uvicorn ===")
stdin, stdout, stderr = ssh.exec_command("whereis uvicorn")
print(stdout.read().decode())

print("=== check pip install location ===")
stdin, stdout, stderr = ssh.exec_command("pip3 show uvicorn | grep Location")
print(stdout.read().decode())

ssh.close()
