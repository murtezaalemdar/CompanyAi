"""Executive Health Index — Şirket Sağlık Skoru v1.0

CEO sorusu: "Şirket sağlık skoru kaç?"

Tek bir bileşik skor (0-100) ile şirketin genel durumunu özetler.

4 Ana Boyut:
1. Financial Stability Score    — Finansal sağlamlık
2. Operational Efficiency Score — Operasyonel verimlilik
3. Growth Momentum Score        — Büyüme ivmesi
4. Risk Exposure Score          — Risk maruziyet

Toplam: Enterprise Health Score (0-100)
"""

from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime
import structlog

logger = structlog.get_logger()


# ══════════════════════════════════════════════════════════════
# VERİ MODELLERİ
# ══════════════════════════════════════════════════════════════

@dataclass
class DimensionScore:
    """Bir boyutun puanı ve detayı."""
    name: str
    score: float               # 0-100
    weight: float              # Toplam ağırlıktaki payı
    grade: str                 # A+, A, B+, B, C+, C, D, F
    color: str                 # 🟢 🟡 🟠 🔴
    indicators: list = field(default_factory=list)   # Alt göstergeler
    trend: str = "stable"      # improving, stable, declining
    description: str = ""


@dataclass
class HealthIndex:
    """Bileşik şirket sağlık endeksi."""
    overall_score: float       # 0-100
    overall_grade: str
    overall_color: str
    overall_status: str        # "Mükemmel", "İyi", "Orta", "Zayıf", "Kritik"
    dimensions: list           # DimensionScore listesi
    timestamp: str = ""
    recommendations: list = field(default_factory=list)
    executive_summary: str = ""


# ══════════════════════════════════════════════════════════════
# BOYUT AĞIRLIKLARI & GRADING
# ══════════════════════════════════════════════════════════════

DIMENSION_WEIGHTS = {
    "financial": 0.30,
    "operational": 0.25,
    "growth": 0.25,
    "risk": 0.20,
}

def _grade(score: float) -> tuple[str, str]:
    """Skoru harf notuna ve renge çevir."""
    if score >= 95: return "A+", "🟢"
    if score >= 85: return "A", "🟢"
    if score >= 75: return "B+", "🟢"
    if score >= 65: return "B", "🟡"
    if score >= 55: return "C+", "🟡"
    if score >= 45: return "C", "🟠"
    if score >= 35: return "D", "🟠"
    return "F", "🔴"


def _status(score: float) -> str:
    """Genel durum etiketi."""
    if score >= 85: return "Mükemmel"
    if score >= 70: return "İyi"
    if score >= 55: return "Orta"
    if score >= 40: return "Zayıf"
    return "Kritik"


# ══════════════════════════════════════════════════════════════
# BOYUT HESAPLAYICILARI
# ══════════════════════════════════════════════════════════════

