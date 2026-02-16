"""Server 2 — Model Q3 → Q4_K_M geçişi ve performans ayarı."""
import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('88.246.13.23', port=2013, username='root', password='Kc435102mn', timeout=15)

# 1. .env'de LLM_MODEL'i q3'ten full Q4_K_M'e değiştir
cmd1 = "sed -i 's/LLM_MODEL=qwen2.5:72b-q3/LLM_MODEL=qwen2.5:72b/' /opt/companyai/.env && grep LLM_MODEL /opt/companyai/.env"
stdin, stdout, stderr = ssh.exec_command(cmd1)
print("ENV:", stdout.read().decode().strip())

# 2. Ollama env'i güncelle — performans modu
env_content = """# CompanyAI — Ollama Environment Config
# GPU: 2x NVIDIA GeForce RTX 3090 (48GB toplam VRAM)
# Performans modu: Q4_K_M model, Flash Attention, KV q4_0

# Flash Attention
OLLAMA_FLASH_ATTENTION=1

# KV Cache — q4_0 daha az VRAM kullanir
OLLAMA_KV_CACHE_TYPE=q4_0

# Paralel istek
OLLAMA_NUM_PARALLEL=2
OLLAMA_MAX_LOADED_MODELS=1

# GPU Erisimi
CUDA_VISIBLE_DEVICES=0,1

# Model surekli bellekte kalsin
OLLAMA_KEEP_ALIVE=-1

# Host
OLLAMA_HOST=0.0.0.0:11434
"""

sftp = ssh.open_sftp()
with sftp.open('/etc/default/ollama', 'w') as f:
    f.write(env_content)
sftp.close()
print("Ollama env yazildi")

# 3. Ollama restart
stdin, stdout, stderr = ssh.exec_command('systemctl daemon-reload && systemctl restart ollama')
stdout.channel.recv_exit_status()
print("Ollama restarted")

import time
time.sleep(4)

# Ollama durum kontrol
stdin, stdout, stderr = ssh.exec_command('systemctl status ollama | head -5')
print("Ollama status:", stdout.read().decode().strip())

# 4. Backend restart (yeni LLM_MODEL'i alsın)
stdin, stdout, stderr = ssh.exec_command('systemctl restart companyai-backend')
stdout.channel.recv_exit_status()
print("Backend restarted")

time.sleep(5)

# 5. Health check
stdin, stdout, stderr = ssh.exec_command('curl -s http://localhost:8000/api/health')
print("Health:", stdout.read().decode().strip())

# 6. Model yükleme tetikle (ilk sorgu ile model VRAM'e yüklenir)
stdin, stdout, stderr = ssh.exec_command('curl -s http://localhost:11434/api/generate -d \'{"model":"qwen2.5:72b","prompt":"test","stream":false}\' --max-time 120 | head -c 200')
out = stdout.read().decode().strip()
print("Model load test:", out[:200] if out else "loading...")

# 7. Ollama ps — model yüklendi mi?
time.sleep(3)
stdin, stdout, stderr = ssh.exec_command('ollama ps')
print("Ollama PS:", stdout.read().decode().strip())

# 8. nvidia-smi VRAM durumu
stdin, stdout, stderr = ssh.exec_command('nvidia-smi --query-gpu=index,name,memory.used,memory.total,utilization.gpu --format=csv,noheader,nounits')
print("GPU VRAM:", stdout.read().decode().strip())

ssh.close()
print("\nTamamlandi!")
