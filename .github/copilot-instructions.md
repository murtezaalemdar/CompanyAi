# Copilot Proje Talimatları — CompanyAi

## Versiyon Kuralı (ÖNEMLİ)
Deploy öncesi `app/config.py` ve `frontend/src/constants.ts` dosyalarındaki `APP_VERSION` değerini eşleşecek şekilde artır.

Format: `MAJOR.MINOR.PATCH` — her segment 2 haneli (ör. 6.01.00)

| Segment | Ne zaman artar? | Açıklama | Örnek |
|---------|----------------|------------|--------|
| **MAJOR** (baş) | Major değişiklik | Mimari değişiklik, büyük yapısal dönüşüm, geriye uyumsuz değişiklik | 6.xx.xx → 7.00.00 |
| **MINOR** (orta) | Önemli değişiklik | Yeni özellik, önemli iyileştirme, görünür değişiklik | 6.01.xx → 6.02.00 |
| **PATCH** (son) | Küçük işlem | Bugfix, ufak düzeltme, küçük iyileştirme | 6.01.00 → 6.01.01 |

> **Not:** MINOR artınca PATCH sıfırlanır. MAJOR artınca hem MINOR hem PATCH sıfırlanır.

## Deploy
- Komut: `cd CompanyAi; $env:PYTHONIOENCODING='utf-8'; python deploy_now.py`
- SSH: `ssh -i keys/companyai_key root@192.168.0.12`
- Sunucu: backend → `/opt/companyai/`, frontend → `/var/www/html/`
- `deploy_now.py` → `BACKEND_FILES` listesi statik — yeni dosya eklendiyse güncelle
