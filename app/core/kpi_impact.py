"""KPI-Impact Mapping — Kararların KPI Etkisi Haritalama Motoru

Her karar/önerinin hangi KPI'ları ne yönde ve ne kadar etkileyeceğini tahmin eder.
"Bu karar brüt kârı %X etkiler, nakit akışını Y gün etkiler" cümlesi kurar.

Çalışma prensibi:
  1. Karar metninden etkilenecek KPI'ları çıkar (anahtar kelime + LLM intent)
  2. Etki yönü ve büyüklüğü tahmin et (doğrudan + dolaylı)
  3. Finansal çeviri: KPI değişimini ₺/$/gün cinsine çevir
  4. Zaman perspektifi: kısa vadeli (0-3 ay), orta vadeli (3-12 ay), uzun vadeli (1-3 yıl)
  5. Domino etkisi: zincirleme KPI etkilerini hesapla
"""

from __future__ import annotations
import time
import math
import hashlib
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Any, Tuple


# ─── Enums ──────────────────────────────────────────────────────────

class ImpactDirection(Enum):
    POSITIVE = "positive"     # Artış (yüksek=iyi KPI'lar için olumlu)
    NEGATIVE = "negative"     # Azalış
    NEUTRAL = "neutral"       # Değişim yok
    UNCERTAIN = "uncertain"   # Belirsiz


class ImpactMagnitude(Enum):
    CRITICAL = "critical"     # >20% değişim
    SIGNIFICANT = "significant"  # 10-20%
    MODERATE = "moderate"     # 5-10%
    MINOR = "minor"           # 1-5%
    NEGLIGIBLE = "negligible"  # <1%


class TimeHorizon(Enum):
    SHORT = "short"           # 0-3 ay
    MEDIUM = "medium"         # 3-12 ay
    LONG = "long"             # 1-3 yıl


# ─── Data Classes ───────────────────────────────────────────────────

@dataclass
class KPIImpact:
    """Tek bir KPI üzerindeki etki"""
    kpi_id: str
    kpi_name: str
    category: str                   # Üretim, Finans, Satış, vb.
    direction: ImpactDirection
    magnitude: ImpactMagnitude
    estimated_change_pct: float     # Tahmini % değişim (-100 to +100)
    confidence: float               # Tahmin güveni (0-1)
    time_horizon: TimeHorizon
    is_direct: bool                 # Doğrudan mı dolaylı mı etki
    financial_impact_text: str = ""  # "Brüt kâra aylık ~50.000₺ etki"
    explanation: str = ""           # Etki açıklaması


@dataclass
class DominoEffect:
    """Zincirleme KPI etkisi"""
    source_kpi: str
    target_kpi: str
    propagation_strength: float     # 0-1 yayılım gücü
    estimated_secondary_pct: float  # İkincil % etki
    explanation: str = ""


@dataclass
class ImpactSummary:
    """Kararın toplam KPI etki özeti"""
    decision_text: str
    primary_impacts: List[KPIImpact]
    domino_effects: List[DominoEffect]
    net_financial_direction: ImpactDirection
    net_risk_change: str            # "azalır", "artar", "değişmez"
    executive_summary: str          # "Bu karar üretim verimliliğini %8 artırır, fire oranını %3 düşürür"
    impact_score: float             # -100 to +100 genel etki skoru
    affected_kpi_count: int
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "decision_text": self.decision_text[:200],
            "primary_impacts": [
                {
                    "kpi_id": imp.kpi_id,
                    "kpi_name": imp.kpi_name,
                    "category": imp.category,
                    "direction": imp.direction.value,
                    "magnitude": imp.magnitude.value,
                    "change_pct": round(imp.estimated_change_pct, 1),
                    "confidence": round(imp.confidence, 2),
                    "time_horizon": imp.time_horizon.value,
                    "is_direct": imp.is_direct,
                    "financial_impact": imp.financial_impact_text,
                    "explanation": imp.explanation,
                }
                for imp in self.primary_impacts
            ],
            "domino_effects": [
                {
                    "source": d.source_kpi,
                    "target": d.target_kpi,
                    "strength": round(d.propagation_strength, 2),
                    "secondary_pct": round(d.estimated_secondary_pct, 1),
                    "explanation": d.explanation,
                }
                for d in self.domino_effects
            ],
            "net_financial_direction": self.net_financial_direction.value,
            "net_risk_change": self.net_risk_change,
            "executive_summary": self.executive_summary,
            "impact_score": round(self.impact_score, 1),
            "affected_kpi_count": self.affected_kpi_count,
        }


