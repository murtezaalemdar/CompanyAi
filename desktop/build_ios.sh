#!/bin/bash
# ══════════════════════════════════════════════════════════════
#  CompanyAI — iOS Build Script (IPA)
#  Gereksinimler:
#    - macOS + Xcode (15+)
#    - Node.js + npm
#    - Apple Developer Account + Provisioning Profile
#    - CocoaPods
#  Kullanım:
#    ./desktop/build_ios.sh                     # Ad-hoc IPA
#    ./desktop/build_ios.sh --upload            # Build + sunucuya yükle
#    ./desktop/build_ios.sh --method app-store  # App Store IPA
#    ./desktop/build_ios.sh --unsigned          # Sadece derleme testi
# ══════════════════════════════════════════════════════════════
set -e

METHOD="ad-hoc"
UPLOAD=false
UNSIGNED=false

for arg in "$@"; do
    case $arg in
        --upload)   UPLOAD=true ;;
        --unsigned) UNSIGNED=true ;;
        --method)   ;; # değer sonraki argüman
    esac
done

# --method değerini yakala
while [[ $# -gt 0 ]]; do
    case $1 in
        --method) METHOD="$2"; shift 2 ;;
        *) shift ;;
    esac
done

echo ""
echo "══════════════════════════════════════════════"
echo "  CompanyAI — iOS Build ($METHOD)"
echo "══════════════════════════════════════════════"
echo ""

# Proje kök dizinine git
cd "$(dirname "$0")/.."
ROOT=$(pwd)

# ── Gereksinim kontrolleri ────────────────────
echo "[1/6] Gereksinimler kontrol ediliyor..."

if ! command -v xcodebuild &>/dev/null; then
    echo "  ❌ Xcode yüklü değil. App Store'dan Xcode yükleyin."
    exit 1
fi
XCODE_VER=$(xcodebuild -version | head -1)
echo "  ✅ $XCODE_VER"

if ! command -v node &>/dev/null; then
    echo "  ❌ Node.js yüklü değil. brew install node"
    exit 1
fi
echo "  ✅ Node $(node -v)"

if ! command -v pod &>/dev/null; then
    echo "  ⚠️  CocoaPods yüklü değil. Yükleniyor..."
    gem install cocoapods
fi
echo "  ✅ CocoaPods $(pod --version)"

# ── Frontend build ────────────────────────────
echo "[2/6] Frontend build ediliyor..."
cd frontend
npm ci --silent 2>/dev/null || npm install --silent
npm run build

# ── Capacitor sync ────────────────────────────
echo "[3/6] Capacitor iOS sync..."
npx cap sync ios

# ── CocoaPods install ─────────────────────────
echo "[4/6] CocoaPods install..."
cd ios/App
pod install || pod install --repo-update

# ── Xcode Build ──────────────────────────────
echo "[5/6] Xcode build ediliyor..."

if [ "$UNSIGNED" = true ]; then
    echo "  ⚠️  Unsigned simulator build (imzasız derleme testi)"
    xcodebuild build \
        -workspace App.xcworkspace \
        -scheme App \
        -configuration Release \
        -destination "generic/platform=iOS Simulator" \
        CODE_SIGNING_ALLOWED=NO \
        | xcpretty || xcodebuild build \
            -workspace App.xcworkspace \
            -scheme App \
            -configuration Release \
            -destination "generic/platform=iOS Simulator" \
            CODE_SIGNING_ALLOWED=NO

    echo ""
    echo "══════════════════════════════════════════════"
    echo "  ✅ Derleme başarılı (unsigned)"
    echo "  ℹ️  Signed IPA için Apple Developer hesabı gerekli"
    echo "══════════════════════════════════════════════"
    exit 0
fi

# Signed build
ARCHIVE_PATH="$ROOT/dist/CompanyAI.xcarchive"
EXPORT_PATH="$ROOT/dist/ios-export"
IPA_PATH="$ROOT/dist/CompanyAI.ipa"

mkdir -p "$ROOT/dist"

# Archive
xcodebuild archive \
    -workspace App.xcworkspace \
    -scheme App \
    -configuration Release \
    -archivePath "$ARCHIVE_PATH" \
    -destination "generic/platform=iOS" \
    | xcpretty

# Export options plist
cat > /tmp/ExportOptions.plist << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>method</key>
    <string>${METHOD}</string>
    <key>compileBitcode</key>
    <false/>
    <key>stripSwiftSymbols</key>
    <true/>
    <key>thinning</key>
    <string>&lt;none&gt;</string>
</dict>
</plist>
EOF

# Export
xcodebuild -exportArchive \
    -archivePath "$ARCHIVE_PATH" \
    -exportPath "$EXPORT_PATH" \
    -exportOptionsPlist /tmp/ExportOptions.plist \
    | xcpretty

# IPA'yı bul ve kopyala
find "$EXPORT_PATH" -name "*.ipa" -exec cp {} "$IPA_PATH" \;

# ── Sonuç ─────────────────────────────────────
echo ""
if [ -f "$IPA_PATH" ]; then
    IPA_SIZE=$(du -sh "$IPA_PATH" | cut -f1)
    echo "  ✅ dist/CompanyAI.ipa ($IPA_SIZE)"

    # Upload
    if [ "$UPLOAD" = true ]; then
        echo "[6/6] Sunucuya yükleniyor..."
        KEY="$ROOT/keys/companyai_key"
        if [ -f "$KEY" ]; then
            scp -i "$KEY" "$IPA_PATH" root@192.168.0.12:/var/www/html/downloads/CompanyAI.ipa
            ssh -i "$KEY" root@192.168.0.12 "chmod 644 /var/www/html/downloads/CompanyAI.ipa; systemctl reload nginx"
            echo "  ✅ S1'e yüklendi"
        else
            echo "  ⚠️  SSH key bulunamadı: $KEY"
        fi
    fi

    echo ""
    echo "══════════════════════════════════════════════"
    echo "  ✅ iOS BUILD TAMAMLANDI"
    echo "  📦 dist/CompanyAI.ipa ($IPA_SIZE)"
    echo "══════════════════════════════════════════════"
else
    echo "  ❌ IPA oluşturulamadı!"
    echo "  📋 Apple Developer hesabı yapılandırılmış mı?"
    echo "     - Xcode → Signing & Capabilities → Team seçili mi?"
    echo "     - Provisioning profile yüklü mü?"
    exit 1
fi
