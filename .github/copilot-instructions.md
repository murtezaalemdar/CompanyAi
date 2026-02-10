# Copilot Proje Talimatları — CompanyAi

## 🏷️ VERSİYON KURALI — HER DEPLOY ÖNCESİNDE ZORUNLU!

> ⚠️ **ASLA UNUTMA:** Deploy yapılacaksa versiyon numarası artırılmalıdır!
>
> Bu kural her deploy, her sunucu güncellemesi, her `deploy_now.py` çalıştırması,
> her `scp` ile dosya gönderimi, her frontend build+upload için geçerlidir.

### Versiyon Dosyaları (her ikisi de aynı değeri taşımalı):

| Dosya | Sabit | Açıklama |
|-------|-------|----------|
| `app/config.py` | `APP_VERSION = "X.Y.Z"` | Backend tek kaynak |
| `frontend/src/constants.ts` | `APP_VERSION = 'X.Y.Z'` | Frontend tek kaynak |

### Versiyon Artırma Kuralı (Semantic Versioning):

- **PATCH** (+0.0.1): Bug fix, küçük düzeltme, stil değişikliği
- **MINOR** (+0.1.0): Yeni özellik, yeni sayfa, yeni endpoint
- **MAJOR** (+1.0.0): Büyük mimari değişiklik, API kırılması

### Deploy Öncesi Checklist:

1. ✅ `app/config.py` → `APP_VERSION` güncelle
2. ✅ `frontend/src/constants.ts` → `APP_VERSION` güncelle (aynı değer!)
3. ✅ Frontend build yap (`npm run build`)
4. ✅ Deploy et

### Versiyon Gösterim Yerleri:

- Login sayfası (alt kısım, badge)
- Sidebar (nav altı, badge)
- Mobil menü (alt kısım, badge)
- `/api/health` endpoint (`"version": "X.Y.Z"`)
- `/` root endpoint
- Uygulama başlangıç logu

## 📋 Diğer Deploy Kuralları

- `deploy_now.py` içindeki `BACKEND_FILES` listesi statik — yeni dosya eklendiyse güncelle!
- Deploy komutu: `cd CompanyAi; $env:PYTHONIOENCODING='utf-8'; python deploy_now.py`
- SSH: `ssh -i keys/companyai_key root@192.168.0.12`
- Sunucu backend: `/opt/companyai/`, frontend: `/var/www/html/`
