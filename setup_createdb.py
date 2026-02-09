
import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('192.168.0.12', username='root', password='435102')

print("=== Creating Database 'companyai' on port 5433 ===")
cmd = "sudo -u postgres createdb -p 5433 -O companyai companyai || echo 'Database already exists or failed'"
stdin, stdout, stderr = ssh.exec_command(cmd)
print(stdout.read().decode())
err = stderr.read().decode()
if err: print("Error:", err)

# Restart backend
print("\n=== Restarting Backend ===")
ssh.exec_command("systemctl restart companyai-backend")
time.sleep(3)

# Test API
print("\n=== Testing API status ===")
stdin, stdout, stderr = ssh.exec_command("curl -s http://localhost:8000/api/health")
print(stdout.read().decode())

ssh.close()
