#!/bin/bash

echo "=========================================="
echo "CompanyAI - Complete Fix Script"
echo "=========================================="

# 1. .env dosyasını düzelt (asyncpg format)
echo ""
echo "=== Step 1: Fixing .env file ==="
cat > /opt/companyai/.env << 'ENVEOF'
# Database (asyncpg format for async SQLAlchemy)
DATABASE_URL=postgresql+asyncpg://companyai:companyai@localhost:5433/companyai

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

# CORS
CORS_ORIGINS=["http://localhost:3000","http://localhost:5173","http://192.168.0.12","http://192.168.0.12:3000"]
ENVEOF
echo ".env updated with asyncpg driver"

# 2. asyncpg kurulu mu kontrol et
echo ""
echo "=== Step 2: Checking asyncpg installation ==="
pip3 show asyncpg > /dev/null 2>&1
if [ $? -ne 0 ]; then
    echo "Installing asyncpg..."
    pip3 install asyncpg
else
    echo "asyncpg already installed"
fi

# 3. Backend servisini yeniden başlat
echo ""
echo "=== Step 3: Restarting backend service ==="
systemctl daemon-reload
systemctl restart companyai-backend
sleep 5

# 4. Servis durumunu kontrol et
echo ""
echo "=== Step 4: Checking service status ==="
systemctl status companyai-backend --no-pager | head -15

# 5. Health check
echo ""
echo "=== Step 5: Health check ==="
sleep 2
HEALTH=$(curl -s http://localhost:8000/api/health)
echo "Health: $HEALTH"

# 6. DB bağlantısını test et
echo ""
echo "=== Step 6: Testing DB connection ==="
PGPASSWORD=companyai psql -h localhost -p 5433 -U companyai -d companyai -c "SELECT 'DB Connection OK!' as status;" 2>&1

echo ""
echo "=========================================="
echo "Fix script completed!"
echo "=========================================="
