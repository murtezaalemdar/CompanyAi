# 🤖 Copilot Kalıcı Bağlam — CompanyAi

Bu dosya GitHub Copilot Chat için ana bağlamdır. Kod üretirken bu dosya önceliklidir.

## 🏢 Proje Özeti
- **Proje:** Kurumsal AI Asistanı (tamamen lokal, öğrenen)
- **Backend:** FastAPI + Uvicorn, async SQLAlchemy (asyncpg), structlog
- **LLM:** Ollama + qwen2.5:72b (48GB RAM), CPU-only ~2 tok/s
- **Vector DB:** ChromaDB + SentenceTransformers
- **RAG Embedding:** `paraphrase-multilingual-mpnet-base-v2` (768-dim)
- **DB:** PostgreSQL 14.20, port 5433, user `companyai`, db `companyai`
- **Auth:** JWT (HS256) + pbkdf2_sha256 + RBAC (Admin/Manager/User)
- **Frontend:** React + TypeScript + Vite + Tailwind CSS + TanStack Query
- **Desktop:** pywebview + PyInstaller → CompanyAI.exe (12MB)
- **Versiyon:** v3.9.2
- **Proje dizini (lokal):** `C:\Users\murteza.KARAKOC\Desktop\Python\CompanyAi`
- **Proje dizini (sunucu):** `/opt/companyai`

## 🌍 Sunucu & SSH
- **IP:** `192.168.0.12`
- **URL:** `https://192.168.0.12`
- **User:** `root` — **Şifre:** `435102`
- **SSH Key:** `keys/companyai_key` (Ed25519)
- **Bağlantı:** `ssh -i keys/companyai_key root@192.168.0.12`
- **Backend servis:** `systemctl restart companyai-backend`
- **Frontend:** `/var/www/html/` (Nginx)
- **Deploy:** `python deploy_now.py` (backend + frontend otomatik)

## 🚀 Deploy Süreci
- `deploy_now.py` — Backend dosyaları SCP + frontend npm build + SCP to /var/www/html/
- **ÖNEMLİ:** `BACKEND_FILES` listesi statik — yeni dosya eklendiğinde güncelle!
- Frontend build: `cd frontend && npm run build`
- Deploy komutu: `cd CompanyAi; $env:PYTHONIOENCODING='utf-8'; python deploy_now.py`

## 🏷️ VERSİYON KURALI — HER DEPLOY'İN ÖNCESİNDE ZORUNLU!

Deploy öncesi `app/config.py` ve `frontend/src/constants.ts` içindeki `APP_VERSION` eşleşecek şekilde artır.
(PATCH=bugfix, MINOR=özellik, MAJOR=kırılma)

## 🖥️ Desktop Uygulaması (Windows + macOS)
- **Windows:** `desktop/app.py` → pywebview (Edge WebView2) native pencere
  - Build: `desktop/build.bat` veya `pyinstaller desktop/companyai.spec`
  - Çıktı: `dist/CompanyAI.exe` (~12MB tek dosya)
  - Download: `https://192.168.0.12/downloads/CompanyAI.exe`
- **macOS:** `desktop/app.py` → pywebview (WebKit cocoa) native pencere
  - Build: `./desktop/build_mac.sh` veya `pyinstaller desktop/companyai_mac.spec`
  - Çıktı: `dist/CompanyAI.app` bundle
  - ATS exception için plist spec içine gömülü
- **Ortak özellikler:** HTTPS redirect, self-signed cert, loading sayaç, imza
- **Web banner:** `DesktopBanner.tsx` — tarayıcıdan girince "İndir" bildirimi (7 gün dismiss)
- `deploy_now.py` otomatik kontrol eder, farklıysa uyarı verir

## 📱 Mobil Uygulama (Android + iOS)
- **Framework:** Capacitor 6.2.1 (Node 18 uyumlu; v8 Node 22 gerektirdi)
- **AppId:** `com.companyai.app`
- **Mimari:** Sunucudaki React SPA'yı native WebView içinde açar (`http://192.168.0.12`)
- **Config:** `frontend/capacitor.config.ts`
- **Android:** `frontend/android/` — AGP 8.7.3, Gradle 8.11.1, SDK 35, minSdk 22
  - HTTP izni: `network_security_config.xml` + `AndroidManifest.xml`
  - Build: `cd frontend && npm run mobile:build-android`
  - Aç: `npm run mobile:android` (Android Studio)
- **iOS:** `frontend/ios/` — ATS exception (Info.plist)
  - Aç: `npm run mobile:ios` (Xcode)
