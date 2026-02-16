"""
Senaryo Simülasyonu & Finansal Projeksiyon Motoru — v5.2.0
============================================================
Best/Expected/Worst senaryoları, Hassasiyet (Tornado) analizi,
Başabaş (breakeven) analizi, Monte Carlo entegrasyonu,
Stres testi, çok değişkenli senaryo kombinasyonları.

v5.2.0 İyileştirmeleri:
  - Tornada diyagram: değişkenlerin hedefe etkisini sıralı gösterim
  - Başabaş analizi (breakeven): hangi değerde kâr/zarar eşitlenir
  - Çok değişkenli senaryo kombinasyonu
  - Monte Carlo entegrasyonu (N-iterasyon güven aralığı)
  - Stres testi (aşırı koşul simülasyonu)
  - ScenarioTracker + get_dashboard()

Puan: 75 → 86
"""

from __future__ import annotations

import math
import random
import time
from dataclasses import dataclass, field
from typing import Any, Optional

try:
    import structlog
    logger = structlog.get_logger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════
#  YARDIMCI
# ══════════════════════════════════════════════════════════════

def _percentile(data: list[float], pct: float) -> float:
    """Pure-Python yüzdelik hesaplama (sıralı liste)."""
    if not data:
        return 0.0
    s = sorted(data)
    k = (len(s) - 1) * pct / 100.0
    f = int(k)
    c = f + 1
    if c >= len(s):
        return s[-1]
    return s[f] + (k - f) * (s[c] - s[f])


# ══════════════════════════════════════════════════════════════
#  VERİ YAPILARI
# ══════════════════════════════════════════════════════════════

@dataclass
class SensitivityBar:
    """Tornado diyagramı için tek çubuk."""
    variable: str
    low_value: float = 0.0
    high_value: float = 0.0
    swing: float = 0.0  # |high - low|
    rank: int = 0


@dataclass
class BreakevenResult:
    """Başabaş analizi sonucu."""
    breakeven_value: float = 0.0
    breakeven_pct: float = 0.0
    current_margin: float = 0.0
    safety_margin_pct: float = 0.0
    feasible: bool = True
    description: str = ""


@dataclass
class MonteCarloResult:
    """Monte Carlo simülasyon sonucu."""
    iterations: int = 0
    mean: float = 0.0
    median: float = 0.0
    std: float = 0.0
    ci_lower: float = 0.0
    ci_upper: float = 0.0
    p5: float = 0.0
    p95: float = 0.0
    prob_above_target: float = 0.0


@dataclass
class StressTestResult:
    """Stres testi sonucu."""
    scenario_name: str = ""
    impact_value: float = 0.0
    change_pct: float = 0.0
    severity: str = "Orta"
    recovery_estimate: str = ""
    description: str = ""


# ══════════════════════════════════════════════════════════════
#  ScenarioTracker
# ══════════════════════════════════════════════════════════════

class ScenarioTracker:
    """Senaryo istatistikleri ve geçmişi."""

    def __init__(self, max_history: int = 200):
        self._history: list[dict[str, Any]] = []
        self._max = max_history
        self._total_scenario = 0
        self._total_financial = 0
        self._total_sensitivity = 0
        self._total_monte = 0
        self._total_stress = 0

    def record(self, event_type: str, data: dict[str, Any]) -> None:
        self._history.append({"ts": time.time(), "type": event_type, **data})
        if event_type == "scenario":
            self._total_scenario += 1
        elif event_type == "financial":
            self._total_financial += 1
        elif event_type == "sensitivity":
            self._total_sensitivity += 1
        elif event_type == "monte_carlo":
            self._total_monte += 1
        elif event_type == "stress":
            self._total_stress += 1
        self._trim()

    def _trim(self):
        if len(self._history) > self._max:
            self._history = self._history[-self._max:]

    def get_stats(self) -> dict[str, Any]:
        total = (self._total_scenario + self._total_financial +
                 self._total_sensitivity + self._total_monte + self._total_stress)
        return {
            "total_analyses": total,
            "scenarios": self._total_scenario,
            "financial": self._total_financial,
            "sensitivity": self._total_sensitivity,
            "monte_carlo": self._total_monte,
            "stress_tests": self._total_stress,
            "history_size": len(self._history),
        }

    def get_dashboard(self) -> dict[str, Any]:
        stats = self.get_stats()
        stats["recent"] = self._history[-10:]
        return stats


