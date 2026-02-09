
import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('192.168.0.12', username='root', password='435102')

# Nginx Config: Proxy /api to localhost:8000
nginx_conf = """
server {
    listen 80;
    server_name _;

    root /var/www/html;
    index index.html;

    # Frontend
    location / {
        try_files $uri $uri/ /index.html;
    }

    # Backend API Proxy
    location /api {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
        
        # Timeout settings for long-running AI requests
        proxy_read_timeout 300s;
        proxy_connect_timeout 300s;
        proxy_send_timeout 300s;
    }
}
"""

print("=== Updating Nginx Config ===")
cmd = f"cat > /etc/nginx/sites-available/default << 'EOF'\n{nginx_conf}EOF"
ssh.exec_command(cmd)

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
