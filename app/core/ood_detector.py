"""OOD Detector — Out-of-Distribution Girdi Algılama

Sisteme gelen soruların "bilinen dağılım" içinde olup olmadığını tespit eder.
Modelin daha önce görmediği konularda kendinden emin karar vermesini önler.

Yetenekler:
  1. Semantic novelty — soru, bilinen konu kümesine ne kadar yakın?
  2. Input profiling — soru uzunluğu, dil, yapı normlardan sapıyor mu?
  3. Domain boundary — tekstil/üretim/finans alanı dışına mı çıkıyor?
  4. Complexity spike — beklenenden çok daha karmaşık mı?
  5. Confidence calibration — OOD ise uncertainty/confidence ayarı önerisi

Patron riski: "Model bilmediği konuda güvenli görünen ama yanlış cevap verdi"
→ Bu modül o riski yakalar.

v5.3.0 — CompanyAI Enterprise
"""

from __future__ import annotations

import math
import re
import time
from collections import Counter, deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Any, Set, Tuple


# ─── Enums ──────────────────────────────────────────────────────────

class OODSeverity(Enum):
    """OOD tespit şiddeti"""
    SAFE = "safe"                 # Bilinen dağılım içinde
    BORDERLINE = "borderline"     # Sınırda — dikkat
    OUT_OF_DISTRIBUTION = "ood"   # Dağılım dışı
    HIGHLY_OOD = "highly_ood"     # Çok farklı — uyarı zorunlu


class DomainArea(Enum):
    """Bilinen alan tanımları"""
    TEXTILE = "textile"
    MANUFACTURING = "manufacturing"
    FINANCE = "finance"
    HR = "hr"
    SUPPLY_CHAIN = "supply_chain"
    QUALITY = "quality"
    ENERGY = "energy"
    SALES_MARKETING = "sales_marketing"
    IT_TECH = "it_tech"
    STRATEGY = "strategy"
    GENERAL = "general"
    UNKNOWN = "unknown"


# ─── Data Classes ───────────────────────────────────────────────────

@dataclass
class OODSignal:
    """Tek bir OOD sinyali"""
    dimension: str       # "semantic", "domain", "complexity", "structural"
    score: float         # 0-1 (0 = tamamen bilinen, 1 = tamamen yabancı)
    detail: str          # Açıklama
    weight: float = 1.0


@dataclass
class OODResult:
    """OOD analiz sonucu"""
    severity: OODSeverity
    ood_score: float               # 0-100 (0 = güvenli, 100 = tamamen OOD)
    signals: List[OODSignal]
    detected_domain: DomainArea
    is_ood: bool                   # ood_score > eşik
    confidence_adjustment: float   # Örn: -15 → confidence'ı %15 düşür
    uncertainty_adjustment: float  # Örn: +20 → uncertainty'yi %20 artır
    warning_message: str           # Kullanıcıya gösterilecek uyarı
    recommendation: str            # Sistem önerisi
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "severity": self.severity.value,
            "ood_score": round(self.ood_score, 1),
            "is_ood": self.is_ood,
            "detected_domain": self.detected_domain.value,
            "signals": [
                {"dimension": s.dimension, "score": round(s.score, 2), "detail": s.detail}
                for s in self.signals
            ],
            "confidence_adjustment": round(self.confidence_adjustment, 1),
            "uncertainty_adjustment": round(self.uncertainty_adjustment, 1),
            "warning_message": self.warning_message,
            "recommendation": self.recommendation,
        }


# ─── Domain Definitions ────────────────────────────────────────────