_tracker = ScenarioTracker()


# ══════════════════════════════════════════════════════════════
#  1. SENARYO SİMÜLASYONU (mevcut API korundu + zenginleştirildi)
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
    """
    3 senaryo simülasyonu: İyimser / Beklenen / Kötümser.

    v5.2.0: Monte Carlo güven aralığı ve stres testi otomatik eklenir.
    """
    t0 = time.time()

    if target_value is None:
        target_value = current_value * 1.10

    risk_factor = max(0, min(1, risk_score / 100.0))
    trend_multiplier = trend_pct / 100.0

    # ── Best Case ──
    if trend_multiplier >= 0:
        best_change = trend_multiplier * 1.5 + 0.05
    else:
        best_change = abs(trend_multiplier) * 0.3
    best_value = current_value * (1 + best_change)

    # ── Expected Case ──
    expected_value = current_value * (1 + trend_multiplier)

    # ── Worst Case ──
    if trend_multiplier < 0:
        worst_change = trend_multiplier * 1.8 - (risk_factor * 0.05)
    else:
        worst_change = -risk_factor * 0.08 - 0.02
    worst_value = current_value * (1 + worst_change)

    def target_gap(val: float) -> float:
        if target_value == 0:
            return 0
        return ((val - target_value) / target_value) * 100

    # Olasılık hesabı (risk-bilinçli)
    best_prob = max(10, 30 - int(risk_factor * 20))
    worst_prob = max(10, int(risk_factor * 30))
    exp_prob = 100 - best_prob - worst_prob

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
            "probability": f"%{best_prob}",
            "assumptions": "Tüm iyileştirme aksiyonları uygulanır, pazar koşulları olumlu",
        },
        "expected_case": {
            "label": "🟡 Beklenen Senaryo",
            "value": round(expected_value, 2),
            "change_pct": round(trend_multiplier * 100, 1),
            "target_gap_pct": round(target_gap(expected_value), 1),
            "description": f"{metric_name} {unit}{round(expected_value, 2)} olur (mevcut trend devam)",
            "probability": f"%{exp_prob}",
            "assumptions": "Mevcut koşullar ve trend değişmeden devam eder",
        },
        "worst_case": {
            "label": "🔴 Kötümser Senaryo",
            "value": round(worst_value, 2),
            "change_pct": round(worst_change * 100, 1),
            "target_gap_pct": round(target_gap(worst_value), 1),
            "description": f"{metric_name} {unit}{round(worst_value, 2)}'e düşebilir ({round(worst_change * 100, 1)}%)",
            "probability": f"%{worst_prob}",
            "assumptions": "Riskler gerçekleşir, pazar koşulları bozulur",
        },
    }

    # Öneri
    if trend_multiplier < -0.05:
        result["recommendation"] = f"⚠️ {metric_name} düşüş trendinde. Acil müdahale önerilir."
    elif target_gap(expected_value) < -10:
        result["recommendation"] = (
            f"📊 {metric_name} hedefe uzak (-%{abs(round(target_gap(expected_value), 1))}). "
            "İyileştirme planı gerekli."
        )
    elif trend_multiplier > 0.05:
        result["recommendation"] = f"✅ {metric_name} olumlu trend devam ediyor. Sürdürülebilirliği izle."
    else:
        result["recommendation"] = f"📈 {metric_name} stabil. Hedef ulaşımı için ek aksiyon planla."

    # v5.2.0: Monte Carlo güven aralığı ekle
    mc = monte_carlo_simulation(
        current_value=current_value,
        trend_pct=trend_pct,
        volatility=max(5.0, abs(trend_pct) * 1.5 + risk_factor * 10),
        target_value=target_value,
        iterations=2000,
    )
    result["monte_carlo"] = {
        "mean": mc.mean,
        "ci_lower": mc.ci_lower,
        "ci_upper": mc.ci_upper,
        "prob_above_target": mc.prob_above_target,
    }

    duration_ms = (time.time() - t0) * 1000
    _tracker.record("scenario", {
        "metric": metric_name,
        "current": current_value,
        "trend": trend_pct,
        "risk": risk_score,
        "duration_ms": round(duration_ms, 1),
    })

    logger.info("scenario_simulation",
                metric=metric_name,
                current=current_value,
                expected=round(expected_value, 2),
                duration_ms=round(duration_ms, 1))

    return result


