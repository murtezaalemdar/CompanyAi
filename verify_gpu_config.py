import paramiko, json

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('88.246.13.23', port=2013, username='root', password='Kc435102mn', timeout=15)

# 1) Backend startup loglarindan gpu_config kararini al
print("=== GPU Config Startup Log ===")
stdin, stdout, stderr = ssh.exec_command(
    'journalctl -u companyai-backend --no-pager -n 50 --output=short | grep -i gpu'
)
gpu_logs = stdout.read().decode().strip()
print(gpu_logs if gpu_logs else "(no gpu log)")

# 2) Ollama PS
stdin, stdout, stderr = ssh.exec_command('ollama ps')
print("\n=== Ollama PS ===")
print(stdout.read().decode().strip() or "(bos)")

# 3) VRAM
stdin, stdout, stderr = ssh.exec_command(
    'nvidia-smi --query-gpu=index,name,memory.used,memory.total --format=csv,noheader,nounits'
)
print("\n=== VRAM ===")
for line in stdout.read().decode().strip().split('\n'):
    parts = [p.strip() for p in line.split(',')]
    if len(parts) >= 4:
        print(f"  GPU {parts[0]}: {parts[1]} — {parts[2]}MB / {parts[3]}MB")

# 4) Backend health + gpu bilgisi
stdin, stdout, stderr = ssh.exec_command('curl -s http://localhost:8000/api/health')
print("\n=== Health ===")
print(stdout.read().decode().strip())

ssh.close()
print("\nBitti.")
