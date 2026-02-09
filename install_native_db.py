
import paramiko
import time

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('192.168.0.12', username='root', password='435102')

def run_cmd(cmd, desc):
    print(f"\n⚙️ {desc}...")
    stdin, stdout, stderr = ssh.exec_command(cmd)
    
    # wait and print output
    while not stdout.channel.exit_status_ready():
        time.sleep(1)
            
    out = stdout.read().decode()
    err = stderr.read().decode()
    
    if stdout.channel.recv_exit_status() != 0:
        print(f"❌ Error: {err}")
    else:
        print(f"✅ OK")
        if out: print(out[:200] + "..." if len(out) > 200 else out)

# 1. Update apt
run_cmd("apt update", "Updating apt repositories")

# 2. Install PostgreSQL
run_cmd("apt install -y postgresql postgresql-contrib", "Installing PostgreSQL")

# 3. Check status
run_cmd("systemctl status postgresql --no-pager", "Checking PG status")

# 4. Configure Database (Create user and db if not exists)
# Using sudo -u postgres for initial setup
print("Configuring Database...")
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
# Save SQL to file
cmd = f"echo \"{setup_sql}\" > /tmp/setup_db.sql"
ssh.exec_command(cmd)

# Execute SQL
run_cmd("sudo -u postgres psql -f /tmp/setup_db.sql", "Executing DB setup SQL")

# 5. Install Redis
run_cmd("apt install -y redis-server", "Installing Redis")
run_cmd("systemctl enable redis-server && systemctl start redis-server", "Starting Redis")

# 6. Verify Ports
run_cmd("netstat -tuln | grep -E '5432|6379'", "Verifying Ports")

# 7. Restart Backend
run_cmd("systemctl restart companyai-backend", "Restarting Backend Service")
run_cmd("systemctl status companyai-backend --no-pager", "Backend Status")

ssh.close()
