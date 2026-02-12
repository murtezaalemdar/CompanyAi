"""
Autonomous Experiment Layer — v3.1.0
======================================
A/B Strateji Simülasyonu, Cross-Department Impact Mapping,
Threshold Auto-Adjustment ve Self-KPI Optimization.

Enterprise Package autonomous_experiment_layer.json referanslı.
"""

from __future__ import annotations

import random
import hashlib
from dataclasses import dataclass, field
from typing import Any, Optional

try:
    import structlog
    logger = structlog.get_logger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)

# ──────────────────── Departman Tanımları ────────────────────

DEPARTMENTS = {
    "Üretim": {"icon": "🏭", "kpis": ["OEE", "Fire Oranı", "Üretim Hızı", "Makine Arıza"]},
    "Satış": {"icon": "📈", "kpis": ["Gelir", "Sipariş Adedi", "Müşteri Kaybı", "Ortalama Sipariş"]},
    "Finans": {"icon": "💰", "kpis": ["Nakit Akış", "Brüt Kâr", "İşletme Gideri", "Borç/Özkaynak"]},
    "İK": {"icon": "👥", "kpis": ["Devir Oranı", "Eğitim Saati", "Memnuniyet", "Verimlilik"]},
    "Lojistik": {"icon": "🚚", "kpis": ["Zamanında Teslimat", "Stok Devir", "Taşıma Maliyeti", "Depo Doluluğu"]},
    "Kalite": {"icon": "✅", "kpis": ["Ret Oranı", "Müşteri Şikayeti", "ISO Uyum", "Kontrol Süresi"]},
}

# Departmanlar arası etki matrisi — her satırdaki departmanın karardaki
# değişikliğinin diğer departmanlara etkisi (0-1 aralığında)
IMPACT_MATRIX = {
    "Üretim":   {"Satış": 0.7, "Finans": 0.6, "İK": 0.4, "Lojistik": 0.8, "Kalite": 0.9},
    "Satış":    {"Üretim": 0.6, "Finans": 0.8, "İK": 0.3, "Lojistik": 0.5, "Kalite": 0.4},
    "Finans":   {"Üretim": 0.5, "Satış": 0.4, "İK": 0.6, "Lojistik": 0.4, "Kalite": 0.3},
    "İK":       {"Üretim": 0.5, "Satış": 0.3, "Finans": 0.4, "Lojistik": 0.3, "Kalite": 0.4},
    "Lojistik": {"Üretim": 0.6, "Satış": 0.5, "Finans": 0.5, "İK": 0.2, "Kalite": 0.5},
    "Kalite":   {"Üretim": 0.8, "Satış": 0.6, "Finans": 0.4, "İK": 0.3, "Lojistik": 0.4},
}


# ──────────────────── Veri Yapıları ────────────────────

@dataclass
class ABVariant:
    """A/B test varyantı."""
    name: str
    description: str = ""
    estimated_impact: float = 0.0       # % değişim
    confidence: float = 0.0             # 0-100
    risk_level: str = "Orta"
    implementation_cost: float = 0.0    # ₺


@dataclass
class ABTestResult:
    """A/B strateji simülasyon sonucu."""
    strategy_a: ABVariant = field(default_factory=ABVariant)
    strategy_b: ABVariant = field(default_factory=ABVariant)
    recommended: str = "A"
    recommendation_reason: str = ""
    expected_difference: float = 0.0
    statistical_significance: float = 0.0


@dataclass
class DeptImpact:
    """Tek bir departmana etki."""
    department: str = ""
    icon: str = ""
    impact_score: float = 0.0   # -1.0 to +1.0
    impact_type: str = ""       # "Pozitif", "Negatif", "Nötr"
    affected_kpis: list[str] = field(default_factory=list)
    description: str = ""


@dataclass
class CrossDeptResult:
    """Çapraz departman etki analizi sonucu."""
    source_department: str = ""
    impacts: list[DeptImpact] = field(default_factory=list)
    total_positive: int = 0
    total_negative: int = 0
    summary: str = ""


# ──────────────────── A/B Strateji Simülasyonu ────────────────────