DOMAIN_KEYWORDS: Dict[DomainArea, List[str]] = {
    DomainArea.TEXTILE: [
        "tekstil", "kumaş", "iplik", "dokuma", "örme", "boyama", "boya",
        "apre", "konfeksiyon", "denim", "pamuk", "polyester", "viskon",
        "kalite kontrol", "lot", "parti", "metraj", "gramaj", "fire",
        "çözgü", "atkı", "terbiye", "numune", "koleksiyon", "sezon",
    ],
    DomainArea.MANUFACTURING: [
        "üretim", "fabrika", "makine", "hat", "vardiya", "bakım", "arıza",
        "oee", "verimlilik", "kapasite", "duruş", "setup", "kalıp",
        "otomasyon", "plc", "scada", "erp", "mes", "proses", "tezgah",
    ],
    DomainArea.FINANCE: [
        "bütçe", "maliyet", "gelir", "gider", "kâr", "kar", "zarar",
        "nakit", "akış", "bilanço", "muhasebe", "fatura", "alacak",
        "borç", "vade", "döviz", "kur", "banka", "kredi", "yatırım",
        "roi", "irr", "npv", "fiyat", "marj", "ciro",
    ],
    DomainArea.HR: [
        "personel", "çalışan", "işe alım", "eğitim", "performans",
        "maaş", "özlük", "kadro", "organizasyon", "ik", "izin",
        "devamsızlık", "turnover", "yetenek",
    ],
    DomainArea.SUPPLY_CHAIN: [
        "tedarik", "lojistik", "depo", "stok", "envanter", "sipariş",
        "sevkiyat", "teslim", "müşteri", "ihracat", "ithalat", "gümrük",
        "forwarder", "konteyner", "navlun",
    ],
    DomainArea.QUALITY: [
        "kalite", "hata", "kusur", "rework", "scrap", "muayene",
        "test", "standart", "iso", "denetim", "uygunsuzluk", "düzeltici",
    ],
    DomainArea.ENERGY: [
        "enerji", "elektrik", "doğalgaz", "kwh", "yakıt", "tasarruf",
        "karbon", "emisyon", "sürdürülebilirlik", "yeşil",
    ],
    DomainArea.SALES_MARKETING: [
        "satış", "pazarlama", "müşteri", "pazar", "rakip", "kampanya",
        "marka", "hedef", "tahmin", "forecast", "segment", "kanal",
    ],
    DomainArea.IT_TECH: [
        "yazılım", "veri", "analiz", "dashboard", "rapor", "sistem",
        "entegrasyon", "api", "database", "sunucu", "ağ", "güvenlik",
    ],
    DomainArea.STRATEGY: [
        "strateji", "vizyon", "misyon", "hedef", "plan", "büyüme",
        "dönüşüm", "inovasyon", "ar-ge", "rekabet", "swot",
    ],
}

# Her alan için ortalama domain coverage (ne kadar zengin kelime dağarcığı)
DOMAIN_WEIGHTS = {
    DomainArea.TEXTILE: 1.2,       # Ana alan — bonus ağırlık
    DomainArea.MANUFACTURING: 1.2,
    DomainArea.FINANCE: 1.0,
    DomainArea.SUPPLY_CHAIN: 0.9,
    DomainArea.QUALITY: 0.9,
    DomainArea.HR: 0.8,
    DomainArea.ENERGY: 0.8,
    DomainArea.SALES_MARKETING: 0.8,
    DomainArea.IT_TECH: 0.7,
    DomainArea.STRATEGY: 0.7,
    DomainArea.GENERAL: 0.3,
    DomainArea.UNKNOWN: 0.1,
}

# Tamamen bilinen alan dışı konular
OFF_DOMAIN_INDICATORS = [
    "futbol", "basketbol", "film", "dizi", "tarif", "yemek", "sağlık",
    "ilaç", "tıp", "hukuk", "mahkeme", "siyaset", "seçim", "oyun",
    "müzik", "sanat", "felsefe", "uzay", "astronomi", "fizik dersi",
    "kimya dersi", "biyoloji", "tarih dersi", "coğrafya dersi",
    "matematik sorusu", "sınav", "ödev", "spor", "tatil", "gezi",
]

# Normal soru yapısı profili
NORMAL_QUESTION_PROFILE = {
    "min_length": 10,
    "max_length": 2000,
    "typical_length_range": (30, 500),
    "min_turkish_ratio": 0.3,
    "max_special_char_ratio": 0.15,
    "expected_word_count_range": (3, 200),
}


# ─── OOD Analyzer ──────────────────────────────────────────────────

