#!/bin/bash
# ══════════════════════════════════════════════
#  CompanyAI Desktop — Linux Build Script
# ══════════════════════════════════════════════
set -e

echo ""
echo "══════════════════════════════════════════════"
echo "  CompanyAI Desktop — Linux Build"
echo "══════════════════════════════════════════════"
echo ""

# Proje kök dizinine git
cd "$(dirname "$0")/.."

# Bağımlılıkları kontrol et
echo "[0/4] Sistem bağımlılıkları kontrol ediliyor..."
missing=""
dpkg -l | grep -q gir1.2-webkit2-4.0 || missing="$missing gir1.2-webkit2-4.0"
dpkg -l | grep -q python3-gi || missing="$missing python3-gi"
dpkg -l | grep -q python3-venv || missing="$missing python3-venv"

if [ -n "$missing" ]; then
    echo "  Eksik paketler kuruluyor:$missing"
    sudo apt-get install -y -qq $missing
fi

# Sanal ortam kontrolü
if [ -d "desktop/venv_linux" ]; then
    echo "[1/4] Sanal ortam bulundu, aktif ediliyor..."
    source desktop/venv_linux/bin/activate
else
    echo "[1/4] Sanal ortam oluşturuluyor..."
    python3 -m venv desktop/venv_linux --system-site-packages
    source desktop/venv_linux/bin/activate
fi

# Bağımlılıkları yükle
echo "[2/4] Bağımlılıklar yükleniyor..."
pip install --quiet pywebview pyinstaller

# Build
echo "[3/4] PyInstaller ile binary oluşturuluyor..."
pyinstaller desktop/companyai_linux.spec --noconfirm --clean

# Sonuç
echo ""
if [ -f "dist/CompanyAI" ]; then
    chmod +x dist/CompanyAI
    SIZE=$(du -sh dist/CompanyAI | cut -f1)
    echo "══════════════════════════════════════════════"
    echo "  ✅ Build başarılı!"
    echo "  📦 dist/CompanyAI"
    echo "  📐 Boyut: $SIZE"
    echo "══════════════════════════════════════════════"
else
    echo "  ❌ Build başarısız! Yukarıdaki hata mesajlarını kontrol edin."
    exit 1
fi
