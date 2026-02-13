# Active Context

## Current Goals

## Güncel Durum — v3.9.2 (13 Şubat 2026)

### Tamamlanan İşler
- v3.9.0 — Insight Engine (7 otomatik içgörü türü) + Paralel Agent Pipeline + Tekstil bilgi tabanı 500+ terim + CEO Dashboard (RadarChart + İçgörüler + Darboğaz)
- v3.9.1 — Kod Kopyalama Fix: MessageContent.tsx bileşeni (kod bloğu ayrıştırma + kopyala butonu)
- v3.9.2 — Seçip Sor: ChatGPT tarzı metin seçip "CompanyAi'ye sor" popup + alıntı chip + submit entegrasyonu

### Aktif Versiyon
- Backend: v3.9.2 ✅ (192.168.0.12)
- Frontend: v3.9.2 ✅
- 24+ AI modülü aktif

### Sonraki Adımlar
- ChromaDB boyut uyumsuzluğu düzeltilmeli (384-dim → 768-dim)
- GPU eklendiğinde LLM timeout 900s → 120s'ye düşürülebilir
- Seçip sor özelliği test ve UX iyileştirme

## ⚠️ DEPLOY KURALI

> **HER DEPLOY ÖNCESI VERSİYON NUMARASI ARTIRILMALIDIR!**
> - `app/config.py` → `APP_VERSION`
> - `frontend/src/constants.ts` → `APP_VERSION`
> - Semantic Versioning: PATCH (bug fix), MINOR (yeni özellik), MAJOR (büyük değişiklik)