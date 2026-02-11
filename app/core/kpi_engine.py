"""KPI Engine — KPI Tanımlama, Hesaplama, Tahminleme ve Yorumlama

Kurumsal KPI yönetimi:
- 50+ önceden tanımlı tekstil/üretim/finans KPI'ı
- Otomatik KPI hesaplama
- KPI tahminleme (forecasting entegrasyonu)
- Sektörel benchmark karşılaştırma
- Balanced Scorecard desteği
"""

import numpy as np
from typing import Optional
import structlog

logger = structlog.get_logger()


# ══════════════════════════════════════════════════════════════
# 1. KPI TANIMLARI — Kapsamlı Veritabanı
# ══════════════════════════════════════════════════════════════

KPI_DATABASE = {
    # ── ÜRETİM KPI'ları ──
    "oee": {
        "name": "OEE (Genel Ekipman Verimliliği)",
        "formula": "Kullanılabilirlik × Performans × Kalite",
        "unit": "%",
        "category": "Üretim",
        "direction": "higher_is_better",
        "benchmarks": {"dünya_sınıfı": 85, "iyi": 70, "orta": 55, "düşük": 40},
        "textile_benchmark": 72,
        "description": "Ekipmanın teorik maksimumuna göre gerçek etkinliği",
    },
    "fire_orani": {
        "name": "Fire Oranı",
        "formula": "(Fire Miktar / Toplam Üretim) × 100",
        "unit": "%",
        "category": "Üretim",
        "direction": "lower_is_better",
        "benchmarks": {"iyi": 2, "normal": 5, "yüksek": 8, "kritik": 12},
        "textile_benchmark": 3.5,
        "description": "Üretim sürecindeki atık/fire oranı",
    },
    "verimlilik": {
        "name": "Hat Verimliliği",
        "formula": "(Gerçekleşen Üretim / Planlanan Üretim) × 100",
        "unit": "%",
        "category": "Üretim",
        "direction": "higher_is_better",
        "benchmarks": {"iyi": 90, "normal": 75, "düşük": 60},
        "textile_benchmark": 82,
    },
    "durus_orani": {
        "name": "Duruş Oranı",
        "formula": "(Toplam Duruş Süresi / Toplam Çalışma Süresi) × 100",
        "unit": "%",
        "category": "Üretim",
        "direction": "lower_is_better",
        "benchmarks": {"iyi": 5, "normal": 10, "yüksek": 20},
        "textile_benchmark": 8,
    },
    "cevrim_suresi": {
        "name": "Çevrim Süresi",
        "formula": "Toplam Süre / Üretilen Birim",
        "unit": "dk/birim",
        "category": "Üretim",
        "direction": "lower_is_better",
        "benchmarks": {},
    },
    "ilk_seferde_dogru": {
        "name": "İlk Seferde Doğru Oranı (FTR)",
        "formula": "(İlk seferde kabul / Toplam üretim) × 100",
        "unit": "%",
        "category": "Üretim",
        "direction": "higher_is_better",
        "benchmarks": {"iyi": 95, "normal": 85, "düşük": 70},
        "textile_benchmark": 88,
    },
    "setup_suresi": {
        "name": "Ortalama Setup Süresi",
        "formula": "Toplam Setup Süresi / Setup Sayısı",
        "unit": "dakika",
        "category": "Üretim",
        "direction": "lower_is_better",
        "benchmarks": {"iyi": 15, "normal": 30, "yüksek": 60},
    },
    
    # ── FİNANS KPI'ları ──
    "brut_kar_marji": {
        "name": "Brüt Kâr Marjı",
        "formula": "(Satışlar - SMM) / Satışlar × 100",
        "unit": "%",
        "category": "Finans",
        "direction": "higher_is_better",
        "benchmarks": {"iyi": 25, "normal": 15, "düşük": 8, "zarar": 0},
        "textile_benchmark": 18,
    },
    "favok_marji": {
        "name": "FAVÖK (EBITDA) Marjı",
        "formula": "FAVÖK / Satışlar × 100",
        "unit": "%",
        "category": "Finans",
        "direction": "higher_is_better",
        "benchmarks": {"iyi": 15, "normal": 8, "düşük": 3},
        "textile_benchmark": 10,
    },
    "nakit_cevrim_suresi": {
        "name": "Nakit Çevrim Süresi",
        "formula": "Stok Gün + Alacak Gün - Borç Gün",
        "unit": "gün",
        "category": "Finans",
        "direction": "lower_is_better",
        "benchmarks": {"iyi": 30, "normal": 60, "yüksek": 90, "kritik": 120},
        "textile_benchmark": 55,
    },
    "cari_oran": {
        "name": "Cari Oran",
        "formula": "Dönen Varlıklar / Kısa Vadeli Borçlar",
        "unit": "x",
        "category": "Finans",
        "direction": "higher_is_better",
        "benchmarks": {"iyi": 2.0, "normal": 1.5, "düşük": 1.0, "kritik": 0.8},
    },
    "borc_ozsermaye": {
        "name": "Borç/Özsermaye Oranı",
        "formula": "Toplam Borç / Özsermaye",
        "unit": "x",
        "category": "Finans",
        "direction": "lower_is_better",
        "benchmarks": {"iyi": 0.5, "normal": 1.0, "yüksek": 2.0, "kritik": 3.0},
    },
    "birim_maliyet": {
        "name": "Birim Üretim Maliyeti",
        "formula": "Toplam Maliyet / Üretim Adedi",
        "unit": "₺/birim",
        "category": "Finans",
        "direction": "lower_is_better",
        "benchmarks": {},
    },
    
    # ── SATIŞ KPI'ları ──
    "satis_buyume": {
        "name": "Satış Büyüme Oranı",
        "formula": "(Bu Dönem - Önceki) / Önceki × 100",
        "unit": "%",
        "category": "Satış",
        "direction": "higher_is_better",
        "benchmarks": {"iyi": 15, "normal": 5, "düşük": 0, "küçülme": -5},
    },
    "musteri_tutma": {
        "name": "Müşteri Tutma Oranı",
        "formula": "(Dönem sonu aktif / Dönem başı aktif) × 100",
        "unit": "%",
        "category": "Satış",
        "direction": "higher_is_better",
        "benchmarks": {"iyi": 90, "normal": 75, "düşük": 60},
    },
    "donusum_orani": {
        "name": "Dönüşüm Oranı",
        "formula": "(Sipariş / Teklif) × 100",
        "unit": "%",
        "category": "Satış",
        "direction": "higher_is_better",
        "benchmarks": {"iyi": 35, "normal": 20, "düşük": 10},
    },
    "ortalama_siparis": {
        "name": "Ortalama Sipariş Değeri",
        "formula": "Toplam Ciro / Sipariş Adedi",
        "unit": "₺",
        "category": "Satış",
        "direction": "higher_is_better",
        "benchmarks": {},
    },
    
    # ── İK KPI'ları ──
    "personel_devir": {
        "name": "Personel Devir Oranı",
        "formula": "(Ayrılan / Ort. Çalışan) × 100",
        "unit": "%",
        "category": "İK",
        "direction": "lower_is_better",
        "benchmarks": {"iyi": 10, "normal": 20, "yüksek": 30, "kritik": 40},
        "textile_benchmark": 22,
    },
    "ise_alim_suresi": {
        "name": "İşe Alım Süresi",
        "formula": "Talep-İşe Başlama arası gün",
        "unit": "gün",
        "category": "İK",
        "direction": "lower_is_better",
        "benchmarks": {"iyi": 20, "normal": 30, "yüksek": 45, "kritik": 60},
    },
    "devamsizlik": {
        "name": "Devamsızlık Oranı",
        "formula": "(Devamsız Gün / İş Günü) × 100",
        "unit": "%",
        "category": "İK",
        "direction": "lower_is_better",
        "benchmarks": {"iyi": 2, "normal": 5, "yüksek": 8},
    },
    "is_kazasi": {
        "name": "İş Kazası Sıklık Oranı",
        "formula": "(Kaza Sayısı / Çalışma Saati) × 1.000.000",
        "unit": "oran",
        "category": "İK",
        "direction": "lower_is_better",
        "benchmarks": {"iyi": 2, "normal": 5, "yüksek": 10},
    },
    
    # ── IT KPI'ları ──
    "uptime": {
        "name": "Sistem Uptime",
        "formula": "(Çalışma Süresi / Toplam Süre) × 100",
        "unit": "%",
        "category": "IT",
        "direction": "higher_is_better",
        "benchmarks": {"iyi": 99.9, "normal": 99.5, "düşük": 99.0},
    },
    "mttr": {
        "name": "Ortalama Onarım Süresi (MTTR)",
        "formula": "Toplam Onarım Süresi / Arıza Sayısı",
        "unit": "saat",
        "category": "IT",
        "direction": "lower_is_better",
        "benchmarks": {"iyi": 1, "normal": 4, "yüksek": 8},
    },
}