# ─── KPI Etki Haritası ─────────────────────────────────────────────

# Anahtar kelime → KPI eşleştirme matrisi
KEYWORD_KPI_MAP: Dict[str, List[Tuple[str, str, float]]] = {
    # keyword → [(kpi_id, category, base_confidence), ...]
    "verimlilik": [("oee", "Üretim", 0.85), ("verimlilik", "Üretim", 0.9)],
    "fire": [("fire_orani", "Üretim", 0.9), ("ilk_seferde_dogru", "Üretim", 0.7)],
    "kalite": [("ilk_seferde_dogru", "Üretim", 0.85), ("fire_orani", "Üretim", 0.7)],
    "maliyet": [("brut_kar_marji", "Finans", 0.8), ("favok_marji", "Finans", 0.7), ("birim_maliyet", "Üretim", 0.85)],
    "kâr": [("brut_kar_marji", "Finans", 0.9), ("favok_marji", "Finans", 0.85), ("net_kar_marji", "Finans", 0.8)],
    "kar": [("brut_kar_marji", "Finans", 0.9), ("favok_marji", "Finans", 0.85)],
    "satış": [("satış_büyümesi", "Satış", 0.85), ("brut_kar_marji", "Finans", 0.6)],
    "gelir": [("satış_büyümesi", "Satış", 0.8), ("brut_kar_marji", "Finans", 0.7)],
    "nakit": [("nakit_donusum", "Finans", 0.9), ("isletme_sermayesi", "Finans", 0.7)],
    "stok": [("stok_devir", "Tedarik", 0.9), ("nakit_donusum", "Finans", 0.6)],
    "tedarik": [("stok_devir", "Tedarik", 0.8), ("tedarik_suresi", "Tedarik", 0.85)],
    "enerji": [("enerji_tuketimi", "Üretim", 0.9), ("birim_maliyet", "Üretim", 0.7)],
    "duruş": [("durus_orani", "Üretim", 0.9), ("oee", "Üretim", 0.75)],
    "setup": [("setup_suresi", "Üretim", 0.9), ("oee", "Üretim", 0.65)],
    "personel": [("ciro_orani", "İK", 0.8), ("birim_maliyet", "Üretim", 0.5)],
    "yatırım": [("yatirim_getirisi", "Finans", 0.9), ("brut_kar_marji", "Finans", 0.6)],
    "üretim": [("oee", "Üretim", 0.7), ("verimlilik", "Üretim", 0.75), ("birim_maliyet", "Üretim", 0.6)],
    "kapasite": [("kapasite_kullanim", "Üretim", 0.9), ("oee", "Üretim", 0.7)],
    "teslim": [("zamaninda_teslim", "Tedarik", 0.9), ("musteri_memnuniyet", "Satış", 0.6)],
    "müşteri": [("musteri_memnuniyet", "Satış", 0.85), ("zamaninda_teslim", "Tedarik", 0.6)],
    "çevrim": [("cevrim_suresi", "Üretim", 0.9)],
    "bakım": [("durus_orani", "Üretim", 0.7), ("oee", "Üretim", 0.65)],
    "iplik": [("fire_orani", "Üretim", 0.7), ("birim_maliyet", "Üretim", 0.6)],
    "dokuma": [("oee", "Üretim", 0.75), ("verimlilik", "Üretim", 0.8)],
    "boya": [("fire_orani", "Üretim", 0.75), ("enerji_tuketimi", "Üretim", 0.6)],
    "ihracat": [("ihracat_orani", "Satış", 0.9), ("satış_büyümesi", "Satış", 0.7)],
    "döviz": [("brut_kar_marji", "Finans", 0.7), ("ihracat_orani", "Satış", 0.6)],
    "hammadde": [("birim_maliyet", "Üretim", 0.85), ("brut_kar_marji", "Finans", 0.7)],
}

