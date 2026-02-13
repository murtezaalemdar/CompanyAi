# 🧠 Proje Hafızası

## Amaç
Kurumsal AI Asistanı — tamamen lokal, öğrenen, çok departmanlı yapay zeka sistemi.
Tekstil sektörü odaklı, her bölümün kendi bilgi tabanı ve yetkilendirmesi var.

## Sunucu
- **IP:** 192.168.0.12, Ubuntu 22.04, Intel Xeon 4316 16-core, **64GB RAM**, no GPU
- **LLM:** Ollama qwen2.5:72b (48GB in RAM, 0 swap), ~2 tok/s CPU-only
- **Versiyon:** v3.9.2

## Önemli Kararlar
- Tamamen lokal LLM (Ollama + qwen2.5:72b) — GPU yok, CPU-only (Xeon Silver 4316), 64GB RAM
- PostgreSQL kalıcı hafıza (sohbet geçmişi, tercihler, kültür)
- ChromaDB vektör hafıza (RAG + semantik arama)
- SerpAPI ile web arama (250 ücretsiz/ay, kredi kartı yok)
- rich_data sistemi: list yapısı — birden fazla kart (weather, images, export)
- Export formatları: Excel, PDF, PowerPoint, Word, CSV — otomatik + manuel
- Frontend deploy: Nginx `/var/www/html/` — `deploy_now.py` ile otomatik
- JWT Auth + RBAC (Admin/Manager/User) + departman bazlı erişim
- Desktop viewer: pywebview + PyInstaller → tek .exe dosya
- İmza: "Designed by Murteza ALEMDAR" — Login, Sidebar, Mobil menü, Desktop exe

## 🏷️ VERSİYON KURALI
Deploy öncesi `app/config.py` ve `frontend/src/constants.ts` içindeki `APP_VERSION` eşleşecek şekilde artır.

## Notlar
- Sunucu: 192.168.0.12, 64GB RAM, 16-core Xeon Silver 4316, NO GPU
- SerpAPI ücretsiz plan: 250 arama/ay
- fpdf2 kütüphanesi PDF export için eklendi (Helvetica font, Türkçe transliteration)
- python-pptx, openpyxl, python-docx zaten mevcut
- deploy_now.py BACKEND_FILES listesi statik — yeni dosya eklendiğinde güncellenmeli!

## 🔄 Oturum Özetleri

### Tarih: 10 Şubat 2026 — Phase 20: Web Arama + Görsel + Export

**Yapılan işler:**

**Phase 20a — Web Arama Entegrasyonu:**
- (commit `39bfbbf`) SerpAPI Google arama entegrasyonu
- (commit `4eafe02`) LLM prompt fix — web sonuçlarını kullansın
- (commit `e213d69`) Hava durumu kartı (WeatherCard.tsx) — Google tarzı gradient kart
- (commit `5f9dbf4`) Frontend deploy fix — deploy_now.py'ye `build_and_deploy_frontend()` eklendi

**Phase 20b — Görsel Arama Sonuçları:**
- (commit `c478097`) ImageResultsCard.tsx — 3x4 grid, lightbox, lazy loading
- Google Images engine (`google_images`) ile akıllı görsel arama
- `_query_needs_images()` — Türkçe tetikleyici kelimeler (örnek, desen, baskı vb.)
- `rich_data` dict → list refactoru (birden fazla kart desteği)

**Phase 20c — Rapor Export (Excel/PDF/PPTX/Word/CSV):**
- (commit `ad5a827`) Tam export sistemi
- `app/core/export_service.py` — 5 format üretici (Excel, PDF, PPTX, Word, CSV)
- `app/api/routes/export.py` — `/api/export/generate` + `/api/export/download/{file_id}`
- `ExportCard.tsx` — Format ikonu + indirme butonu
- `QuickExportButtons.tsx` — Her mesajdan sonradan export imkanı
- `engine.py` — Otomatik export: soru içinde "excel olarak", "sunum hazırla" vb.
- Akıllı format tespiti: Türkçe tetikleyiciler
- Markdown tablo parse → stilli Excel/PDF/PPTX çıktısı
- PDF: Türkçe transliteration (ı→i, ş→s vb.) + bullet fix
- Excel: MergedCell fix + auto-width
- deploy_now.py BACKEND_FILES listesine `export_service.py` + `export.py` eklendi

