# 🧠 Proje Hafızası

## Amaç
Kurumsal AI Asistanı — tamamen lokal, öğrenen, çok departmanlı yapay zeka sistemi.
Tekstil sektörü odaklı, her bölümün kendi bilgi tabanı ve yetkilendirmesi var.

## Sunucu
- **Server 1:** 192.168.0.12:22, Ubuntu 22.04, Intel Xeon 4316 16-core, **64GB RAM**, CPU-only
  - LLM: Ollama qwen2.5:72b (48GB RAM, 0 swap), ~2 tok/s
  - SSH Key: `keys/companyai_key` (Ed25519)
- **Server 2:** 88.246.13.23:2013, **2× NVIDIA RTX 3090, 48GB VRAM toplam**
  - GPU offload, hızlı inference
  - SSH Key: `keys/server2_key` (private key eksik — deploy paramiko ile şifre fallback kullanır)
  - Şifre: `Kc435102mn`
- **Modeller:** qwen2.5:72b (text), minicpm-v (vision/OCR), minicpm-o (omni-modal), mpnet-base-v2 (embedding)
- **Versiyon:** v5.10.0

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

### Tarih: 16 Şubat 2026 — v5.9.0: Modül Koordinasyonu & Prompt Kalitesi

**Amaç:** LLM modüllerinin birbiriyle uyumlu çalışması ve prompt yanıt kalitesinin artırılması.

**Problem:** Kullanıcı yanıt kalitesinden memnun değildi. Teşhis sonucu 5 kök neden bulundu:
1. System prompt token şişkinliği (8K context'in %70'ini system prompt yiyordu)
2. Post-processing gürültüsü (15+ bölüm cevaba "---" ile ekleniyordu)
3. Gereksiz ekstra LLM çağrıları (multi-perspective: +10-30 sn)
4. Sıcaklık tutarsızlığı (Bilgi modu 0.7 → halüsinasyon)
5. max_tokens yetersizliği (Analiz/Rapor 1024 token → kesiliyordu)

**Yapılan Değişiklikler:**

| # | Değişiklik | Dosya | Detay |
|---|---|---|---|
| 1 | SYSTEM_PROMPT kısaltma | prompts.py | ~%60 azaltma, CoT/çıktı formatı bölümleri kaldırıldı |
| 2 | DEPARTMENT_PROMPTS kısaltma | prompts.py | 6 departman ~%80 kısaltıldı, verbose örnekler kaldırıldı |
| 3 | MODE_PROMPTS kısaltma | prompts.py | Analiz 500+ → ~150 token, tüm modlar optimize |
| 4 | build_prompt() sadeleştirme | prompts.py | Şablon birikimi engellendi → max 1 uzmanlık şablonu |
| 5 | build_rag_prompt() kısaltma | prompts.py | Doküman kuralları 6 → 3 madde |
| 6 | Sıcaklık düzeltme | engine.py | Bilgi/Öneri 0.7 → 0.4, Sohbet/Beyin Fırtınası 0.7 kalır |
| 7 | max_tokens artırma | engine.py | Analiz/Rapor 1024 → 2048 |
| 8 | Kullanıcı kimliği dedup | engine.py | 3 tekrar → 1 satır |
| 9 | Multi-perspective kaldırma | engine.py | Ekstra LLM çağrısı devre dışı (CoT zaten kapsıyor) |
| 10 | Post-processing temizleme | engine.py | 12 bölüm cevaptan kaldırıldı → JSON metadata'da |

**Deploy:** Server 1 ✅ + Server 2 ✅ — Her iki sunucu `v5.9.0 healthy`

**Sonuç:** İŞE YARADI ✅ — Yanıtlar daha temiz, odaklı ve hızlı.

---

## 🚨 GELİŞTİRİLMESİ GEREKEN ALANLAR (v5.9.0 sonrası)

> **ÖNEMLİ:** v5.9.0 prompt optimizasyonu işe yaradı. Aşağıdaki konular bir sonraki iterasyonda ele alınmalı.

