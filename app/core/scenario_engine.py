"""Senaryo Simülasyonu & Finansal Projeksiyon Motoru

Enterprise Tier-0 Seviye:
- Best Case / Expected Case / Worst Case senaryoları
- Gelir/Maliyet/Net etki projeksiyonu
- Scenario-based risk hesaplama
- Tool olarak çağrılabilir
"""

import re
import structlog
from typing import Optional

logger = structlog.get_logger()


# ══════════════════════════════════════════════════════════════
# 1. SENARYO SİMÜLASYONU
# ══════════════════════════════════════════════════════════════

def simulate_scenarios(
    current_value: float,
    target_value: float = None,
    trend_pct: float = 0.0,
    risk_score: float = 50.0,
    metric_name: str = "Metrik",
    unit: str = "",
    period: str = "sonraki çeyrek",
) -> dict:
    """3 senaryo simülasyonu hesapla.
    
    Args:
        current_value: Mevcut değer
        target_value: Hedef değer (opsiyonel)
        trend_pct: Mevcut dönemsel trend yüzdesi (örn: +5.2 veya -3.1)
        risk_score: Risk skoru (0-100, yüksek = riskli)
        metric_name: Metrik adı (OEE, Fire Oranı vb.)
        unit: Birim (%, ₺, kg vb.)
        period: Tahmin dönemi
    
    Returns:
        {
            "best_case": {...},
            "expected_case": {...},
            "worst_case": {...},
            "recommendation": str,
        }
    """
    if target_value is None:
        target_value = current_value * 1.10  # Default: %10 iyileşme hedefi
    
    # Risk faktörü — risk yüksekse worst case daha kötü
    risk_factor = risk_score / 100.0  # 0-1 arası
    
    # Trend bazlı projeksiyonlar
    trend_multiplier = trend_pct / 100.0  # -0.05 → %5 düşüş
    
    # ── Best Case ──
    # Trend olumlu ise trendin 1.5 katı, olumsuz ise düzeltme varsayımı
    if trend_multiplier >= 0:
        best_change = trend_multiplier * 1.5 + 0.05  # Ekstra %5 iyileşme
    else:
        best_change = abs(trend_multiplier) * 0.3  # Düzeltme: düşüşün %30'u geri
    best_value = current_value * (1 + best_change)
    
    # ── Expected Case ──
    # Mevcut trend devam eder
    expected_value = current_value * (1 + trend_multiplier)
    
    # ── Worst Case ──
    # Trend olumsuz ise hızlanır, olumlu ise durur + risk etkisi
    if trend_multiplier < 0:
        worst_change = trend_multiplier * 1.8 - (risk_factor * 0.05)
    else:
        worst_change = -risk_factor * 0.08 - 0.02
    worst_value = current_value * (1 + worst_change)
    
    # Hedefe uzaklık
    def target_gap(val):
        if target_value == 0:
            return 0
        return ((val - target_value) / target_value) * 100
    
    result = {
        "metric": metric_name,
        "current_value": round(current_value, 2),
        "target_value": round(target_value, 2),
        "period": period,
        "unit": unit,
        "best_case": {
            "label": "🟢 İyimser Senaryo",
            "value": round(best_value, 2),
            "change_pct": round(best_change * 100, 1),
            "target_gap_pct": round(target_gap(best_value), 1),
            "description": f"{metric_name} {unit}{round(best_value, 2)}'e ulaşabilir (+%{round(best_change * 100, 1)})",
            "probability": f"%{max(15, 30 - int(risk_factor * 20))}",
            "assumptions": "Tüm iyileştirme aksiyonları uygulanır, pazar koşulları olumlu",
        },
        "expected_case": {
            "label": "🟡 Beklenen Senaryo",
            "value": round(expected_value, 2),
            "change_pct": round(trend_multiplier * 100, 1),
            "target_gap_pct": round(target_gap(expected_value), 1),
            "description": f"{metric_name} {unit}{round(expected_value, 2)} olur (mevcut trend devam)",
            "probability": f"%{50 + int(risk_factor * 10)}",
            "assumptions": "Mevcut koşullar ve trend değişmeden devam eder",
        },
        "worst_case": {
            "label": "🔴 Kötümser Senaryo",
            "value": round(worst_value, 2),
            "change_pct": round(worst_change * 100, 1),
            "target_gap_pct": round(target_gap(worst_value), 1),
            "description": f"{metric_name} {unit}{round(worst_value, 2)}'e düşebilir ({round(worst_change * 100, 1)}%)",
            "probability": f"%{max(10, int(risk_factor * 30))}",
            "assumptions": "Riskler gerçekleşir, pazar koşulları bozulur",
        },
    }
    
    # Öneri
    if trend_multiplier < -0.05:
        result["recommendation"] = f"⚠️ {metric_name} düşüş trendinde. Acil müdahale önerilir."
    elif target_gap(expected_value) < -10:
        result["recommendation"] = f"📊 {metric_name} hedefe uzak (-%{abs(round(target_gap(expected_value), 1))}). İyileştirme planı gerekli."
    elif trend_multiplier > 0.05:
        result["recommendation"] = f"✅ {metric_name} olumlu trend devam ediyor. Sürdürülebilirliği izle."
    else:
        result["recommendation"] = f"📈 {metric_name} stabil. Hedef ulaşımı için ek aksiyon planla."
    
    return result