def _calc_financial(data: dict) -> DimensionScore:
    """
    Finansal Sağlamlık Skoru.
    
    Göstergeler:
    - brut_kar_marji (%)
    - favok_marji (%)
    - cari_oran (x)
    - borc_ozsermaye (x)
    - nakit_cevrim_gun (gün)
    - gelir_buyume (%)
    """
    indicators = []
    scores = []
    
    # Brüt Kâr Marjı
    bkm = data.get("brut_kar_marji")
    if bkm is not None:
        s = min(100, max(0, bkm * 2.5))  # %40+ = 100
        if bkm < 15:
            s = max(0, bkm * 2)
        indicators.append({"name": "Brüt Kâr Marjı", "value": f"%{bkm:.1f}", "score": round(s, 1)})
        scores.append(s)
    
    # FAVÖK Marjı
    favok = data.get("favok_marji")
    if favok is not None:
        s = min(100, max(0, favok * 5))  # %20+ = 100
        indicators.append({"name": "FAVÖK Marjı", "value": f"%{favok:.1f}", "score": round(s, 1)})
        scores.append(s)
    
    # Cari Oran
    cari = data.get("cari_oran")
    if cari is not None:
        if cari >= 2.0:
            s = 100
        elif cari >= 1.5:
            s = 80 + (cari - 1.5) * 40
        elif cari >= 1.0:
            s = 50 + (cari - 1.0) * 60
        else:
            s = max(0, cari * 50)
        indicators.append({"name": "Cari Oran", "value": f"{cari:.2f}x", "score": round(s, 1)})
        scores.append(s)
    
    # Borç/Özsermaye
    bos = data.get("borc_ozsermaye")
    if bos is not None:
        if bos <= 0.5:
            s = 100
        elif bos <= 1.0:
            s = 80 - (bos - 0.5) * 40
        elif bos <= 2.0:
            s = 60 - (bos - 1.0) * 30
        else:
            s = max(0, 30 - (bos - 2.0) * 15)
        indicators.append({"name": "Borç/Özsermaye", "value": f"{bos:.2f}x", "score": round(s, 1)})
        scores.append(s)
    
    # Nakit Çevrim Süresi
    ncs = data.get("nakit_cevrim_gun")
    if ncs is not None:
        if ncs <= 30:
            s = 100
        elif ncs <= 60:
            s = 80 - (ncs - 30) * 0.67
        elif ncs <= 90:
            s = 60 - (ncs - 60) * 0.67
        else:
            s = max(0, 40 - (ncs - 90) * 0.5)
        indicators.append({"name": "Nakit Çevrim Süresi", "value": f"{ncs:.0f} gün", "score": round(s, 1)})
        scores.append(s)
    
    # Gelir Büyümesi
    gb = data.get("gelir_buyume")
    if gb is not None:
        if gb >= 20:
            s = 100
        elif gb >= 10:
            s = 70 + (gb - 10) * 3
        elif gb >= 0:
            s = 40 + gb * 3
        else:
            s = max(0, 40 + gb * 2)
        indicators.append({"name": "Gelir Büyümesi", "value": f"%{gb:.1f}", "score": round(s, 1)})
        scores.append(s)
    
    score = sum(scores) / len(scores) if scores else 50
    grade, color = _grade(score)
    
    # Trend (basit — gelir büyümesine göre)
    trend = "stable"
    if gb is not None:
        if gb > 5:
            trend = "improving"
        elif gb < -5:
            trend = "declining"
    
    return DimensionScore(
        name="Finansal Sağlamlık",
        score=round(score, 1),
        weight=DIMENSION_WEIGHTS["financial"],
        grade=grade,
        color=color,
        indicators=indicators,
        trend=trend,
        description="Karlılık, likidite ve borç yapısı değerlendirmesi",
    )


def _calc_operational(data: dict) -> DimensionScore:
    """
    Operasyonel Verimlilik Skoru.
    
    Göstergeler:
    - oee (%)
    - fire_orani (%)
    - hat_verimliligi (%)
    - durus_orani (%)
    - isk_devir (%)
    - zamaninda_teslimat (%)
    """
    indicators = []
    scores = []
    
    # OEE
    oee = data.get("oee")
    if oee is not None:
        if oee >= 85:
            s = 100
        elif oee >= 70:
            s = 60 + (oee - 70) * 2.67
        elif oee >= 55:
            s = 30 + (oee - 55) * 2
        else:
            s = max(0, oee * 0.55)
        indicators.append({"name": "OEE", "value": f"%{oee:.1f}", "score": round(s, 1)})
        scores.append(s)
    
    # Fire Oranı (lower is better)
    fire = data.get("fire_orani")
    if fire is not None:
        if fire <= 2:
            s = 100
        elif fire <= 5:
            s = 70 + (5 - fire) * 10
        elif fire <= 10:
            s = 30 + (10 - fire) * 8
        else:
            s = max(0, 30 - (fire - 10) * 3)
        indicators.append({"name": "Fire Oranı", "value": f"%{fire:.1f}", "score": round(s, 1)})
        scores.append(s)
    
    # Hat Verimliliği
    hv = data.get("hat_verimliligi")
    if hv is not None:
        s = min(100, max(0, (hv - 50) * 2))
        indicators.append({"name": "Hat Verimliliği", "value": f"%{hv:.1f}", "score": round(s, 1)})
        scores.append(s)
    
    # Duruş Oranı (lower is better)
    do = data.get("durus_orani")
    if do is not None:
        if do <= 5:
            s = 100
        elif do <= 10:
            s = 70 + (10 - do) * 6
        elif do <= 20:
            s = 30 + (20 - do) * 4
        else:
            s = max(0, 30 - (do - 20) * 2)
        indicators.append({"name": "Duruş Oranı", "value": f"%{do:.1f}", "score": round(s, 1)})
        scores.append(s)
    
    # İşgücü Devir Hızı (lower is better)
    isk = data.get("isk_devir")
    if isk is not None:
        if isk <= 5:
            s = 100
        elif isk <= 15:
            s = 60 + (15 - isk) * 4
        elif isk <= 30:
            s = 20 + (30 - isk) * 2.67
        else:
            s = max(0, 20 - (isk - 30) * 1)
        indicators.append({"name": "İşgücü Devir Hızı", "value": f"%{isk:.1f}", "score": round(s, 1)})
        scores.append(s)
    
    # Zamanında Teslimat
    zt = data.get("zamaninda_teslimat")
    if zt is not None:
        s = min(100, max(0, (zt - 60) * 2.5))
        indicators.append({"name": "Zamanında Teslimat", "value": f"%{zt:.1f}", "score": round(s, 1)})
        scores.append(s)
    
    score = sum(scores) / len(scores) if scores else 50
    grade, color = _grade(score)
    
    return DimensionScore(
        name="Operasyonel Verimlilik",
        score=round(score, 1),
        weight=DIMENSION_WEIGHTS["operational"],
        grade=grade,
        color=color,
        indicators=indicators,
        trend="stable",
        description="Üretim performansı, fire, duruş ve teslimat değerlendirmesi",
    )


