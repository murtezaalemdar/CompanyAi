
import paramiko
from scp import SCPClient

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('192.168.0.12', username='root', password='435102')

with SCPClient(ssh.get_transport()) as scp:
    scp.put("test_db_connect.py", remote_path="/opt/companyai/test_db_connect.py")

print("=== Running DB Test ===")
stdin, stdout, stderr = ssh.exec_command("cd /opt/companyai && python3 test_db_connect.py")
print("STDOUT:", stdout.read().decode())
print("STDERR:", stderr.read().decode())

ssh.close()
