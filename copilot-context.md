# 🤖 Copilot Kalıcı Bağlam — CompanyAi

Bu dosya GitHub Copilot Chat için ana bağlamdır. Kod üretirken bu dosya önceliklidir.

## 🏢 Proje Özeti
- **Proje:** Kurumsal AI Asistanı (tamamen lokal, öğrenen)
- **Backend:** FastAPI + Uvicorn, async SQLAlchemy (asyncpg), structlog
- **LLM:** Ollama + Mistral (`localhost:11434`), vision: LLaVA
- **Vector DB:** ChromaDB + SentenceTransformers (`all-MiniLM-L6-v2`)
- **RAG Embedding:** `paraphrase-multilingual-mpnet-base-v2`
- **DB:** PostgreSQL port 5433, user `companyai`, db `companyai`
- **Auth:** JWT (HS256) + pbkdf2_sha256 + RBAC (Admin/Manager/User)
- **Frontend:** React + TypeScript + Vite + Tailwind CSS + TanStack Query
- **Proje dizini (lokal):** `C:\Users\murteza.KARAKOC\Desktop\Python\CompanyAi`
- **Proje dizini (sunucu):** `/opt/companyai`

## 🌍 Sunucu & SSH
- **IP:** `192.168.0.12`
- **URL:** `https://192.168.0.12`
- **User:** `root` — **Şifre:** `435102`
- **SSH Key:** `keys/companyai_key` (Ed25519)
- **Fingerprint:** `SHA256:avkGBtNyqcbRQxfMZR+0IpS0W3Eb6gMgcbmVc9E9kD0`
- **Bağlantı:** `ssh -i keys/companyai_key root@192.168.0.12`
- **Backend servis:** `systemctl restart companyai-backend`
- **Frontend:** `/var/www/html/` (Nginx)
- **Deploy:** `python deploy_now.py` (backend) / `cd frontend && npm run build` + SCP (frontend)

## 📄 Doküman Yönetimi v2 (Güncel)
- **Desteklenen format:** 65+ dosya formatı (metin, office, kod, e-posta, görüntü OCR)
- **Öğrenme kaynakları:** Dosya yükleme, metin girişi, URL scraping, YouTube altyazı
- **Frontend sekmeleri:** Dosya Yükle / Bilgi Gir / URL Öğren / Video Öğren
- **Klasör desteği:** webkitdirectory ile klasör seçimi + alt klasör ağacı görünümü
- **Doküman kütüphanesi:** Tablo görünümü (kaynak, tür, departman, ekleyen, tarih, parça)
- **Pip bağımlılıkları:** beautifulsoup4, youtube-transcript-api, striprtf, lxml
- **Yeni endpoint'ler:** `/rag/learn-url`, `/rag/learn-video`, `/rag/capabilities`

## Kod Prensipleri
- Clean code
- Okunabilirlik > kısalık
- Fonksiyonlar tek iş yapar
- `any` kullanma (zorunlu değilse)

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



