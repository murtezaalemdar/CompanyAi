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
- [x] v3.4.0 — 6 Yeni Modül + Dashboard v2
- [x] v3.5.0 — Analiz Motoru İyileştirme (13 analiz tipi)
- [x] v3.5.1 — Pro Seviye Analiz (5-model tahmin, istatistiksel testler)
- [x] v3.8.0 — CEO-Tier Analiz (Executive Health + Bottleneck Engine)
- [x] v3.9.0 — Insight Engine + Paralel Agent + Tekstil KB genişletme + CEO Dashboard
- [x] v3.9.1 — Kod Bloğu Kopyalama Fix (MessageContent.tsx bileşeni)
- [x] v3.9.2 — Seçip Sor özelliği (ChatGPT tarzı quote & ask)

### v3.9.x Detay (13 Şubat 2026)
- [x] insight_engine.py — 7 otomatik içgörü türü + TEXTILE_THRESHOLDS
- [x] textile_knowledge.py genişletme: 200 → 500+ terim
- [x] agent_pipeline.py paralel grup yürütme
- [x] CEO Dashboard (RadarChart + İçgörü + Darboğaz panelleri)
- [x] MessageContent.tsx — kod bloğu ayırma + Kopyala butonu
- [x] Ask.tsx — Seçip Sor popup + alıntı chip + submit entegrasyonu
- [x] Deploy + doğrulama tamamlandı (commit 0986e99)

## Doing

- [ ] GitHub commit & push (v3.9.2)

## Next

- [ ] ChromaDB boyut uyumsuzluğu düzeltmesi (384-dim → 768-dim)
- [ ] GPU eklendiğinde LLM timeout optimize

## ⚠️ DEPLOY HATIRLATMA

> Her deploy öncesi `APP_VERSION` artırılmalı!
> - `app/config.py` + `frontend/src/constants.ts`
> - Güncel versiyon: **v3.9.2**