class OODAnalyzer:
    """Out-of-Distribution girdi analiz motoru"""

    OOD_THRESHOLD = 45  # Bu skorun üstü OOD kabul edilir

    # Sinyal ağırlıkları
    SIGNAL_WEIGHTS = {
        "semantic": 0.35,    # Konu benzerliği en önemli
        "domain": 0.30,      # Alan uyumu
        "structural": 0.15,  # Yapısal normallik
        "complexity": 0.20,  # Karmaşıklık sapması
    }

    def __init__(self):
        self._question_history: deque = deque(maxlen=500)
        self._domain_counts: Dict[str, int] = {}
        self._avg_length: float = 100
        self._avg_word_count: float = 15
        self._total_analyzed: int = 0

    def _update_profile(self, question: str, domain: DomainArea):
        """Girdi profilini güncelle"""
        self._question_history.append(question)
        self._domain_counts[domain.value] = self._domain_counts.get(domain.value, 0) + 1

        # Running average
        n = self._total_analyzed + 1
        self._avg_length = (self._avg_length * self._total_analyzed + len(question)) / n
        word_count = len(question.split())
        self._avg_word_count = (self._avg_word_count * self._total_analyzed + word_count) / n
        self._total_analyzed = n

    def analyze(self, question: str, department: str = "") -> OODResult:
        """Girdiyi OOD açısından analiz et"""
        signals: List[OODSignal] = []

        # 1. Domain analizi
        detected_domain, domain_signal = self._analyze_domain(question)
        signals.append(domain_signal)

        # 2. Semantik yenilik
        semantic_signal = self._analyze_semantic_novelty(question)
        signals.append(semantic_signal)

        # 3. Yapısal normallik
        structural_signal = self._analyze_structure(question)
        signals.append(structural_signal)

        # 4. Karmaşıklık sapması
        complexity_signal = self._analyze_complexity(question)
        signals.append(complexity_signal)

        # Ağırlıklı OOD skoru
        weighted_sum = sum(
            s.score * self.SIGNAL_WEIGHTS.get(s.dimension, 0.25)
            for s in signals
        )
        total_weight = sum(self.SIGNAL_WEIGHTS.get(s.dimension, 0.25) for s in signals)
        ood_score = (weighted_sum / total_weight * 100) if total_weight > 0 else 0

        # Severity
        severity = self._classify_severity(ood_score)
        is_ood = ood_score >= self.OOD_THRESHOLD

        # Adjustments
        conf_adj, unc_adj = self._calculate_adjustments(ood_score)

        # Warning & recommendation
        warning = self._build_warning(severity, detected_domain, signals)
        recommendation = self._build_recommendation(severity, ood_score)

        # Profili güncelle
        self._update_profile(question, detected_domain)

        return OODResult(
            severity=severity,
            ood_score=ood_score,
            signals=signals,
            detected_domain=detected_domain,
            is_ood=is_ood,
            confidence_adjustment=conf_adj,
            uncertainty_adjustment=unc_adj,
            warning_message=warning,
            recommendation=recommendation,
        )

    # ─── Signal analyzers ───────────────────────────────────────

    def _analyze_domain(self, question: str) -> Tuple[DomainArea, OODSignal]:
        """Alan uyumu analizi"""
        q_lower = question.lower()

        # Off-domain kontrolü
        off_domain_hits = sum(1 for kw in OFF_DOMAIN_INDICATORS if kw in q_lower)
        if off_domain_hits >= 2:
            return DomainArea.UNKNOWN, OODSignal(
                dimension="domain",
                score=0.95,
                detail=f"İş alanı dışı konu tespit edildi ({off_domain_hits} gösterge)",
                weight=1.2,
            )

        # Domain scoring
        domain_scores: Dict[DomainArea, float] = {}
        for domain, keywords in DOMAIN_KEYWORDS.items():
            hits = sum(1 for kw in keywords if kw in q_lower)
            if hits > 0:
                weight = DOMAIN_WEIGHTS.get(domain, 0.5)
                domain_scores[domain] = hits * weight

        if not domain_scores:
            # Hiçbir alanla eşleşmedi
            return DomainArea.UNKNOWN, OODSignal(
                dimension="domain",
                score=0.7,
                detail="Bilinen iş alanlarından hiçbiriyle eşleşmedi",
                weight=1.0,
            )

        best_domain = max(domain_scores, key=domain_scores.get)
        best_score = domain_scores[best_domain]
        total_coverage = sum(domain_scores.values())

        # Coverage ne kadar düşükse o kadar OOD
        if best_score >= 3:
            ood = 0.05  # Çok iyi eşleşme
        elif best_score >= 2:
            ood = 0.15
        elif best_score >= 1:
            ood = 0.35
        else:
            ood = 0.6

        return best_domain, OODSignal(
            dimension="domain",
            score=ood,
            detail=f"Alan: {best_domain.value}, eşleşme: {best_score:.1f}, kapsam: {total_coverage:.1f}",
        )

    def _analyze_semantic_novelty(self, question: str) -> OODSignal:
        """Semantik yenilik — geçmiş sorularla benzerlik"""
        if not self._question_history:
            # İlk soru — OOD değil, baseline yok
            return OODSignal(
                dimension="semantic",
                score=0.3,
                detail="Karşılaştırma için yeterli geçmiş yok",
            )

        q_tokens = set(self._tokenize(question))
        if not q_tokens:
            return OODSignal(dimension="semantic", score=0.5, detail="Token çıkarılamadı")

        # Son 50 soruyla benzerlik hesapla
        recent = list(self._question_history)[-50:]
        similarities = []
        for hist_q in recent:
            h_tokens = set(self._tokenize(hist_q))
            if h_tokens:
                jaccard = len(q_tokens & h_tokens) / len(q_tokens | h_tokens)
                similarities.append(jaccard)

        if not similarities:
            return OODSignal(dimension="semantic", score=0.4, detail="Benzerlik hesaplanamadı")

        max_sim = max(similarities)
        avg_sim = sum(similarities) / len(similarities)

        # Hiçbir geçmiş soruya benzemiyorsa → OOD
        if max_sim < 0.05:
            ood = 0.8
            detail = "Geçmiş sorularla neredeyse hiç benzerlik yok"
        elif max_sim < 0.15:
            ood = 0.5
            detail = f"Düşük benzerlik (max: %{max_sim*100:.0f})"
        elif max_sim < 0.3:
            ood = 0.25
            detail = f"Orta benzerlik (max: %{max_sim*100:.0f})"
        else:
            ood = 0.05
            detail = f"Bilinen soru tipi (max benzerlik: %{max_sim*100:.0f})"

        return OODSignal(dimension="semantic", score=ood, detail=detail)

    def _analyze_structure(self, question: str) -> OODSignal:
        """Yapısal normallik analizi"""
        issues = []
        score = 0.0

        length = len(question)
        word_count = len(question.split())

        # Uzunluk kontrolü
        if length < NORMAL_QUESTION_PROFILE["min_length"]:
            issues.append("Çok kısa girdi")
            score += 0.3
        elif length > NORMAL_QUESTION_PROFILE["max_length"]:
            issues.append("Aşırı uzun girdi")
            score += 0.2

        # Tipik uzunluk aralığı
        typ_min, typ_max = NORMAL_QUESTION_PROFILE["typical_length_range"]
        if length < typ_min or length > typ_max:
            score += 0.1

        # Özel karakter oranı
        special_chars = sum(1 for c in question if not c.isalnum() and not c.isspace())
        special_ratio = special_chars / max(length, 1)
        if special_ratio > NORMAL_QUESTION_PROFILE["max_special_char_ratio"]:
            issues.append(f"Yüksek özel karakter oranı (%{special_ratio*100:.0f})")
            score += 0.2

        # Türkçe karakter oranı (Latin+Türkçe harf / toplam harf)
        alpha_chars = [c for c in question if c.isalpha()]
        if alpha_chars:
            turkish_chars = set("abcçdefgğhıijklmnoöprsştuüvyzABCÇDEFGĞHIİJKLMNOÖPRSŞTUÜVYZ")
            turkish_ratio = sum(1 for c in alpha_chars if c in turkish_chars) / len(alpha_chars)
            if turkish_ratio < NORMAL_QUESTION_PROFILE["min_turkish_ratio"]:
                issues.append("Düşük Türkçe karakter oranı")
                score += 0.15

        # Running average'dan sapma
        if self._total_analyzed > 5:
            length_deviation = abs(length - self._avg_length) / max(self._avg_length, 1)
            if length_deviation > 3:
                issues.append(f"Uzunluk ortalamanın {length_deviation:.1f}x farklı")
                score += 0.15

        score = min(score, 1.0)
        detail = "; ".join(issues) if issues else "Yapısal olarak normal"

        return OODSignal(dimension="structural", score=score, detail=detail)

    def _analyze_complexity(self, question: str) -> OODSignal:
        """Karmaşıklık sapması"""
        words = question.lower().split()
        word_count = len(words)

        # Unique word ratio (tekrar eden kelime azsa karmaşıklık yüksek)
        unique_ratio = len(set(words)) / max(word_count, 1)

        # Ortalama kelime uzunluğu
        avg_word_len = sum(len(w) for w in words) / max(word_count, 1)

        # Cümle sayısı tahmini
        sentences = re.split(r'[.!?;]', question)
        sentence_count = len([s for s in sentences if len(s.strip()) > 5])

        # Complexity score
        complexity = 0.0

        if unique_ratio > 0.95 and word_count > 20:
            complexity += 0.2  # Çok yüksek kelime çeşitliliği
        if avg_word_len > 8:
            complexity += 0.15  # Uzun/teknik kelimeler
        if word_count > 100:
            complexity += 0.2  # Çok uzun soru
        if sentence_count > 10:
            complexity += 0.15

        # Running average'dan sapma
        if self._total_analyzed > 5:
            wc_deviation = abs(word_count - self._avg_word_count) / max(self._avg_word_count, 1)
            if wc_deviation > 3:
                complexity += 0.2

        complexity = min(complexity, 1.0)

        if complexity > 0.5:
            detail = f"Beklenenden karmaşık girdi (kelime: {word_count}, benzersizlik: %{unique_ratio*100:.0f})"
        elif complexity > 0.25:
            detail = f"Orta karmaşıklık (kelime: {word_count})"
        else:
            detail = f"Normal karmaşıklık seviyesi (kelime: {word_count})"

        return OODSignal(dimension="complexity", score=complexity, detail=detail)

    # ─── Helpers ─────────────────────────────────────────────────

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        """Basit tokenizer"""
        text = text.lower()
        text = re.sub(r'[^\w\sğüşıöçĞÜŞİÖÇ]', ' ', text)
        stop = {"bir", "ve", "bu", "de", "da", "ile", "için", "mi", "mı", "ne", "var", "yok"}
        return [t for t in text.split() if len(t) > 2 and t not in stop]

    def _classify_severity(self, ood_score: float) -> OODSeverity:
        if ood_score >= 75:
            return OODSeverity.HIGHLY_OOD
        if ood_score >= self.OOD_THRESHOLD:
            return OODSeverity.OUT_OF_DISTRIBUTION
        if ood_score >= 25:
            return OODSeverity.BORDERLINE
        return OODSeverity.SAFE

    def _calculate_adjustments(self, ood_score: float) -> Tuple[float, float]:
        """Confidence ve uncertainty ayar değerlerini hesapla"""
        if ood_score < 25:
            return 0, 0  # Ayar yok

        # OOD arttıkça confidence düşer, uncertainty artar
        conf_adj = -(ood_score - 25) * 0.4  # max -30
        unc_adj = (ood_score - 25) * 0.4     # max +30

        return round(max(conf_adj, -30), 1), round(min(unc_adj, 30), 1)

    def _build_warning(self, severity: OODSeverity, domain: DomainArea, signals: List[OODSignal]) -> str:
        """Kullanıcı uyarı mesajı"""
        if severity == OODSeverity.SAFE:
            return ""

        if severity == OODSeverity.HIGHLY_OOD:
            if domain == DomainArea.UNKNOWN:
                return "⚠️ Bu soru sistemin uzmanlık alanı dışında. Öneriler güvenilir olmayabilir."
            return "⚠️ Sistem bu tip soruyu daha önce görmedi. Sonuçları dikkatle değerlendirin."

        if severity == OODSeverity.OUT_OF_DISTRIBUTION:
            highest = max(signals, key=lambda s: s.score)
            return f"⚠️ Alışılmadık girdi tespit edildi ({highest.detail}). Sonuçları doğrulatmanız önerilir."

        # BORDERLINE
        return "ℹ️ Girdi bilinen kalıplardan kısmen sapıyor. Ekstra doğrulama faydalı olabilir."

    def _build_recommendation(self, severity: OODSeverity, ood_score: float) -> str:
        """Sistem önerisi"""
        if severity == OODSeverity.SAFE:
            return "Normal işlem — ek eylem gerekmez"

        if severity == OODSeverity.HIGHLY_OOD:
            return "Cevap güvenilirliği düşük. İnsan uzman doğrulaması şiddetle önerilir. Otomatik karar alınmamalı."

        if severity == OODSeverity.OUT_OF_DISTRIBUTION:
            return "Cevap ek doğrulama gerektirir. Karar kalitesi düşük olabilir. Sonuçları departman yöneticisiyle paylaşın."

        return "Sonuçlar genel olarak güvenilir ancak bilinen kalıplardan kısmen sapma var."