### 1. Prompt Kalitesi — Devam Eden İyileştirmeler
- **CoT şablonları hâlâ uzun**: REASONING_TEMPLATES (deductive, comparative, causal, risk_based, financial) her biri ~150 token. Bunlar da kısaltılabilir.
- **ACTION_PLAN_TEMPLATE ve MULTI_PERSPECTIVE_TEMPLATE**: build_prompt()'tan kaldırıldı ama dosyada duruyor. Kullanılmıyor → temizlenebilir ya da başka yolla entegre edilebilir.
- **STRUCTURED_OUTPUT_PROMPT**: build_prompt()'tan kaldırıldı. JSON çıktı ihtiyacı varsa farklı bir mekanizma gerekir.

### 2. Post-Processing — Akıllı Seçim
- 12 bölüm cevaptan kaldırıldı ama veriler JSON'da. Frontend'de bu verileri gösterecek UI bileşenleri YOK.
- **Yapılması gereken:** Frontend'de `reflection`, `ranking`, `kpi_impact`, `executive_digest` gibi JSON verilerini gösteren akordiyon/tab bileşenleri ekle.
- **Alternatif:** Kullanıcı ayarı ile "detaylı cevap" / "kısa cevap" seçimi.

### 3. Router Geliştirme
- `router.py` hâlâ regex tabanlı. Bazen yanlış intent sınıflandırması yapıyor.
- `KNOWLEDGE_PATTERNS` çok geniş → `\bver(...)?\b` neredeyse her cümleyi yakalar.
- **Yapılması gereken:** Regex pattern'lerini daralt veya hibrit (regex + embedding similarity) yaklaşıma geç.

### 4. Reflection & Self-Correction Token Maliyeti
- Düşük güvenli yanıtlarda (<%60) self-correction loop 2 tur daha LLM çağırıyor.
- Her tur ~10-30 sn ve ~1K token. 8K context'te bu çok fazla.
- **Yapılması gereken:** Self-correction'ı sadece Analiz/Rapor modlarında tut, token bütçesinin %20'sinden fazlasını harcamasın.

### 5. Context Window Optimizasyonu
- 8K context iyi TPS sağlıyor (~7.7) ama uzun RAG belgelerinde yetersiz kalabilir.
- **Yapılması gereken:** RAG belge truncation'ı daha akıllı hale getir (önemli bölümleri koru, gürültüyü at). Belki 12K'ya çıkarıp TPS etkisini test et.

---

**Amaç:** Otonom AI değerlendirmesi sonucu tespit edilen 2 boşluğu kapatmak.

**Arka plan:**
- 5 aday modül değerlendirildi (Internal Critic, Causal Graph, Uncertainty, Risk Gatekeeper, Retraining Scheduler)
- 3'ü zaten %85-90 örtüşüyordu — sadece 2 gerçek boşluk tespit edildi:
  - **Decision Risk Gatekeeper** — Sistemde hiçbir "engelle/eskalas et" mekanizması yoktu
  - **Uncertainty Quantification** — Birden fazla kaynaktan ensemble güven skoru eksikti

**Yapılan işler:**

| # | İş | Dosya | Detay |
|---|---|---|---|
| 1 | Decision Gatekeeper | decision_gatekeeper.py (~635 satır) | 12 sınıf, PASS/WARN/BLOCK/ESCALATE, eskalasyon kuyruğu, risk sinyal toplama |
| 2 | Uncertainty Quantification | uncertainty_quantification.py (~404 satır) | 9 sınıf, epistemik-aleatoric ayrımı, 5 kaynak ensemble, hata payı hesaplama |
| 3 | Engine entegrasyonu | engine.py | Step 6h (Uncertainty) + 6i (Gate) pipeline tetikleme |
| 4 | Admin API | admin.py | 13 yeni endpoint (gate:7 + uncertainty:5 + resolve-escalation:1) |
| 5 | Dashboard | Dashboard.tsx | 2 yeni modül kartı: Karar Risk Kapısı, Belirsizlik Ölçümleme |
| 6 | Versiyon | config.py + constants.ts | 5.0.0 → 5.1.0 |

**Deploy:** Server 1 ✅ + Server 2 ✅ — Her iki sunucu `v5.1.0 healthy`

**AI Modül Sayısı:** 35 → 37

---

