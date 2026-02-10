# Şirket AI Asistanı - Günlük Notlar

## 📅 Tarih: 11 Şubat 2026 (Güncelleme 5)

### 🧠 Qwen2.5:72B Model Yükseltmesi & 64GB RAM

**Sunucu RAM:** 32GB → **64GB** yükseltildi.
**Model:** `qwen2.5:72b` (47GB) — tamamen RAM'de çalışıyor, swap kullanımı 0.
**Performans:** CPU-only (Intel Xeon 4316, 16-core), ~2 token/s, pattern yanıtlar <0.1s.

| Parametre | Eski | Yeni | Neden |
|-----------|------|------|-------|
| `max_tokens` | 2048 | **512** | CPU'da gereksiz uzun yanıt üretimi engellemek (100s → ~25-30s) |
| `num_thread` | default | **16** | 16 fiziksel çekirdek tam kullanım |
| `swappiness` | 60 | **10** | Model'in swap'a düşmesini engellemek |
| `timeout` | 120s | **900s** | CPU inference uzun sürdüğü için |

**Değişen dosyalar:**
- `app/llm/client.py` — max_tokens=512, num_thread=16, timeout=900
- `app/core/engine.py` — explicit max_tokens=512
- `app/config.py` — LLM_MODEL="qwen2.5:72b"
- `companyai-backend.service` — Environment=LLM_MODEL=qwen2.5:72b
- **Commit:** `7cb1148`

### 🐛 "ismimle hitap et" Pattern Bug Düzeltmesi

**Sorun:** Kullanıcı "bana ismimle hitap edersen sevinirim" deyince sistem "Murteza, memnun oldum Mehmet!" diye cevap veriyordu.
**Kök neden:**
1. `ismim` kelimesi "ismimle" içinde eşleşiyor → `introduction` kategorisine yönlendiriyordu
2. `random.choice()` placeholder isimlerden "Mehmet"i getiriyordu
**Çözüm:**
1. Regex negative lookahead: `ismim\b(?!le|i|e|den|in)` — Türkçe ekleri geçiriyor
2. "hitap/söyle/seslen/çağır" kelimeleri varsa pattern'i skip et
3. Eğer gerçek isim bulunamazsa `None` dön → LLM'e yönlendir
**Değişen dosya:** `app/llm/chat_examples.py`
**Commit:** `e1bf035`

### 📊 Analiz Sayfası RecursionError Düzeltmesi

**Sorun:** Analiz sayfasında dosya keşfetme "pandas/openpyxl yüklü değil" hatası veriyordu.
**Gerçek hata:** `RecursionError: maximum recursion depth exceeded` in `discover_data(df)`
**Kök neden:** `parse_file_to_dataframe()` içinde `df.attrs['_sheets_data'] = sheets` satırı DataFrame nesnelerini attrs dict'ine koyuyordu. pandas 2.3.x'te `__finalize__` → `deepcopy(other.attrs)` sonsuz döngüye giriyordu.
**Çözüm:**
1. `_sheets_data` attrs'tan kaldırıldı
2. `discover_data()` başında `df.attrs = {}` eklendi (güvenlik katmanı)
3. `xlrd>=2.0.1` kuruldu (.xls desteği için)
**Değişen dosyalar:**
- `app/core/document_analyzer.py`
- `requirements.txt` (xlrd eklendi)
**Commit:** `6a1d0b6`

### 🗄️ Veritabanı Şeması Yedeklendi

DB şeması `docs/db_schema.sql` olarak export edildi (`pg_dump --schema-only`).
**8 tablo:** users, audit_logs, chat_sessions, company_culture, conversation_memory, queries, system_settings, user_preferences
**İlişkiler:** Tüm FK'lar `users(id)` referans alıyor.

### 📈 Sunucu Durum Özeti (11 Şubat 2026)

| Kaynak | Değer |
|--------|-------|
| RAM | 62Gi total, ~47Gi used (model), ~14Gi available |
| Disk | 489GB, 137GB used, 331GB free (%30) |
| Swap | 40GB (8+32), 263MB used (minimal) |
| Ollama modelleri | qwen2.5:72b (47GB), gpt-oss:20b (13GB), llama3.1:8b (5GB), qwen2.5:7b (5GB), mistral (4GB) |
| Servisler | companyai-backend ✅, ollama ✅, nginx ✅, postgresql ✅ |

### ⚠️ Bilinen Sorun — ChromaDB Boyut Uyumsuzluğu

