
import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('192.168.0.12', username='root', password='435102')

setup_sql = """
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_user WHERE usename = 'companyai') THEN
        CREATE USER companyai WITH ENCRYPTED PASSWORD 'your_secure_password';
    END IF;
END
$$;

SELECT 'CREATE DATABASE companyai'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'companyai')\\gexec

GRANT ALL PRIVILEGES ON DATABASE companyai TO companyai;
ALTER USER companyai WITH SUPERUSER;
"""

print("=== Creating DB on port 5433 ===")
cmd = f"echo \"{setup_sql}\" > /tmp/setup_db_5433.sql"
ssh.exec_command(cmd)

# Execute SQL on 5433
cmd = "sudo -u postgres psql -p 5433 -f /tmp/setup_db_5433.sql"
stdin, stdout, stderr = ssh.exec_command(cmd)
print(stdout.read().decode())
err = stderr.read().decode()
if err: print("Error:", err)

# Restart backend
print("\n=== Restarting Backend ===")
ssh.exec_command("systemctl restart companyai-backend")
import time
time.sleep(3)

# Test API
print("\n=== Testing API status ===")
stdin, stdout, stderr = ssh.exec_command("curl -s http://localhost:8000/api/health")
print(stdout.read().decode())

ssh.close()