### Tarih: 16 Şubat 2026 — v5.0.0: Strategic Planner + Executive Intelligence + Knowledge Graph

**Amaç:** Enterprise Audit (63/100) sonrasında güvenlik iyileştirmesi + MiniCPM-o 2.6 omni-modal AI entegrasyonu.

**Enterprise Güvenlik Düzeltmeleri (Audit 63→78+):**

| # | İyileştirme | Dosya | Detay |
|---|---|---|---|
| 1 | Credentials Externalization | deploy_now.py, .env.deploy | Hardcoded şifreler → `.env.deploy` (gitignored) |
| 2 | Service Hardening | companyai-backend.service | root→companyai user, NoNewPrivileges, ProtectSystem=strict |
| 3 | DoS Koruması | gunicorn.conf.py | Timeout 960s → 180s |
| 4 | CORS Sıkılaştırma | main.py | Wildcard → spesifik HTTP yöntemleri ve headerlar |
| 5 | Base64 Injection Algılama | prompts.py | Prompt injection'da base64 saldırı tespiti (+3 pattern) |
| 6 | Hesap Kilitleme | auth.py, models.py | 5 başarısız giriş → 15dk hesap kilidi |
| 7 | Şifre Değişim Zorlama | auth.py, main.py | Admin ilk girişte must_change_password |
| 8 | Audit Hash Chain | audit.py, models.py | SHA-256 hash chain — tamper-proof denetim kaydı |

**MiniCPM-o 2.6 Omni-Modal Entegrasyonu:**

| # | İyileştirme | Dosya | Detay |
|---|---|---|---|
| 1 | Omni Model Config | config.py | OMNI_MODEL = "minicpm-o" |
| 2 | Audio/Video Sabitler | constants.py | 9 ses + 5 video format, 25MB/100MB limit, 120s max |
| 3 | Akıllı Model Routing | client.py | use_omni: audio/video→minicpm-o, resim→minicpm-v, metin→qwen2.5 |
| 4 | Ses/Video İşleme | multimodal.py | cv2 frame sampling (8 kare), base64 audio, 3 yeni endpoint |
| 5 | Frontend Omni UI | Ask.tsx, api.ts | Music/Film ikonları, mor/mavi önizleme, dosya tipi algılama |
| 6 | RAG Chunk Tutarlılık | constants.py | CHUNK_SIZE 1000→2000, OVERLAP 200→300 |

**Deploy:** Server 1 ✅ (SyntaxError fix + DB migration sonrası başarılı)

**Notlar:**
- `models.py` SyntaxError: aynı satırda iki statement birleşmişti → düzeltildi
- DB migration: `must_change_password`, `password_changed_at`, `failed_login_attempts`, `locked_until`, `hash_chain` kolonları
- deploy_now.py: key-first auth yaklaşıma geçirildi (şifre gerektirmez)
- Server 2 deploy: `server2_key` private key eksik, ayrıca yapılmalı
- `opencv-python-headless` bağımlılığı eklendi

---

### Tarih: 15 Şubat 2026 — v4.4.0: 20 AI İyileştirmesi (OCR, Chart, Rapor)

**Amaç:** AI Yetkinlik Değerlendirmesi sonucu (73.5 → 94.5/100) — 20 iyileştirme 4 öncelik seviyesinde.

**P0 — Kritik (6 iyileştirme):**
- Sayısal Doğrulama Motoru — LLM uydurma/uyumsuz rakam tespiti ve uyarısı
- Türkçe Cross-Encoder — `mmarco-mMiniLMv2-L12-H384-v1` çok dilli re-ranking
- Few-Shot Örnekler — 6 departmana özel 10 soru-cevap prompts.py'ye enjekte
- OCR Motor — EasyOCR (TR+EN), etiket/fatura/tablo yapısal parse, PDF OCR
- Vision Model Yükseltme — `llava` → `minicpm-v` (yüksek çözünürlük, Türkçe)
- Kaynak Atıf Doğrulama — LLM atıflarını RAG ile çapraz kontrol

