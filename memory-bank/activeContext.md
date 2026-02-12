# Active Context

## Current Goals

- ## Güncel Durum — v3.3.0 (12 Şubat 2026)
- ### Tamamlanan İşler
- - v3.3.0 deploy edildi — ARIMA/SARIMA Forecast + Gelişmiş Dashboard
- - ARIMA(3,1,0) otomatik model seçimi çalışıyor (AIC bazlı grid search)
- - Dashboard'a AI Modül Grid, Governance Panel, Departman Dağılımı eklendi
- - 3 yeni backend endpoint: ai-modules, governance, dept-queries
- - statsmodels>=0.14.0 bağımlılık olarak eklendi
- ### Aktif Versiyon
- - Backend: v3.3.0 ✅ (192.168.0.12)
- - Frontend: v3.3.0 ✅
- - 18 AI modülü aktif
- ### Sonraki Adımlar
- - ChromaDB boyut uyumsuzluğu düzeltilmeli (384-dim → 768-dim)
- - GPU eklendiğinde LLM timeout 900s → 120s'ye düşürülebilir
- ## ⚠️ DEPLOY KURALI
- > **HER DEPLOY ÖNCESI VERSİYON NUMARASI ARTIRILMALIDIR!**
- > - `app/config.py` → `APP_VERSION`
- > - `frontend/src/constants.ts` → `APP_VERSION`
- > - Semantic Versioning: PATCH (bug fix), MINOR (yeni özellik), MAJOR (büyük değişiklik)

## Current Blockers

- None

## ⚠️ DEPLOY KURALI

> **HER DEPLOY ÖNCESI VERİYON NUMARASI ARTIRILMALIDIR!**
>
> - `app/config.py` → `APP_VERSION = "X.Y.Z"`
> - `frontend/src/constants.ts` → `APP_VERSION = 'X.Y.Z'`
> - İki dosya aynı versiyon olmalı
> - Semantic Versioning: PATCH (bug fix), MINOR (yeni özellik), MAJOR (büyük değişiklik)