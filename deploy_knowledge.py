
import paramiko
from scp import SCPClient

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('192.168.0.12', username='root', password='435102')

files = [
    ("textile_kb.zip", "/opt/companyai/textile_kb.zip")
]

print("=== Uploading Knowledge Base ===")
with SCPClient(ssh.get_transport()) as scp:
    for local, remote in files:
        print(f"Uploading {local}...")
        scp.put(local, remote_path=remote)

print("=== Installing Unzip ===")
ssh.exec_command("apt-get update && apt-get install -y unzip")

print("=== Unzipping Knowledge Base ===")
cmd = "cd /opt/companyai && unzip -o textile_kb.zip"
stdin, stdout, stderr = ssh.exec_command(cmd)
print(stdout.read().decode())

print("=== Organizing ===")
# Move files to documents/KnowledgeBase
cmd_list = [
    "mkdir -p /opt/companyai/documents/KnowledgeBase",
    "cp -r /opt/companyai/textile_knowledge_base/* /opt/companyai/documents/KnowledgeBase/",
    "ls -R /opt/companyai/documents/KnowledgeBase"
]
for cmd in cmd_list:
    stdin, stdout, stderr = ssh.exec_command(cmd)
    if cmd.startswith("ls"):
        print(stdout.read().decode())

print("✅ Knowledge Base Deployed!")
ssh.close()