**P1 — Yüksek (5 iyileştirme):**
- ChromaDB 3 Koleksiyon — `company_documents`, `learned_knowledge`, `web_cache`
- Öğrenme Kalite Filtresi — `score_knowledge_quality()`, min eşik 0.35
- Chunk Stratejisi — 1000→2000, overlap 200→300
- Chart Motoru — `chart_engine.py`: bar, line, pie, grouped_bar, heatmap (Base64 PNG)
- Rapor Şablon Sistemi — `report_templates.py`: 5 departman, LLM prompt builder

**P2/P3 — Orta/İleri (9 iyileştirme):**
- Prompt Sıkıştırma, Excel çoklu sayfa, PDF tablo çıkarma, Retrieval metrikleri
- Metadata filtreleme, Rate limiter, Learning dashboard, Whisper STT, Test altyapısı

**Yeni dosyalar:** ocr_engine.py, chart_engine.py, report_templates.py, whisper_stt.py, tests/test_core.py

---

### Tarih: 15 Şubat 2026 — Enterprise Audit (5-Perspektif Değerlendirme)

**Sonuçlar:** CTO 62, AI Researcher 71, CFO 78, CISO 51, COO 55 = **Genel: 63/100**

**Kritik bulgular:**
- Hardcoded credentials (deploy_now.py)
- No HA — tek sunucu, SPOF
- %0.76 test kapsama oranı (1134 satır / ~30K+ Python)
- 960s gunicorn timeout → DoS vektörü
- Root user ile çalışan servis
- CORS wildcard
- Prompt injection'da base64 saldırı algılanmıyor
- Hesap kilitleme/denetim hash chain yok

---

### Tarih: 14 Şubat 2026 — v4.3.0: 15 AI Yetkinlik İyileştirmesi

**Amaç:** AI puanını 73.5 → 97/100'e çıkarmak. 15 iyileştirme 7 eksende uygulandı.

**Yapılan işler (15 improvement, 10 dosya):**

| # | İyileştirme | Dosya | Detay |
|---|---|---|---|
| 1 | CoT Prompt Templates | prompts.py | 5 düşünce zinciri şablonu (tümdengelim, karşılaştırma, nedensel, risk, finansal) |
| 2 | Reasoning Steps Doldurma | reasoning.py | Boş interpret/synthesize/analyze_question → LLM çağrıları |
| 3 | Token Budget Manager | token_budget.py (YENİ) | 32K context window bütçeleme, bölüm bazlı kırpma |
| 4 | LLM-Based Reflection | engine.py | 60-75% güven → REFLECTION_PROMPT ile LLM self-eval |
| 5 | LLM-Based Router | router.py | Regex yerine LLM intent classification + 50-entry cache |
| 6 | Active Learning | engine.py | 40-60% güven → kullanıcıdan doğrulama isteği |
| 7 | Action Plan Template | prompts.py | 5W1H + ROI formatında aksiyon planı |
| 8 | Ollama Function Calling | client.py + tool_registry.py | tools param + to_ollama_tools_schema() |
| 9 | Cross-Encoder Rerank | vector_store.py | ms-marco-MiniLM-L-6-v2, %60 CE + %40 hybrid |
| 10 | Step Data Chaining | reasoning.py | accumulated_context ile adımlar arası veri aktarımı |
| 11 | Multi-Perspective | engine.py | CFO/COO/CRO perspektiflerinden 3 yönlü değerlendirme |
| 12 | ROI Recommendations | engine.py | Yatırım sorularında Monte Carlo simülasyonu |
| 13 | Cross-Module Orchestrator | engine.py | asyncio.gather ile Executive Health + Bottleneck + Graph paralel |
| 14 | Cross-Session Context | persistent_memory.py | Son 3 oturum konularını LLM bağlamına enjekte |
| 15 | Trend Detection | engine.py | Aynı KPI tekrar sorgulanınca trend tespiti |

**Deploy:** Server 1 (192.168.0.12) ✅ + Server 2 (88.246.13.23) ✅

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
- `frontend/src/pages/Documents.tsx` (~1334 satır) — Doküman yönetimi + upload progress UI
- `frontend/src/services/api.ts` — Backend API servisleri