ChromaDB koleksiyonu eski `MiniLM` modelle 384-dim olarak oluşturulmuş, ancak şu an `paraphrase-multilingual-mpnet-base-v2` 768-dim üretiyor. Koleksiyon yeniden oluşturulmalı.

---

## 📅 Tarih: 10 Şubat 2026 (Güncelleme 4)

### ⏱️ LLM Timeout 15 Dakikaya Uzatıldı

**Neden:** Sunucuda GPU yok, Ollama CPU üzerinden inference yapıyor. 120 saniyelik timeout yetersiz kalıyor ve "LLM yanıt süresi aşıldı" hatası veriyor.
**Değişiklik:** `app/llm/client.py` → `self.timeout = 120.0` → `self.timeout = 900.0` (15 dakika)
**Not:** GPU eklendiğinde bu değer tekrar 120 saniyeye düşürülebilir.

### 🔐 "Tüm Hafızayı Temizle" — Admin Şifre Doğrulaması Eklendi

- **Endpoint:** `DELETE /rag/documents` → `POST /rag/documents/clear-all` (body: `{password}`)
- **Modal dialog:** Kırmızı uyarı bandı, "TÜM departmanlardaki TÜM dokümanlar silinecek" uyarısı
- **Şifre doğrulama:** `verify_password()` ile admin şifresi doğrulanıyor
- **Ekleyen (author):** `current_user.email` → `current_user.full_name or current_user.email`
- **Tarih:** `str(datetime.utcnow())` → `datetime.utcnow().isoformat()` (Invalid Date düzeltildi)
- **Frontend formatDate:** Python datetime formatını da destekliyor (boşluk → T normalize)

---

## 📅 Tarih: 10 Şubat 2026 (Güncelleme 3)

### 🔧 CSS İkon/Yazı Üst Üste Binme Düzeltmesi

**Sorun:** Departman dropdown, URL input, Video URL input gibi ikonlu alanlarda ikon ile yazı üst üste biniyordu.
**Kök neden:** `index.css` dosyasındaki `.input` CSS sınıfı `@layer` dışında tanımlıydı. CSS katmanlama kurallarına göre katmansız (unlayered) stiller, `@layer utilities` içindeki Tailwind utility sınıflarını (`pl-10` gibi) her zaman ezer. Bu yüzden `.input`'un `px-4` padding'i daima kazanıyordu ve ikonlar yazının üzerine biniyordu.
**Çözüm:** `.input`, `.glass`, `.card`, `.btn-primary`, `.btn-secondary`, `.gradient-text` sınıfları `@layer components` bloğu içine alındı. Bu sayede `pl-10` gibi utility sınıflar artık component sınıfların padding'ini doğru şekilde override edebiliyor.

| Etkilenen Alan | Durum |
|----------------|-------|
| Departman dropdown (Building2 ikonu) | ✅ Düzeltildi |
| URL input (Globe ikonu) | ✅ Düzeltildi |
| YouTube URL input (Youtube ikonu) | ✅ Düzeltildi |
| Kullanıcı arama (Search ikonu) | ✅ Düzeltildi |
| Doküman filtre dropdown (Filter ikonu) | ✅ Düzeltildi |

**Değişen dosya:** `frontend/src/index.css` — Tüm özel CSS sınıfları `@layer components { }` içine alındı.

---

## 📅 Tarih: 10 Şubat 2026 (Güncelleme 2)

### 🔄 Doküman Yönetimi — Kapsamlı Yeniden Yazım (Phase 5)

**Amaç:** Doküman Yönetimi sayfasını departman bazlı, çok formatlı, URL/video destekli
kapsamlı bir öğrenme platformuna dönüştürmek.

#### Yeni Özellikler

| # | Özellik | Detay | Durum |
|---|---------|-------|-------|
| 1 | **Departman bazlı doküman listesi** | Her departman sadece kendi dokümanlarını görür/siler/ekler. Admin/Manager tümünü görür. | ✅ |
| 2 | **Genişletilmiş format desteği** | 27 format → **65+ format**. RTF, ODT, EPUB, ODS, ODP, e-posta (.eml), görüntü OCR, 20+ programlama dili | ✅ |
| 3 | **Klasör seçme ve alt klasör ağacı** | `webkitdirectory` ile klasör seçimi, iç içe klasör ağacı görünümü (FolderTreeView) | ✅ |
| 4 | **URL/Link öğrenme** | `POST /rag/learn-url` — Web sayfası scraping (httpx + BeautifulSoup), otomatik başlık çekme, ana içerik çıkarma | ✅ |
| 5 | **YouTube video öğrenme** | `POST /rag/learn-video` — Altyazı çekme (youtube-transcript-api), 9 dil desteği, otomatik başlık | ✅ |
| 6 | **Doküman kütüphanesi tablosu** | Tüm dokümanlar: kaynak, tür, departman, ekleyen, tarih, parça sayısı. Tür/departman filtresi | ✅ |
| 7 | **Yetenek durumu (capabilities)** | `GET /rag/capabilities` — URL, YouTube, OCR desteklerinin runtime durumu | ✅ |
| 8 | **4 sekmeli öğrenme arayüzü** | Dosya Yükle / Bilgi Gir / URL Öğren / Video Öğren | ✅ |