def _calc_growth(data: dict) -> DimensionScore:
    """
    Büyüme İvmesi Skoru.
    
    Göstergeler:
    - satis_buyume (%)
    - musteri_sayisi_degisim (%)
    - yeni_urun_orani (%)
    - pazar_payi_degisim (%)
    - yatirim_orani (%)
    - ar_ge_harcama_orani (%)
    """
    indicators = []
    scores = []
    
    # Satış Büyümesi
    sb = data.get("satis_buyume")
    if sb is not None:
        if sb >= 20:
            s = 100
        elif sb >= 10:
            s = 60 + (sb - 10) * 4
        elif sb >= 0:
            s = 30 + sb * 3
        else:
            s = max(0, 30 + sb * 2)
        indicators.append({"name": "Satış Büyümesi", "value": f"%{sb:.1f}", "score": round(s, 1)})
        scores.append(s)
    
    # Müşteri Sayısı Değişimi
    md = data.get("musteri_sayisi_degisim")
    if md is not None:
        if md >= 15:
            s = 100
        elif md >= 5:
            s = 60 + (md - 5) * 4
        elif md >= 0:
            s = 40 + md * 4
        else:
            s = max(0, 40 + md * 3)
        indicators.append({"name": "Müşteri Değişimi", "value": f"%{md:+.1f}", "score": round(s, 1)})
        scores.append(s)
    
    # Yeni Ürün Oranı
    yuo = data.get("yeni_urun_orani")
    if yuo is not None:
        s = min(100, max(0, yuo * 4))  # %25+ = 100
        indicators.append({"name": "Yeni Ürün Oranı", "value": f"%{yuo:.1f}", "score": round(s, 1)})
        scores.append(s)
    
    # Pazar Payı Değişimi
    ppd = data.get("pazar_payi_degisim")
    if ppd is not None:
        if ppd >= 5:
            s = 100
        elif ppd >= 0:
            s = 50 + ppd * 10
        else:
            s = max(0, 50 + ppd * 10)
        indicators.append({"name": "Pazar Payı Değişimi", "value": f"%{ppd:+.1f}", "score": round(s, 1)})
        scores.append(s)
    
    # Yatırım Oranı
    yo = data.get("yatirim_orani")
    if yo is not None:
        s = min(100, max(0, yo * 6.67))  # %15+ = 100
        indicators.append({"name": "Yatırım Oranı", "value": f"%{yo:.1f}", "score": round(s, 1)})
        scores.append(s)
    
    # AR-GE Harcama
    arge = data.get("ar_ge_harcama_orani")
    if arge is not None:
        s = min(100, max(0, arge * 20))  # %5+ = 100
        indicators.append({"name": "AR-GE Harcama", "value": f"%{arge:.1f}", "score": round(s, 1)})
        scores.append(s)
    
    score = sum(scores) / len(scores) if scores else 50
    grade, color = _grade(score)
    
    trend = "stable"
    if sb is not None:
        if sb > 10:
            trend = "improving"
        elif sb < -5:
            trend = "declining"
    
    return DimensionScore(
        name="Büyüme İvmesi",
        score=round(score, 1),
        weight=DIMENSION_WEIGHTS["growth"],
        grade=grade,
        color=color,
        indicators=indicators,
        trend=trend,
        description="Satış büyümesi, müşteri kazanımı ve yatırım değerlendirmesi",
    )