# KPI'lar arası zincirleme etki haritası
# source_kpi → [(target_kpi, propagation_strength, explanation)]
DOMINO_MAP: Dict[str, List[Tuple[str, float, str]]] = {
    "oee": [
        ("birim_maliyet", 0.7, "OEE artışı birim maliyeti düşürür"),
        ("brut_kar_marji", 0.5, "OEE artışı brüt kâra olumlu yansır"),
        ("zamaninda_teslim", 0.6, "OEE artışı teslimat performansını iyileştirir"),
    ],
    "fire_orani": [
        ("birim_maliyet", 0.8, "Fire azalışı birim maliyeti doğrudan düşürür"),
        ("brut_kar_marji", 0.6, "Fire azalışı kârlılığı artırır"),
        ("musteri_memnuniyet", 0.4, "Fire azalışı kaliteyi artırır → müşteri memnuniyeti"),
    ],
    "birim_maliyet": [
        ("brut_kar_marji", 0.8, "Birim maliyet düşüşü kâr marjını artırır"),
        ("favok_marji", 0.6, "Birim maliyet düşüşü FAVÖK'ü iyileştirir"),
    ],
    "durus_orani": [
        ("oee", 0.7, "Duruş azalışı OEE'yi artırır"),
        ("verimlilik", 0.8, "Duruş azalışı hat verimliliğini artırır"),
    ],
    "stok_devir": [
        ("nakit_donusum", 0.7, "Stok devir hızlanması nakit döngüsünü kısaltır"),
        ("isletme_sermayesi", 0.5, "Stok devir iyileşmesi işletme sermayesini düşürür"),
    ],
    "verimlilik": [
        ("birim_maliyet", 0.6, "Verimlilik artışı birim maliyeti düşürür"),
        ("oee", 0.5, "Verimlilik artışı OEE'yi iyileştirir"),
    ],
    "satış_büyümesi": [
        ("brut_kar_marji", 0.4, "Satış artışı ölçek ekonomisiyle marjı iyileştirebilir"),
        ("nakit_donusum", 0.3, "Satış artışı nakit döngüsünü etkileyebilir"),
    ],
    "brut_kar_marji": [
        ("favok_marji", 0.7, "Brüt kâr marjı FAVÖK'e yansır"),
        ("net_kar_marji", 0.6, "Brüt kâr marjı net kâra yansır"),
    ],
    "kapasite_kullanim": [
        ("birim_maliyet", 0.6, "Kapasite kullanımı artışı sabit maliyetleri dağıtır"),
        ("oee", 0.5, "Kapasite kullanımı OEE bileşenidir"),
    ],
}

# Etki yönü anahtar kelimeleri
POSITIVE_KEYWORDS = [
    "artır", "iyileştir", "yükselt", "geliştir", "optimize", "hızlandır",
    "arttır", "büyüt", "güçlendir", "düzelt", "azalt.*maliyet", "düşür.*maliyet",
    "azalt.*fire", "düşür.*fire", "azalt.*duruş", "düşür.*duruş",
    "iyileştirme", "modernizasyon", "otomasyon", "dijitalleşme",
]
NEGATIVE_KEYWORDS = [
    "azalt.*satış", "düşür.*üretim", "azalt.*kapasite", "kes.*personel",
    "durdur", "iptal", "erteleme", "kısıtla", "artır.*maliyet",
    "yükselt.*fiyat", "yavaşlat",
]


# ─── KPI Adları ─────────────────────────────────────────────────────

