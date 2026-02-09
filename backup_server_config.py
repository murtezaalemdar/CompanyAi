import paramiko
import os

if not os.path.exists("server_backup"):
    os.makedirs("server_backup")

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('192.168.0.12', username='root', password='435102')

files = [
    ("/etc/systemd/system/companyai-backend.service", "companyai-backend.service"),
    ("/etc/nginx/sites-available/default", "nginx_default.conf"),
    ("/opt/companyai/.env", ".env.server")
]

print("=== Downloading Configuration Files ===")
sftp = ssh.open_sftp()
for remote, local in files:
    try:
        sftp.get(remote, f"server_backup/{local}")
        print(f"✅ Downloaded: {local}")
    except Exception as e:
        print(f"❌ Failed {local}: {e}")

sftp.close()
ssh.close()
