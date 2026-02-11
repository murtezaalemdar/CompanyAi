#!/bin/bash
# ══════════════════════════════════════════════
#  CompanyAI Desktop — macOS Build Script
# ══════════════════════════════════════════════
set -e

echo ""
echo "══════════════════════════════════════════════"
echo "  CompanyAI Desktop — macOS Build"
echo "══════════════════════════════════════════════"
echo ""

# Proje kök dizinine git
cd "$(dirname "$0")/.."

# Sanal ortam kontrolü
if [ -d "desktop/venv" ]; then
    echo "[1/4] Sanal ortam bulundu, aktif ediliyor..."
    source desktop/venv/bin/activate
else
    echo "[1/4] Sanal ortam oluşturuluyor..."
    python3 -m venv desktop/venv
    source desktop/venv/bin/activate
fi

# Bağımlılıkları yükle
echo "[2/4] Bağımlılıklar yükleniyor..."
pip install --quiet pywebview pyinstaller

# Build (py2app alternatifi olarak PyInstaller kullanılıyor — cross-platform)
echo "[3/4] PyInstaller ile .app oluşturuluyor..."
pyinstaller desktop/companyai_mac.spec --noconfirm --clean

# Sonuç
echo ""
if [ -d "dist/CompanyAI.app" ]; then
    echo "══════════════════════════════════════════════"
    echo "  ✅ Build başarılı!"
    echo "  📦 dist/CompanyAI.app"
    SIZE=$(du -sh dist/CompanyAI.app | cut -f1)
    echo "  📐 Boyut: $SIZE"
    echo "══════════════════════════════════════════════"
else
    echo "  ❌ Build başarısız! Yukarıdaki hata mesajlarını kontrol edin."
    exit 1
fi