- **Error page:** `frontend/public/error.html` — sunucu bağlantısı kesildiğinde
- **Splash & İkonlar:** `python scripts/generate_icons.py` — Pillow ile ~35 görsel üretir
- **npm Scriptleri:** `mobile:sync`, `mobile:android`, `mobile:ios`, `mobile:build-android`

## 📄 Doküman Yönetimi v2 (Güncel)
- **Desteklenen format:** 65+ dosya formatı (metin, office, kod, e-posta, görüntü OCR)
- **Öğrenme kaynakları:** Dosya yükleme, metin girişi, URL scraping, YouTube altyazı
- **Frontend sekmeleri:** Dosya Yükle / Bilgi Gir / URL Öğren / Video Öğren
- **Klasör desteği:** webkitdirectory ile klasör seçimi + alt klasör ağacı görünümü
- **Doküman kütüphanesi:** Tablo görünümü (kaynak, tür, departman, ekleyen, tarih, parça)
- **Pip bağımlılıkları:** beautifulsoup4, youtube-transcript-api, striprtf, lxml
- **Endpoint'ler:** `/rag/learn-url`, `/rag/learn-video`, `/rag/capabilities`

## 🌐 Web Arama (Phase 20)
- **SerpAPI:** Ücretsiz 250 arama/ay, key `.env`'de
- **Engine:** `google` (normal) + `google_images` (görsel arama)
- **Akıllı tetikleme:** Soruda "örnek, desen, baskı" → otomatik görsel arama
- **Rich data:** `rich_data: Optional[list]` — her kart bir dict: `{type, ...}`
  - `type: "weather"` → WeatherCard.tsx
  - `type: "images"` → ImageResultsCard.tsx (lightbox + grid)
  - `type: "export"` → ExportCard.tsx (indirme kartı)

## 🎩️ Ses Özellikleri (v2.8.0 → v2.9.0)
- **STT:** Web Speech API (SpeechRecognition) — mikrofon butonu, Ask.tsx
- **TTS:** Web Speech Synthesis — her mesajda "Dinle"/"Durdur" butonu
- **Browser-native:** Backend değişikliği yok, tamamen frontend
- **Sesli Sohbet Modu (v2.9.0):** ChatGPT tarzı tam ekran karşılıklı sesli sohbet
  - `VoiceChat.tsx` bileşeni — full-screen overlay
  - Döngü: Dinle → Gönder → AI Yanıtla → Sesli Oku → Tekrar Dinle
  - 2 sn sessizlik algılama ile otomatik gönderim
  - AudioLines buton (gönder yanında siyah yuvarlak)
  - Konuşma geçmişi chat mesajlarına da yansır

## 🎨 ChatGPT Tarzı Karşılama Ekranı (v2.9.0)
- Ask.tsx boş durum → Şirket logosu + Copilot ikonu + kişisel karşılama
- 6 tıklanabilir öneri kartı (Satış Raporu, Üretim, Maliyet, Pazar, Politika, Genel)
- Karta tıklayınca prompt input'a yazılır
- `logoApi.getLogo()` ile dinamik logo çekme

## 💾 Yedekleme & Geri Yükleme (v2.9.0)
- **Backend:** `app/api/routes/backup.py` — 9 endpoint
  - `GET /api/backup/list` — yedek listesi
  - `POST /api/backup/create` — manuel yedek oluştur (PG + ChromaDB)
  - `GET /api/backup/download/{filename}?token=JWT` — ZIP indir
  - `POST /api/backup/restore` — geri yükle (confirm=true)
  - `DELETE /api/backup/delete/{filename}` — yedek sil
  - `POST /api/backup/upload` — harici ZIP yükle
  - `GET /api/backup/schedule` — zamanlama ayarı oku
  - `PUT /api/backup/schedule` — zamanlama güncelle
  - `GET /api/backup/info` — tablo stats, disk bilgisi, ChromaDB boyutu
- **Kapsam:** PostgreSQL (8 tablo) + ChromaDB (AI hafızası + RAG) tek ZIP'te
- **Frontend:** Settings.tsx — iki sütunlu layout (Sol: Ayarlar, Sağ: Backup)
- **DB Şeması:** `docs/db_schema.sql`
- **log_action() uyarı:** keyword-only args kullanır: `await log_action(db, user_id=..., action=..., resource=..., details=...)`
- **JWT sub alanı:** `sub` = user ID (int as string), email DEĞİL

## 📥 Export Sistemi (Phase 20c)
- **Formatlar:** Excel (.xlsx), PDF, PowerPoint (.pptx), Word (.docx), CSV
- **Servis:** `app/core/export_service.py`
- **API:** `POST /api/export/generate` + `GET /api/export/download/{file_id}`
- **Otomatik:** `engine.py` soruda "excel olarak", "sunum hazırla" → otomatik dosya üretimi
- **Manuel:** `QuickExportButtons.tsx` — her mesajdan export
- **Kütüphaneler:** openpyxl, fpdf2, python-pptx, python-docx
- **TTL:** Temp dizinde 1 saat

