# 🏢 Kurumsal Yapay Zeka Asistanı

> **Local LLM (Mistral) + Öğrenen Vektör Hafıza + JWT Auth**

Kurumsal kullanım için tasarlanmış, tamamen lokal çalışan yapay zeka asistanı.

## ✨ Özellikler

- 🔐 **JWT Authentication** - Güvenli kullanıcı kimlik doğrulama
- 👥 **RBAC** - Rol tabanlı erişim kontrolü (Admin, Manager, User)
- 🤖 **Mistral LLM** - Ollama ile lokal dil modeli
- 💾 **PostgreSQL** - Async veritabanı desteği
- 📊 **Admin Dashboard** - Kullanıcı ve sorgu yönetimi
- 🧠 **Öğrenen Hafıza** - Vektör tabanlı sorgu hafızası
- 🏭 **Akıllı Router** - Departman bazlı yönlendirme

## 🚀 Hızlı Başlangıç

### 1. Gereksinimleri Yükle

```bash
# Python 3.10+ gerekli
pip install -r requirements.txt
```

### 2. Ortam Değişkenlerini Ayarla

```bash
cp .env.example .env
# .env dosyasını düzenleyin
```

### 3. Ollama + Mistral Kur

```bash
# Ollama yükle
curl -fsSL https://ollama.com/install.sh | sh

# Mistral modelini indir
ollama pull mistral
```

### 4. Uygulamayı Başlat

```bash
# Development
uvicorn app.main:app --reload

# veya
python -m app.main
```

### 5. API Dokümantasyonu

```
http://localhost:8000/docs
```

## 🐳 Docker ile Çalıştırma

```bash
# Tüm servisleri başlat (API, PostgreSQL, Redis, Nginx)
docker compose -f docker/docker-compose.yml up -d
```

## 📁 Proje Yapısı

```
CompanyAi/
├── app/
│   ├── api/routes/          # API endpoint'leri
│   ├── auth/                # JWT & RBAC
│   ├── core/                # İşlem motoru
│   ├── db/                  # Veritabanı modelleri
│   ├── llm/                 # Mistral client
│   ├── memory/              # Vektör hafıza
│   ├── router/              # Akıllı yönlendirci
│   └── main.py              # FastAPI app
├── docker/                  # Docker yapılandırması
├── frontend/                # React dashboard (yakında)
└── tests/                   # Testler
```

## 🔗 API Endpoints

| Endpoint | Method | Açıklama |
|----------|--------|----------|
| `/api/auth/register` | POST | Kullanıcı kaydı |
| `/api/auth/login` | POST | Giriş & token al |
| `/api/auth/me` | GET | Mevcut kullanıcı |
| `/api/ask` | POST | AI'a soru sor |
| `/api/health` | GET | Sağlık kontrolü |
| `/api/llm/status` | GET | LLM durumu |
| `/api/admin/users` | GET | Kullanıcı listesi |
| `/api/admin/stats/dashboard` | GET | Dashboard istatistikleri |

## 🛠️ Teknoloji Stack

- **Backend:** FastAPI, SQLAlchemy, Pydantic
- **LLM:** Ollama + Mistral
- **Database:** PostgreSQL
- **Cache:** Redis
- **Auth:** JWT + OAuth2
- **Deploy:** Docker, Nginx

## 📄 Lisans

MIT License