"""Risk & Maliyet Analizi Modülü

- FMEA (Failure Mode & Effect Analysis)
- Risk matrisi (5×5 olasılık × etki)
- Operasyonel risk sınıflandırması
- Maliyet kırılım analizi
- What-if senaryoları
- Trend bazlı maliyet tahmini
"""

import numpy as np
from dataclasses import dataclass, field
from typing import Optional
import structlog

logger = structlog.get_logger(__name__)


# ══════════════════════════════════════════════════════════════
# 1. RİSK MATRİSİ (5×5)
# ══════════════════════════════════════════════════════════════

RISK_MATRIX_5x5 = {
    (5, 5): ("Kritik", 25, "🔴 Acil müdahale — durdurun ve çözün"),
    (5, 4): ("Kritik", 20, "🔴 Acil aksiyon planı hazırla"),
    (4, 5): ("Kritik", 20, "🔴 Acil aksiyon planı hazırla"),
    (5, 3): ("Yüksek", 15, "🟠 Üst yönetim bilgilendir, 1 hafta içinde çöz"),
    (4, 4): ("Yüksek", 16, "🟠 Üst yönetim bilgilendir, 1 hafta içinde çöz"),
    (3, 5): ("Yüksek", 15, "🟠 Üst yönetim bilgilendir, 1 hafta içinde çöz"),
    (5, 2): ("Yüksek", 10, "🟠 Yakın takip"),
    (4, 3): ("Yüksek", 12, "🟠 Yakın takip"),
    (3, 4): ("Yüksek", 12, "🟠 Yakın takip"),
    (2, 5): ("Yüksek", 10, "🟠 Yakın takip"),
    (5, 1): ("Orta", 5, "🟡 Rutin takip"),
    (4, 2): ("Orta", 8, "🟡 Planlanmış iyileştirme"),
    (3, 3): ("Orta", 9, "🟡 Planlanmış iyileştirme"),
    (2, 4): ("Orta", 8, "🟡 Planlanmış iyileştirme"),
    (1, 5): ("Orta", 5, "🟡 İzle"),
    (4, 1): ("Düşük", 4, "🟢 Periyodik gözden geçirme"),
    (3, 2): ("Düşük", 6, "🟢 Periyodik gözden geçirme"),
    (2, 3): ("Düşük", 6, "🟢 Periyodik gözden geçirme"),
    (1, 4): ("Düşük", 4, "🟢 Periyodik gözden geçirme"),
    (3, 1): ("Düşük", 3, "🟢 Kabul edilebilir"),
    (2, 2): ("Düşük", 4, "🟢 Kabul edilebilir"),
    (1, 3): ("Düşük", 3, "🟢 Kabul edilebilir"),
    (2, 1): ("Düşük", 2, "🟢 Kabul edilebilir"),
    (1, 2): ("Düşük", 2, "🟢 Kabul edilebilir"),
    (1, 1): ("Düşük", 1, "🟢 Kabul edilebilir"),
}

PROBABILITY_SCALE = {
    1: "Çok Düşük (<%5 olasılık — yılda 1'den az)",
    2: "Düşük (%5-15 — yılda 1-2 kez)",
    3: "Orta (%15-40 — çeyrekte 1-2 kez)",
    4: "Yüksek (%40-70 — ayda 1-2 kez)",
    5: "Çok Yüksek (>%70 — haftada 1+)",
}

IMPACT_SCALE = {
    1: "Önemsiz (<%1 gelir etkisi, operasyon durmuyor)",
    2: "Küçük (%1-3 gelir etkisi, kısmen etkileniyor)",
    3: "Orta (%3-10 gelir etkisi, gecikme/kalite kaybı)",
    4: "Büyük (%10-25 gelir etkisi, ciddi operasyon aksaması)",
    5: "Felaket (>%25 gelir etkisi, iş sürekliliği tehlikede)",
}


# ══════════════════════════════════════════════════════════════
# 2. TEKSTİL OPERASYONEL RİSK KATEGORİLERİ
# ══════════════════════════════════════════════════════════════

