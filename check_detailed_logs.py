import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('192.168.0.12', username='root', password='435102')

print("=== Journal Logs ===")
stdin, stdout, stderr = ssh.exec_command("journalctl -u companyai-backend -n 100 --no-pager")
print(stdout.read().decode())

print("\n=== Ports ===")
stdin, stdout, stderr = ssh.exec_command("netstat -tuln | grep 8000")
print(stdout.read().decode())

ssh.close()