KPI_NAMES = {
    "oee": "OEE (Genel Ekipman Verimliliği)",
    "fire_orani": "Fire Oranı",
    "verimlilik": "Hat Verimliliği",
    "durus_orani": "Duruş Oranı",
    "cevrim_suresi": "Çevrim Süresi",
    "ilk_seferde_dogru": "İlk Seferde Doğru (FTR)",
    "setup_suresi": "Setup Süresi",
    "birim_maliyet": "Birim Maliyet",
    "brut_kar_marji": "Brüt Kâr Marjı",
    "favok_marji": "FAVÖK Marjı",
    "net_kar_marji": "Net Kâr Marjı",
    "satış_büyümesi": "Satış Büyümesi",
    "nakit_donusum": "Nakit Dönüşüm Süresi",
    "isletme_sermayesi": "İşletme Sermayesi Devir",
    "stok_devir": "Stok Devir Hızı",
    "tedarik_suresi": "Tedarikçi Teslim Süresi",
    "enerji_tuketimi": "Enerji Tüketimi",
    "kapasite_kullanim": "Kapasite Kullanım Oranı",
    "zamaninda_teslim": "Zamanında Teslimat",
    "musteri_memnuniyet": "Müşteri Memnuniyeti",
    "ihracat_orani": "İhracat Oranı",
    "ciro_orani": "Personel Devir Oranı",
    "yatirim_getirisi": "Yatırım Getirisi (ROI)",
}

# KPI yönleri (higher_is_better / lower_is_better)
KPI_DIRECTIONS = {
    "oee": "higher", "verimlilik": "higher", "ilk_seferde_dogru": "higher",
    "brut_kar_marji": "higher", "favok_marji": "higher", "net_kar_marji": "higher",
    "satış_büyümesi": "higher", "kapasite_kullanim": "higher",
    "zamaninda_teslim": "higher", "musteri_memnuniyet": "higher",
    "ihracat_orani": "higher", "yatirim_getirisi": "higher",
    "stok_devir": "higher",
    # lower_is_better
    "fire_orani": "lower", "durus_orani": "lower", "cevrim_suresi": "lower",
    "setup_suresi": "lower", "birim_maliyet": "lower",
    "tedarik_suresi": "lower", "enerji_tuketimi": "lower",
    "ciro_orani": "lower", "nakit_donusum": "lower",
    "isletme_sermayesi": "lower",
}


# ─── Impact Analyzer ───────────────────────────────────────────────