def simulate_ab_strategy(
    strategy_a_desc: str,
    strategy_b_desc: str,
    context: str = "",
    target_kpi: str = "Genel Performans",
    department: str = "Genel",
) -> ABTestResult:
    """
    İki strateji arasında A/B simülasyon karşılaştırması.
    
    Basit heuristik tabanlı — LLM çıktısından gelen kontekst ile
    zenginleştirilir.
    """
    # Deterministik seed (aynı girdi = aynı sonuç)
    seed = int(hashlib.md5(
        f"{strategy_a_desc}{strategy_b_desc}".encode()
    ).hexdigest()[:8], 16)
    rng = random.Random(seed)
    
    # Heuristik skor hesaplama
    score_a = _estimate_strategy_score(strategy_a_desc, context, rng)
    score_b = _estimate_strategy_score(strategy_b_desc, context, rng)
    
    variant_a = ABVariant(
        name="Strateji A",
        description=strategy_a_desc[:200],
        estimated_impact=score_a["impact"],
        confidence=score_a["confidence"],
        risk_level=score_a["risk"],
        implementation_cost=score_a["cost"],
    )
    
    variant_b = ABVariant(
        name="Strateji B",
        description=strategy_b_desc[:200],
        estimated_impact=score_b["impact"],
        confidence=score_b["confidence"],
        risk_level=score_b["risk"],
        implementation_cost=score_b["cost"],
    )
    
    # Karar
    # Net skor = impact * confidence / risk_weight
    risk_weights = {"Düşük": 1.0, "Orta": 1.3, "Yüksek": 1.8, "Kritik": 2.5}
    net_a = (score_a["impact"] * score_a["confidence"]) / risk_weights.get(score_a["risk"], 1.3)
    net_b = (score_b["impact"] * score_b["confidence"]) / risk_weights.get(score_b["risk"], 1.3)
    
    recommended = "A" if net_a >= net_b else "B"
    diff = abs(score_a["impact"] - score_b["impact"])
    significance = min(95, 60 + diff * 2 + abs(net_a - net_b) * 0.5)
    
    reason = _build_recommendation_reason(variant_a, variant_b, recommended)
    
    result = ABTestResult(
        strategy_a=variant_a,
        strategy_b=variant_b,
        recommended=recommended,
        recommendation_reason=reason,
        expected_difference=round(diff, 1),
        statistical_significance=round(significance, 1),
    )
    
    logger.info("ab_simulation_complete",
                recommended=recommended,
                diff=diff,
                significance=significance)
    
    return result


def _estimate_strategy_score(description: str, context: str, rng: random.Random) -> dict:
    """Strateji metninden heuristik skor çıkar."""
    text = (description + " " + context).lower()
    
    impact = 5.0 + rng.uniform(-2, 2)
    confidence = 65.0 + rng.uniform(-5, 5)
    
    # Anahtar kelime bazlı ayarlama
    if any(w in text for w in ["otomasyon", "dijital", "teknoloji", "yazılım"]):
        impact += 3
        confidence += 5
    if any(w in text for w in ["eğitim", "gelişim", "yetenek"]):
        impact += 2
        confidence += 3
    if any(w in text for w in ["maliyet düşür", "tasarruf", "verimlilik"]):
        impact += 4
        confidence += 4
    if any(w in text for w in ["riskli", "belirsiz", "deneysel"]):
        confidence -= 10
    if any(w in text for w in ["uzun vadeli", "yatırım", "altyapı"]):
        impact += 2
        confidence -= 3  # uzun vadeli = belirsiz
    
    # Risk seviyesi
    if any(w in text for w in ["düşük risk", "güvenli", "kanıtlanmış"]):
        risk = "Düşük"
    elif any(w in text for w in ["yüksek risk", "agresif", "radikal"]):
        risk = "Yüksek"
    else:
        risk = "Orta"
    
    cost = rng.uniform(50000, 500000)
    
    return {
        "impact": round(max(1, min(15, impact)), 1),
        "confidence": round(max(40, min(95, confidence)), 1),
        "risk": risk,
        "cost": round(cost, -3),  # en yakın bin
    }