def _calc_risk(data: dict) -> DimensionScore:
    """
    Risk Maruziyet Skoru (100 = düşük risk = iyi).
    
    Göstergeler:
    - musteri_yogunlasma (%) — en büyük müşterinin payı
    - tedarikci_bagimliligi (%) — tek tedarikçi payı
    - stok_devir_hizi (x)
    - alacak_gun (gün)
    - is_kazasi_orani (%)
    - regulasyon_uyum (%)
    """
    indicators = []
    scores = []
    
    # Müşteri Yoğunlaşma (düşük = iyi)
    my = data.get("musteri_yogunlasma")
    if my is not None:
        if my <= 10:
            s = 100
        elif my <= 25:
            s = 70 + (25 - my) * 2
        elif my <= 50:
            s = 30 + (50 - my) * 1.6
        else:
            s = max(0, 30 - (my - 50) * 0.6)
        indicators.append({"name": "Müşteri Yoğunlaşma Riski", "value": f"%{my:.0f}", "score": round(s, 1)})
        scores.append(s)
    
    # Tedarikçi Bağımlılığı (düşük = iyi)
    tb = data.get("tedarikci_bagimliligi")
    if tb is not None:
        if tb <= 15:
            s = 100
        elif tb <= 30:
            s = 70 + (30 - tb) * 2
        elif tb <= 60:
            s = 30 + (60 - tb) * 1.33
        else:
            s = max(0, 30 - (tb - 60) * 0.75)
        indicators.append({"name": "Tedarikçi Bağımlılığı", "value": f"%{tb:.0f}", "score": round(s, 1)})
        scores.append(s)
    
    # Stok Devir Hızı (higher = better)
    sdh = data.get("stok_devir_hizi")
    if sdh is not None:
        if sdh >= 8:
            s = 100
        elif sdh >= 5:
            s = 60 + (sdh - 5) * 13.3
        elif sdh >= 2:
            s = 20 + (sdh - 2) * 13.3
        else:
            s = max(0, sdh * 10)
        indicators.append({"name": "Stok Devir Hızı", "value": f"{sdh:.1f}x", "score": round(s, 1)})
        scores.append(s)
    
    # Alacak Gün (düşük = iyi)
    ag = data.get("alacak_gun")
    if ag is not None:
        if ag <= 30:
            s = 100
        elif ag <= 60:
            s = 70 + (60 - ag) * 1
        elif ag <= 90:
            s = 40 + (90 - ag) * 1
        else:
            s = max(0, 40 - (ag - 90) * 0.67)
        indicators.append({"name": "Alacak Tahsil Süresi", "value": f"{ag:.0f} gün", "score": round(s, 1)})
        scores.append(s)
    
    # İş Kazası Oranı (düşük = iyi)
    iko = data.get("is_kazasi_orani")
    if iko is not None:
        if iko <= 0.5:
            s = 100
        elif iko <= 2:
            s = 70 + (2 - iko) * 20
        elif iko <= 5:
            s = 30 + (5 - iko) * 13.3
        else:
            s = max(0, 30 - (iko - 5) * 6)
        indicators.append({"name": "İş Kazası Oranı", "value": f"%{iko:.1f}", "score": round(s, 1)})
        scores.append(s)
    
    # Regülasyon Uyumu (yüksek = iyi)
    ru = data.get("regulasyon_uyum")
    if ru is not None:
        s = min(100, max(0, ru))
        indicators.append({"name": "Regülasyon Uyum", "value": f"%{ru:.0f}", "score": round(s, 1)})
        scores.append(s)
    
    score = sum(scores) / len(scores) if scores else 50
    grade, color = _grade(score)
    
    return DimensionScore(
        name="Risk Maruziyet",
        score=round(score, 1),
        weight=DIMENSION_WEIGHTS["risk"],
        grade=grade,
        color=color,
        indicators=indicators,
        trend="stable",
        description="Müşteri yoğunlaşma, tedarik bağımlılığı ve operasyonel risk değerlendirmesi",
    )


# ══════════════════════════════════════════════════════════════
# ANA FONKSİYONLAR
# ══════════════════════════════════════════════════════════════