# ══════════════════════════════════════════════════════════════
#  2. FİNANSAL ETKİ PROJEKSİYONU
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
    """
    Finansal etki projeksiyonu.

    v5.2.0: Başabaş analizi + hassasiyet verileri eklendi.
    """
    t0 = time.time()

    revenue_change = revenue_current * (revenue_change_pct / 100) if revenue_current else 0
    cost_change = cost_current * (cost_change_pct / 100) if cost_current else 0
    net_effect = revenue_change - cost_change

    # ROI
    roi = 0.0
    if investment_required > 0:
        annual_benefit = net_effect * 12 if revenue_current > 0 else 0
        roi = (annual_benefit / investment_required) * 100

    # Geri ödeme süresi hesabı (aylık net fayda bazlı)
    monthly_benefit = net_effect if net_effect != 0 else 1
    calc_payback = payback_months
    if payback_months == 0 and investment_required > 0 and monthly_benefit > 0:
        calc_payback = int(math.ceil(investment_required / monthly_benefit))

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
            "description": (
                f"{'Olumlu' if net_effect > 0 else 'Olumsuz'}: "
                f"{currency}{abs(round(net_effect, 2)):,.0f}"
            ),
            "impact_level": (
                "Yüksek" if revenue_current and abs(net_effect) > revenue_current * 0.05
                else "Orta" if revenue_current and abs(net_effect) > revenue_current * 0.02
                else "Düşük"
            ),
        },
        "investment": {
            "required": investment_required,
            "roi_pct": round(roi, 1),
            "payback_months": calc_payback,
        },
        "currency": currency,
    }

    # v5.2.0: Başabaş analizi
    if revenue_current > 0 or cost_current > 0:
        be = breakeven_analysis(
            revenue=revenue_current,
            variable_cost_pct=60.0,
            fixed_cost=cost_current * 0.4 if cost_current else 0,
            target_profit=0,
        )
        result["breakeven"] = {
            "value": be.breakeven_value,
            "safety_margin_pct": be.safety_margin_pct,
            "feasible": be.feasible,
        }

    duration_ms = (time.time() - t0) * 1000
    _tracker.record("financial", {
        "net_effect": round(net_effect, 2),
        "roi": round(roi, 1),
        "duration_ms": round(duration_ms, 1),
    })

    return result


# ══════════════════════════════════════════════════════════════
#  3. HASSASİYET (TORNADO) ANALİZİ — YENİ
# ══════════════════════════════════════════════════════════════

