# CompanyAI — Mobil Uygulama (Capacitor)

## Genel Bakış

CompanyAI mobil uygulaması, sunucudaki web arayüzünü Android ve iOS cihazlarda
native WebView içinde açar. Desktop (pywebview) uygulamasıyla aynı mantıkta çalışır.

**Mimari:**
```
React Frontend (mevcut kod)  →  Capacitor Shell  →  Android / iOS Native WebView
                                                      ↓
                                           http://192.168.0.12 sunucusu
```

## Gereksinimler

### Android Build
- **Node.js** 18+ ve npm
- **Android Studio** (Hedgehog 2023.1+ önerilen)
- **Android SDK** API Level 22+ (SDK Manager'dan indir)
- **Java JDK** 17+

### iOS Build (sadece macOS'ta)
- **macOS** 12+ (Monterey ve üzeri)
- **Xcode** 15+
- **CocoaPods** (`sudo gem install cocoapods`)
- **Apple Developer Account** (dağıtım için)

### macOS Desktop Build
- **Python** 3.10+
- **pywebview** + **PyInstaller**

---

## Hızlı Başlangıç

### 1. Frontend Build
```bash
cd frontend
npm install
npm run build
```

### 2. Android APK
```bash
cd frontend

# Web assets'leri Android projesine kopyala
npx cap sync android

# Android Studio'da aç
npx cap open android

# Android Studio'da: Build → Build Bundle(s) / APK(s) → Build APK(s)
```

**Doğrudan terminal ile build (Android Studio olmadan):**
```bash
cd frontend/android
./gradlew assembleDebug
# APK: android/app/build/outputs/apk/debug/app-debug.apk
```

### 3. iOS IPA (macOS gerekir)
```bash
cd frontend

# CocoaPods bağımlılıklarını kur
npx cap sync ios

# Xcode'da aç
npx cap open ios

# Xcode'da: Product → Archive → Distribute App
```

### 4. macOS Desktop (.app)
```bash
chmod +x desktop/build_mac.sh
./desktop/build_mac.sh
# Çıktı: dist/CompanyAI.app
```

### 5. Windows Desktop (.exe) — mevcut
```bash
desktop\build.bat
# Çıktı: dist\CompanyAI.exe
```

---

## Proje Yapısı

```
frontend/
├── capacitor.config.ts       ← Capacitor ayarları (sunucu URL, splash, vb.)
├── android/                   ← Android native proje
│   └── app/src/main/
│       ├── AndroidManifest.xml
│       └── res/xml/network_security_config.xml  ← HTTP izni
├── ios/                       ← iOS native proje (Xcode)
│   └── App/App/
│       └── Info.plist         ← ATS (HTTP izni)
└── dist/
    ├── index.html             ← React build çıktısı
    └── error.html             ← Sunucu bağlantı hatası sayfası

desktop/
├── app.py                     ← pywebview uygulaması (Windows + macOS)
├── build.bat                  ← Windows build scripti
├── build_mac.sh               ← macOS build scripti
├── companyai.spec             ← Windows PyInstaller spec
└── companyai_mac.spec         ← macOS PyInstaller spec
```

---

## Sunucu URL Değişikliği

Sunucu IP adresi değişirse şu dosyaları güncelle:

| Dosya | Değiştirilecek Yer |
|---|---|
| `frontend/capacitor.config.ts` | `server.url` |
| `desktop/app.py` | `SERVER_URL` sabiti |
| `frontend/android/.../network_security_config.xml` | `<domain>` |
| `frontend/ios/.../Info.plist` | `NSExceptionDomains` key |
| `frontend/dist/error.html` | (bilgilendirme amaçlı) |

Sonra: `npx cap sync` (mobil projeler güncellenir)

---

## Önemli Notlar

- **Ağ Gereksinimi:** Cihaz, 192.168.0.12 sunucusuna erişebilir şirket ağında olmalı
- **HTTP:** Sunucu HTTP kullandığı için Android (network_security_config) ve iOS (ATS exception) ayarları yapıldı
- **Splash Screen:** Karanlık tema (#0f1117 arka plan, #6366f1 spinner)
- **Error Page:** Sunucu bağlantısı kesildiğinde `error.html` gösterilir
- **Versiyon:** Her deploy'da `capacitor.config.ts` içindeki `overrideUserAgent` versiyonunu da güncelle

---

## Sık Kullanılan Komutlar

```bash
# Web assets güncelle (her frontend build sonrası)
npx cap sync

# Sadece Android güncelle
npx cap sync android

# Sadece iOS güncelle
npx cap sync ios

# Android Studio'da aç
npx cap open android

# Xcode'da aç
npx cap open ios

# Capacitor doctor (sorun teşhisi)
npx cap doctor
```