def calculate_health_index(data: dict) -> HealthIndex:
    """
    Bileşik Enterprise Health Score hesapla.
    
    data formatı:
    {
        "financial": {"brut_kar_marji": 25, "favok_marji": 12, ...},
        "operational": {"oee": 72, "fire_orani": 4, ...},
        "growth": {"satis_buyume": 8, ...},
        "risk": {"musteri_yogunlasma": 35, ...}
    }
    
    Veya düz format (tüm göstergeler tek seviyede):
    {"brut_kar_marji": 25, "oee": 72, "satis_buyume": 8, "musteri_yogunlasma": 35, ...}
    """
    # Veriyi normalize et — iç içe veya düz olabilir
    financial_data = data.get("financial", {})
    operational_data = data.get("operational", {})
    growth_data = data.get("growth", {})
    risk_data = data.get("risk", {})
    
    # Düz formattan iç içe'ye çevirme
    if not any([financial_data, operational_data, growth_data, risk_data]):
        financial_keys = {"brut_kar_marji", "favok_marji", "cari_oran", "borc_ozsermaye", "nakit_cevrim_gun", "gelir_buyume"}
        operational_keys = {"oee", "fire_orani", "hat_verimliligi", "durus_orani", "isk_devir", "zamaninda_teslimat"}
        growth_keys = {"satis_buyume", "musteri_sayisi_degisim", "yeni_urun_orani", "pazar_payi_degisim", "yatirim_orani", "ar_ge_harcama_orani"}
        risk_keys = {"musteri_yogunlasma", "tedarikci_bagimliligi", "stok_devir_hizi", "alacak_gun", "is_kazasi_orani", "regulasyon_uyum"}
        
        for k, v in data.items():
            if k in financial_keys:
                financial_data[k] = v
            elif k in operational_keys:
                operational_data[k] = v
            elif k in growth_keys:
                growth_data[k] = v
            elif k in risk_keys:
                risk_data[k] = v
    
    # Boyutları hesapla
    dim_financial = _calc_financial(financial_data)
    dim_operational = _calc_operational(operational_data)
    dim_growth = _calc_growth(growth_data)
    dim_risk = _calc_risk(risk_data)
    
    dimensions = [dim_financial, dim_operational, dim_growth, dim_risk]
    
    # Ağırlıklı genel skor
    overall = sum(d.score * d.weight for d in dimensions)
    overall = round(overall, 1)
    
    grade, color = _grade(overall)
    status = _status(overall)
    
    # Öneriler
    recommendations = _generate_health_recommendations(dimensions)
    
    # Executive summary
    summary = _generate_executive_summary(overall, dimensions)
    
    return HealthIndex(
        overall_score=overall,
        overall_grade=grade,
        overall_color=color,
        overall_status=status,
        dimensions=dimensions,
        timestamp=datetime.now().isoformat(),
        recommendations=recommendations,
        executive_summary=summary,
    )


def _generate_health_recommendations(dimensions: list[DimensionScore]) -> list[str]:
    """Boyut skorlarına göre stratejik öneriler üret."""
    recs = []
    
    # En zayıf boyutu bul
    weakest = min(dimensions, key=lambda d: d.score)
    strongest = max(dimensions, key=lambda d: d.score)
    
    recs.append(f"🎯 En güçlü alan: {strongest.name} ({strongest.color} {strongest.score:.0f}/100)")
    recs.append(f"⚠️ Öncelikli iyileştirme alanı: {weakest.name} ({weakest.color} {weakest.score:.0f}/100)")
    
    for dim in dimensions:
        if dim.score < 40:
            recs.append(f"🔴 KRİTİK — {dim.name}: Acil aksiyon planı gerekli")
            # En düşük göstergeyi bul
            if dim.indicators:
                worst_ind = min(dim.indicators, key=lambda x: x["score"])
                recs.append(f"   └─ En zayıf gösterge: {worst_ind['name']} ({worst_ind['value']}, skor: {worst_ind['score']:.0f})")
        elif dim.score < 60:
            recs.append(f"🟠 DİKKAT — {dim.name}: Kısa vadeli iyileştirme planı oluşturulmalı")
    
    # Declining trend uyarısı
    for dim in dimensions:
        if dim.trend == "declining":
            recs.append(f"📉 {dim.name} düşüş trendinde — trend tersine çevrilmeli")
    
    return recs