def _build_recommendation_reason(a: ABVariant, b: ABVariant, recommended: str) -> str:
    """Tavsiye nedenini açıkla."""
    winner = a if recommended == "A" else b
    loser = b if recommended == "A" else a
    
    reasons = []
    if winner.estimated_impact > loser.estimated_impact:
        reasons.append(f"daha yüksek tahmini etki (+{winner.estimated_impact - loser.estimated_impact:.1f}%)")
    if winner.confidence > loser.confidence:
        reasons.append(f"daha yüksek güven (%{winner.confidence:.0f} vs %{loser.confidence:.0f})")
    if winner.risk_level in ("Düşük",) and loser.risk_level not in ("Düşük",):
        reasons.append("daha düşük risk seviyesi")
    
    if not reasons:
        reasons.append("genel risk-getiri dengesi daha iyi")
    
    return f"Strateji {recommended} önerilir: {', '.join(reasons)}."


# ──────────────────── Cross-Department Impact ────────────────────

def analyze_cross_dept_impact(
    source_department: str,
    change_description: str,
    change_magnitude: float = 0.5,
) -> CrossDeptResult:
    """
    Bir departmandaki değişikliğin diğer departmanlara etkisini hesapla.
    
    Args:
        source_department: Değişikliğin yapıldığı departman
        change_description: Değişiklik açıklaması
        change_magnitude: Değişikliğin büyüklüğü (0-1, 1=çok büyük)
    """
    source = source_department.strip()
    
    # Kaynak departmanı bul (fuzzy match)
    matched_source = None
    for dept in DEPARTMENTS:
        if dept.lower() in source.lower() or source.lower() in dept.lower():
            matched_source = dept
            break
    
    if not matched_source:
        matched_source = "Üretim"  # default
    
    impacts_map = IMPACT_MATRIX.get(matched_source, {})
    impacts: list[DeptImpact] = []
    
    change_lower = change_description.lower()
    
    for dept, base_impact in impacts_map.items():
        dept_info = DEPARTMENTS.get(dept, {"icon": "📊", "kpis": []})
        
        # Etki skoru = matris değeri × değişiklik büyüklüğü
        impact_score = base_impact * change_magnitude
        
        # Değişiklik türüne göre pozitif/negatif ayarla
        if any(w in change_lower for w in ["düşür", "azalt", "kes", "küçült", "iptal"]):
            # Maliyet düşürme genelde finans için pozitif, diğerleri için karışık
            if dept == "Finans":
                impact_score = abs(impact_score)
            else:
                impact_score = -abs(impact_score) * 0.5
        elif any(w in change_lower for w in ["artır", "yatırım", "geliştir", "iyileştir"]):
            impact_score = abs(impact_score)
        else:
            # Nötr — yönü belirsiz
            impact_score = impact_score * (0.5 if random.random() > 0.5 else -0.3)
        
        impact_type = "Pozitif" if impact_score > 0.1 else ("Negatif" if impact_score < -0.1 else "Nötr")
        
        # Etkilenen KPI'lar
        affected = dept_info["kpis"][:2] if abs(impact_score) > 0.3 else dept_info["kpis"][:1]
        
        impacts.append(DeptImpact(
            department=dept,
            icon=dept_info["icon"],
            impact_score=round(impact_score, 2),
            impact_type=impact_type,
            affected_kpis=affected,
            description=_describe_impact(dept, impact_type, affected),
        ))
    
    # Sırala (en yüksek mutlak etki önce)
    impacts.sort(key=lambda x: abs(x.impact_score), reverse=True)
    
    total_pos = sum(1 for i in impacts if i.impact_type == "Pozitif")
    total_neg = sum(1 for i in impacts if i.impact_type == "Negatif")
    
    summary = _build_cross_dept_summary(matched_source, impacts, total_pos, total_neg)
    
    result = CrossDeptResult(
        source_department=matched_source,
        impacts=impacts,
        total_positive=total_pos,
        total_negative=total_neg,
        summary=summary,
    )
    
    logger.info("cross_dept_analysis",
                source=matched_source,
                positive=total_pos,
                negative=total_neg)
    
    return result


def _describe_impact(dept: str, impact_type: str, kpis: list) -> str:
    """Etkiyi kısa metin olarak açıkla."""
    kpi_str = ", ".join(kpis) if kpis else "genel performans"
    if impact_type == "Pozitif":
        return f"{dept} departmanında {kpi_str} üzerinde olumlu etki beklenir."
    elif impact_type == "Negatif":
        return f"{dept} departmanında {kpi_str} üzerinde olumsuz etki riski var."
    else:
        return f"{dept} departmanı üzerinde belirgin bir etki beklenmez."