**Alınan kararlar:**
- rich_data her zaman list (birden fazla kart tipi desteklemek için)
- Export dosyaları temp dizinde saklanır, 1 saat TTL
- PDF'de Helvetica font kullanılır (Unicode desteği yok → transliteration)
- Soruda format tetikleyicisi varsa otomatik export, yoksa QuickExportButtons ile manuel

**Açık kalanlar:**
- Hava durumu kartı + görsel kart browser'da test edilecek (kullanıcı teyidi bekleniyor)
- Export kartları browser'da test edilecek
- SerpAPI kota takibi (250/ay limit)
- İleride: Markdown render (yanıtlar şu an whitespace-pre-wrap)

### Önceki Fazlar (Özet):
- Phase 1-16: Temel altyapı, auth, RAG, hafıza, dashboard, doküman yönetimi
- Phase 17: Şirket kültürü öğrenme + sohbet oturum persistance
- Phase 18: Güvenlik & kalite iyileştirmesi (17 düzeltme)
- Phase 19: Konuşma hafızası + session persistence düzeltmesi

## 📊 Commit Geçmişi (Son)
```
32cb128 fix: exe imza, download butonu, versiyon notları sadeleştirildi
5f82740 fix: Desktop HTTPS redirect, loading sayaç, web banner + downloads endpoint
44d9d38 feat: Desktop viewer (pywebview + PyInstaller) - CompanyAI.exe
992aef6 v2.6.0: Chat history UX - tarih gruplaması, mesaj sayısı, tekil silme, auto-refresh
fd8d181 v2.5.0: Versiyon sistemi, imza, deploy kontrol
ad5a827 feat: Rapor export - Excel, PDF, PowerPoint, Word, CSV indirme
c478097 feat: Gorsel arama sonuclari karti + rich_data liste destegi
```

### 11 Şubat 2026 — Oturum Özeti

**v2.5.0 → v2.6.0 güncelleme:**
- Qwen2.5:72b model kullanımda (48GB RAM, 0 swap)
- 64GB RAM yükseltme tamamlandı
- İmza: "Designed by Murteza ALEMDAR" — Login, Sidebar, Mobil menü, Desktop exe
- Versiyon badge: Login, Sidebar, Mobil menü, /api/health

**v2.6.0 — Sohbet Geçmişi UX:**
- Backend: `list_user_sessions` → mesaj sayısı (message_count) subquery
- Backend: `DELETE /memory/sessions/{id}` — tekil oturum silme
- Frontend sidebar: Tarih gruplandırması (Bugün/Dün/Bu Hafta/Bu Ay/Daha Eski)
- Her oturumda mesaj sayısı badge + hover'da silme butonu
- Mesaj gönderildikten sonra oturum listesi otomatik yenileme

**Desktop Viewer:**
- `desktop/app.py` — pywebview ile native Windows penceresi
- `desktop/companyai.spec` — PyInstaller tek dosya build config
- `desktop/build.bat` — Otomatik build scripti (venv + pip + pyinstaller)
- `dist/CompanyAI.exe` — 12.2MB, kurulum gerektirmez
- HTTPS redirect desteği + self-signed cert + loading sayaç
- İmza: Loading + hata ekranında "Designed by Murteza ALEMDAR"
- Nginx `/downloads` lokasyonu → exe sunucudan indirilebilir
- `DesktopBanner.tsx` — Web'de "Masaüstü uygulamasını indirin" bildirimi
  - pywebview içinde gizlenir, tarayıcıda gösterilir
  - 7 gün dismiss (localStorage)
  - window.open() ile indirme (self-signed cert uyumlu)

### 11 Şubat 2026 — Phase 21: Multi-Platform (Android + iOS + macOS)

**Yapılan işler:**

**Capacitor Kurulumu:**
- Capacitor 6.2.1 kuruldu (core, cli, android, ios, app, splash-screen, status-bar)
- `frontend/capacitor.config.ts` oluşturuldu (server URL, splash, statusbar, Android/iOS ayarları)
- `npx cap add android` + `npx cap add ios` → native projeler eklendi
- `npx cap sync` başarılı

