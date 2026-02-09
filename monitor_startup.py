import paramiko
import time

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('192.168.0.12', username='root', password='435102')

print("=== Restarting ===")
ssh.exec_command("systemctl restart companyai-backend")

print("=== Monitoring Logs (30s) ===")
# We can't easily follow logs via exec_command without blocking forever or tricky parsing.
# We'll just loop and tail every few seconds.
for i in range(6):
    stdin, stdout, stderr = ssh.exec_command("journalctl -u companyai-backend -n 20 --no-pager")
    print(f"--- {i*5}s ---")
    print(stdout.read().decode())
    time.sleep(5)

print("\n=== Check Port ===")
stdin, stdout, stderr = ssh.exec_command("netstat -tuln | grep 8000")
print(stdout.read().decode())

ssh.close()
