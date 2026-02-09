import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('192.168.0.12', username='root', password='435102')

print("=== PG Logs ===")
stdin, stdout, stderr = ssh.exec_command("tail -n 20 /var/log/postgresql/postgresql-14-main.log")
print(stdout.read().decode())

print("=== Check Cluster Status ===")
stdin, stdout, stderr = ssh.exec_command("pg_lsclusters")
print(stdout.read().decode())

ssh.close()