# ══════════════════════════════════════════════════════════════
# 2. KPI HESAPLAMA & YORUMLAMA
# ══════════════════════════════════════════════════════════════

def calculate_kpi(kpi_id: str, **kwargs) -> dict:
    """KPI hesapla ve yorumla."""
    kpi_def = KPI_DATABASE.get(kpi_id)
    if not kpi_def:
        return {"error": f"Bilinmeyen KPI: {kpi_id}", "available": list(KPI_DATABASE.keys())}
    
    # Spesifik hesaplamalar
    value = None
    
    if kpi_id == "oee":
        a = kwargs.get("availability", 0)
        p = kwargs.get("performance", 0)
        q = kwargs.get("quality", 0)
        value = (a / 100) * (p / 100) * (q / 100) * 100
    
    elif kpi_id == "fire_orani":
        waste = kwargs.get("waste", 0)
        total = kwargs.get("total_production", 1)
        value = (waste / total) * 100 if total > 0 else 0
    
    elif kpi_id == "verimlilik":
        actual = kwargs.get("actual", 0)
        planned = kwargs.get("planned", 1)
        value = (actual / planned) * 100 if planned > 0 else 0
    
    elif kpi_id == "brut_kar_marji":
        revenue = kwargs.get("revenue", 0)
        cogs = kwargs.get("cogs", 0)
        value = ((revenue - cogs) / revenue) * 100 if revenue > 0 else 0
    
    elif kpi_id == "nakit_cevrim_suresi":
        stock_days = kwargs.get("stock_days", 0)
        receivable_days = kwargs.get("receivable_days", 0)
        payable_days = kwargs.get("payable_days", 0)
        value = stock_days + receivable_days - payable_days
    
    elif kpi_id == "personel_devir":
        left = kwargs.get("left", 0)
        avg_employees = kwargs.get("avg_employees", 1)
        value = (left / avg_employees) * 100 if avg_employees > 0 else 0
    
    elif "value" in kwargs:
        value = kwargs["value"]
    
    if value is None:
        return {"error": "Hesaplama için gerekli parametreler eksik", "formula": kpi_def["formula"]}
    
    # Yorumla
    interpretation = interpret_kpi_value(kpi_id, value)
    
    return {
        "kpi_id": kpi_id,
        "name": kpi_def["name"],
        "value": round(value, 2),
        "unit": kpi_def["unit"],
        "formula": kpi_def["formula"],
        "category": kpi_def["category"],
        **interpretation,
    }


