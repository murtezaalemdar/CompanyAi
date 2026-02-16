"""Server 2 deploy doğrulama testi"""
import paramiko, time

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('88.246.13.23', port=2013, username='root', password='Kc435102mn', timeout=15)

print('=== Server 2 Deploy Doğrulama ===\n')

# Frontend dosya kontrolü
print('Frontend JS dosyası:')
stdin, stdout, stderr = client.exec_command('ls -la /var/www/html/assets/*.js')
print(stdout.read().decode('utf-8', errors='replace'))

# Backend durumu
print('Backend durumu:')
stdin, stdout, stderr = client.exec_command('systemctl is-active companyai-backend')
print(stdout.read().decode('utf-8', errors='replace'))

# Chat testi
print('Chat testi: "merhaba"')
t0 = time.time()
stdin, stdout, stderr = client.exec_command(
    'curl -s -w "\\nHTTP:%{http_code} TIME:%{time_total}s" '
    '-X POST http://127.0.0.1:8000/api/ask/multimodal '
    '-F "question=merhaba" --max-time 120',
    timeout=130
)
resp = stdout.read().decode('utf-8', errors='replace')
elapsed = time.time() - t0
print(f'  Süre: {elapsed:.1f}s')
lines = resp.strip().split('\n')
for l in lines[-3:]:
    print(f'  {l[:200]}')

# Nginx timeout
print('\nNginx timeout ayarı:')
stdin, stdout, stderr = client.exec_command('grep -i timeout /etc/nginx/sites-enabled/default')
print(stdout.read().decode('utf-8', errors='replace'))

client.close()
print('Test tamamlandı.')
