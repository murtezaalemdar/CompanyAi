# Progress

## Done

- [x] Proje altyapısı (FastAPI + React + PostgreSQL + ChromaDB)
- [x] JWT Auth + RBAC
- [x] RAG doküman yönetimi (65+ format)
- [x] Web arama + görsel arama + hava durumu
- [x] Export sistemi (Excel, PDF, PPTX, Word, CSV)
- [x] Qwen2.5:72B model yükseltmesi + 64GB RAM
- [x] Versiyon numaralama sistemi
- [x] "Designed by Murteza ALEMDAR" imzası
- [x] v3.0.0 — Reflection + Multi-Agent Pipeline + Scenario Engine
- [x] v3.1.0 — Monte Carlo + Decision Ranking + Governance + Experiment Layer
- [x] v3.2.0 — Graph Impact Mapping (26 düğüm, 35 kenar)
- [x] v3.3.0 — ARIMA/SARIMA Forecast + Gelişmiş Dashboard

### v3.3.0 Detay (12 Şubat 2026)
- [x] ARIMA tahmin motoru (AIC bazlı auto-order, ADF durağanlık testi)
- [x] SARIMA mevsimsel tahmin (aylık/çeyreklik periyot)
- [x] auto_forecast() ARIMA/SARIMA entegrasyonu
- [x] conf_int() uyumluluk fix (ndarray vs DataFrame)
- [x] Dashboard: AI Modül Grid (18 modül, aktif/pasif)
- [x] Dashboard: AI Governance Paneli (bias, drift, güven, uyarılar)
- [x] Dashboard: Departman Dağılımı (pie chart + tablo)
- [x] Dashboard: Disk kullanımı progress bar
- [x] 3 yeni backend endpoint (ai-modules, governance, dept-queries)
- [x] statsmodels>=0.14.0 bağımlılık eklendi
- [x] Deploy + doğrulama tamamlandı

## Doing

- [ ] GitHub commit & push (v3.3.0)

## Next

- [ ] ChromaDB boyut uyumsuzluğu düzeltmesi (384-dim → 768-dim)
- [ ] GPU eklendiğinde LLM timeout optimize

## ⚠️ DEPLOY HATIRLATMA

> Her deploy öncesi `APP_VERSION` artırılmalı!
> - `app/config.py` + `frontend/src/constants.ts`
> - Güncel versiyon: **v3.3.0**