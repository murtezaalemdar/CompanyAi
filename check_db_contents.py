
import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('192.168.0.12', username='root', password='435102')

print("=== Check User companyai ===")
stdin, stdout, stderr = ssh.exec_command("sudo -u postgres psql -p 5433 -c '\\du'")
print(stdout.read().decode())

print("=== Check Database companyai ===")
stdin, stdout, stderr = ssh.exec_command("sudo -u postgres psql -p 5433 -c '\\l'")
print(stdout.read().decode())

ssh.close()
