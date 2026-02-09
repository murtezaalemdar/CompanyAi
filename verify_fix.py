import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('192.168.0.12', username='root', password='435102')

print("=== content of /opt/companyai/app/config.py ===")
stdin, stdout, stderr = ssh.exec_command("cat /opt/companyai/app/config.py")
print(stdout.read().decode())

print("\n=== Restarting service again ===")
ssh.exec_command("systemctl restart companyai-backend")
import time
time.sleep(2)

print("\n=== Checking logs ===")
stdin, stdout, stderr = ssh.exec_command("journalctl -u companyai-backend -n 20 --no-pager")
print(stdout.read().decode())

ssh.close()
