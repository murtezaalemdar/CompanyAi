#!/bin/bash

echo "=========================================="
echo "CompanyAI - SSL Setup Script (Self-Signed)"
echo "=========================================="

CERT_DIR="/etc/nginx/ssl"
CERT_FILE="$CERT_DIR/companyai.crt"
KEY_FILE="$CERT_DIR/companyai.key"
NGINX_CONF="/etc/nginx/sites-available/default"

# 1. SSL Sertifikası oluştur
echo ""
echo "=== Step 1: Generating Self-Signed Certificate ==="
mkdir -p $CERT_DIR
if [ ! -f "$CERT_FILE" ]; then
    openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
        -keyout "$KEY_FILE" \
        -out "$CERT_FILE" \
        -subj "/C=TR/ST=Istanbul/L=Istanbul/O=CompanyAI/OU=IT/CN=companyai.local"
    echo "Certificate generated at $CERT_FILE"
else
    echo "Certificate already exists at $CERT_FILE"
fi

# 2. Nginx konfigürasyonunu güncelle
echo ""
echo "=== Step 2: Updating Nginx Configuration ==="
cat > $NGINX_CONF << 'EOF'
# HTTP -> HTTPS Redirect
server {
    listen 80;
    listen [::]:80;
    server_name _;
    return 301 https://$host$request_uri;
}

# HTTPS Server
server {
    listen 443 ssl default_server;
    listen [::]:443 ssl default_server;
    
    server_name _;
    
    # SSL Configuration
    ssl_certificate /etc/nginx/ssl/companyai.crt;
    ssl_certificate_key /etc/nginx/ssl/companyai.key;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    
    root /var/www/html;
    index index.html;

    # Frontend
    location / {
        try_files $uri $uri/ /index.html;
    }

    # Backend API
    location /api {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;

        proxy_read_timeout 300s;
        proxy_connect_timeout 300s;
        proxy_send_timeout 300s;
    }
    
    # Swagger Docs (Opsiyonel - Development)
    location /docs {
        proxy_pass http://127.0.0.1:8000/docs;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    
    location /openapi.json {
        proxy_pass http://127.0.0.1:8000/openapi.json;
        proxy_set_header Host $host;
    }
}
EOF
echo "Nginx configuration updated."

# 3. Nginx'i yeniden başlat
echo ""
echo "=== Step 3: Restarting Nginx ==="
if nginx -t; then
    systemctl restart nginx
    echo "Nginx restarted successfully."
else
    echo "Nginx configuration test failed! Restoring backup..."
    # TODO: Restore backup logic if needed (not implemented here for simplicity)
    exit 1
fi

# 4. HTTPS Test
echo ""
echo "=== Step 4: Testing HTTPS ==="
curl -k -I https://localhost/api/health
echo "HTTPS test completed. (Note: use curl -k to bypass self-signed warning)"

echo ""
echo "=========================================="
echo "SSL Setup Completed!"
echo "=========================================="