class KPIImpactAnalyzer:
    """Karar metninden KPI etkilerini analiz eder"""

    def _extract_affected_kpis(self, text: str) -> List[Tuple[str, str, float]]:
        """Metinden etkilenecek KPI'ları çıkar"""
        text_lower = text.lower()
        found: Dict[str, Tuple[str, float]] = {}

        for keyword, kpis in KEYWORD_KPI_MAP.items():
            if keyword in text_lower:
                for kpi_id, category, conf in kpis:
                    if kpi_id not in found or found[kpi_id][1] < conf:
                        found[kpi_id] = (category, conf)

        return [(kpi_id, cat, conf) for kpi_id, (cat, conf) in found.items()]

    def _detect_direction(self, text: str, kpi_id: str) -> ImpactDirection:
        """Etki yönünü tespit et"""
        import re
        text_lower = text.lower()

        positive_match = any(re.search(p, text_lower) for p in POSITIVE_KEYWORDS)
        negative_match = any(re.search(p, text_lower) for p in NEGATIVE_KEYWORDS)

        if positive_match and not negative_match:
            return ImpactDirection.POSITIVE
        elif negative_match and not positive_match:
            return ImpactDirection.NEGATIVE
        elif positive_match and negative_match:
            return ImpactDirection.UNCERTAIN
        return ImpactDirection.NEUTRAL

    def _estimate_change_pct(self, text: str, kpi_id: str, direction: ImpactDirection) -> float:
        """Tahmini % değişim — metin analizi + heuristic"""
        import re

        # Metindeki sayıları ara
        numbers = re.findall(r'%\s*(\d+(?:\.\d+)?)|(\d+(?:\.\d+)?)\s*%', text)
        mentioned_pcts = [float(n[0] or n[1]) for n in numbers if float(n[0] or n[1]) <= 50]

        if mentioned_pcts:
            base_change = sum(mentioned_pcts) / len(mentioned_pcts)
        else:
            # Büyüklük ipuçları
            text_lower = text.lower()
            if any(w in text_lower for w in ["büyük", "ciddi", "radikal", "köklü", "devrim"]):
                base_change = 15.0
            elif any(w in text_lower for w in ["orta", "makul", "ılımlı"]):
                base_change = 7.0
            elif any(w in text_lower for w in ["küçük", "hafif", "minimal"]):
                base_change = 3.0
            else:
                base_change = 5.0

        sign = 1 if direction == ImpactDirection.POSITIVE else (
            -1 if direction == ImpactDirection.NEGATIVE else 0
        )

        # lower_is_better KPI'larda pozitif karar = negatif değişim (azalma)
        kpi_dir = KPI_DIRECTIONS.get(kpi_id, "higher")
        if kpi_dir == "lower" and direction == ImpactDirection.POSITIVE:
            sign = -1  # "fire oranını azalt" → fire_orani -%X
        elif kpi_dir == "lower" and direction == ImpactDirection.NEGATIVE:
            sign = 1   # Kötüleşme → fire artar

        return round(base_change * sign, 1)

    def _get_magnitude(self, change_pct: float) -> ImpactMagnitude:
        """Değişim büyüklük sınıflandırması"""
        abs_change = abs(change_pct)
        if abs_change >= 20:
            return ImpactMagnitude.CRITICAL
        elif abs_change >= 10:
            return ImpactMagnitude.SIGNIFICANT
        elif abs_change >= 5:
            return ImpactMagnitude.MODERATE
        elif abs_change >= 1:
            return ImpactMagnitude.MINOR
        return ImpactMagnitude.NEGLIGIBLE

    def _estimate_time_horizon(self, text: str) -> TimeHorizon:
        """Zaman perspektifi tahmini"""
        text_lower = text.lower()
        long_kw = ["uzun vadeli", "yıllık", "3 yıl", "5 yıl", "stratejik", "yatırım"]
        short_kw = ["hemen", "acil", "bu hafta", "bu ay", "kısa vadeli", "anlık"]

        if any(k in text_lower for k in long_kw):
            return TimeHorizon.LONG
        if any(k in text_lower for k in short_kw):
            return TimeHorizon.SHORT
        return TimeHorizon.MEDIUM

    def _make_financial_text(self, kpi_id: str, change_pct: float) -> str:
        """KPI değişiminin finansal çevirisi"""
        kpi_name = KPI_NAMES.get(kpi_id, kpi_id)
        direction = "artış" if change_pct > 0 else "azalış"

        # KPI'ya göre finansal yorum
        financial_comments = {
            "brut_kar_marji": f"Brüt kâr marjında %{abs(change_pct):.1f} {direction} — doğrudan kârlılığı etkiler",
            "favok_marji": f"FAVÖK marjında %{abs(change_pct):.1f} {direction} — operasyonel kârlılığa yansır",
            "fire_orani": f"Fire oranında %{abs(change_pct):.1f} {direction} — hammadde maliyetini etkiler",
            "birim_maliyet": f"Birim maliyette %{abs(change_pct):.1f} {direction} — toplam üretim maliyetine yansır",
            "oee": f"OEE'de %{abs(change_pct):.1f} {direction} — kapasite kullanımını etkiler",
            "nakit_donusum": f"Nakit dönüşüm süresinde %{abs(change_pct):.1f} {direction} — likiditeyi etkiler",
            "stok_devir": f"Stok devir hızında %{abs(change_pct):.1f} {direction} — işletme sermayesini etkiler",
        }

        return financial_comments.get(
            kpi_id,
            f"{kpi_name}'da %{abs(change_pct):.1f} {direction} beklenmektedir"
        )

    def _calculate_domino_effects(self, primary_impacts: List[KPIImpact]) -> List[DominoEffect]:
        """Zincirleme KPI etkilerini hesapla"""
        domino_effects: List[DominoEffect] = []
        seen = set()

        for impact in primary_impacts:
            if impact.kpi_id in DOMINO_MAP:
                for target_kpi, strength, explanation in DOMINO_MAP[impact.kpi_id]:
                    pair = (impact.kpi_id, target_kpi)
                    if pair in seen:
                        continue
                    seen.add(pair)

                    # İkincil etki = birincil etki × yayılım gücü
                    secondary_pct = impact.estimated_change_pct * strength

                    # lower_is_better hedeflerde yön ayarla
                    target_dir = KPI_DIRECTIONS.get(target_kpi, "higher")
                    # Kaynak pozitif etki → hedef pozitif etki (genelde)
                    # Ama bazı KPI'larda ters ilişki var (birim_maliyet düşer → kâr artar)

                    domino_effects.append(DominoEffect(
                        source_kpi=KPI_NAMES.get(impact.kpi_id, impact.kpi_id),
                        target_kpi=KPI_NAMES.get(target_kpi, target_kpi),
                        propagation_strength=strength,
                        estimated_secondary_pct=round(secondary_pct, 1),
                        explanation=explanation,
                    ))

        return domino_effects

    def _build_executive_summary(self, impacts: List[KPIImpact], dominos: List[DominoEffect]) -> str:
        """Yönetici özet cümlesi oluştur"""
        if not impacts:
            return "Bu karar için KPI etki analizi yapılamadı."

        parts = []
        for imp in sorted(impacts, key=lambda x: abs(x.estimated_change_pct), reverse=True)[:3]:
            kpi_name = KPI_NAMES.get(imp.kpi_id, imp.kpi_id)
            direction = "artırır" if imp.estimated_change_pct > 0 else "düşürür"
            # lower_is_better ise ters yorumla
            kpi_dir = KPI_DIRECTIONS.get(imp.kpi_id, "higher")
            if kpi_dir == "lower":
                beneficial = imp.estimated_change_pct < 0  # Azalma olumlu
            else:
                beneficial = imp.estimated_change_pct > 0  # Artış olumlu

            qualifier = "olumlu" if beneficial else "olumsuz"
            parts.append(f"{kpi_name}'ı %{abs(imp.estimated_change_pct):.1f} {direction} ({qualifier})")

        summary = "Bu karar " + ", ".join(parts) + "."

        if dominos:
            top_domino = max(dominos, key=lambda d: abs(d.estimated_secondary_pct))
            summary += f" Zincirleme etki: {top_domino.target_kpi}'a da yansıyabilir."

        return summary

    def analyze(self, decision_text: str, context: Optional[dict] = None) -> ImpactSummary:
        """Ana analiz fonksiyonu"""
        # 1. Etkilenecek KPI'ları çıkar
        affected = self._extract_affected_kpis(decision_text)

        if not affected:
            return ImpactSummary(
                decision_text=decision_text[:200],
                primary_impacts=[],
                domino_effects=[],
                net_financial_direction=ImpactDirection.NEUTRAL,
                net_risk_change="belirsiz",
                executive_summary="Bu karar için etkilenecek spesifik KPI tespit edilemedi.",
                impact_score=0,
                affected_kpi_count=0,
            )

        # 2. Her KPI için etki analizi
        direction = self._detect_direction(decision_text, "")
        time_horizon = self._estimate_time_horizon(decision_text)

        primary_impacts: List[KPIImpact] = []
        for kpi_id, category, confidence in affected:
            change_pct = self._estimate_change_pct(decision_text, kpi_id, direction)
            magnitude = self._get_magnitude(change_pct)

            impact = KPIImpact(
                kpi_id=kpi_id,
                kpi_name=KPI_NAMES.get(kpi_id, kpi_id),
                category=category,
                direction=direction,
                magnitude=magnitude,
                estimated_change_pct=change_pct,
                confidence=confidence,
                time_horizon=time_horizon,
                is_direct=True,
                financial_impact_text=self._make_financial_text(kpi_id, change_pct),
                explanation=f"Karar metnindeki '{kpi_id}' ilişkili anahtar kelimeler nedeniyle",
            )
            primary_impacts.append(impact)

        # 3. Domino etkileri
        domino_effects = self._calculate_domino_effects(primary_impacts)

        # 4. Net etki skoru
        positive_sum = sum(
            abs(i.estimated_change_pct) for i in primary_impacts if i.estimated_change_pct > 0
        )
        negative_sum = sum(
            abs(i.estimated_change_pct) for i in primary_impacts if i.estimated_change_pct < 0
        )

        # KPI yönlerini dikkate al
        net_score = 0
        for imp in primary_impacts:
            kpi_dir = KPI_DIRECTIONS.get(imp.kpi_id, "higher")
            if kpi_dir == "lower":
                # lower_is_better: azalma olumlu
                net_score += -imp.estimated_change_pct
            else:
                net_score += imp.estimated_change_pct

        # Net yön
        if net_score > 2:
            net_direction = ImpactDirection.POSITIVE
        elif net_score < -2:
            net_direction = ImpactDirection.NEGATIVE
        else:
            net_direction = ImpactDirection.NEUTRAL

        # Risk değişimi
        risk_kpis = ["fire_orani", "durus_orani", "ciro_orani"]
        risk_impacts = [i for i in primary_impacts if i.kpi_id in risk_kpis]
        if risk_impacts:
            risk_change = sum(i.estimated_change_pct for i in risk_impacts) / len(risk_impacts)
            net_risk = "azalır" if risk_change < -1 else ("artar" if risk_change > 1 else "değişmez")
        else:
            net_risk = "belirsiz"

        # 5. Yönetici özeti
        exec_summary = self._build_executive_summary(primary_impacts, domino_effects)

        return ImpactSummary(
            decision_text=decision_text[:200],
            primary_impacts=primary_impacts,
            domino_effects=domino_effects,
            net_financial_direction=net_direction,
            net_risk_change=net_risk,
            executive_summary=exec_summary,
            impact_score=round(net_score, 1),
            affected_kpi_count=len(primary_impacts),
        )