#### Yeni/Değişen Backend Endpoint'leri

| Endpoint | Method | Açıklama |
|----------|--------|----------|
| `/rag/learn-url` | POST | Web sayfasından öğren (URL scraping) |
| `/rag/learn-video` | POST | YouTube video altyazısından öğren |
| `/rag/capabilities` | GET | Sistem yetenek durumu |
| `/rag/formats` | GET | Güncellenmiş (65+ format, kategorili) |

#### Yeni Request Modelleri

```python
class LearnFromUrlRequest(BaseModel):
    url: str          # Öğrenilecek web sayfası URL'si
    department: str   # Hedef departman
    title: str?       # Opsiyonel başlık

class LearnFromVideoRequest(BaseModel):
    url: str          # YouTube video URL'si
    department: str   # Hedef departman
    title: str?       # Opsiyonel başlık
    language: str     # Tercih edilen altyazı dili (tr, en, de, fr, ...)
```

#### Yeni Pip Bağımlılıkları

| Paket | Versiyon | Kullanım |
|-------|----------|----------|
| `beautifulsoup4` | 4.14.3 | URL öğrenme (HTML parse) |
| `lxml` | 5.0+ | HTML/XML parser |
| `youtube-transcript-api` | 1.2.4 | YouTube altyazı çekme |
| `striprtf` | 0.0.29 | RTF dosya desteği |
| `python-pptx` | 0.6.21+ | PowerPoint desteği |

#### Genişletilmiş Format Listesi (65+ format)

**Metin:** .txt, .md, .csv, .json, .xml, .html, .htm, .rtf, .rst, .tex, .ini, .cfg, .env, .toml, .properties
**Office:** .pdf, .docx, .doc, .xlsx, .xls, .pptx, .ppt, .odt, .ods, .odp, .epub
**Kod:** .py, .js, .ts, .jsx, .tsx, .java, .cs, .cpp, .c, .h, .hpp, .sql, .yaml, .yml, .go, .rb, .php, .swift, .kt, .scala, .rs, .r, .R, .sh, .bat, .ps1, .dockerfile, .vue, .svelte, .graphql, .gql, .proto
**E-posta:** .eml, .msg
**Görüntü (OCR):** .png, .jpg, .jpeg, .gif, .bmp, .tiff, .tif, .webp
**Log:** .log

#### Değişen Dosyalar

| Dosya | Değişiklik |
|-------|-----------|
| `app/api/routes/documents.py` | URL/Video endpoint'leri, genişletilmiş formatlar, capabilities endpoint |
| `frontend/src/pages/Documents.tsx` | Tamamen yeniden yazıldı (426 satır → ~700 satır) |
| `frontend/src/services/api.ts` | `learnFromUrl`, `learnFromVideo`, `getCapabilities` eklendi |
| `requirements.txt` | beautifulsoup4, youtube-transcript-api, striprtf, python-pptx, lxml |

#### Deploy
- Backend: `python deploy_now.py` → 38 dosya + pip install → servis restart → **active** ✅
- Frontend: `npm run build` + SCP → `/var/www/html/` ✅
- Health: `{"status":"healthy","service":"Kurumsal AI Asistanı"}` ✅
- Yeni paketler doğrulandı: beautifulsoup4 4.14.3, youtube-transcript-api 1.2.4, striprtf 0.0.29 ✅

---

## 📅 Tarih: 10 Şubat 2026

### ✅ Toplu Kod Geliştirme (12 Madde) — Tamamlandı
Önceki analizde tespit edilen **tüm eksiklikler** sistematik olarak giderildi:

| # | İş | Durum |
|---|----|-------|
| 1 | `local_llm.py` ölü kod → OllamaClient wrapper | ✅ |
| 2 | `field_assistant.py` STT/TTS (Whisper + pyttsx3/gTTS) | ✅ |
| 3 | `Dashboard.tsx` mock → gerçek API (query-traffic, system-resources) | ✅ |
| 4 | `AuditLog` entegrasyonu (login, query, admin ops) | ✅ |
| 5 | `SystemSettings` CRUD endpoint'leri (GET/PUT/DELETE) | ✅ |
| 6 | Multimodal vision LLM (LLaVA base64 image) | ✅ |
| 7 | `/memory/stats` auth tekrar aktif | ✅ |
| 8 | RBAC `check_admin()` / `check_admin_or_manager()` tüm admin endpoint'lere uygulandı | ✅ |
| 9 | LLM client DEBUG print → structlog | ✅ |
| 10 | SSE streaming endpoint `/api/ask/stream` | ✅ |
| 11 | `build_analysis_prompt()` engine.py'ye entegre (history varsa kullanılır) | ✅ |
| 12 | `reference.md` tam güncelleme | ✅ |

### 🚀 Deployment — 192.168.0.12
- **SSH Key:** `keys/companyai_key` (Ed25519, yeni oluşturuldu)
- **Key Fingerprint:** `SHA256:avkGBtNyqcbRQxfMZR+0IpS0W3Eb6gMgcbmVc9E9kD0`
- **Sunucuya yüklendi:** `authorized_keys` → key auth doğrulandı ✅
- **Backend:** 38 dosya SCP ile `/opt/companyai/` → `pip install -r requirements.txt` → `systemctl restart companyai-backend` → **active** ✅
- **Frontend:** `npm run build` → `dist/` → `/var/www/html/` → `nginx reload` ✅
- **Health check:** `{"status":"healthy","service":"Kurumsal AI Asistanı"}` ✅
- **Deploy scriptleri:** `deploy_now.py` (backend), `deploy_frontend.py` (frontend, silindi — tekrar oluşturulabilir)

### Yeni/Değişen Dosyalar
- **app/core/audit.py** — YENİ: `log_action()` denetim kaydı yardımcısı
- **app/auth/rbac.py** — Yeniden yazıldı: `check_admin`, `check_admin_or_manager`, `check_any_authenticated`
- **app/voice/field_assistant.py** — Sıfırdan implemente edildi
- **app/api/routes/ask.py** — `/api/ask/stream` SSE endpoint eklendi
- **app/api/routes/admin.py** — query-traffic, system-resources, settings CRUD, audit-logs endpoint'leri
- **app/api/routes/multimodal.py** — Vision LLM (LLaVA) entegrasyonu
- **app/llm/client.py** — Vision model + DEBUG temizliği
- **app/core/engine.py** — `build_analysis_prompt` entegrasyonu
- **frontend/src/pages/Dashboard.tsx** — Gerçek API bağlantısı
- **frontend/src/services/api.ts** — Yeni admin API metodları

---

## 📅 Tarih: 09 Şubat 2026

### 🔄 Yedekleme Kaydı
- **Saat:** 08:39 (Yerel), 05:05 (Sunucu)
- **Dosya:** `backup_20260209_050530.sql.gz`
- **Konum (Local):** `Desktop/Python/CompanyAi/backups/backup_latest.sql.gz`
- **Konum (Sunucu):** `/opt/companyai/backups/`
- **Durum:** Manuel yedekleme başarıyla tamamlandı ve locale indirildi.

### ✅ Tamamlanan İşler (Özet)
1. **Veritabanı Bağlantısı:** `asyncpg` entegrasyonu ile düzeltildi.
2. **Vektör Hafıza:** ChromaDB kuruldu ve API'ye bağlandı (`/api/memory`).
3. **Güvenlik (SSL):** Sunucuda HTTPS aktif edildi. Self-signed sertifika kullanılıyor.
4. **Otomatik Yedek:** Her gece 03:00'te çalışan script kuruldu.
5. **Rol Bazlı Erişim Kontrolü (RBAC):**
    - Navigasyon menüsü rollere göre dinamik olarak filtreleniyor.
    - Sorgu geçmişi ve doküman listesi departman bazlı yetkilendirildi.
6. **Gelişmiş Doküman Yönetimi & Yetki:**
    - 20'den fazla dosya formatı desteği eklendi.
    - Çoklu dosya ve klasör yükleme entegre edildi.
    - `/auth/me` endpoint'ine `department` alanı eklendi.
    - Departman bazlı doküman erişim kontrolü sağlandı.