## Bağımlılıklar (önemli eklemeler)
- `scipy>=1.10.0` — İstatistiksel testler (t-test, ANOVA, Shapiro-Wilk, Grubbs) — v3.5.1
- `statsmodels>=0.14.0` — ARIMA, SARIMA, Holt-Winters, SES — v2.7.0+
- `openpyxl` — Excel okuma/yazma
- `easyocr>=1.7.2` — OCR (görüntü tabanlı PDF desteği) — v5.9.2
- `paramiko` — SSH/SCP deploy işlemleri (password fallback)

---

### Tarih: 17 Şubat 2026 — v5.9.1: 500 Hatası Düzeltmeleri & Uzun Yanıt Optimizasyonu

**Amaç:** Server 2'de oluşan 500 hataları ve uzun yanıtla zaman aşımı sorunlarını gidermek.

**Yapılan Değişiklikler:**
- `engine.py`: Timeout/retry mekanizması iyileştirildi
- `client.py`: Connection pooling ve hata yönetimi güçlendirildi
- Nginx (S2): `proxy_read_timeout 900s` artırıldı
- Context window optimizasyonu (TPS iyileştirme)

**Deploy:** Server 1 ✅ + Server 2 ✅ — `v5.9.1 healthy`

---

### Tarih: 17 Şubat 2026 — v5.9.2: RAG/PDF OCR Fix + Sync Düzeltme

**Amaç:** Görüntü tabanlı PDF'lerin RAG'a boş kaydedilmesi ve ChromaDB senkronizasyon sorunlarını gidermek.

**Problem 1 — Görüntü PDF:**
- Kullanıcı image-based PDF yükledi → ChromaDB'ye boş metadata ile kaydedildi
- `documents.py` dosyasında easyocr desteği eklendi (image PDF → OCR → metin çıkarma)
- Sunucularda easyocr v1.7.2 ve PyMuPDF v1.27.1 zaten mevcut
- Eski boş kayıtlar ChromaDB'den temizlendi

**Problem 2 — Sync:**
- S2→S1 yönünde sync yapılıyordu ama S2, S1'in lokal IP'sine erişemiyordu
- **Çözüm:** Sync yönü tersine çevrildi → S1, S2'den çeker (her 15 dk cron)
- Embedding boyut uyuşmazlığı (384 vs 768) re-embed ile çözüldü
- İlk sync başarılı: 247 kayıt her iki sunucuda eşit

**Sync Dosyaları:**
- Server 2: `/opt/companyai/sync_chromadb_export.py` (export)
- Server 1: `/opt/companyai/sync_chromadb.py` (import)
- Cron (S1): `*/15 * * * * /usr/bin/python3 /opt/companyai/sync_chromadb.py`

**Deploy:** Server 1 ✅ + Server 2 ✅ — `v5.9.2 healthy`

---

### Tarih: 17 Şubat 2026 — v5.10.0: Upload Progress UI + Nginx Fix + Hata Bildirimleri

**Amaç:** Dosya yükleme deneyimini iyileştirmek — gerçek zamanlı ilerleme, animasyonlu UI, hata yönetimi.

**Problem 1 — Upload Feedback Eksikliği:**
- Kullanıcı dosya yüklerken sadece "Yükleniyor..." spinner'ı görüyordu, yüzde yoktu
- **Çözüm:** Animasyonlu shimmer/gradient ilerleme çubuğu
  - **Yükleme fazı:** Mavi gradient + shimmer animasyonu, `%XX` gösterimi
  - **İşleme fazı:** Amber pulsing "Öğreniyor..." + Brain ikonu
  - **Tamamlandı:** Yeşil checkmark "Tamamlandı!"
  - Ana buton tam genişlikte ilerleme çubuğuna dönüşür

**Değiştirilen Dosyalar:**

| Dosya | Değişiklik |
|-------|-----------|
| `frontend/src/services/api.ts` | `uploadDocument()` → `onUploadProgress` callback + `timeout: 600000` (10 dk) |
| `frontend/src/pages/Documents.tsx` | `uploadPercent`, `uploadPhase`, `uploadMessage` state'leri, 2 fazlı UI, hata bildirimleri |
| `frontend/tailwind.config.js` | `uploadShimmer` keyframe animasyonu (translateX -100% → 100%, 1.5s) |
| `app/config.py` | `APP_VERSION = "5.10.0"` |
| `frontend/src/constants.ts` | `APP_VERSION = '5.10.0'` |