OPERATIONAL_RISKS = {
    "tedarik_zinciri": {
        "name": "Tedarik Zinciri Riskleri",
        "risks": [
            {"risk": "Pamuk fiyat dalgalanması", "default_p": 4, "default_i": 4, "mitigation": "Vadeli alım kontratları, alternatif elyaf karışımları"},
            {"risk": "Tedarikçi gecikmesi", "default_p": 3, "default_i": 3, "mitigation": "Çoklu tedarikçi politikası, emniyet stoku"},
            {"risk": "Kalite uyumsuzluğu (hammadde)", "default_p": 3, "default_i": 3, "mitigation": "Gelen mal kalite kontrol, tedarikçi audit"},
            {"risk": "Nakliye/lojistik aksaklığı", "default_p": 2, "default_i": 3, "mitigation": "Alternatif rota planı, stok tamponu"},
        ],
    },
    "uretim": {
        "name": "Üretim Riskleri",
        "risks": [
            {"risk": "Kritik makine arızası", "default_p": 3, "default_i": 4, "mitigation": "Preventive maintenance, yedek parça stoku"},
            {"risk": "Yüksek fire oranı", "default_p": 3, "default_i": 3, "mitigation": "SPC, poka-yoke, inline kalite kontrol"},
            {"risk": "İşgücü eksikliği", "default_p": 4, "default_i": 3, "mitigation": "Çapraz eğitim, otomasyon yatırımı"},
            {"risk": "Kapasite yetersizliği (pik sezon)", "default_p": 4, "default_i": 4, "mitigation": "Kapasite planlama, fason anlaşmaları"},
            {"risk": "Enerji kesintisi", "default_p": 2, "default_i": 5, "mitigation": "Jeneratör, UPS, enerji yedekleme"},
        ],
    },
    "pazar": {
        "name": "Pazar/Satış Riskleri",
        "risks": [
            {"risk": "Sipariş iptali", "default_p": 3, "default_i": 4, "mitigation": "Müşteri çeşitlendirme, depozito politikası"},
            {"risk": "Kur riski (ihracat)", "default_p": 4, "default_i": 3, "mitigation": "Forward kontrat, doğal hedge (ithalat-ihracat dengesi)"},
            {"risk": "Müşteri kaybı", "default_p": 2, "default_i": 4, "mitigation": "CRM, kalite tutarlılığı, fiyat rekabeti"},
            {"risk": "Yeni rakip/fiyat baskısı", "default_p": 3, "default_i": 3, "mitigation": "Katma değerli ürün, marka yatırımı"},
        ],
    },
    "regulasyon": {
        "name": "Regülasyon/Uyum Riskleri",
        "risks": [
            {"risk": "Çevre mevzuatı değişikliği", "default_p": 3, "default_i": 3, "mitigation": "Proaktif yatırım, atıksu arıtma iyileştirme"},
            {"risk": "İş güvenliği ihlali", "default_p": 2, "default_i": 4, "mitigation": "İSG eğitimi, risk değerlendirme, PPE"},
            {"risk": "REACH/OEKO-TEX uyumsuzluk", "default_p": 2, "default_i": 4, "mitigation": "Tedarikçi kimyasal yönetimi, MRSL listesi"},
        ],
    },
    "finansal": {
        "name": "Finansal Riskler",
        "risks": [
            {"risk": "Nakit akış sıkışıklığı", "default_p": 3, "default_i": 4, "mitigation": "Alacak takibi, faktoring, bütçe disiplini"},
            {"risk": "Faiz oranı artışı", "default_p": 3, "default_i": 3, "mitigation": "Sabit faizli kredi, borç/özsermaye dengeleme"},
            {"risk": "Müşteri batık alacak", "default_p": 2, "default_i": 4, "mitigation": "Kredi limiti, sigorta, referans kontrolü"},
        ],
    },
}


# ══════════════════════════════════════════════════════════════
# 3. FMEA
# ══════════════════════════════════════════════════════════════

@dataclass
class FMEAItem:
    failure_mode: str
    effect: str
    cause: str
    severity: int  # 1-10
    occurrence: int  # 1-10
    detection: int  # 1-10
    recommended_action: str
    
    @property
    def rpn(self) -> int:
        """Risk Priority Number = S × O × D"""
        return self.severity * self.occurrence * self.detection
    
    @property
    def priority(self) -> str:
        rpn = self.rpn
        if rpn >= 200:
            return "Kritik — Acil aksiyon"
        elif rpn >= 120:
            return "Yüksek — Kısa vadede çöz"
        elif rpn >= 60:
            return "Orta — Planlı iyileştirme"
        return "Düşük — İzle"


