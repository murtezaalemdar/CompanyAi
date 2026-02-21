#!/bin/bash
# ══════════════════════════════════════════════════════════════
#  CompanyAI Desktop — macOS Build Script
#  Kullanım:
#    ./desktop/build_mac.sh              # Build only
#    ./desktop/build_mac.sh --upload     # Build + sunuculara yükle
#    ./desktop/build_mac.sh --server 2   # S2 için build
# ══════════════════════════════════════════════════════════════
set -e

SERVER_ID="${2:-1}"  # Varsayılan: S1
UPLOAD=false
for arg in "$@"; do
    case $arg in
        --upload) UPLOAD=true ;;
        --server) ;; # değer sonraki argüman
    esac
done

echo ""
echo "══════════════════════════════════════════════"
echo "  CompanyAI Desktop — macOS Build (S${SERVER_ID})"
echo "══════════════════════════════════════════════"
echo ""

# Proje kök dizinine git
cd "$(dirname "$0")/.."

# SERVER_ID set
echo "[0/5] SERVER_ID = ${SERVER_ID}"
sed -i '' "s/^SERVER_ID *= *[0-9]*/SERVER_ID = ${SERVER_ID}/" desktop/app.py

# Sanal ortam kontrolü
if [ -d "desktop/venv" ]; then
    echo "[1/5] Sanal ortam bulundu, aktif ediliyor..."
    source desktop/venv/bin/activate
else
    echo "[1/5] Sanal ortam oluşturuluyor..."
    python3 -m venv desktop/venv
    source desktop/venv/bin/activate
fi

# Bağımlılıkları yükle
echo "[2/5] Bağımlılıklar yükleniyor..."
pip install --quiet pywebview pyinstaller pyobjc-framework-WebKit 2>/dev/null

# Build
echo "[3/5] PyInstaller ile .app oluşturuluyor..."
pyinstaller desktop/companyai_mac.spec --noconfirm --clean

# Sonuç
echo ""
if [ -d "dist/CompanyAI.app" ]; then
    SIZE=$(du -sh dist/CompanyAI.app | cut -f1)
    echo "  ✅ dist/CompanyAI.app ($SIZE)"

    # Zip oluştur (symlink'leri koruyarak)
    echo "[4/5] .app.zip oluşturuluyor..."
    cd dist
    ditto -c -k --sequesterRsrc --keepParent CompanyAI.app CompanyAI.app.zip
    ZIP_SIZE=$(du -sh CompanyAI.app.zip | cut -f1)
    echo "  ✅ dist/CompanyAI.app.zip ($ZIP_SIZE)"
    cd ..

    # SERVER_ID'yi geri al
    sed -i '' "s/^SERVER_ID *= *[0-9]*/SERVER_ID = 1/" desktop/app.py

    # Upload
    if [ "$UPLOAD" = true ]; then
        echo "[5/5] Sunuculara yükleniyor..."
        KEY="keys/companyai_key"

        if [ -f "$KEY" ]; then
            scp -i "$KEY" dist/CompanyAI.app.zip root@192.168.0.12:/var/www/html/downloads/CompanyAI.app.zip
            ssh -i "$KEY" root@192.168.0.12 "chmod 644 /var/www/html/downloads/CompanyAI.app.zip; systemctl reload nginx"
            echo "  ✅ S1'e yüklendi"
        else
            echo "  ⚠️  SSH key bulunamadı: $KEY"
        fi
    fi

    echo ""
    echo "══════════════════════════════════════════════"
    echo "  ✅ macOS BUILD TAMAMLANDI"
    echo "  📦 dist/CompanyAI.app.zip ($ZIP_SIZE)"
    echo "══════════════════════════════════════════════"
else
    # SERVER_ID'yi geri al
    sed -i '' "s/^SERVER_ID *= *[0-9]*/SERVER_ID = 1/" desktop/app.py
    echo "  ❌ Build başarısız! Yukarıdaki hata mesajlarını kontrol edin."
    exit 1
fi
