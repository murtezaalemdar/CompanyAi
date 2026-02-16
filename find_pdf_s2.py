import paramiko
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("88.246.13.23", port=2013, username="root", password="Kc435102mn")

cmds = [
    "find /opt/companyai -name '*.pdf' -type f 2>/dev/null | head -20",
    "find /tmp -name '*.pdf' -type f 2>/dev/null | head -5",
    "ls -la /opt/companyai/uploads/ 2>/dev/null || echo 'uploads yok'",
    "ls -la /opt/companyai/data/uploads/ 2>/dev/null || echo 'data/uploads yok'",
]
for cmd in cmds:
    print(f"\n>>> {cmd}")
    _, stdout, stderr = ssh.exec_command(cmd)
    print(stdout.read().decode('utf-8', errors='replace'))

ssh.close()
