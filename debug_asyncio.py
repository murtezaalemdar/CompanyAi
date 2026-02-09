import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('192.168.0.12', username='root', password='435102')

cmd = 'cd /opt/companyai && /usr/bin/python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --loop asyncio'
print(f"=== Running: {cmd} ===")
stdin, stdout, stderr = ssh.exec_command(cmd)

import time
time.sleep(5)

if stdout.channel.exit_status_ready():
    print("Exited with:", stdout.channel.recv_exit_status())
    print("STDOUT:", stdout.read().decode())
    print("STDERR:", stderr.read().decode())
else:
    print("Running successfully!")
    ssh.exec_command("pkill -f uvicorn")

ssh.close()
