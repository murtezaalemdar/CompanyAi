import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('192.168.0.12', username='root', password='435102')

print("=== Check Port 8000 === ")
stdin, stdout, stderr = ssh.exec_command("netstat -tuln | grep 8000")
print(stdout.read().decode())

print("=== Check processes using port 8000 ===")
stdin, stdout, stderr = ssh.exec_command("lsof -i :8000")
print(stdout.read().decode())

print("=== Check logs again (fuller context) ===")
stdin, stdout, stderr = ssh.exec_command("journalctl -u companyai-backend -n 100 --no-pager")
print(stdout.read().decode())

ssh.close()
