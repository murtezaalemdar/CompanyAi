# CompanyAI Desktop Viewer

Kurumsal AI Asistanı'nın masaüstü uygulaması.  
Sunucudaki web arayüzünü native bir pencerede açar. **Windows** ve **macOS** destekler.

## Hızlı Başlangıç

### Windows — Otomatik Build (önerilen)
```
desktop\build.bat
```
Bu script:
1. Sanal ortam oluşturur (`desktop\venv\`)
2. `pywebview` + `pyinstaller` yükler
3. `.exe` dosyasını `dist\CompanyAI.exe` olarak oluşturur

### Windows — Manuel Build
```bash
pip install pywebview pyinstaller
pyinstaller desktop\companyai.spec --noconfirm --clean
```

### macOS — Otomatik Build
```bash
chmod +x desktop/build_mac.sh
./desktop/build_mac.sh
```
Bu script:
1. Sanal ortam oluşturur (`desktop/venv_mac/`)
2. `pywebview` + `pyinstaller` yükler
3. `.app` bundle'ı `dist/CompanyAI.app` olarak oluşturur

### macOS — Manuel Build
```bash
pip install pywebview pyinstaller
pyinstaller desktop/companyai_mac.spec --noconfirm --clean
```

### Geliştirme Modu (python ile çalıştır)
```bash
pip install pywebview
python desktop/app.py
python desktop/app.py --debug    # DevTools açık
```

## Özellikler

- **Cross-platform** — Windows (Edge WebView2) + macOS (WebKit cocoa)
- **Otomatik bağlantı** — Sunucu kapalıysa loading ekranında bekler
- **Hata yönetimi** — Bağlantı koptuğunda bilgilendirme ekranı
- **Cookie/session saklama** — Giriş bilgileri hatırlanır
- **Tek dosya** — Windows: `.exe` (~12MB), macOS: `.app` bundle — kurulum gerektirmez
- **Kısayol** — Windows'ta masaüstüne otomatik kısayol (macOS'ta atlanır)

## Ayarlar

`desktop/app.py` dosyasının başında:

| Ayar | Varsayılan | Açıklama |
|------|-----------|----------|
| `SERVER_URL` | `http://192.168.0.12` | Backend sunucu adresi |
| `WINDOW_WIDTH` | `1280` | Pencere genişliği |
| `WINDOW_HEIGHT` | `820` | Pencere yüksekliği |
| `CHECK_INTERVAL` | `2` | Sunucu kontrol aralığı (sn) |

## İkon Ekleme

İkonlar `scripts/generate_icons.py` ile otomatik üretilir:
```bash
pip install Pillow
python scripts/generate_icons.py
```

| Dosya | Açıklama |
|-------|----------|
| `desktop/icon.ico` | Windows .exe ikonu (16–256px, 6 boyut) |
| `desktop/icon_1024.png` | macOS ikon kaynağı (1024×1024) |

## Dosya Yapısı

```
desktop/
├── app.py              # Ana uygulama — pywebview native pencere
├── build.bat           # Windows otomatik build scripti
├── build_mac.sh        # macOS otomatik build scripti
├── companyai.spec      # Windows PyInstaller spec
├── companyai_mac.spec  # macOS PyInstaller spec (.app bundle)
├── icon.ico            # Windows ikonu
├── icon_1024.png       # macOS ikon kaynağı
└── README.md           # Bu dosya
```

## Gereksinimler

### Windows
- Python 3.9+
- Windows 10/11 (Edge WebView2 Runtime otomatik gelir)

### macOS
- Python 3.9+
- macOS 10.15+ (Catalina veya üstü)
- pywebview WebKit cocoa backend (otomatik)