**Android Native:**
- `AndroidManifest.xml` → usesCleartextTraffic + networkSecurityConfig
- `network_security_config.xml` — 192.168.0.12 HTTP cleartext izni
- Gradle 8.2.1 → 8.11.1, AGP 8.2.1 → 8.7.3 (JDK 23.0.2 uyumu)
- compileSdk/targetSdk 34 → 35, minSdk 22
- Tüm mipmap ikonları ve splash görselleri CompanyAI markalı olarak üretildi
- ic_launcher_background.xml: #FFFFFF → #0f1117
- `local.properties` şablonu oluşturuldu

**iOS Native:**
- `Info.plist` → NSAppTransportSecurity exception (192.168.0.12)
- AppIcon 1024×1024 + Splash 2732×2732 üretildi

**macOS Desktop:**
- `desktop/companyai_mac.spec` — PyInstaller macOS spec (.app bundle, WebKit, ATS plist)
- `desktop/build_mac.sh` — Otomatik build scripti (venv + pip + pyinstaller)
- `desktop/app.py` — sys.platform kontrolü eklendi (kısayol sadece Windows'ta)

**İkon & Splash Üretici:**
- `scripts/generate_icons.py` — Pillow ile ~35 görsel üretir (Android/iOS/Windows/macOS)
- `desktop/icon.ico` (6 boyut) + `desktop/icon_1024.png` üretildi

**Diğer:**
- `frontend/public/error.html` — mobil bağlantı hatası sayfası
- `MOBILE_BUILD.md` — kapsamlı build rehberi
- `frontend/package.json` — mobile:sync/android/ios/build-android scriptleri eklendi

**Alınan kararlar:**
- Capacitor 6 (Node 18 uyumu) > Capacitor 8 (Node 22 zorunlu)
- Tüm platformlar aynı mimari: sunucu URL'ini WebView'da aç
- Splash/ikon programatik üretilir (Pillow) — dış araca gerek yok
- Gradle/AGP JDK 23 ile uyumlu sürümlere yükseltildi

**Açık kalanlar:**
- Android Studio + SDK kurulumu → test APK build
- macOS'ta .app test build (macOS cihaz gerekli)
- iOS Xcode test build (macOS + Xcode + Apple Developer)
- Push notification (Firebase/APNs)
- Offline cache modu

---
## 11 Şubat 2026 — Detaylı Kod & Deploy Notları (özet)

- Versiyon: `2.7.0`
- Tamamlanan ana öğeler: prompts rewrite, structured_output, tool_registry, reasoning, forecasting, kpi_engine, textile_knowledge, risk_analyzer, sql_generator, vector_store hybrid, engine entegrasyonu, deploy.
- Önemli dosyalar: `app/core/engine.py`, `app/llm/prompts.py`, `app/llm/structured_output.py`, `app/core/tool_registry.py`, `app/core/kpi_engine.py`, `app/core/forecasting.py`, `app/core/textile_knowledge.py`, `app/core/risk_analyzer.py`, `app/core/sql_generator.py`, `app/rag/vector_store.py`.
- Deploy: Backend servis `companyai-backend` yeniden başlatıldı; Uvicorn çalışıyor. Frontend build edildi.
- Kısa next-steps: End-to-end smoke testleri; `sql_generator` test DB doğrulaması; hybrid ağırlık kalibrasyonu; tool-calling unit testleri; monitoring eklenecek.

### 11 Şubat 2026 — v2.8.0: Sesli Asistan (STT + TTS)

**Yapılan işler:**
- Ask.tsx'e Web Speech API ile mikrofon butonu (STT) eklendi
- Her mesaja Web Speech Synthesis ile "Dinle"/"Durdur" butonu (TTS) eklendi
- Tamamen browser-native, backend değişikliği yok
- Deploy başarılı

### 11 Şubat 2026 — v2.9.0: Backup & Restore Sistemi

**Yapılan işler:**
- `app/api/routes/backup.py` (9 endpoint) oluşturuldu
- PostgreSQL 8 tablo + ChromaDB (AI hafızası + RAG belgeleri) tek ZIP'te yedekleniyor
- Settings.tsx iki sütunlu layout: Sol=Ayarlar, Sağ=Backup & Restore
- Backup info kartları: DB boyutu, yedek sayısı, zamanlama, AI Hafıza (ChromaDB)
- Manuel yedek oluştur/indir/sil/restore + otomatik zamanlama (günlük/haftalık/aylık)
- Upload (harici ZIP) desteği
- Tablo istatistikleri görünümü
- `docs/db_schema.sql` — tüm tabloların şeması dökümente edildi

**Çözülen buglar:**
- `log_action()` TypeError — keyword-only args (user_id=, action=, resource=, details=)
- `Optional[User]` plain param → FastAPI startup crash (SQLAlchemy model Pydantic'e cast edilemez)
- JWT `sub` alanı user ID, email değil — download endpoint düzeltildi
- Frontend TypeScript type eksiklikleri (chromadb_included, chromadb_size_mb)

**Alınan kararlar:**
- ChromaDB verileri de backup'a dahil (v2.9.0+)
- Download: token query param ile (browser'dan doğrudan indirme için)
- Backup dizini: /opt/companyai/backups/ (sunucuda)
- Max 20 yedek saklanır (eski olanlar otomatik silinir)

### 11 Şubat 2026 — v2.9.0: ChatGPT Tarzı Karşılama + Sesli Sohbet Modu

**Yapılan işler:**

**ChatGPT tarzı karşılama ekranı:**
- Ask.tsx empty state tamamen yenilendi
- Şirket logosu (logoApi) + Copilot tarzı Sparkles ikonu
- Kişisel karşılama: "Merhaba, {isim}!" + "Bugün size nasıl yardımcı olabilirim?"
- 6 tıklanabilir öneri kartı (grid): Satış Raporu, Üretim Verimliliği, Maliyet Analizi, Pazar Araştırması, Şirket Politikaları, Genel Soru
- Karta tıklayınca prompt input'a otomatik yazılır
- RAG badge altında

**Sesli sohbet modu (ChatGPT voice chat benzeri):**
- `frontend/src/components/VoiceChat.tsx` oluşturuldu (~310 satır)
- Tam ekran overlay — kapatınca Ask.tsx'e dönüş
- Döngü: Dinle → 2sn sessizlik → Otomatik gönder → AI yanıt → Sesli oku (TTS) → Tekrar dinle
- Pulse animasyonları (dinleme: mavi, konuşma: mor, işleme: spinner)
- Konuşma log’u gösterilir (user/ai balonları)
- Ask.tsx’e AudioLines ikonu buton eklendi (gönder butonunun yanında siyah yuvarlak)
- Konusmalar aynı zamanda metin olarak chat geçmişine de eklenir
- Markdown temizleme (bold, header, code block, link) TTS öncesi
- Kırmızı telefon butonu ile kapat

**Alınan kararlar:**
- VoiceChat ayrı bileşen (reusable), Ask.tsx’e prop ile bağlı
- `handleVoiceChatSend` — `aiApi.askWithFiles()` ile doğrudan API çağrısı
- HTTPS zorunlu (mikrofon erişimi için)
- Ses tanıma dili: tr-TR

---

### 12 Şubat 2026 — v3.0.0 → v3.3.2: Çekirdek Modüller & UX

**Ana özellikler (özetler):**
- v3.0–v3.2: RAG pipeline, Multi-Agent Pipeline, Scenario Engine, Monte Carlo, Governance modülleri
- v3.3.0: ARIMA/SARIMA Forecast Engine + Enhanced Management Dashboard (commit `231db47`)
- v3.3.1: Yönetim paneli UI farklılaştırması — Sidebar amber tema, Crown icon, AdminRoute (commit `d54338f`)
- v3.3.2: Chat UX iyileştirmeleri — Auto-focus, Durdur butonu (AbortController), Tekrar dene (RotateCcw), DesktopBanner fix (commit `7e872b4`)

---

### 12 Şubat 2026 — v3.4.0: 6 Yeni Modül + Dashboard v2

**Backend — 6 yeni modül (commit `b09d5d9`):**
- `app/core/model_registry.py` — ML model versiyonlama, A/B test, production tracking
- `app/core/data_versioning.py` — Veri seti versiyonlama, lineage, diff
- `app/core/hitl.py` — Human-in-the-Loop onay/ret akışı
- `app/core/monitoring.py` — Sistem sağlığı, metrik toplama, alert
- `app/core/textile_vision.py` — Kumaş görüntü analizi (defekt tespiti)
- `app/core/explainability.py` — XAI, SHAP/LIME benzeri açıklamalar
- `app/api/routes/admin.py` — 24 yeni endpoint eklendi
- `app/core/engine.py` — Tüm yeni modüller entegre edildi

**Frontend — Dashboard v2 (commit `e1f588a`):**
- `frontend/src/services/api.ts` — 13 yeni API metodu
- `Dashboard.tsx` — 5 yeni panel: Health Score, Alerts, Model Registry, HITL, XAI
- `MODULE_LABELS` → 24 modül grid

---

### 12 Şubat 2026 — v3.5.0: Analiz Motoru İyileştirme (commit `d65dae6`)

**Yapılan işler:**
- Mevcut 7 analiz tipi iyileştirildi + 6 yeni analiz fonksiyonu eklendi (toplam 13):
  1. summary (özet), trend, comparison, anomaly_detection, correlation_analysis,
     distribution_analysis, forecast_analysis, pareto_analysis, data_quality_analysis,
     pivot, top_bottom, change (değişim), segment
- Frontend: 7→13 analiz tipi, yeni ikonlar, grid layout
- Dosya: `app/core/document_analyzer.py` (~2033 satır)

---

### 12 Şubat 2026 — v3.5.1: Pro Seviye Analiz Motoru (commit `b849d6d`, 656 ekleme)

**Motivasyon:** Mevcut analiz fonksiyonları yüzeyseldi — forecast basit linear regression kullanıyor (884 satırlık forecasting.py'ye bağlı değildi), korelasyon sadece Pearson, istatistiksel testler yoktu.

**Yükseltilen 6 fonksiyon:**

1. **forecast_analysis()** — TAM YENİDEN YAZILDI
   - 5 model karşılaştırması: Linear Regression, Holt Linear Trend, SES, ARIMA, Holt-Winters
   - MAPE bazlı en iyi model otomatik seçimi
   - Güven aralıkları (confidence intervals)
   - `app/core/forecasting.py` importları bağlandı (FORECASTING_AVAILABLE flag)

2. **correlation_analysis()** — Pearson + Spearman ikili matris
   - scipy p-value hesaplama
   - Doğrusallık (linearity) tespiti

3. **distribution_analysis()** — Normallik testleri
   - Shapiro-Wilk (n≤5000) / Kolmogorov-Smirnov (n>5000)
   - P99, yoğunlaşma metrikleri (concentration_iqr_pct)

4. **comparison_analysis()** — İstatistiksel testler
   - 2 grup: Welch t-test
   - 3+ grup: One-way ANOVA
   - Etki büyüklüğü: Cohen's d / Eta²
   - Anlamlılık bayrağı (p < 0.05)

5. **anomaly_detection()** — 4 yöntem
   - IQR, Z-Score, Modified Z-Score (MAD), Rolling Window
   - Grubbs testi
   - Ciddiyet sınıflandırması: kritik / orta / hafif

6. **data_quality_analysis()** — 4 boyut
   - Tamlık (Completeness) + Benzersizlik (Uniqueness) + Tutarlılık (Consistency) + Geçerlilik (Validity)
   - Tarih formatı doğrulama (regex + pd.to_datetime)
   - Aralık kontrolleri (negatif değerler, aşırı outlier'lar)
   - Çapraz kolon tutarlılığı (start < end)
   - Kardinalite analizi, eksik veri ortak oluşum desenleri

**Prompt şablonları:** `generate_analysis_prompt()` içindeki TÜM 6 bölüm güncellendi

**Bağımlılık:** `requirements.txt` → `scipy>=1.10.0` eklendi

---

### 12 Şubat 2026 — Dashboard React Error #31 Fix (commit `f76c7e0`)

**Sorun:** Dashboard beyaz ekran — React error #31
**Kök neden:** Vite build cache bayattı — derlenmiş JS eski `production_model` objesini property erişimi olmadan render ediyordu
**Çözüm:** `dist/` + `node_modules/.vite` temizlenip sıfırdan build → `index-Dug67X34.js`
**Ders:** Kritik deploy'lardan önce Vite cache'i mutlaka temizlenmeli

---

### 13 Şubat 2026 — v3.9.0 Insight Engine + CEO Dashboard (commit `0986e99`)

**Yeni Dosyalar:**
- `app/core/insight_engine.py` (~280 satır) — 7 otomatik içgörü türü (korelasyon, anomali, pareto, yoğunlaşma, trend, eşik, karşılaştırma), TEXTILE_THRESHOLDS (15 sektör metriği)
- `frontend/src/components/MessageContent.tsx` (~230 satır) — Kod bloğu ayrıştırma + Kopyala butonu + satır içi markdown

**Güncellenen Dosyalar:**
- `app/core/textile_knowledge.py` — 200 → 500+ terim (penye, örme, baskı, nakış, tedarik zinciri, sürdürülebilirlik)
- `app/core/agent_pipeline.py` — `execute_parallel_pipeline()`, PARALLEL_GROUPS: DataValidator → [Statistical ∥ Risk] → Financial → Strategy
- `app/api/routes/admin.py` — 3 yeni endpoint: `/insights/demo`, `/insights/analyze`, `/ceo/dashboard`
- `frontend/src/pages/Dashboard.tsx` (~1350 satır) — RadarChart, İçgörü kartları, Darboğaz özeti
- `frontend/src/pages/Ask.tsx` (~1575 satır) — MessageContent import, Seçip Sor popup (fixed z-[9999]), alıntı chip, submit entegrasyonu

**v3.9.1 — Kod Kopyalama Fix:**
- `MessageContent.tsx` bileşeni: `parseContent()` satır satır tarayıcı (regex yerine), kapatılmamış ``` bloklarını otomatik kapatır
- `CodeBlock`: koyu arka plan, dil etiketi, "Kopyala" butonu (`navigator.clipboard.writeText` + `execCommand` fallback)
- `renderInlineMarkdown()`: **kalın**, *italik*, `satır içi kod`, h1-h3

**v3.9.2 — Seçip Sor (Quote & Ask):**
- Metin seçim popup: `fixed` konumlandırma `z-[9999]`, Quote+ArrowRight ikonları
- Alıntı chip: input üstünde italik alıntı + X kapat butonu
- Submit: `"alıntı" — soru` formatında gönderim
- Fix: `absolute` → `fixed` (overflow-y-auto container clipping sorunu)

---

## Commit Geçmişi (güncel)
| Commit | Açıklama |
|--------|----------|
| `0986e99` | v3.9.0: Insight Engine + Paralel Agent + CEO Dashboard |
| `f76c7e0` | fix: Dashboard production_model obje render hatası |
| `b849d6d` | v3.5.1: Pro analiz — 5-model tahmin, Pearson+Spearman, normallik, t-test/ANOVA, Grubbs |
| `d65dae6` | v3.5.0: Analiz motoru iyileştirme + 6 yeni analiz tipi |
| `e1f588a` | v3.4.0: Dashboard v2 — Model Registry, HITL, Monitoring, XAI panelleri |
| `b09d5d9` | v3.4.0: 6 yeni modül, 24 endpoint, engine.py entegrasyonu |
| `7e872b4` | v3.3.2: DesktopBanner fix + debug cleanup |
| `a55ff7b` | v3.3.2: Chat UX iyileştirmeleri |
| `d54338f` | v3.3.1: Yönetim paneli UI |
| `231db47` | v3.3.0: ARIMA/SARIMA Forecast Engine |

## Önemli Dosyalar (güncel)
- `app/core/document_analyzer.py` (~2033 satır) — 13 analiz tipi, pro istatistiksel motor
- `app/core/insight_engine.py` (~280 satır) — 7 otomatik içgörü türü + tekstil eşikleri
- `app/core/forecasting.py` (884 satır) — ARIMA, SARIMA, Holt-Winters, SES
- `app/core/engine.py` — Ana koordinasyon motoru, 24+ modül
- `app/core/textile_knowledge.py` — 500+ tekstil sektör terimi
- `app/core/agent_pipeline.py` — Paralel multi-agent pipeline
- `app/core/model_registry.py` — ML model versiyonlama
- `app/core/monitoring.py` — Sistem sağlığı izleme
- `app/core/explainability.py` — XAI açıklamalar
- `frontend/src/components/MessageContent.tsx` (~230 satır) — Kod bloğu + markdown render
- `frontend/src/pages/Ask.tsx` (~1575 satır) — AI chat + seçip sor + alıntı
- `frontend/src/pages/Dashboard.tsx` (~1350 satır) — CEO dashboard + RadarChart
- `frontend/src/services/api.ts` — Backend API servisleri

## Bağımlılıklar (önemli eklemeler)
- `scipy>=1.10.0` — İstatistiksel testler (t-test, ANOVA, Shapiro-Wilk, Grubbs) — v3.5.1
- `statsmodels>=0.14.0` — ARIMA, SARIMA, Holt-Winters, SES — v2.7.0+
- `openpyxl` — Excel okuma/yazma