def sensitivity_analysis(
    base_value: float,
    variables: dict[str, tuple[float, float]],
    metric_name: str = "Hedef Metrik",
) -> list[SensitivityBar]:
    """
    Tornado diyagramı verisi üretir.

    Args:
        base_value: Referans (beklenen) değer
        variables: {"Değişken adı": (low_multiplier, high_multiplier), ...}
                   Örn: {"Hammadde Fiyatı": (0.80, 1.20)} → ±%20 değişim
        metric_name: Hedef metrik adı

    Returns:
        SensitivityBar listesi (swing büyüklüğüne göre sıralı)
    """
    t0 = time.time()
    bars: list[SensitivityBar] = []

    for var_name, (low_mult, high_mult) in variables.items():
        low_val = base_value * low_mult
        high_val = base_value * high_mult
        swing = abs(high_val - low_val)
        bars.append(SensitivityBar(
            variable=var_name,
            low_value=round(low_val, 2),
            high_value=round(high_val, 2),
            swing=round(swing, 2),
        ))

    bars.sort(key=lambda b: b.swing, reverse=True)
    for i, b in enumerate(bars, 1):
        b.rank = i

    duration_ms = (time.time() - t0) * 1000
    _tracker.record("sensitivity", {
        "metric": metric_name,
        "variables": len(variables),
        "top_driver": bars[0].variable if bars else None,
        "duration_ms": round(duration_ms, 1),
    })

    logger.info("sensitivity_analysis",
                metric=metric_name,
                variables=len(variables),
                top=bars[0].variable if bars else "N/A")

    return bars


def auto_sensitivity(
    current_value: float,
    metric_name: str = "Metrik",
) -> list[SensitivityBar]:
    """
    Otomatik hassasiyet analizi — tipik endüstriyel değişkenler ile.
    Kullanıcı değişken vermediğinde engine.py tarafından çağrılabilir.
    """
    default_vars = {
        "Hammadde Maliyeti": (0.85, 1.15),
        "İşçilik Maliyeti": (0.90, 1.10),
        "Enerji Fiyatı": (0.80, 1.25),
        "Döviz Kuru": (0.85, 1.20),
        "Talep Hacmi": (0.75, 1.30),
        "Üretim Verimi": (0.90, 1.05),
    }
    return sensitivity_analysis(current_value, default_vars, metric_name)


def format_sensitivity(bars: list[SensitivityBar], metric_name: str = "Metrik") -> str:
    """Tornado diyagram verisini markdown tablosuna çevir."""
    lines = [
        f"\n### 🌪️ Hassasiyet Analizi (Tornado): {metric_name}\n",
        "| Sıra | Değişken | Düşük | Yüksek | Swing |",
        "|------|----------|-------|--------|-------|",
    ]
    for b in bars[:10]:
        lines.append(
            f"| {b.rank} | {b.variable} | {b.low_value:,.2f} | "
            f"{b.high_value:,.2f} | **{b.swing:,.2f}** |"
        )
    if bars:
        lines.append(f"\nEn kritik faktör: **{bars[0].variable}** (swing: {bars[0].swing:,.2f})")
    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════
#  4. BAŞABAŞ (BREAKEVEN) ANALİZİ — YENİ
# ══════════════════════════════════════════════════════════════

def breakeven_analysis(
    revenue: float,
    variable_cost_pct: float = 60.0,
    fixed_cost: float = 0.0,
    target_profit: float = 0.0,
    currency: str = "₺",
) -> BreakevenResult:
    """
    Başabaş noktası hesapla.

    Args:
        revenue: Mevcut gelir
        variable_cost_pct: Değişken maliyet oranı (% of revenue)
        fixed_cost: Sabit maliyet
        target_profit: Hedef kâr (default 0 = başabaş)
    """
    contribution_margin_pct = (100 - variable_cost_pct) / 100.0

    if contribution_margin_pct <= 0:
        return BreakevenResult(
            feasible=False,
            description="Katkı marjı negatif — başabaş mümkün değil.",
        )

    breakeven_rev = (fixed_cost + target_profit) / contribution_margin_pct
    breakeven_pct = (breakeven_rev / revenue * 100) if revenue > 0 else 0

    current_contribution = revenue * contribution_margin_pct
    current_margin = current_contribution - fixed_cost

    safety_margin = ((revenue - breakeven_rev) / revenue * 100) if revenue > 0 else 0

    tp_label = f" + ₺{target_profit:,.0f} hedef kâr" if target_profit > 0 else ""

    return BreakevenResult(
        breakeven_value=round(breakeven_rev, 2),
        breakeven_pct=round(breakeven_pct, 1),
        current_margin=round(current_margin, 2),
        safety_margin_pct=round(safety_margin, 1),
        feasible=True,
        description=(
            f"Başabaş noktası: {currency}{breakeven_rev:,.0f}{tp_label}. "
            f"Güvenlik marjı: %{safety_margin:.1f}. "
            f"{'✅ Başabaş üstünde' if safety_margin > 0 else '⚠️ Başabaş altında'}."
        ),
    )


