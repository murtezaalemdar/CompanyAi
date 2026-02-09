import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('192.168.0.12', username='root', password='435102')

print("=== Redis Status ===")
stdin, stdout, stderr = ssh.exec_command("systemctl status redis-server --no-pager")
print(stdout.read().decode())

print("=== Redis Port ===")
stdin, stdout, stderr = ssh.exec_command("netstat -tuln | grep 6379")
print(stdout.read().decode())

print("=== Redis Ping ===")
stdin, stdout, stderr = ssh.exec_command("redis-cli ping")
print(stdout.read().decode())

ssh.close()