# ══════════════════════════════════════════════════════════════
# 2. FİNANSAL ETKİ PROJEKSİYONU
# ══════════════════════════════════════════════════════════════

def project_financial_impact(
    revenue_current: float = 0,
    cost_current: float = 0,
    revenue_change_pct: float = 0,
    cost_change_pct: float = 0,
    investment_required: float = 0,
    payback_months: int = 0,
    currency: str = "₺",
) -> dict:
    """Finansal etki projeksiyonu hesapla.
    
    Args:
        revenue_current: Mevcut gelir
        cost_current: Mevcut maliyet
        revenue_change_pct: Tahmini gelir değişim %
        cost_change_pct: Tahmini maliyet değişim %
        investment_required: Gereken yatırım
        payback_months: Tahmini geri ödeme süresi (ay)
        currency: Para birimi
    
    Returns:
        Finansal etki detayları
    """
    revenue_change = revenue_current * (revenue_change_pct / 100)
    cost_change = cost_current * (cost_change_pct / 100)
    net_effect = revenue_change - cost_change
    
    # ROI hesaplama
    roi = 0
    if investment_required > 0:
        annual_benefit = net_effect * 12 if revenue_current > 0 else 0
        roi = (annual_benefit / investment_required) * 100
    
    result = {
        "revenue": {
            "current": revenue_current,
            "change_pct": revenue_change_pct,
            "change_amount": round(revenue_change, 2),
            "projected": round(revenue_current + revenue_change, 2),
        },
        "cost": {
            "current": cost_current,
            "change_pct": cost_change_pct,
            "change_amount": round(cost_change, 2),
            "projected": round(cost_current + cost_change, 2),
        },
        "net_effect": {
            "amount": round(net_effect, 2),
            "description": f"{'Olumlu' if net_effect > 0 else 'Olumsuz'}: {currency}{abs(round(net_effect, 2)):,.0f}",
            "impact_level": "Yüksek" if abs(net_effect) > revenue_current * 0.05 else "Orta" if abs(net_effect) > revenue_current * 0.02 else "Düşük",
        },
        "investment": {
            "required": investment_required,
            "roi_pct": round(roi, 1),
            "payback_months": payback_months,
        },
        "currency": currency,
    }
    
    return result


# ══════════════════════════════════════════════════════════════
# 3. SENARYO TABLOSU FORMATLAMA
# ══════════════════════════════════════════════════════════════

