# 🤖 Copilot Kalıcı Bağlam — CompanyAi

Bu dosya GitHub Copilot Chat için ana bağlamdır. Kod üretirken bu dosya önceliklidir.

## 🏢 Proje Özeti
- **Proje:** Kurumsal AI Asistanı (tamamen lokal, öğrenen)
- **Backend:** FastAPI + Uvicorn, async SQLAlchemy (asyncpg), structlog
- **LLM:** Ollama + qwen2.5:72b (48GB RAM), CPU-only ~2 tok/s
- **Vision:** minicpm-v (görüntü + OCR)
- **Omni-Modal:** minicpm-o (görüntü + video + ses)
- **Vector DB:** ChromaDB + SentenceTransformers
- **RAG Embedding:** `paraphrase-multilingual-mpnet-base-v2` (768-dim)
- **DB:** PostgreSQL 14.20, port 5433, user `companyai`, db `companyai`
- **Auth:** JWT (HS256) + pbkdf2_sha256 + RBAC (Admin/Manager/User)
- **Frontend:** React + TypeScript + Vite + Tailwind CSS + TanStack Query
- **Desktop:** pywebview + PyInstaller → CompanyAI.exe (S1+S2 ayrı build)
- **Versiyon:** v6.03.00
- **AI Modül Sayısı:** 49
- **Proje dizini (lokal):** `C:\Users\murteza.KARAKOC\Desktop\Python\CompanyAi`
- **Proje dizini (sunucu):** `/opt/companyai`

## 🌍 Sunucu & SSH
- **Server 1:** `192.168.0.12` (CPU-only, 64GB RAM, Xeon 4316)
- **URL:** `https://192.168.0.12`
- **User:** `root` — **SSH Key:** `keys/companyai_key` (Ed25519)
- **Bağlantı:** `ssh -i keys/companyai_key root@192.168.0.12`
- **Server 2:** `88.246.13.23:2013` (2× RTX 3090, 48GB VRAM toplamı)
- **Şifre S2:** `Kc435102mn` (server2_key private key eksik — deploy paramiko ile şifre fallback kullanır)
- **SSH Key S2:** `keys/server2_key`
- **Backend servis:** `systemctl restart companyai-backend`
- **Frontend:** `/var/www/html/` (Nginx)
- **Deploy:** `python deploy_now.py` (server1) / `--all` (her iki sunucu) / `--server2`

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
  - Build: `python desktop/build_all.py` (S1+S2 toplu) veya `pyinstaller desktop/companyai.spec`
  - Çıktı: `dist/CompanyAI.exe` (S1) + `dist/CompanyAI_S2.exe` (S2)
  - Download S1: `https://192.168.0.12/downloads/CompanyAI.exe`
  - Download S2: `https://88.246.13.23:2015/downloads/CompanyAI.exe`
  - SERVER_ID + SERVERS dict: S1(HTTP) / S2(HTTPS+SSL) ayrı URL
  - Kısayol adı: `CompanyAI (Sunucu 1).lnk` / `CompanyAI (Sunucu 2).lnk`
  - İkon: LOGO.png'den üretilmiş `icon.ico` (7 boyut: 16-256px) — Orhan Karakoç gold tree logosu
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

## � Upload Progress & Error Handling (v5.10.0)
- **Upload Progress UI:** Animasyonlu shimmer/gradient ilerleme çubuğu
  - **Yükleme fazı:** Mavi gradient + shimmer, `%XX` gösterimi
  - **İşleme fazı:** Amber pulsing "Öğreniyor..." Brain ikonu
  - **Tamamlandı:** Yeşil CheckCircle "Tamamlandı!"
- **api.ts:** `uploadDocument()` → `onUploadProgress` callback + `timeout: 600000` (10 dk)
- **Documents.tsx:** `uploadPercent`, `uploadPhase`, `uploadMessage` state'leri
- **tailwind.config.js:** `uploadShimmer` keyframe animasyonu (translateX -100% → 100%)
- **Hata Yönetimi:**
  - 413 → "Dosya çok büyük (X MB). Maksimum 500 MB."
  - Timeout → "Zaman aşımı — dosya çok büyük veya bağlantı yavaş"
  - 500 → "Sunucu hatası"
  - Network Error → "Bağlantı hatası"
  - Başarı → "X dosya başarıyla yüklendi ve öğrenildi!" (yeşil bildirim)
