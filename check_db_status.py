import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('192.168.0.12', username='root', password='435102')

print("=== PostgreSQL Status ===")
stdin, stdout, stderr = ssh.exec_command("systemctl status postgresql --no-pager")
print(stdout.read().decode())

print("\n=== Redis Status ===")
stdin, stdout, stderr = ssh.exec_command("systemctl status redis-server --no-pager")
print(stdout.read().decode())

print("\n=== Port 5432 (PG) & 6379 (Redis) ===")
stdin, stdout, stderr = ssh.exec_command("netstat -tuln | grep -E '5432|6379'")
print(stdout.read().decode())

ssh.close()