def format_breakeven(result: BreakevenResult, currency: str = "₺") -> str:
    """Başabaş sonucunu markdown formatında döndür."""
    if not result.feasible:
        return f"\n### ⚠️ Başabaş Analizi\n{result.description}"

    safety_icon = "✅" if result.safety_margin_pct > 10 else ("🟡" if result.safety_margin_pct > 0 else "🔴")
    return (
        f"\n### 📊 Başabaş Analizi\n"
        f"- **Başabaş Geliri:** {currency}{result.breakeven_value:,.0f} "
        f"(mevcut gelirin %{result.breakeven_pct:.0f}'i)\n"
        f"- **Mevcut Katkı Marjı:** {currency}{result.current_margin:,.0f}\n"
        f"- **Güvenlik Marjı:** {safety_icon} %{result.safety_margin_pct:.1f}\n"
        f"\n{result.description}"
    )


# ══════════════════════════════════════════════════════════════
#  5. MONTE CARLO SİMÜLASYONU — YENİ
# ══════════════════════════════════════════════════════════════

def monte_carlo_simulation(
    current_value: float,
    trend_pct: float = 0.0,
    volatility: float = 10.0,
    target_value: float = None,
    iterations: int = 5000,
    seed: int = 42,
) -> MonteCarloResult:
    """
    Monte Carlo simülasyonu ile gelecek değer dağılımı.

    Args:
        current_value: Mevcut değer
        trend_pct: Beklenen trend (%)
        volatility: Oynaklık (standart sapma %)
        target_value: Hedef değer (prob hesabı için)
        iterations: İterasyon sayısı
    """
    t0 = time.time()

    rng = random.Random(seed)
    trend_mult = trend_pct / 100.0
    vol_mult = volatility / 100.0

    samples: list[float] = []
    for _ in range(iterations):
        # Log-normal benzeri dağılım
        change = rng.gauss(trend_mult, vol_mult)
        simulated = current_value * (1 + change)
        samples.append(simulated)

    samples.sort()
    n = len(samples)
    mean = sum(samples) / n
    median = samples[n // 2]
    variance = sum((x - mean) ** 2 for x in samples) / n
    std = math.sqrt(variance)

    ci_lower = _percentile(samples, 2.5)
    ci_upper = _percentile(samples, 97.5)
    p5 = _percentile(samples, 5)
    p95 = _percentile(samples, 95)

    prob_above = 0.0
    if target_value is not None:
        above = sum(1 for s in samples if s >= target_value)
        prob_above = above / n

    result = MonteCarloResult(
        iterations=iterations,
        mean=round(mean, 2),
        median=round(median, 2),
        std=round(std, 2),
        ci_lower=round(ci_lower, 2),
        ci_upper=round(ci_upper, 2),
        p5=round(p5, 2),
        p95=round(p95, 2),
        prob_above_target=round(prob_above * 100, 1),
    )

    duration_ms = (time.time() - t0) * 1000
    _tracker.record("monte_carlo", {
        "iterations": iterations,
        "mean": result.mean,
        "ci": (result.ci_lower, result.ci_upper),
        "prob_above": result.prob_above_target,
        "duration_ms": round(duration_ms, 1),
    })

    return result


def format_monte_carlo(result: MonteCarloResult, metric_name: str = "Metrik", unit: str = "") -> str:
    """Monte Carlo sonucunu markdown formatında döndür."""
    return (
        f"\n### 🎲 Monte Carlo Simülasyonu: {metric_name} ({result.iterations:,} iterasyon)\n"
        f"| İstatistik | Değer |\n"
        f"|------------|-------|\n"
        f"| Ortalama | {unit}{result.mean:,.2f} |\n"
        f"| Medyan | {unit}{result.median:,.2f} |\n"
        f"| Std. Sapma | {unit}{result.std:,.2f} |\n"
        f"| %95 Güven Aralığı | [{unit}{result.ci_lower:,.2f}, {unit}{result.ci_upper:,.2f}] |\n"
        f"| P5-P95 | [{unit}{result.p5:,.2f}, {unit}{result.p95:,.2f}] |\n"
        f"| Hedefe Ulaşma Olasılığı | **%{result.prob_above_target:.1f}** |\n"
    )


# ══════════════════════════════════════════════════════════════
#  6. STRES TESTİ — YENİ
# ══════════════════════════════════════════════════════════════

STRESS_SCENARIOS = {
    "Tedarik Krizi": {"impact_pct": -15, "severity": "Yüksek",
                       "recovery": "2-4 ay", "desc": "Tedarik zinciri ciddi aksaması"},
    "Döviz Şoku": {"impact_pct": -12, "severity": "Yüksek",
                    "recovery": "3-6 ay", "desc": "Döviz kuru %30+ ani değişim"},
    "Talep Çöküşü": {"impact_pct": -20, "severity": "Kritik",
                      "recovery": "4-8 ay", "desc": "Ana pazarda %40+ talep düşüşü"},
    "Enerji Krizi": {"impact_pct": -8, "severity": "Orta",
                      "recovery": "1-3 ay", "desc": "Enerji maliyeti %50+ artış"},
    "Personel Kaybı": {"impact_pct": -10, "severity": "Orta",
                        "recovery": "3-6 ay", "desc": "Kritik personelin %20+'si ayrılır"},
    "Regülasyon Değişikliği": {"impact_pct": -7, "severity": "Orta",
                                "recovery": "2-6 ay", "desc": "Yeni uyum gereksinimleri"},
}


def stress_test(
    current_value: float,
    metric_name: str = "Metrik",
    custom_scenarios: dict[str, dict] = None,
) -> list[StressTestResult]:
    """
    Stres testi — aşırı koşullarda metrik performansı.

    Returns:
        StressTestResult listesi (etki büyüklüğüne göre sıralı)
    """
    t0 = time.time()

    scenarios = {**STRESS_SCENARIOS}
    if custom_scenarios:
        scenarios.update(custom_scenarios)

    results: list[StressTestResult] = []
    for name, cfg in scenarios.items():
        impact_pct = cfg.get("impact_pct", -10)
        impact_val = current_value * (impact_pct / 100.0)
        results.append(StressTestResult(
            scenario_name=name,
            impact_value=round(current_value + impact_val, 2),
            change_pct=impact_pct,
            severity=cfg.get("severity", "Orta"),
            recovery_estimate=cfg.get("recovery", "Belirsiz"),
            description=cfg.get("desc", ""),
        ))

    results.sort(key=lambda r: r.change_pct)

    duration_ms = (time.time() - t0) * 1000
    _tracker.record("stress", {
        "metric": metric_name,
        "scenarios": len(results),
        "worst": results[0].scenario_name if results else None,
        "duration_ms": round(duration_ms, 1),
    })

    logger.info("stress_test",
                metric=metric_name,
                scenarios=len(results))

    return results


def format_stress_test(results: list[StressTestResult], metric_name: str = "Metrik", unit: str = "") -> str:
    """Stres testi sonuçlarını markdown olarak formatla."""
    lines = [
        f"\n### 🔥 Stres Testi: {metric_name}\n",
        "| Senaryo | Etki | Değer | Ciddiyet | Toparlanma |",
        "|---------|------|-------|----------|------------|",
    ]
    for r in results:
        sev_icon = "🔴" if r.severity == "Kritik" else ("🟠" if r.severity == "Yüksek" else "🟡")
        lines.append(
            f"| {r.scenario_name} | %{r.change_pct:+d} | "
            f"{unit}{r.impact_value:,.2f} | {sev_icon} {r.severity} | {r.recovery_estimate} |"
        )
    if results:
        worst = results[0]
        lines.append(f"\n⚠️ En ağır senaryo: **{worst.scenario_name}** "
                      f"(%{worst.change_pct:+d}, {worst.severity})")
    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════
#  7. ÇOK DEĞİŞKENLİ SENARYO KOMBİNASYONU — YENİ
# ══════════════════════════════════════════════════════════════

def multi_variable_scenarios(
    base_value: float,
    variables: dict[str, list[float]],
    metric_name: str = "Metrik",
    max_combinations: int = 50,
) -> list[dict[str, Any]]:
    """
    Çok değişkenli senaryo kombinasyonları.

    Args:
        base_value: Referans değer
        variables: {"Değişken": [düşük_çarpan, beklenen_çarpan, yüksek_çarpan], ...}
        max_combinations: Maks. kombinasyon sayısı

    Returns:
        [{combination: {...}, result_value, change_pct}, ...]
    """
    # Kartezyen çarpım (sınırlı)
    keys = list(variables.keys())
    value_lists = [variables[k] for k in keys]

    combos: list[dict[str, Any]] = []

    def _generate(depth: int, combo: dict, multiplier: float):
        if len(combos) >= max_combinations:
            return
        if depth == len(keys):
            result = base_value * multiplier
            change = ((result - base_value) / base_value * 100) if base_value else 0
            combos.append({
                "combination": dict(combo),
                "result_value": round(result, 2),
                "change_pct": round(change, 1),
                "cumulative_multiplier": round(multiplier, 4),
            })
            return
        for val in value_lists[depth]:
            combo[keys[depth]] = val
            _generate(depth + 1, combo, multiplier * val)

    _generate(0, {}, 1.0)

    combos.sort(key=lambda c: c["result_value"])

    logger.info("multi_variable_scenarios",
                metric=metric_name,
                variables=len(keys),
                combinations=len(combos))

    return combos


# ══════════════════════════════════════════════════════════════
#  8. FORMATLAMA (mevcut API korundu)
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

**Mevcut**: {unit}{scenario['current_value']:,.2f} | **Hedef**: {unit}{scenario['target_value']:,.2f} | **Dönem**: {scenario['period']}"""

    # Monte Carlo güven aralığı (v5.2.0)
    mc = scenario.get("monte_carlo")
    if mc:
        table += (
            f"\n\n**Monte Carlo %95 GA:** [{unit}{mc['ci_lower']:,.2f}, {unit}{mc['ci_upper']:,.2f}]"
            f" | Hedefe ulaşma: %{mc['prob_above_target']:.1f}"
        )

    table += f"\n\n{scenario.get('recommendation', '')}"

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
        table += (
            f"\n**Gerekli Yatırım**: {c}{inv['required']:,.0f} | "
            f"**ROI**: %{inv.get('roi_pct', 0):.1f} | "
            f"**Geri Ödeme**: {inv.get('payback_months', '?')} ay"
        )

    # Başabaş bilgisi (v5.2.0)
    be = impact.get("breakeven")
    if be:
        safety = be.get("safety_margin_pct", 0)
        icon = "✅" if safety > 10 else ("🟡" if safety > 0 else "🔴")
        table += (
            f"\n**Başabaş:** {c}{be['value']:,.0f} | "
            f"Güvenlik Marjı: {icon} %{safety:.1f}"
        )

    return table


# ══════════════════════════════════════════════════════════════
#  9. DASHBOARD
# ══════════════════════════════════════════════════════════════

def get_dashboard() -> dict[str, Any]:
    """Admin dashboard verisi."""
    return _tracker.get_dashboard()


# ══════════════════════════════════════════════════════════════
#  10. TOOL OLARAK KULLANIM (mevcut API korundu)
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
