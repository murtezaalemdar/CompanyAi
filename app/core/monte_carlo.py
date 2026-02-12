"""Monte Carlo Risk Engine — Olasılıksal Risk Simülasyonu

Enterprise Tier-0 Seviye:
- N iterasyonlu Monte Carlo simülasyonu
- Hedef başarısızlık olasılığı
- Beklenen kayıp dağılımı
- Volatilite indeksi
- Confidence interval hesaplama
"""

import random
import math
import structlog
from typing import Optional

logger = structlog.get_logger()

# ══════════════════════════════════════════════════════════════
# 1. MONTE CARLO SİMÜLASYON MOTORU
# ══════════════════════════════════════════════════════════════

DEFAULT_SIMULATIONS = 5000  # Sunucu CPU için optimize (10K yerine 5K)
CONFIDENCE_INTERVAL = 0.95


def monte_carlo_simulate(
    current_value: float,
    target_value: float,
    trend_pct: float = 0.0,
    volatility_pct: float = 10.0,
    risk_events: list[dict] = None,
    periods: int = 4,
    simulations: int = DEFAULT_SIMULATIONS,
    metric_name: str = "Metrik",
    unit: str = "",
) -> dict:
    """Monte Carlo simülasyonu ile risk/fırsat dağılımı hesapla.
    
    Args:
        current_value:  Mevcut KPI/metrik değeri
        target_value:   Hedef değer
        trend_pct:      Dönemsel ortalama trend (%)
        volatility_pct: Dönemsel oynaklık/belirsizlik (%)
        risk_events:    Ek risk olayları [{name, probability, impact_pct}]
        periods:        Kaç dönem ileriye simüle edilecek
        simulations:    Simülasyon sayısı
        metric_name:    Metrik adı
        unit:           Birim
    
    Returns:
        Monte Carlo sonuçları (olasılık dağılımı, kayıp analizi, volatilite)
    """
    if risk_events is None:
        risk_events = []
    
    trend_rate = trend_pct / 100.0
    volatility = volatility_pct / 100.0
    
    # ── Simülasyonları çalıştır ──
    final_values = []
    target_hit_count = 0
    below_critical_count = 0
    critical_threshold = current_value * 0.85  # %15 düşüş = kritik
    
    for _ in range(simulations):
        value = current_value
        
        for period in range(periods):
            # Normal dağılımlı rastgele yürüyüş (Random Walk)
            # Box-Muller transform ile normal dağılım (numpy olmadan)
            u1 = max(1e-10, random.random())
            u2 = random.random()
            z = math.sqrt(-2 * math.log(u1)) * math.cos(2 * math.pi * u2)
            
            period_return = trend_rate + volatility * z
            value *= (1 + period_return)
            
            # Risk olayları — belirli olasılıkla tetiklenir
            for event in risk_events:
                if random.random() < event.get("probability", 0.05):
                    impact = event.get("impact_pct", -5) / 100.0
                    value *= (1 + impact)
        
        final_values.append(value)
        
        if value >= target_value:
            target_hit_count += 1
        if value < critical_threshold:
            below_critical_count += 1
    
    # ── İstatistikler ──
    final_values.sort()
    n = len(final_values)
    
    mean_val = sum(final_values) / n
    variance = sum((x - mean_val) ** 2 for x in final_values) / n
    std_dev = math.sqrt(variance)
    
    # Percentiller
    def percentile(data, pct):
        idx = int(pct / 100 * len(data))
        return data[min(idx, len(data) - 1)]
    
    p5 = percentile(final_values, 5)
    p25 = percentile(final_values, 25)
    p50 = percentile(final_values, 50)  # Medyan
    p75 = percentile(final_values, 75)
    p95 = percentile(final_values, 95)
    
    # Confidence Interval
    ci_lower = percentile(final_values, (1 - CONFIDENCE_INTERVAL) / 2 * 100)
    ci_upper = percentile(final_values, (1 + CONFIDENCE_INTERVAL) / 2 * 100)
    
    # Kayıp analizi
    losses = [v for v in final_values if v < current_value]
    expected_loss = abs(sum(current_value - v for v in losses) / n) if losses else 0
    max_loss = abs(current_value - min(final_values)) if final_values else 0
    
    # Volatilite indeksi (CV — değişim katsayısı)
    volatility_index = (std_dev / mean_val * 100) if mean_val > 0 else 0
    
    # Hedef başarısızlık olasılığı
    target_failure_prob = 1 - (target_hit_count / n)
    
    result = {
        "metric_name": metric_name,
        "unit": unit,
        "current_value": round(current_value, 2),
        "target_value": round(target_value, 2),
        "simulations": n,
        "periods_ahead": periods,
        
        "distribution": {
            "mean": round(mean_val, 2),
            "median": round(p50, 2),
            "std_dev": round(std_dev, 2),
            "min": round(min(final_values), 2),
            "max": round(max(final_values), 2),
            "p5": round(p5, 2),
            "p25": round(p25, 2),
            "p75": round(p75, 2),
            "p95": round(p95, 2),
        },
        
        "confidence_interval": {
            "level": f"%{CONFIDENCE_INTERVAL * 100:.0f}",
            "lower": round(ci_lower, 2),
            "upper": round(ci_upper, 2),
        },
        
        "risk_metrics": {
            "target_failure_probability": round(target_failure_prob * 100, 1),
            "critical_breach_probability": round(below_critical_count / n * 100, 1),
            "expected_loss": round(expected_loss, 2),
            "max_potential_loss": round(max_loss, 2),
            "value_at_risk_95": round(current_value - p5, 2),
            "volatility_index": round(volatility_index, 1),
        },
        
        "assessment": _assess_mc_result(
            target_failure_prob, volatility_index, below_critical_count / n, metric_name
        ),
    }
    
    logger.info("monte_carlo_completed",
                metric=metric_name,
                simulations=n,
                target_failure=f"%{target_failure_prob * 100:.1f}",
                volatility=f"%{volatility_index:.1f}")
    
    return result


