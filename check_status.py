import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('192.168.0.12', username='root', password='435102')

print("=== Status ===")
stdin, stdout, stderr = ssh.exec_command("systemctl status companyai-backend --no-pager")
print(stdout.read().decode())

print("\n=== Logs (last 50 lines) ===")
stdin, stdout, stderr = ssh.exec_command("journalctl -u companyai-backend -n 50 --no-pager")
print(stdout.read().decode())

ssh.close()
