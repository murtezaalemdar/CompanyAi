#!/bin/bash

echo "=========================================="
echo "CompanyAI - ChromaDB Setup Script"
echo "=========================================="

cd /opt/companyai

# 1. ChromaDB ve bağımlılıklarını kur
echo ""
echo "=== Step 1: Installing ChromaDB dependencies ==="
pip3 install chromadb sentence-transformers --upgrade

# 2. Data dizinini oluştur
echo ""
echo "=== Step 2: Creating data directory ==="
mkdir -p /opt/companyai/data/chromadb
chmod 755 /opt/companyai/data

# 3. vector_memory.py dosyasını güncelle (scp ile kopyalanacak)
echo ""
echo "=== Step 3: Verifying vector_memory.py ==="
ls -la /opt/companyai/app/memory/

# 4. Backend'i yeniden başlat
echo ""
echo "=== Step 4: Restarting backend ==="
systemctl restart companyai-backend
sleep 5

# 5. Health check
echo ""
echo "=== Step 5: Health check ==="
curl -s http://localhost:8000/api/health

# 6. Memory stats endpoint test (varsa)
echo ""
echo "=== Step 6: Memory stats ==="
curl -s http://localhost:8000/api/memory/stats 2>/dev/null || echo "Memory stats endpoint not available yet"

echo ""
echo "=========================================="
echo "ChromaDB setup completed!"
echo "=========================================="