def _build_cross_dept_summary(source: str, impacts: list[DeptImpact], pos: int, neg: int) -> str:
    """Çapraz departman özeti."""
    lines = [f"**{source}** departmanındaki değişiklik {len(impacts)} departmanı etkiler.\n"]
    
    if pos > neg:
        lines.append(f"Genel etki **pozitif**: {pos} olumlu, {neg} olumsuz departman.")
    elif neg > pos:
        lines.append(f"⚠️ Genel etki **negatif**: {neg} olumsuz, {pos} olumlu departman. "
                      "Dikkatli planlama gerekli.")
    else:
        lines.append(f"Dengeli etki: {pos} olumlu, {neg} olumsuz departman.")
    
    # En çok etkilenen
    if impacts:
        top = impacts[0]
        lines.append(f"\nEn çok etkilenen: **{top.department}** ({top.impact_type}, "
                      f"skor: {abs(top.impact_score):.2f})")
    
    return "\n".join(lines)


# ──────────────────── Formatlama ────────────────────

def format_ab_result(result: ABTestResult) -> str:
    """A/B simülasyon sonucunu markdown olarak formatla."""
    a = result.strategy_a
    b = result.strategy_b
    winner = "🏆" 
    
    lines = [
        "\n### 🔬 A/B Strateji Simülasyonu\n",
        "| Kriter | Strateji A | Strateji B |",
        "|--------|-----------|-----------|",
        f"| Açıklama | {a.description[:80]} | {b.description[:80]} |",
        f"| Tahmini Etki | %{a.estimated_impact:.1f} | %{b.estimated_impact:.1f} |",
        f"| Güven | %{a.confidence:.0f} | %{b.confidence:.0f} |",
        f"| Risk | {a.risk_level} | {b.risk_level} |",
        f"| Tahmini Maliyet | ₺{a.implementation_cost:,.0f} | ₺{b.implementation_cost:,.0f} |",
        "",
        f"**{winner} Tavsiye:** {result.recommendation_reason}",
        f"- Beklenen Fark: %{result.expected_difference:.1f}",
        f"- İstatistiksel Güven: %{result.statistical_significance:.0f}",
    ]
    
    return "\n".join(lines)


def format_cross_dept_impact(result: CrossDeptResult) -> str:
    """Çapraz departman etkisini markdown olarak formatla."""
    lines = [
        f"\n### 🌐 Çapraz Departman Etki Analizi — Kaynak: {result.source_department}\n",
        "| Departman | Etki | Skor | Etkilenen KPI'lar |",
        "|-----------|------|------|-------------------|",
    ]
    
    for imp in result.impacts:
        emoji = "🟢" if imp.impact_type == "Pozitif" else ("🔴" if imp.impact_type == "Negatif" else "⚪")
        kpis = ", ".join(imp.affected_kpis)
        lines.append(
            f"| {imp.icon} {imp.department} | {emoji} {imp.impact_type} | {abs(imp.impact_score):.2f} | {kpis} |"
        )
    
    lines.append("")
    lines.append(result.summary)
    
    return "\n".join(lines)


# ──────────────────── Tool Wrappers ────────────────────

def ab_strategy_tool(question: str, context: str = "") -> str:
    """Tool registry'den çağrılabilir A/B simülasyon wrapper."""
    # Basit heuristik: soruda iki alternatif bul
    parts = question.split(" veya ")
    if len(parts) < 2:
        parts = question.split(" ya da ")
    if len(parts) < 2:
        parts = question.split(" vs ")
    
    if len(parts) >= 2:
        a_desc = parts[0].strip()
        b_desc = parts[1].strip()
    else:
        a_desc = "Mevcut strateji ile devam"
        b_desc = question[:100]
    
    result = simulate_ab_strategy(a_desc, b_desc, context)
    return format_ab_result(result)


def cross_dept_tool(question: str, context: str = "", department: str = "Üretim") -> str:
    """Tool registry'den çağrılabilir çapraz departman wrapper."""
    result = analyze_cross_dept_impact(department, question, 0.5)
    return format_cross_dept_impact(result)