# ─── Tracker ────────────────────────────────────────────────────────

class OODTracker:
    """OOD tespitlerini izler"""

    MAX_HISTORY = 500

    def __init__(self):
        self._history: List[dict] = []
        self._ood_count: int = 0
        self._safe_count: int = 0
        self._domain_dist: Dict[str, int] = {}

    def record(self, result: OODResult):
        entry = {
            "ood_score": result.ood_score,
            "severity": result.severity.value,
            "domain": result.detected_domain.value,
            "is_ood": result.is_ood,
            "timestamp": result.timestamp,
        }
        self._history.append(entry)
        if len(self._history) > self.MAX_HISTORY:
            self._history = self._history[-self.MAX_HISTORY:]

        if result.is_ood:
            self._ood_count += 1
        else:
            self._safe_count += 1

        self._domain_dist[result.detected_domain.value] = self._domain_dist.get(result.detected_domain.value, 0) + 1

    def get_stats(self) -> dict:
        total = self._ood_count + self._safe_count
        return {
            "total_analyzed": total,
            "ood_count": self._ood_count,
            "safe_count": self._safe_count,
            "ood_rate": round(self._ood_count / total, 3) if total else 0,
            "domain_distribution": dict(self._domain_dist),
        }

    def get_dashboard(self) -> dict:
        stats = self.get_stats()
        recent = self._history[-5:] if self._history else []
        return {
            **stats,
            "recent_analyses": list(reversed(recent)),
        }


