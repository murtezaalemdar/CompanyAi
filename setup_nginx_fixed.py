
import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('192.168.0.12', username='root', password='435102')

nginx_conf = """server {
    listen 80;
    server_name _;

    root /var/www/html;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }

    location /api {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
        
        proxy_read_timeout 300s;
        proxy_connect_timeout 300s;
        proxy_send_timeout 300s;
    }
}"""

print("=== Writing Nginx Config ===")
# Use temporary file locally then upload
with open("nginx_temp.conf", "w") as f:
    f.write(nginx_conf)
    
sftp = ssh.open_sftp()
sftp.put("nginx_temp.conf", "/etc/nginx/sites-available/default")
sftp.close()

# Reload Nginx
print("=== Reloading Nginx ===")
stdin, stdout, stderr = ssh.exec_command("nginx -t && systemctl reload nginx")
out = stdout.read().decode()
err = stderr.read().decode()
print("Out:", out)
print("Err:", err)

# Test Proxy
print("=== Testing Proxy ===")
stdin, stdout, stderr = ssh.exec_command("curl -s http://localhost/api/health")
print(stdout.read().decode())

ssh.close()
