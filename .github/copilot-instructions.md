# Copilot Proje Talimatları — CompanyAi

## Versiyon Kuralı
Deploy öncesi `app/config.py` ve `frontend/src/constants.ts` dosyalarındaki `APP_VERSION` değerini eşleşecek şekilde artır. (PATCH=bugfix, MINOR=özellik, MAJOR=kırılma)

## Deploy
- Komut: `cd CompanyAi; $env:PYTHONIOENCODING='utf-8'; python deploy_now.py`
- SSH: `ssh -i keys/companyai_key root@192.168.0.12`
- Sunucu: backend → `/opt/companyai/`, frontend → `/var/www/html/`
- `deploy_now.py` → `BACKEND_FILES` listesi statik — yeni dosya eklendiyse güncelle