# ─── Module Instances ──────────────────────────────────────────────

_analyzer = OODAnalyzer()
_tracker = OODTracker()


# ─── Public API ─────────────────────────────────────────────────────

def check_ood(
    question: str,
    department: str = "",
) -> OODResult:
    """Girdiyi OOD açısından kontrol et"""
    result = _analyzer.analyze(question, department)
    _tracker.record(result)
    return result


def format_ood_warning(result: OODResult) -> str:
    """OOD uyarısını Markdown formatında göster"""
    if not result.is_ood and result.severity == OODSeverity.SAFE:
        return ""

    lines = []

    if result.severity in (OODSeverity.HIGHLY_OOD, OODSeverity.OUT_OF_DISTRIBUTION):
        lines.append(f"\n> {result.warning_message}")
        lines.append(f"> OOD Skoru: {result.ood_score:.0f}/100 | Alan: {result.detected_domain.value}")
        lines.append(f"> Öneri: {result.recommendation}")
        lines.append("")
    elif result.severity == OODSeverity.BORDERLINE:
        lines.append(f"\n> {result.warning_message}")
        lines.append("")

    return "\n".join(lines)


def format_ood_badge(result: OODResult) -> str:
    """Tek satırlık OOD durumu"""
    if result.severity == OODSeverity.SAFE:
        return ""

    icons = {
        "borderline": "🟡",
        "ood": "🟠",
        "highly_ood": "🔴",
    }
    icon = icons.get(result.severity.value, "⚪")
    return f"{icon} OOD: {result.ood_score:.0f}/100 — {result.warning_message}"


# ─── Dashboard ──────────────────────────────────────────────────────

def get_dashboard() -> dict:
    return {
        "module": "ood_detector",
        "module_name": "OOD Girdi Algılama",
        **_tracker.get_dashboard(),
    }


def get_statistics() -> dict:
    return _tracker.get_stats()
