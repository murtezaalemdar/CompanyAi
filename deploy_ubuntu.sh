#!/bin/bash

# Kurumsal AI Asistanı - Ubuntu Deployment Scripti
# Kullanım: chmod +x deploy.sh && ./deploy.sh

echo "🚀 Kurumsal AI Asistanı Kurulumu Başlıyor..."

# 1. Sistem Güncelleme
echo "📦 Sistem güncelleniyor..."
sudo apt update && sudo apt upgrade -y
sudo apt install -y curl git apt-transport-https ca-certificates software-properties-common

# 2. Docker Kurulumu
if ! command -v docker &> /dev/null; then
    echo "🐳 Docker kuruluyor..."
    curl -fsSL https://get.docker.com | sh
    sudo usermod -aG docker $USER
    echo "⚠️ Docker grubu güncellendi, lütfen oturumu kapatıp açın veya 'newgrp docker' komutunu kullanın."
else
    echo "✅ Docker zaten kurulu."
fi

# 3. Ollama Kurulumu
if ! command -v ollama &> /dev/null; then
    echo "🦙 Ollama kuruluyor..."
    curl -fsSL https://ollama.com/install.sh | sh
    
    echo "⏳ Mistral modeli indiriliyor (bu biraz sürebilir)..."
    ollama pull mistral
else
    echo "✅ Ollama zaten kurulu."
fi

# 4. Proje Kurulumu
echo "📂 Proje dosyaları hazırlanıyor..."
if [ ! -f .env ]; then
    cp .env.example .env
    echo "⚠️ .env dosyası default ayarlarla oluşturuldu. Lütfen düzenleyin!"
fi

# 5. Başlatma
echo "🔥 Servisler başlatılıyor..."
docker compose --env-file .env -f docker/docker-compose.yml up -d --build

echo "========================================"
echo "✅ Kurulum Tamamlandı!"
echo "----------------------------------------"
echo "API:      http://localhost:8000"
echo "Frontend: http://localhost:3000 (Nginx port 80 ayarlanmalı)"
echo "----------------------------------------"
echo "Logları izlemek için: docker compose -f docker/docker-compose.yml logs -f"
echo "========================================"
