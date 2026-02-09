import paramiko
import time

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('192.168.0.12', username='root', password='435102')

# Run uvicorn manually to see error
print('=== Running uvicorn manually ===')
stdin, stdout, stderr = ssh.exec_command('cd /opt/companyai && python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000')
# Give it a second to fail
time.sleep(2)
# It might block, so we check if it exited
if stdout.channel.exit_status_ready():
    print("Exited with:", stdout.channel.recv_exit_status())
    print("Out:", stdout.read().decode())
    print("Err:", stderr.read().decode())
else:
    print("Running successfully!")
    ssh.exec_command("pkill -f uvicorn") # Kill it

ssh.close()
