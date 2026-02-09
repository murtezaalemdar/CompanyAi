# Şirket AI Asistanı - Sunucu Kurulum Notları
**Tarih:** 07 Şubat 2026

## 🚀 Özet
Projenin Ubuntu sunucusuna (`192.168.0.12`) deployment işlemi sırasında yaşanan sorunlar çözülmüş ve sistem kararlı hale getirilmiştir.

### ✅ Yapılan Değişiklikler
1. **Veritabanı (PostgreSQL)**
   - Port **5433** olarak ayarlandı (varsayılan 5432 dolu veya çakışıyordu).
   - `companyai` kullanıcı ve veritabanı 5433 portunda oluşturuldu.
   - `.env` dosyasında `DATABASE_URL` portu `5433` olarak güncellendi.
2. **Backend Servisi**
   - Systemd servisi `/etc/systemd/system/companyai-backend.service` düzeltildi.
   - **Önemli:** `uvicorn` doğrudan çalıştırıldı ve `--loop asyncio` parametresi eklendi (asyncpg uyumluluğu için).
   - `ExecStart=/usr/local/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --loop asyncio`
   - `Type=simple`, `Restart=always` ayarları yapıldı.
3. **Nginx Proxy**
   - `/api` istekleri `http://127.0.0.1:8000` adresine yönlendirildi.
   - Config: `/etc/nginx/sites-available/default`
   - Statik dosyalar: `/var/www/html`
4. **Redis**
   - Kuruldu ve çalışıyor (Port 6379, IPv6 dinliyor ama localhost erişimi var).

---

## 🛠️ Sorun Giderme (Troubleshooting)

### 1. Servis Başlamazsa
```bash
# Servis durumunu kontrol et
systemctl status companyai-backend

# Hata loglarını canlı izle
journalctl -u companyai-backend -f
```

### 2. Veritabanı Bağlantı Hatası
Eğer veritabanına bağlanılamıyorsa, 5433 portunu ve servisi kontrol edin:
```bash
# Port dinleniyor mu?
netstat -tuln | grep 5433

# PSQL ile manuel giriş testi
psql -h localhost -p 5433 -U companyai -d companyai
```

### 3. Nginx 502 Bad Gateway
Backend kapalıysa veya yanıt vermiyorsa bu hatayı alırsınız.
```bash
# Backend portunu kontrol et
curl -v http://localhost:8000/api/health

# Nginx loglarını incele
tail -f /var/log/nginx/error.log
```

### 4. Kod Güncelleme (Deploy)
Yeni kodları yüklemek için:
1. `deploy_remote.py` script'ini çalıştırın (kodları günceller).
2. Sunucuda servisi yeniden başlatın: `systemctl restart companyai-backend`.

---

## 📂 Dosya Konumları
| Bileşen | Konum |
|---------|-------|
| Proje Kodu | `/opt/companyai` |
| .env Dosyası | `/opt/companyai/.env` |
| Frontend Build | `/var/www/html` |
| Backend Logları | `journalctl -u companyai-backend` |
| Nginx Config | `/etc/nginx/sites-available/default` |
