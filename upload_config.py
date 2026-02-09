import paramiko
from scp import SCPClient
import os

HOST = "192.168.0.12"
USER = "root"
PASS = "435102"
REMOTE_PATH = "/opt/companyai/app"

def upload_config():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASS)

    print(f"🔌 Connected to {HOST}")

    # Upload config.py
    print(f"🚀 Uploading app/config.py to {REMOTE_PATH}/config.py")
    with SCPClient(ssh.get_transport()) as scp:
        scp.put("app/config.py", remote_path=f"{REMOTE_PATH}/config.py")

    # Restart service
    print("🔄 Restarting backend service...")
    stdin, stdout, stderr = ssh.exec_command("systemctl restart companyai-backend")
    
    # Check status
    stdin, stdout, stderr = ssh.exec_command("systemctl status companyai-backend --no-pager")
    print(stdout.read().decode())
    
    # Test API locally on server
    print("🧪 Checking API health locally...")
    stdin, stdout, stderr = ssh.exec_command("curl -s http://localhost:8000/api/health")
    print(stdout.read().decode())

    ssh.close()

if __name__ == "__main__":
    upload_config()