**Problem 2 — 233MB PDF Sessiz Başarısızlık:**
- 233MB PDF upload ettikten sonra ne başarı ne hata mesajı gösteriliyordu
- **Kök neden:** Server 2 Nginx `client_max_body_size 100M` → 244MB dosya 413 ile reddediliyordu
- **Çözüm 1:** Nginx body size limit S2'de 100M → 500M artırıldı
- **Çözüm 2:** Frontend kapsamlı hata yönetimi eklendi:
  - 413: "Dosya çok büyük (X MB). Maksimum 500 MB."
  - Timeout/408: "Zaman aşımı — dosya çok büyük veya bağlantı yavaş"
  - 500: "Sunucu hatası — dosya işlenirken bir sorun oluştu"
  - Network Error: "Bağlantı hatası — ağ bağlantınızı kontrol edin"
  - Başarı: "X dosya başarıyla yüklendi ve öğrenildi!" (yeşil bildirim, 8 sn auto-dismiss)

**Sunucu Konfigürasyon:**
- Server 1: `client_max_body_size 500M` (zaten vardı)
- Server 2: `client_max_body_size 100M → 500M` (güncellendi)
- Server 2: `proxy_read_timeout 900s` (zaten vardı)

**Deploy:** Server 1 ✅ + Server 2 ✅ — `v5.10.0 healthy`

---

## Sunucu Yapılandırma Özeti (v5.10.0)

### Server 1 (192.168.0.12)
- CPU-only, Intel Xeon 4316, 64GB RAM
- Ollama qwen2.5:72b (CPU inference ~2 tok/s)
- Nginx: `client_max_body_size 500M`
- ChromaDB sync: Her 15 dk S2'den çeker

### Server 2 (88.246.13.23:2013)
- 2× RTX 3090, 48GB VRAM
- Ollama qwen2.5:72b (GPU inference, hızlı)
- Nginx: `client_max_body_size 500M`, `proxy_read_timeout 900s`
- ChromaDB export: `/opt/companyai/sync_chromadb_export.py`
- SSL: Self-signed sertifika (RSA 2048, 10 yıl: 2026–2036)
  - Sertifika: `/etc/nginx/ssl/server.crt` + `/etc/nginx/ssl/server.key`
  - CN/SAN: `88.246.13.23`
  - Nginx: `listen 443 ssl` + `listen 80` (ikisi de aktif)
  - Dış erişim: `https://88.246.13.23:2015` (port yönlendirme: 2015 → 443)

---

## 🗄️ PostgreSQL DB Şeması (v5.10.0)

**DB:** PostgreSQL 14.20, port 5433, user `companyai`, db `companyai`
**ORM:** SQLAlchemy async (asyncpg) — Model dosyası: `app/db/models.py`

### Tablolar (8 tablo)
| Tablo | Satır Sayısı (yaklaşık) | Açıklama |
|-------|------------------------|----------|
| `users` | 13 kolon | Kullanıcı yönetimi + RBAC + hesap kilitleme |
| `queries` | 10 kolon | AI sorgu geçmişi + performans metrikleri |
| `audit_logs` | 9 kolon | SHA-256 hash chain tamper-proof denetim |
| `system_settings` | 6 kolon | Anahtar-değer sistem ayarları |
| `chat_sessions` | 6 kolon | Kalıcı sohbet oturumları |
| `conversation_memory` | 8 kolon | Kalıcı konuşma hafızası |
| `user_preferences` | 7 kolon | AI'ın hatırlaması gereken kullanıcı tercihleri |
| `company_culture` | 9 kolon | Şirket çalışma kalıpları (otomatik çıkarım) |
| `xai_records` | 17 kolon | XAI açıklanabilirlik verileri + kullanıcı rating |

### İlişkiler
```
users ──1:N──→ queries
users ──1:N──→ audit_logs (hash_chain tamper-proof)
users ──1:N──→ chat_sessions ──1:N──→ conversation_memory
users ──1:N──→ user_preferences
users ──1:N──→ company_culture (source_user_id)
users ──1:1──→ system_settings (updated_by)
```

