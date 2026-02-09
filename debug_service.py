import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('192.168.0.12', username='root', password='435102')

print("=== Simulating Service Start ===")
# Run exactly as service would
stdin, stdout, stderr = ssh.exec_command('cd /opt/companyai && /usr/bin/python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000')

# Read output for 5 seconds
import time
time.sleep(5)
if stdout.channel.exit_status_ready():
    print("Exited with:", stdout.channel.recv_exit_status())
else:
    print("Still running...")
    # Kill it
    ssh.exec_command("pkill -f uvicorn")

print("STDOUT:", stdout.read().decode())
print("STDERR:", stderr.read().decode())

print("\n=== Grepping errors in logs ===")
stdin, stdout, stderr = ssh.exec_command('journalctl -u companyai-backend | grep -i "error\|traceback\|fail" | tail -20')
print(stdout.read().decode())

ssh.close()
