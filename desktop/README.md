# CompanyAI Desktop Viewer

Kurumsal AI Asistanı'nın masaüstü uygulaması.  
Sunucudaki web arayüzünü native bir Windows penceresinde açar.

## Hızlı Başlangıç

### Otomatik Build (önerilen)
```
desktop\build.bat
```
Bu script:
1. Sanal ortam oluşturur (`desktop\venv\`)
2. `pywebview` + `pyinstaller` yükler
3. `.exe` dosyasını `dist\CompanyAI.exe` olarak oluşturur

### Manuel Build
```bash
pip install pywebview pyinstaller
pyinstaller desktop\companyai.spec --noconfirm --clean
```

### Geliştirme Modu (python ile çalıştır)
```bash
pip install pywebview
python desktop\app.py
python desktop\app.py --debug    # DevTools açık
```

## Özellikler

- **Native Windows penceresi** — Edge WebView2 (Chromium tabanlı)
- **Otomatik bağlantı** — Sunucu kapalıysa loading ekranında bekler
- **Hata yönetimi** — Bağlantı koptuğunda bilgilendirme ekranı
- **Cookie/session saklama** — Giriş bilgileri hatırlanır
- **Tek .exe** — Kurulum gerektirmez, USB'den çalışır

## Ayarlar

`desktop/app.py` dosyasının başında:

| Ayar | Varsayılan | Açıklama |
|------|-----------|----------|
| `SERVER_URL` | `http://192.168.0.12` | Backend sunucu adresi |
| `WINDOW_WIDTH` | `1280` | Pencere genişliği |
| `WINDOW_HEIGHT` | `820` | Pencere yüksekliği |
| `CHECK_INTERVAL` | `2` | Sunucu kontrol aralığı (sn) |

## İkon Ekleme

`desktop/icon.ico` dosyasını koyun — build sırasında otomatik kullanılır.  
256x256 çözünürlük önerilir.

## Gereksinimler

- Python 3.9+
- Windows 10/11 (Edge WebView2 Runtime otomatik gelir)
