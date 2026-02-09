
import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('192.168.0.12', username='root', password='435102')

setup_sql = """DO $$
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

print("=== Creating SQL file ===")
with open("/tmp/setup_db_final.sql", "w") as f:
    f.write(setup_sql)

sftp = ssh.open_sftp()
sftp.put("/tmp/setup_db_final.sql", "/tmp/setup_db_final.sql")
sftp.close()

print("=== Executing SQL on port 5433 ===")
cmd = "sudo -u postgres psql -p 5433 -f /tmp/setup_db_final.sql"
stdin, stdout, stderr = ssh.exec_command(cmd)
print(stdout.read().decode())
err = stderr.read().decode()
if err: print("Error:", err)

# Check
cmd = "sudo -u postgres psql -p 5433 -c '\\l'"
stdin, stdout, stderr = ssh.exec_command(cmd)
print(stdout.read().decode())

# Restart backend
print("\n=== Restarting Backend ===")
ssh.exec_command("systemctl restart companyai-backend")

ssh.close()