def _assess_mc_result(
    failure_prob: float, 
    volatility: float, 
    critical_prob: float,
    metric_name: str,
) -> dict:
    """Monte Carlo sonucunu değerlendir."""
    # Risk seviyesi
    if failure_prob > 0.7 or critical_prob > 0.3:
        risk_level = "🔴 Kritik"
        action = f"{metric_name} hedefi büyük risk altında. Acil aksiyon planı gerekli."
    elif failure_prob > 0.5 or critical_prob > 0.15:
        risk_level = "🟠 Yüksek"
        action = f"{metric_name} hedefe ulaşma olasılığı düşük. İyileştirme planı oluştur."
    elif failure_prob > 0.3:
        risk_level = "🟡 Orta"
        action = f"{metric_name} izlenmeli. Trend kötüleşirse müdahale planla."
    else:
        risk_level = "🟢 Düşük"
        action = f"{metric_name} olumlu seyirde. Mevcut stratejiyi sürdür."
    
    # Volatilite değerlendirmesi
    if volatility > 30:
        vol_assessment = "Çok yüksek belirsizlik — tahminler güvenilir değil"
    elif volatility > 20:
        vol_assessment = "Yüksek belirsizlik — dikkatli planlama gerekli"
    elif volatility > 10:
        vol_assessment = "Orta belirsizlik — makul tahmin aralığı"
    else:
        vol_assessment = "Düşük belirsizlik — güvenilir tahmin"
    
    return {
        "risk_level": risk_level,
        "action": action,
        "volatility_assessment": vol_assessment,
    }


# ══════════════════════════════════════════════════════════════
# 2. FORMATLAMA
# ══════════════════════════════════════════════════════════════

def format_monte_carlo_table(result: dict) -> str:
    """Monte Carlo sonuçlarını markdown tablo formatında döndür."""
    dist = result.get("distribution", {})
    risk = result.get("risk_metrics", {})
    ci = result.get("confidence_interval", {})
    assess = result.get("assessment", {})
    unit = result.get("unit", "")
    metric = result.get("metric_name", "Metrik")
    
    table = f"""### 🎲 Monte Carlo Simülasyonu: {metric}
**{result['simulations']:,} simülasyon** | **{result['periods_ahead']} dönem ileri** | {ci['level']} güven aralığı

| İstatistik | Değer |
|------------|-------|
| Mevcut | {unit}{result['current_value']:,.2f} |
| Hedef | {unit}{result['target_value']:,.2f} |
| Ortalama Projeksiyon | {unit}{dist['mean']:,.2f} |
| Medyan Projeksiyon | {unit}{dist['median']:,.2f} |
| Güven Aralığı | {unit}{ci['lower']:,.2f} — {unit}{ci['upper']:,.2f} |
| En İyi Durum (P95) | {unit}{dist['p95']:,.2f} |
| En Kötü Durum (P5) | {unit}{dist['p5']:,.2f} |

### ⚠️ Risk Metrikleri

| Metrik | Değer | Açıklama |
|--------|-------|----------|
| Hedef Başarısızlık | **%{risk['target_failure_probability']:.1f}** | Hedefe ulaşamama olasılığı |
| Kritik Eşik İhlali | %{risk['critical_breach_probability']:.1f} | Kritik seviyenin altına düşme |
| Beklenen Kayıp | {unit}{risk['expected_loss']:,.2f} | Ortalama potansiyel kayıp |
| VaR (%95) | {unit}{risk['value_at_risk_95']:,.2f} | %95 güvenle maks kayıp |
| Volatilite İndeksi | %{risk['volatility_index']:.1f} | Belirsizlik seviyesi |

**{assess.get('risk_level', '')}** — {assess.get('action', '')}
📊 Belirsizlik: {assess.get('volatility_assessment', '')}"""
    
    return table


# ══════════════════════════════════════════════════════════════
# 3. TOOL OLARAK KULLANIM
# ══════════════════════════════════════════════════════════════

def monte_carlo_tool(params: dict) -> dict:
    """Tool registry için Monte Carlo simülasyonu."""
    try:
        # Risk event'leri parse et
        risk_events = []
        risk_text = params.get("risk_events", "")
        if isinstance(risk_text, list):
            risk_events = risk_text
        
        result = monte_carlo_simulate(
            current_value=float(params.get("current_value", 0)),
            target_value=float(params.get("target_value", 0)),
            trend_pct=float(params.get("trend_pct", 0)),
            volatility_pct=float(params.get("volatility_pct", 10)),
            risk_events=risk_events,
            periods=int(params.get("periods", 4)),
            simulations=int(params.get("simulations", DEFAULT_SIMULATIONS)),
            metric_name=str(params.get("metric_name", "Metrik")),
            unit=str(params.get("unit", "")),
        )
        
        table = format_monte_carlo_table(result)
        return {"success": True, "result": table, "data": result}
        
    except Exception as e:
        return {"success": False, "error": str(e)}