- **Nginx:** Her iki sunucuda `client_max_body_size 500M`

## 🔄 ChromaDB Senkronizasyonu (v5.9.2)
- **Yön:** Server 1 ← Server 2 (S1 her 15 dk S2'den çeker)
- **S2 Export:** `/opt/companyai/sync_chromadb_export.py`
- **S1 Import:** `/opt/companyai/sync_chromadb.py`
- **Cron (S1):** `*/15 * * * * /usr/bin/python3 /opt/companyai/sync_chromadb.py`
- **Koleksiyonlar:** learned_knowledge (5), company_documents (62), company_memory (180) = 247 kayıt
- **Embedding:** `paraphrase-multilingual-mpnet-base-v2` (768-dim) — boyut uyuşmazlığı re-embed ile çözüldü

## �📄 Doküman Yönetimi v2 (Güncel)
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
| `desktop/app.py` | Masaüstü uygulaması (pywebview — Windows + macOS, SERVER_ID config) |
| `desktop/companyai.spec` | Windows PyInstaller build config |
| `desktop/companyai_mac.spec` | macOS PyInstaller build config (.app bundle) |
| `desktop/build_all.py` | S1+S2 toplu build scripti (set_server_id + PyInstaller) |
| `desktop/build_mac.sh` | macOS otomatik build scripti |
| `desktop/icon.ico` / `icon_1024.png` | Desktop ikonları (LOGO.png kaynaklı Windows .ico + macOS PNG) |
| `scripts/generate_icons.py` | Tüm platformlar ikon + splash üretici (Pillow) |
| `MOBILE_BUILD.md` | Mobil uygulama build rehberi |
| `deploy_now.py` | Otomatik deploy script |

## 🧠 AI Modül Puanları (v5.1.0 — 37 Modül, Ortalama: 81.6/100)

| # | Modül | Puan | Satır | Açıklama |
|---|-------|------|-------|----------|
| 1 | Tool Registry | 88 | 858 | ReAct pattern, 8+ araç, Ollama function calling |
| 2 | Reasoning | 72 | 343 | Çok adımlı CoT, max 5 adım |
| 3 | Structured Output | 70 | 289 | JSON extraction, şema validasyonu |
| 4 | KPI Engine | 85 | 442 | 50+ KPI, Balanced Scorecard, benchmark |
| 5 | Textile Knowledge | 80 | 373 | 200+ terim, fire analizi, kalite kontrol |
| 6 | Risk Analyzer | 82 | 339 | FMEA, 5×5 matris, what-if |
| 7 | Reflection | 90 | 673 | 5 kriter, hallucination, auto-retry |
| 8 | Agent Pipeline | 78 | 554 | 6 uzman ajan, sequential+parallel |
| 9 | Scenario Engine | 75 | 271 | Best/Expected/Worst senaryolar |
| 10 | Monte Carlo | 80 | 264 | N-iterasyon, VaR, CI, volatilite |
| 11 | Decision Ranking | 76 | 261 | ROI×Risk×Strateji puanlama |
| 12 | Governance | 92 | 643 | Bias, drift, 12 politika, hash chain |
| 13 | Experiment Layer | 74 | 377 | A/B strateji sim, auto-tune |
| 14 | Graph Impact | 73 | 371 | KPI/Dept/Risk ilişki grafı |
| 15 | ARIMA Forecasting | 89 | 844 | ARIMA/SARIMA, Holt-Winters, SES |
| 16 | SQL Generator | 77 | 409 | Doğal dil→SQL, feature engineering |
| 17 | Export Service | 83 | 683 | Excel/PDF/PPTX/Word/CSV |
| 18 | Web Search | 79 | 515 | SerpAPI+Google+DuckDuckGo |
| 19 | Model Registry | 71 | 222 | Model versiyonlama, staging/prod |
| 20 | Data Versioning | 70 | 267 | Dataset snapshot/rollback, diff |
| 21 | Human-in-the-Loop | 81 | 287 | Onay kuyruğu, feedback öğrenme |
| 22 | Monitoring | 84 | 586 | GPU/API izleme, z-score, SLA |
| 23 | Textile Vision | 68 | 311 | LLM Vision kumaş hatası, renk |
| 24 | Explainability | 91 | 1209 | XAI v4, faktör skoru, kalibrasyon |
| 25 | Bottleneck Engine | 77 | 421 | Darboğaz tespiti, kuyruk analizi |
| 26 | Executive Health | 82 | 688 | Sağlık skoru 0-100, 4 boyut |
| 27 | OCR Engine | 76 | 450 | EasyOCR (TR+EN), fatura/tablo |
| 28 | Numerical Validation | 73 | — | Sayısal tutarsızlık tespiti |
| 29 | Meta Learning | 93 | 824 | Strategy profiling, knowledge gap |
| 30 | Self Improvement | 94 | 1042 | ThresholdOptimizer, PromptEvolver |
| 31 | Multi-Agent Debate | 92 | 1098 | 6 perspektif, consensus, sentez |
| 32 | Causal Inference | 91 | 1208 | 5 Whys, Ishikawa, DAG, counterfactual |
| 33 | Strategic Planner | 90 | 1171 | PESTEL, Porter, SMART, OKR |
| 34 | Executive Intelligence | 89 | 1008 | CEO brifing, RAPID/RACI, board raporu |
| 35 | Knowledge Graph | 88 | 944 | Entity/relation, BFS, kümeleme |
| 36 | Decision Gatekeeper | 87 | 635 | PASS/WARN/BLOCK/ESCALATE |
| 37 | Uncertainty Quantification | 85 | 404 | Epistemik/Aleatoric, ensemble |

**Toplam:** ~21.500 satır AI kodu, ~158 sınıf, ~698 fonksiyon
**En güçlü:** Self Improvement (94), Meta Learning (93), Governance (92), Multi-Agent Debate (92)
**Gelişime açık:** Textile Vision (68), Structured Output (70), Data Versioning (70)

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

---

## 🛡️ Enterprise Güvenlik (v4.5.0)
- **Credentials:** `.env.deploy` dosyasından (gitignored), environment variable override destekler
- **Servis:** systemd Unit → companyai user, NoNewPrivileges, ProtectSystem=strict, PrivateTmp
- **Timeout:** gunicorn 180s (eski: 960s)
- **CORS:** Spesifik HTTP method + header listesi (wildcard kaldırıldı)
- **Injection:** Base64-encoded prompt injection algılama (3 pattern)
- **Auth:** 5 başarısız giriş → 15dk hesap kilitleme, must_change_password
- **Audit:** SHA-256 hash chain → tamper-proof denetim kaydı (her kayıt öncekine bağlı)

## 🎙️ Omni-Modal AI (v4.5.0 — MiniCPM-o 2.6)
- **Model:** `minicpm-o` — görüntü + video + ses analizi tek modelden
- **Routing:** `use_omni=True` → minicpm-o, sadece resim → minicpm-v, metin → qwen2.5
- **Video:** cv2 frame sampling (8 kare, 512px, WebP), max 100MB / 120s
- **Ses:** Base64 audio, WAV duration, max 25MB, 9 format (mp3, wav, ogg, flac, m4a, aac, wma, opus, webm)
- **Endpoint'ler:** `/upload/audio`, `/upload/video`, `/omni/capabilities`
- **Frontend:** Music/Film ikonları, mor (ses) / mavi (video) önizleme, dosya tipi algılama
- **Bağımlılık:** `opencv-python-headless>=4.8.0`

## 🔒 SSL (v5.10.0)
- **Server 1:** Mevcut HTTPS (`https://192.168.0.12`)
- **Server 2:** Self-signed SSL sertifika (10 yıl, 2036'ya kadar geçerli)
  - Sertifika: `/etc/nginx/ssl/server.crt` + `/etc/nginx/ssl/server.key`
  - CN/SAN: `88.246.13.23`
  - Nginx: `listen 443 ssl` + `listen 80` (ikisi de aktif)
  - Dış erişim: `https://88.246.13.23:2015` (port yönlendirme: 2015 → 443)
  - Not: Self-signed → tarayıcı uyarısı verir, "Devam et" ile geçilir

## 🗄️ PostgreSQL Veritabanı Şeması
- **DB:** PostgreSQL 14.20, port 5433, user `companyai`, db `companyai`
- **ORM:** SQLAlchemy (async, asyncpg driver)
- **Modeller** (`app/db/models.py`):

### users
| Kolon | Tip | Açıklama |
|-------|-----|----------|
| id | Integer PK | |
| email | String(255) UNIQUE | Giriş e-postası |
| hashed_password | String(255) | pbkdf2_sha256 hash |
| full_name | String(255) | |
| department | String(100) | Üretim, Satış, İK vb. |
| role | String(50) | admin / manager / user |
| is_active | Boolean | Hesap aktif mi |
| must_change_password | Boolean | İlk giriş şifre değişimi |
| password_changed_at | DateTime | Son şifre değişim zamanı |
| failed_login_attempts | Integer | Ardışık başarısız giriş (5→kilit) |
| locked_until | DateTime | Hesap kilitleme zamanı |
| created_at / updated_at | DateTime | |

### queries
| Kolon | Tip | Açıklama |
|-------|-----|----------|
| id | Integer PK | |
| user_id | FK→users | |
| question | Text | Sorulan soru |
| answer | Text | AI yanıtı |
| department | String(100) | |
| mode | String(100) | |
| risk_level | String(50) | |
| confidence | Float | |
| processing_time_ms | Integer | İşlem süresi (ms) |
| created_at | DateTime | |

### audit_logs
| Kolon | Tip | Açıklama |
|-------|-----|----------|
| id | Integer PK | |
| user_id | FK→users | |
| action | String(100) | login, logout, query, admin_action |
| resource | String(100) | Etkilenen kaynak |
| details | Text | JSON detaylar |
| ip_address | String(50) | |
| user_agent | String(255) | |
| hash_chain | String(64) | SHA-256 tamper-proof zincir |
| created_at | DateTime | |

### system_settings
| Kolon | Tip | Açıklama |
|-------|-----|----------|
| id | Integer PK | |
| key | String(100) UNIQUE | Ayar anahtarı |
| value | Text | Ayar değeri |
| description | String(255) | |
| updated_at | DateTime | |
| updated_by | FK→users | |

### chat_sessions
| Kolon | Tip | Açıklama |
|-------|-----|----------|
| id | Integer PK | |
| user_id | FK→users | |
| title | String(255) | "Yeni Sohbet" default |
| is_active | Boolean | |
| created_at / updated_at | DateTime | |

### conversation_memory
| Kolon | Tip | Açıklama |
|-------|-----|----------|
| id | Integer PK | |
| user_id | FK→users | |
| session_id | FK→chat_sessions | |
| question | Text | |
| answer | Text | |
| department | String(100) | |
| intent | String(50) | |
| created_at | DateTime | |

### user_preferences
| Kolon | Tip | Açıklama |
|-------|-----|----------|
| id | Integer PK | |
| user_id | FK→users | |
| key | String(100) | name, favorite_topic, style vb. |
| value | Text | |
| source | String(200) | Hangi konuşmadan çıkarıldı |
| created_at / updated_at | DateTime | |

### company_culture
| Kolon | Tip | Açıklama |
|-------|-----|----------|
| id | Integer PK | |
| category | String(100) | report_style, comm_style, tool_preference, workflow |
| key | String(200) | |
| value | Text | |
| frequency | Integer | Kaç kez gözlemlendi |
| source_user_id | FK→users | |
| source_text | String(300) | |
| created_at / updated_at | DateTime | |

### xai_records
| Kolon | Tip | Açıklama |
|-------|-----|----------|
| id | Integer PK | |
| query_hash | String(20) | |
| query_preview | String(200) | |
| mode | String(50) | |
| module_source | String(50) | |
| weighted_confidence | Float | |
| risk_level | String(20) | |
| risk_score | Float | |
| reasoning_steps | Integer | |
| sources_used | Integer | |
| rag_hit / web_searched / had_reflection | Boolean | |
| word_count | Integer | |
| factors | JSON | Faktör skorları |
| counterfactual | Text | |
| user_rating | Float | 1-5 arası geri bildirim |
| created_at | DateTime | |

### İlişkiler
- User → queries, audit_logs, chat_sessions, conversation_memories, preferences
- ChatSession → messages (ConversationMemory)
- Query → user
- AuditLog → user (hash_chain ile tamper-proof)



