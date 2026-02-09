
import paramiko
from scp import SCPClient

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('192.168.0.12', username='root', password='435102')

files = [
    ("requirements.txt", "/opt/companyai/requirements.txt"),
    ("app/api/routes/multimodal.py", "/opt/companyai/app/api/routes/multimodal.py"),
    ("app/llm/prompts.py", "/opt/companyai/app/llm/prompts.py"),
]

print("=== Uploading File Updates ===")
with SCPClient(ssh.get_transport()) as scp:
    for local, remote in files:
        print(f"Uploading {local}...")
        scp.put(local, remote_path=remote)

print("=== Installing Dependencies (Pillow) ===")
stdin, stdout, stderr = ssh.exec_command("cd /opt/companyai && pip3 install -r requirements.txt")
print(stdout.read().decode())

print("=== Restarting Backend ===")
ssh.exec_command("systemctl restart companyai-backend")

import time
time.sleep(5)

print("=== Testing API ===")
stdin, stdout, stderr = ssh.exec_command("curl -s http://localhost:8000/api/health")
print(stdout.read().decode())

ssh.close()