# ─── Tracker ────────────────────────────────────────────────────────

class ImpactTracker:
    """KPI etki analizlerinin geçmişini takip eder"""

    MAX_HISTORY = 300

    def __init__(self):
        self._history: List[dict] = []
        self._total = 0
        self._positive_count = 0
        self._negative_count = 0
        self._kpi_hit_counts: Dict[str, int] = {}

    def record(self, summary: ImpactSummary, department: str = ""):
        entry = {
            "decision_preview": summary.decision_text[:100],
            "affected_kpi_count": summary.affected_kpi_count,
            "impact_score": summary.impact_score,
            "net_direction": summary.net_financial_direction.value,
            "department": department,
            "timestamp": summary.timestamp,
        }
        self._history.append(entry)
        if len(self._history) > self.MAX_HISTORY:
            self._history = self._history[-self.MAX_HISTORY:]

        self._total += 1
        if summary.net_financial_direction == ImpactDirection.POSITIVE:
            self._positive_count += 1
        elif summary.net_financial_direction == ImpactDirection.NEGATIVE:
            self._negative_count += 1

        for imp in summary.primary_impacts:
            self._kpi_hit_counts[imp.kpi_id] = self._kpi_hit_counts.get(imp.kpi_id, 0) + 1

    def get_stats(self) -> dict:
        return {
            "total_analyses": self._total,
            "positive_impact_count": self._positive_count,
            "negative_impact_count": self._negative_count,
            "neutral_count": self._total - self._positive_count - self._negative_count,
            "most_affected_kpis": sorted(
                self._kpi_hit_counts.items(), key=lambda x: x[1], reverse=True
            )[:10],
        }

    def get_dashboard(self) -> dict:
        stats = self.get_stats()
        return {
            **stats,
            "recent_history": self._history[-10:],
        }