def format_scenario_table(scenario: dict) -> str:
    """Senaryo sonuçlarını markdown tablo formatında döndür."""
    unit = scenario.get("unit", "")
    metric = scenario.get("metric", "Metrik")
    
    table = f"""### 🎯 Senaryo Simülasyonu: {metric}

| Senaryo | Değer | Değişim | Hedefe Uzaklık | Olasılık |
|---------|-------|---------|----------------|----------|
| {scenario['best_case']['label']} | {unit}{scenario['best_case']['value']:,.2f} | +%{scenario['best_case']['change_pct']} | %{scenario['best_case']['target_gap_pct']:+.1f} | {scenario['best_case']['probability']} |
| {scenario['expected_case']['label']} | {unit}{scenario['expected_case']['value']:,.2f} | %{scenario['expected_case']['change_pct']:+.1f} | %{scenario['expected_case']['target_gap_pct']:+.1f} | {scenario['expected_case']['probability']} |
| {scenario['worst_case']['label']} | {unit}{scenario['worst_case']['value']:,.2f} | %{scenario['worst_case']['change_pct']:+.1f} | %{scenario['worst_case']['target_gap_pct']:+.1f} | {scenario['worst_case']['probability']} |

**Mevcut**: {unit}{scenario['current_value']:,.2f} | **Hedef**: {unit}{scenario['target_value']:,.2f} | **Dönem**: {scenario['period']}

{scenario.get('recommendation', '')}"""
    
    return table


def format_financial_impact(impact: dict) -> str:
    """Finansal etki sonuçlarını markdown formatında döndür."""
    c = impact.get("currency", "₺")
    rev = impact.get("revenue", {})
    cost = impact.get("cost", {})
    net = impact.get("net_effect", {})
    inv = impact.get("investment", {})
    
    table = f"""### 💰 Finansal Etki Projeksiyonu

| Kalem | Mevcut | Değişim | Projeksiyon |
|-------|--------|---------|-------------|
| Gelir | {c}{rev.get('current', 0):,.0f} | %{rev.get('change_pct', 0):+.1f} ({c}{rev.get('change_amount', 0):+,.0f}) | {c}{rev.get('projected', 0):,.0f} |
| Maliyet | {c}{cost.get('current', 0):,.0f} | %{cost.get('change_pct', 0):+.1f} ({c}{cost.get('change_amount', 0):+,.0f}) | {c}{cost.get('projected', 0):,.0f} |
| **Net Etki** | — | — | **{net.get('description', '')}** |

**Etki Seviyesi**: {net.get('impact_level', 'Belirsiz')}"""
    
    if inv.get("required", 0) > 0:
        table += f"""
**Gerekli Yatırım**: {c}{inv['required']:,.0f} | **ROI**: %{inv.get('roi_pct', 0):.1f} | **Geri Ödeme**: {inv.get('payback_months', '?')} ay"""
    
    return table


# ══════════════════════════════════════════════════════════════
# 4. TOOL OLARAK KULLANIM
# ══════════════════════════════════════════════════════════════

def scenario_tool(params: dict) -> dict:
    """Tool registry için senaryo simülasyonu fonksiyonu."""
    try:
        current = float(params.get("current_value", 0))
        target = params.get("target_value")
        if target is not None:
            target = float(target)
        trend = float(params.get("trend_pct", 0))
        risk = float(params.get("risk_score", 50))
        name = params.get("metric_name", "Metrik")
        unit = params.get("unit", "")
        
        result = simulate_scenarios(
            current_value=current,
            target_value=target,
            trend_pct=trend,
            risk_score=risk,
            metric_name=name,
            unit=unit,
        )
        
        table = format_scenario_table(result)
        return {"success": True, "result": table, "data": result}
        
    except Exception as e:
        return {"success": False, "error": str(e)}


def financial_tool(params: dict) -> dict:
    """Tool registry için finansal projeksiyon fonksiyonu."""
    try:
        result = project_financial_impact(
            revenue_current=float(params.get("revenue", 0)),
            cost_current=float(params.get("cost", 0)),
            revenue_change_pct=float(params.get("revenue_change_pct", 0)),
            cost_change_pct=float(params.get("cost_change_pct", 0)),
            investment_required=float(params.get("investment", 0)),
            payback_months=int(params.get("payback_months", 0)),
        )
        
        table = format_financial_impact(result)
        return {"success": True, "result": table, "data": result}
        
    except Exception as e:
        return {"success": False, "error": str(e)}