def interpret_kpi_value(kpi_id: str, value: float) -> dict:
    """KPI değerini benchmark'larla karşılaştırarak yorumla."""
    kpi_def = KPI_DATABASE.get(kpi_id, {})
    benchmarks = kpi_def.get("benchmarks", {})
    direction = kpi_def.get("direction", "higher_is_better")
    textile_benchmark = kpi_def.get("textile_benchmark")
    
    if not benchmarks:
        return {
            "status": "info",
            "interpretation": f"{kpi_def.get('name', kpi_id)}: {value}{kpi_def.get('unit', '')}",
        }
    
    # Seviye belirle
    level = "bilinmiyor"
    color = "⚪"
    sorted_benchmarks = sorted(benchmarks.items(), key=lambda x: x[1])
    
    if direction == "higher_is_better":
        sorted_benchmarks.reverse()
        for bm_name, bm_value in sorted_benchmarks:
            if value >= bm_value:
                level = bm_name
                break
        else:
            level = sorted_benchmarks[-1][0] if sorted_benchmarks else "düşük"
    else:  # lower_is_better
        for bm_name, bm_value in sorted_benchmarks:
            if value <= bm_value:
                level = bm_name
                break
        else:
            level = sorted_benchmarks[-1][0] if sorted_benchmarks else "yüksek"
    
    # Renk
    color_map = {
        "iyi": "🟢", "dünya_sınıfı": "🟢", 
        "normal": "🟡", "orta": "🟡", "kabul_edilebilir": "🟡",
        "düşük": "🟠", "yüksek": "🟠",
        "kritik": "🔴", "zarar": "🔴", "küçülme": "🔴",
    }
    color = color_map.get(level, "⚪")
    
    # Aksiyon
    if level in ("kritik", "zarar", "küçülme"):
        action_urgency = "ACİL"
        action = "Hemen müdahale gerekiyor"
    elif level in ("düşük", "yüksek"):
        action_urgency = "ÖNCELİKLİ"
        action = "Kısa vadede iyileştirme planı oluşturulmalı"
    elif level in ("normal", "orta"):
        action_urgency = "İYİLEŞTİR"
        action = "Hedef seviyeye ulaşmak için çalışma yapılmalı"
    else:
        action_urgency = "SÜRDÜR"
        action = "Mevcut performansı koru"
    
    interpretation = (
        f"{kpi_def.get('name', kpi_id)}: {value}{kpi_def.get('unit', '')} → "
        f"{color} {level.upper()}"
    )
    
    if textile_benchmark:
        vs_benchmark = value - textile_benchmark
        interpretation += f" (Tekstil sektör ort: {textile_benchmark}, fark: {'+' if vs_benchmark >= 0 else ''}{round(vs_benchmark, 1)})"
    
    return {
        "status": level,
        "color": color,
        "interpretation": interpretation,
        "action_urgency": action_urgency,
        "action": action,
        "benchmarks": benchmarks,
        "textile_benchmark": textile_benchmark,
    }