## 🔑 Önemli Dosyalar
| Dosya | Açıklama |
|---|---|
| `app/core/engine.py` | Merkezi işlem motoru — RAG + Web + Hafıza + Export |
| `app/llm/web_search.py` | SerpAPI + Google Images + DuckDuckGo fallback |
| `app/core/export_service.py` | Excel/PDF/PPTX/Word/CSV üretici |
| `app/api/routes/export.py` | Export API endpoint'leri |
| `app/api/routes/multimodal.py` | Ana AI soru-cevap endpoint'i (Form-data) |
| `app/main.py` | FastAPI app + tüm router kayıtları |
| `frontend/src/pages/Ask.tsx` | Ana sohbet sayfası (~1260 satır) |
| `frontend/src/components/VoiceChat.tsx` | Tam ekran sesli sohbet overlay bileşeni |
| `frontend/src/components/DesktopBanner.tsx` | Desktop app indirme banner'ı |
| `frontend/src/services/api.ts` | Axios API client |
| `frontend/capacitor.config.ts` | Capacitor mobil ayarları (sunucu URL, splash, statusbar) |
| `frontend/public/error.html` | Mobil sunucu bağlantı hatası sayfası |
| `desktop/app.py` | Masaüstü uygulaması (pywebview — Windows + macOS) |
| `desktop/companyai.spec` | Windows PyInstaller build config |
| `desktop/companyai_mac.spec` | macOS PyInstaller build config (.app bundle) |
| `desktop/build_mac.sh` | macOS otomatik build scripti |
| `desktop/icon.ico` / `icon_1024.png` | Desktop ikonları (Windows .ico + macOS PNG) |
| `scripts/generate_icons.py` | Tüm platformlar ikon + splash üretici (Pillow) |
| `MOBILE_BUILD.md` | Mobil uygulama build rehberi |
| `deploy_now.py` | Otomatik deploy script |

## Kod Prensipleri
- Clean code
- Okunabilirlik > kısalık
- Fonksiyonlar tek iş yapar
- `any` kullanma (zorunlu değilse)

## 📱 Platform Desteği
| Platform | Araç | Build | Çıktı | Durum |
|----------|------|-------|-------|-------|
| Windows | pywebview + PyInstaller | `desktop\build.bat` | `.exe` | ✅ Hazır |
| macOS | pywebview + PyInstaller | `./desktop/build_mac.sh` | `.app` | ✅ Hazır |
| Android | Capacitor 6 + WebView | `npm run mobile:android` | `.apk` | ✅ Hazır |
| iOS | Capacitor 6 + WKWebView | `npm run mobile:ios` | `.ipa` | ✅ Hazır |
| Web | React + Vite + Nginx | `deploy_now.py` | HTML | ✅ Canlı |

### Sunucu URL Değiştiğinde Güncelle
| Dosya | Alan |
|-------|------|
| `frontend/capacitor.config.ts` | `server.url` |
| `desktop/app.py` | `SERVER_URL` |
| `frontend/android/.../network_security_config.xml` | `<domain>` |
| `frontend/ios/.../Info.plist` | `NSExceptionDomains` |
| Sonra: `cd frontend && npx cap sync` | |

## Mimari
- Business logic izole
- Modüler yapı
- Test edilebilirlik öncelikli

## Frontend Kuralları
- UI logic ile business logic ayrılmalı
- State minimal tutulmalı
- Re-render maliyeti düşünülmeli
- Component'ler küçük olmalı
- Side-effect'ler hook içinde

## Backend Kuralları
- Controller ince, service kalın
- Validation girişte yapılır
- Error handling merkezi
- IO ve business logic ayrılır
- Loglar anlamlı ve seviyeli (structlog)

---
## 11 Şubat 2026 — Özet Notlar (referans: reference.md)

- Versiyon: `2.7.0` (backend + frontend)
- Özet: Prompts rewrite, structured output, tool registry, multi-step reasoning, forecasting, KPI engine, textile knowledge, risk analyzer, SQL generator, vector_store hybrid ve engine entegrasyonu tamamlandı.
- Deploy: `deploy_now.py` ile deploy yapıldı; `companyai-backend` servisi active; Uvicorn dinliyor.
- Dikkat: `sql_generator` üretilecek SQL'leri test DB'de doğrulayın, hybrid search ağırlıklarını kalibre edin.



