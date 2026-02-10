# 🧠 Proje Hafızası

## Amaç
Kurumsal AI Asistanı — tamamen lokal, öğrenen, çok departmanlı yapay zeka sistemi.
Tekstil sektörü odaklı, her bölümün kendi bilgi tabanı ve yetkilendirmesi var.

## Önemli Kararlar
- Tamamen lokal LLM (Ollama + Mistral 7B) — GPU yok, CPU-only (Xeon Silver 4316)
- PostgreSQL kalıcı hafıza (sohbet geçmişi, tercihler, kültür)
- ChromaDB vektör hafıza (RAG + semantik arama)
- SerpAPI ile web arama (250 ücretsiz/ay, kredi kartı yok)
- rich_data sistemi: list yapısı — birden fazla kart (weather, images, export)
- Export formatları: Excel, PDF, PowerPoint, Word, CSV — otomatik + manuel
- Frontend deploy: Nginx `/var/www/html/` — `deploy_now.py` ile otomatik
- JWT Auth + RBAC (Admin/Manager/User) + departman bazlı erişim

## 🏷️ VERSİYON KURALI (HER DEPLOY'İN ÖNCESİNDE ZORUNLU!)
- **Her deploy öncesi `APP_VERSION` artırılmalı!**
- Backend: `app/config.py` → `APP_VERSION`
- Frontend: `frontend/src/constants.ts` → `APP_VERSION`
- İki dosyadaki versiyon her zaman AYNI olmalı
- Format: Semantic Versioning (MAJOR.MINOR.PATCH)

## Notlar
- Sunucu: 192.168.0.12, 32GB RAM, 16-core Xeon Silver 4316, NO GPU
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
ad5a827 feat: Rapor export - Excel, PDF, PowerPoint, Word, CSV indirme
c478097 feat: Gorsel arama sonuclari karti + rich_data liste destegi
5f9dbf4 fix: deploy_now.py artik frontend build+deploy yapiyor
e213d69 feat: Hava durumu gorsel kart (rich data) - Google tarzi
4eafe02 fix: LLM artik web arama sonuclarini kullaniyor
39bfbbf feat: SerpAPI entegrasyonu Google arama kredi kartsiz
0ff27ef feat: Google Custom Search API entegrasyonu (Phase 20)
```

Copilot:
Bu dosya proje için kalıcı hafızadır.