TEXTILE_FMEA_TEMPLATES = [
    FMEAItem("Çözgü kopuşu", "Üretim durması, fire artışı", "Çözgü gerginlik ayarı hatalı", 6, 5, 3, "Otomatik gerginlik kontrol sistemi"),
    FMEAItem("Renk farkı (parti içi)", "Müşteri reddi, maliyet", "Boya reçetesi sapması", 8, 4, 4, "Spektrofotometre ile online kontrol"),
    FMEAItem("Kumaş deformasyonu", "Kalite ret, fire", "Ram sıcaklık/hız ayarı yanlış", 7, 3, 4, "PLC ile otomatik kontrol, alarm sistemi"),
    FMEAItem("İğne kırılması (dikim)", "Kalite hatası, güvenlik riski", "Yanlış iğne numarası, yıpranma", 9, 4, 5, "İğne değişim takvimleri, metal dedektör"),
    FMEAItem("Kesim hatası", "Fire artışı, malzeme kaybı", "Pastal planı hatası, bıçak körlüğü", 6, 4, 3, "CAD/CAM optimizasyon, otomatik kesim"),
    FMEAItem("Boyama sonrası leke", "İkinci kalite, indirimli satış", "Su kalitesi, kimyasal kontaminasyon", 7, 3, 5, "Su arıtma bakımı, makine temizlik SOP"),
    FMEAItem("Dikiş mukavemet yetersizliği", "Müşteri iadesi", "Yanlış iplik, gerginlik ayarı", 8, 3, 4, "Standart iş prosedürü, çekme testi"),
    FMEAItem("Çekme/boy oynama", "Müşteri şikayeti", "Yetersiz sanfor, ön yıkama eksik", 7, 4, 3, "Yıkama testi %100 uygulama"),
]


# ══════════════════════════════════════════════════════════════
# 4. FONKSİYONLAR
# ══════════════════════════════════════════════════════════════

def assess_risk(probability: int, impact: int) -> dict:
    """5×5 risk matrisi ile risk değerlendir."""
    p = max(1, min(5, probability))
    i = max(1, min(5, impact))
    
    level, score, action = RISK_MATRIX_5x5.get((p, i), ("Bilinmiyor", 0, ""))
    
    return {
        "probability": p,
        "probability_desc": PROBABILITY_SCALE.get(p, ""),
        "impact": i,
        "impact_desc": IMPACT_SCALE.get(i, ""),
        "risk_score": score,
        "risk_level": level,
        "recommended_action": action,
    }


def risk_heatmap(risks: list[dict]) -> dict:
    """Birden fazla risk için ısı haritası özeti oluştur.
    
    risks: [{"name": "...", "probability": 3, "impact": 4}, ...]
    """
    matrix = np.zeros((5, 5), dtype=int)
    assessed = []
    
    for risk in risks:
        p = risk.get("probability", 3)
        i = risk.get("impact", 3)
        result = assess_risk(p, i)
        result["name"] = risk.get("name", "Bilinmeyen Risk")
        assessed.append(result)
        matrix[5 - p][i - 1] += 1
    
    # Seviye dağılımı
    distribution = {"Kritik": 0, "Yüksek": 0, "Orta": 0, "Düşük": 0}
    for r in assessed:
        level = r["risk_level"]
        if level in distribution:
            distribution[level] += 1
    
    # Sıralama (yüksek risk önce)
    assessed.sort(key=lambda x: x["risk_score"], reverse=True)
    
    return {
        "risks": assessed,
        "distribution": distribution,
        "total_risks": len(risks),
        "top_3_risks": assessed[:3],
        "average_risk_score": round(np.mean([r["risk_score"] for r in assessed]), 1),
    }


def fmea_analysis(items: list[FMEAItem] = None) -> dict:
    """FMEA analiz özeti oluştur."""
    if items is None:
        items = TEXTILE_FMEA_TEMPLATES
    
    results = []
    for item in items:
        results.append({
            "failure_mode": item.failure_mode,
            "effect": item.effect,
            "cause": item.cause,
            "S": item.severity,
            "O": item.occurrence,
            "D": item.detection,
            "RPN": item.rpn,
            "priority": item.priority,
            "recommended_action": item.recommended_action,
        })
    
    # RPN sıralı
    results.sort(key=lambda x: x["RPN"], reverse=True)
    
    return {
        "items": results,
        "total_items": len(results),
        "critical_items": [r for r in results if r["RPN"] >= 200],
        "high_items": [r for r in results if 120 <= r["RPN"] < 200],
        "average_rpn": round(np.mean([r["RPN"] for r in results]), 1),
        "max_rpn": max(r["RPN"] for r in results),
    }


