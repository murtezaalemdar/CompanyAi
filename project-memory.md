# 🧠 Proje Hafızası

## Amaç
Kurumsal AI Asistanı — tamamen lokal, öğrenen, çok departmanlı yapay zeka sistemi.
Tekstil sektörü odaklı, her bölümün kendi bilgi tabanı ve yetkilendirmesi var.

## Sunucu
- **IP:** 192.168.0.12, Ubuntu 22.04, Intel Xeon 4316 16-core, **64GB RAM**, no GPU
- **LLM:** Ollama qwen2.5:72b (48GB in RAM, 0 swap), ~2 tok/s CPU-only
- **Versiyon:** v2.6.0

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