def _generate_executive_summary(overall: float, dimensions: list[DimensionScore]) -> str:
    """CEO için tek paragraf özet."""
    status = _status(overall)
    grade, _ = _grade(overall)
    
    dim_texts = []
    for d in sorted(dimensions, key=lambda x: x.score, reverse=True):
        dim_texts.append(f"{d.name}: {d.color} {d.score:.0f}")
    
    dim_str = " | ".join(dim_texts)
    
    weak_areas = [d.name for d in dimensions if d.score < 55]
    strong_areas = [d.name for d in dimensions if d.score >= 75]
    
    summary = f"Şirket Sağlık Skoru: {overall:.0f}/100 ({grade} — {status}). {dim_str}."
    
    if strong_areas:
        summary += f" Güçlü yönler: {', '.join(strong_areas)}."
    if weak_areas:
        summary += f" İyileştirme gereken alanlar: {', '.join(weak_areas)}."
    
    return summary


def format_health_dashboard(index: HealthIndex) -> str:
    """Health Index'i Markdown dashboard formatına çevir."""
    lines = [
        f"\n\n---\n## 🏥 Şirket Sağlık Endeksi",
        f"\n### {index.overall_color} Genel Skor: **{index.overall_score:.0f}/100** ({index.overall_grade} — {index.overall_status})",
        f"\n| Boyut | Skor | Not | Trend |",
        f"|-------|------|-----|-------|",
    ]
    
    trend_icons = {"improving": "📈", "stable": "➡️", "declining": "📉"}
    
    for d in index.dimensions:
        trend_icon = trend_icons.get(d.trend, "➡️")
        lines.append(f"| {d.name} | {d.color} {d.score:.0f}/100 | {d.grade} | {trend_icon} |")
    
    # En iyi ve en kötü göstergeler
    all_indicators = []
    for d in index.dimensions:
        for ind in d.indicators:
            all_indicators.append({**ind, "dimension": d.name})
    
    if all_indicators:
        best = sorted(all_indicators, key=lambda x: x["score"], reverse=True)[:3]
        worst = sorted(all_indicators, key=lambda x: x["score"])[:3]
        
        lines.append(f"\n### 🟢 En Güçlü Göstergeler")
        for b in best:
            lines.append(f"- **{b['name']}**: {b['value']} (skor: {b['score']:.0f})")
        
        lines.append(f"\n### 🔴 En Zayıf Göstergeler")
        for w in worst:
            lines.append(f"- **{w['name']}**: {w['value']} (skor: {w['score']:.0f})")
    
    if index.recommendations:
        lines.append(f"\n### 💡 Stratejik Öneriler")
        for r in index.recommendations:
            lines.append(f"- {r}")
    
    return "\n".join(lines)


def get_demo_health_index() -> HealthIndex:
    """Demo verilerle örnek Health Index hesapla."""
    demo_data = {
        "financial": {
            "brut_kar_marji": 28,
            "favok_marji": 14,
            "cari_oran": 1.35,
            "borc_ozsermaye": 0.85,
            "nakit_cevrim_gun": 55,
            "gelir_buyume": 7,
        },
        "operational": {
            "oee": 72,
            "fire_orani": 4.2,
            "hat_verimliligi": 78,
            "durus_orani": 12,
            "isk_devir": 18,
            "zamaninda_teslimat": 88,
        },
        "growth": {
            "satis_buyume": 8,
            "musteri_sayisi_degisim": 3,
            "yeni_urun_orani": 12,
            "pazar_payi_degisim": 1.5,
            "yatirim_orani": 8,
        },
        "risk": {
            "musteri_yogunlasma": 32,
            "tedarikci_bagimliligi": 28,
            "stok_devir_hizi": 4.5,
            "alacak_gun": 65,
            "is_kazasi_orani": 1.8,
            "regulasyon_uyum": 92,
        },
    }
    return calculate_health_index(demo_data)


# ── Tool Registry Entegrasyonu ──
def health_index_tool(params: dict) -> dict:
    """Tool calling wrapper."""
    data = params.get("data", {})
    if data:
        result = calculate_health_index(data)
    else:
        result = get_demo_health_index()
    
    return {
        "overall_score": result.overall_score,
        "grade": result.overall_grade,
        "status": result.overall_status,
        "dimensions": {d.name: d.score for d in result.dimensions},
        "dashboard": format_health_dashboard(result),
    }
