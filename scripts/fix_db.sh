#!/bin/bash

# 1. PostgreSQL şifresini düzelt
echo "=== Fixing PostgreSQL Password ==="
sudo -u postgres psql -p 5433 << 'EOF'
ALTER USER companyai WITH PASSWORD 'companyai';
EOF

# 2. Bağlantıyı test et
echo "=== Testing Connection ==="
PGPASSWORD=companyai psql -h localhost -p 5433 -U companyai -d companyai -c "SELECT 'Connection successful!' as status;"

# 3. .env dosyasını güncelle
echo "=== Updating .env ==="
cat > /opt/companyai/.env << 'ENVEOF'
# Database
DATABASE_URL=postgresql://companyai:companyai@localhost:5433/companyai

# JWT Authentication
SECRET_KEY=your-super-long-and-secure-secret-key-change-this-in-production-min-32-chars
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# LLM (Ollama + Mistral)
OLLAMA_BASE_URL=http://localhost:11434
LLM_MODEL=mistral

# Redis
REDIS_URL=redis://localhost:6379

# Server
HOST=0.0.0.0
PORT=8000
DEBUG=false
ENVEOF

# 4. Backend'i yeniden başlat
echo "=== Restarting Backend ==="
systemctl restart companyai-backend
sleep 3
systemctl status companyai-backend --no-pager | head -10

# 5. Health check
echo "=== Health Check ==="
curl -s http://localhost:8000/api/health

echo ""
echo "=== DB Fix Complete ==="
