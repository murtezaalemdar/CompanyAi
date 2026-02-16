"""Server 2 - Nginx timeout fix + backend optimizasyonu."""
import paramiko

HOST = "88.246.13.23"
PORT = 2013
USER = "root"
PWD  = "Kc435102mn"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, port=PORT, username=USER, password=PWD, timeout=15)

def run(cmd, timeout=60):
    _, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='replace').strip()
    err = stderr.read().decode('utf-8', errors='replace').strip()
    return out, err

# 1. Nginx config dosyasını bul
print("="*60)
print("1. NGINX CONFIG BULUNUYOR...")
print("="*60)
conf_out, _ = run("ls -la /etc/nginx/sites-enabled/ 2>/dev/null; echo '---'; cat /etc/nginx/sites-enabled/default 2>/dev/null | head -80")
print(conf_out)

print("\n" + "="*60)
print("2. MEVCUT NGINX CONFIG")
print("="*60)
full_conf, _ = run("cat /etc/nginx/sites-enabled/default 2>/dev/null || cat /etc/nginx/conf.d/default.conf 2>/dev/null")
print(full_conf[:3000])

ssh.close()