def kpi_scorecard(kpi_values: dict) -> dict:
    """Birden fazla KPI'ı Balanced Scorecard formatında değerlendir."""
    categories = {"Üretim": [], "Finans": [], "Satış": [], "İK": [], "IT": []}
    
    for kpi_id, value in kpi_values.items():
        result = calculate_kpi(kpi_id, value=value)
        if "error" not in result:
            cat = result.get("category", "Diğer")
            if cat in categories:
                categories[cat].append(result)
    
    # Kategori bazlı skor hesapla
    category_scores = {}
    for cat, kpis in categories.items():
        if kpis:
            scores = []
            for kpi in kpis:
                status = kpi.get("status", "normal")
                score_map = {"iyi": 100, "dünya_sınıfı": 100, "normal": 70, "orta": 70, "düşük": 40, "yüksek": 40, "kritik": 10, "zarar": 0}
                scores.append(score_map.get(status, 50))
            category_scores[cat] = {
                "score": round(np.mean(scores), 1),
                "kpi_count": len(kpis),
                "kpis": kpis,
            }
    
    overall_score = round(np.mean([v["score"] for v in category_scores.values()]), 1) if category_scores else 0
    
    return {
        "overall_score": overall_score,
        "overall_status": "İyi" if overall_score >= 70 else "Geliştirilmeli" if overall_score >= 40 else "Kritik",
        "categories": category_scores,
    }


def list_kpis(category: str = None) -> list[dict]:
    """Tüm KPI'ları listele."""
    result = []
    for kpi_id, kpi_def in KPI_DATABASE.items():
        if category and kpi_def.get("category") != category:
            continue
        result.append({
            "id": kpi_id,
            "name": kpi_def["name"],
            "formula": kpi_def["formula"],
            "unit": kpi_def["unit"],
            "category": kpi_def["category"],
        })
    return result


def predict_kpi(kpi_id: str, historical_values: list[float], periods: int = 6) -> dict:
    """KPI değerini forecasting ile tahmin et."""
    from app.core.forecasting import auto_forecast, holt_linear_trend
    
    if len(historical_values) < 4:
        return {"error": "En az 4 dönemlik geçmiş veri gerekli"}
    
    kpi_def = KPI_DATABASE.get(kpi_id, {})
    
    forecast_result = holt_linear_trend(historical_values, forecast_periods=periods)
    
    if not forecast_result.get("success"):
        return forecast_result
    
    forecasts = forecast_result["forecasts"]
    
    # Her tahmin dönemini yorumla
    predictions = []
    for i, val in enumerate(forecasts):
        interpretation = interpret_kpi_value(kpi_id, val)
        predictions.append({
            "period": f"T+{i+1}",
            "predicted_value": val,
            "status": interpretation.get("status", "bilinmiyor"),
            "color": interpretation.get("color", "⚪"),
        })
    
    return {
        "kpi_id": kpi_id,
        "kpi_name": kpi_def.get("name", kpi_id),
        "historical_count": len(historical_values),
        "forecast_method": forecast_result.get("method", "Holt Linear"),
        "mape": forecast_result.get("mape", "N/A"),
        "trend": forecast_result.get("trend_direction", "N/A"),
        "predictions": predictions,
        "confidence_intervals": forecast_result.get("confidence_intervals", []),
    }