# ─── Module-Level Instances ────────────────────────────────────────

_analyzer = KPIImpactAnalyzer()
_tracker = ImpactTracker()


# ─── Public API ─────────────────────────────────────────────────────

def analyze_kpi_impact(decision_text: str, context: Optional[dict] = None, department: str = "") -> ImpactSummary:
    """
    Karar metninin KPI etkilerini analiz eder.

    Args:
        decision_text: Karar/öneri metni
        context: Ek bağlam bilgileri
        department: Departman

    Returns:
        ImpactSummary: KPI etki özeti
    """
    result = _analyzer.analyze(decision_text, context)
    _tracker.record(result, department)
    return result


def format_kpi_impact(summary: ImpactSummary) -> str:
    """KPI etki analizini Markdown formatında göster"""
    if not summary.primary_impacts:
        return ""

    lines = [
        f"\n### 📈 KPI Etki Haritalama",
        f"",
        summary.executive_summary,
        f"",
        f"| KPI | Değişim | Büyüklük | Güven | Süre | Finansal Etki |",
        f"|-----|---------|----------|-------|------|---------------|",
    ]

    for imp in sorted(summary.primary_impacts, key=lambda x: abs(x.estimated_change_pct), reverse=True):
        direction_icon = "📈" if imp.estimated_change_pct > 0 else ("📉" if imp.estimated_change_pct < 0 else "➡️")
        horizon_label = {"short": "Kısa", "medium": "Orta", "long": "Uzun"}
        mag_label = {
            "critical": "🔴 Kritik", "significant": "🟠 Önemli",
            "moderate": "🟡 Orta", "minor": "🟢 Minör", "negligible": "⚪ İhmal edilebilir",
        }

        lines.append(
            f"| {imp.kpi_name} | {direction_icon} %{abs(imp.estimated_change_pct):.1f} | "
            f"{mag_label.get(imp.magnitude.value, imp.magnitude.value)} | "
            f"%{imp.confidence*100:.0f} | "
            f"{horizon_label.get(imp.time_horizon.value, imp.time_horizon.value)} | "
            f"{imp.financial_impact_text} |"
        )

    # Domino etkileri
    if summary.domino_effects:
        lines.append("")
        lines.append("**Zincirleme Etkiler:**")
        for d in summary.domino_effects[:5]:
            arrow = "↑" if d.estimated_secondary_pct > 0 else "↓"
            lines.append(f"- {d.source_kpi} → {d.target_kpi}: %{abs(d.estimated_secondary_pct):.1f} {arrow} ({d.explanation})")

    # Net etki
    lines.append("")
    net_icon = {"positive": "🟢 Olumlu", "negative": "🔴 Olumsuz", "neutral": "🟡 Nötr", "uncertain": "⚪ Belirsiz"}
    lines.append(f"**Net Finansal Etki:** {net_icon.get(summary.net_financial_direction.value, '—')} (skor: {summary.impact_score:+.1f})")
    lines.append(f"**Risk Değişimi:** {summary.net_risk_change}")

    return "\n".join(lines)


def format_kpi_impact_brief(summary: ImpactSummary) -> str:
    """Kısa KPI etki özeti"""
    if not summary.primary_impacts:
        return ""

    top = sorted(summary.primary_impacts, key=lambda x: abs(x.estimated_change_pct), reverse=True)[:2]
    parts = []
    for imp in top:
        direction = "↑" if imp.estimated_change_pct > 0 else "↓"
        parts.append(f"{imp.kpi_name} %{abs(imp.estimated_change_pct):.1f}{direction}")

    return f"📈 KPI Etkisi: {', '.join(parts)} | Net skor: {summary.impact_score:+.1f}"


# ─── Tool Wrapper ───────────────────────────────────────────────────

def kpi_impact_tool(decision_text: str) -> str:
    """Tool calling entegrasyonu"""
    summary = analyze_kpi_impact(decision_text)
    return format_kpi_impact(summary)


# ─── Dashboard ──────────────────────────────────────────────────────

def get_dashboard() -> dict:
    return {
        "module": "kpi_impact",
        "module_name": "KPI Etki Haritalama",
        **_tracker.get_dashboard(),
    }


def get_statistics() -> dict:
    return _tracker.get_stats()