def get_operational_risks(category: str = None) -> dict:
    """Operasyonel risk kategorisini getir."""
    if category:
        cat_lower = category.lower().replace(" ", "_")
        for key, val in OPERATIONAL_RISKS.items():
            if cat_lower in key or cat_lower in val["name"].lower():
                return val
    return OPERATIONAL_RISKS


def cost_analysis(revenue: float, costs: dict, department: str = "konfeksiyon") -> dict:
    """Maliyet kırılım analizi yap.
    
    costs: {"hammadde": 100000, "iscilik": 60000, "enerji": 15000, ...}
    """
    total_cost = sum(costs.values())
    gross_profit = revenue - total_cost
    gross_margin = (gross_profit / revenue * 100) if revenue > 0 else 0
    
    breakdown = []
    for category, amount in sorted(costs.items(), key=lambda x: x[1], reverse=True):
        share_pct = (amount / total_cost * 100) if total_cost > 0 else 0
        breakdown.append({
            "category": category,
            "amount": amount,
            "share_pct": round(share_pct, 1),
        })
    
    # Benchmark ile karşılaştırma
    from app.core.textile_knowledge import COST_BREAKDOWN_TEMPLATE
    template = COST_BREAKDOWN_TEMPLATE.get(department.lower(), {})
    deviations = []
    
    for item in breakdown:
        cat = item["category"]
        if cat in template:
            expected = template[cat]["share"]
            actual = item["share_pct"]
            deviation = actual - expected
            if abs(deviation) > 3:  # %3'ten fazla sapma
                direction = "yüksek" if deviation > 0 else "düşük"
                deviations.append({
                    "category": cat,
                    "actual_pct": actual,
                    "expected_pct": expected,
                    "deviation": round(deviation, 1),
                    "note": f"{cat} sektör ortalamasından {abs(deviation):.1f} puan {direction}",
                })
    
    return {
        "revenue": revenue,
        "total_cost": total_cost,
        "gross_profit": gross_profit,
        "gross_margin_pct": round(gross_margin, 1),
        "breakdown": breakdown,
        "deviations": deviations,
        "status": "İyi" if gross_margin > 20 else "Normal" if gross_margin > 10 else "Düşük",
    }


def what_if_scenario(base_costs: dict, scenarios: list[dict]) -> list[dict]:
    """What-if maliyet senaryoları.
    
    scenarios: [
        {"name": "Pamuk %20 artarsa", "changes": {"hammadde": 1.20}},
        {"name": "Enerji %15 artarsa", "changes": {"enerji": 1.15}},
    ]
    """
    base_total = sum(base_costs.values())
    results = []
    
    for scenario in scenarios:
        adjusted = {}
        for cat, amount in base_costs.items():
            multiplier = scenario.get("changes", {}).get(cat, 1.0)
            adjusted[cat] = amount * multiplier
        
        new_total = sum(adjusted.values())
        impact = new_total - base_total
        impact_pct = (impact / base_total * 100) if base_total > 0 else 0
        
        results.append({
            "scenario": scenario["name"],
            "base_total": round(base_total, 2),
            "new_total": round(new_total, 2),
            "impact": round(impact, 2),
            "impact_pct": round(impact_pct, 1),
            "severity": "Kritik" if impact_pct > 10 else "Yüksek" if impact_pct > 5 else "Orta" if impact_pct > 2 else "Düşük",
        })
    
    return results


def build_risk_report_prompt(risks: list[dict]) -> str:
    """Risk raporu için LLM prompt'u oluştur."""
    heatmap = risk_heatmap(risks)
    
    prompt_parts = [
        "## Risk Analiz Özeti",
        f"Toplam {heatmap['total_risks']} risk değerlendirildi.",
        f"Ortalama risk skoru: {heatmap['average_risk_score']}/25",
        "",
        "### Dağılım:",
    ]
    
    for level, count in heatmap["distribution"].items():
        if count > 0:
            prompt_parts.append(f"- {level}: {count} adet")
    
    prompt_parts.append("")
    prompt_parts.append("### Öncelikli Riskler:")
    
    for risk in heatmap["top_3_risks"]:
        prompt_parts.append(
            f"- **{risk['name']}** — Skor: {risk['risk_score']}, "
            f"Seviye: {risk['risk_level']}, Aksiyon: {risk['recommended_action']}"
        )
    
    return "\n".join(prompt_parts)
