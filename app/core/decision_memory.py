"""Decision Memory — Karar Hafızası Katmanı

Şirket içi karar destek sistemi için kritik öğrenme katmanı.
Her kararı kaydeder, benzer geçmiş kararları bulur, sonuçları izler.

Yetenekler:
  1. Karar kayıt — soru, AI önerisi, kalite skoru, KPI etkisi, departman, timestamp
  2. Benzer karar arama — anahtar kelime + TF-IDF benzeri benzerlik
  3. Sonuç takibi — karar sonucu (uygulandı mı, başarılı mı, gerçek KPI etkisi)
  4. Başarı analizi — AI önerilerinin tarihsel isabet oranı
  5. Karar kalıpları — dept/konu bazlı karar kalıpları tespiti
  6. Öğrenme döngüsü — meta_learning'e geri bildirim

Patron sorusu: "Daha önce benzer bir karar aldık mı? Sonucu ne oldu?"
"""

from __future__ import annotations
import time
import math
import hashlib
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Any, Tuple
from collections import Counter


# ─── Enums ──────────────────────────────────────────────────────────

class DecisionOutcome(Enum):
    """Karar sonucu"""
    PENDING = "pending"             # Henüz sonuç yok
    APPLIED = "applied"             # Uygulandı, sonuç bekleniyor
    SUCCESSFUL = "successful"       # Başarılı
    PARTIALLY_SUCCESSFUL = "partial"  # Kısmen başarılı
    UNSUCCESSFUL = "unsuccessful"   # Başarısız
    CANCELLED = "cancelled"         # İptal edildi
    SUPERSEDED = "superseded"       # Başka kararla değiştirildi


class DecisionCategory(Enum):
    """Karar kategorisi"""
    STRATEGIC = "strategic"         # Stratejik
    OPERATIONAL = "operational"     # Operasyonel
    FINANCIAL = "financial"         # Finansal
    TECHNICAL = "technical"         # Teknik
    HR = "hr"                       # İnsan kaynakları
    RISK = "risk"                   # Risk yönetimi
    INVESTMENT = "investment"       # Yatırım
    OTHER = "other"


# ─── Data Classes ───────────────────────────────────────────────────

@dataclass
class DecisionRecord:
    """Tek bir karar kaydı"""
    decision_id: str                     # Benzersiz ID
    question: str                        # Orijinal soru
    ai_recommendation: str               # AI önerisi (cevap)
    department: str
    category: DecisionCategory
    quality_score: float                 # Decision quality score (0-100)
    quality_band: str                    # "high", "moderate", vb.
    kpi_impacts: List[Dict[str, Any]]    # Tahmini KPI etkileri
    risk_level: str                      # "low", "medium", "high", "critical"
    gate_verdict: str                    # PASS, PASS_WITH_WARNING, BLOCK, ESCALATE
    uncertainty: float                   # 0-100
    confidence: float                    # 0-100
    user_id: Optional[str] = None
    outcome: DecisionOutcome = DecisionOutcome.PENDING
    outcome_notes: str = ""
    actual_impact: Optional[Dict[str, Any]] = None  # Gerçekleşen etki
    tags: List[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)
    outcome_timestamp: Optional[float] = None

    def to_dict(self) -> dict:
        return {
            "decision_id": self.decision_id,
            "question": self.question[:200],
            "recommendation_preview": self.ai_recommendation[:300],
            "department": self.department,
            "category": self.category.value,
            "quality_score": round(self.quality_score, 1),
            "quality_band": self.quality_band,
            "risk_level": self.risk_level,
            "gate_verdict": self.gate_verdict,
            "uncertainty": round(self.uncertainty, 1),
            "confidence": round(self.confidence, 1),
            "outcome": self.outcome.value,
            "outcome_notes": self.outcome_notes,
            "kpi_impact_count": len(self.kpi_impacts),
            "tags": self.tags,
            "timestamp": self.timestamp,
        }


@dataclass
class SimilarDecision:
    """Benzer karar sonucu"""
    record: DecisionRecord
    similarity_score: float   # 0-1
    match_reasons: List[str]  # Neden benzer bulundu


@dataclass
class AccuracyReport:
    """AI öneri doğruluk raporu"""
    total_decisions: int
    with_outcome: int
    successful: int
    partial: int
    unsuccessful: int
    cancelled: int
    accuracy_rate: float          # 0-1 (successful + 0.5*partial) / with_outcome
    dept_accuracy: Dict[str, float]
    category_accuracy: Dict[str, float]
    trend: str                    # "improving", "declining", "stable"
    avg_quality_of_successful: float
    avg_quality_of_unsuccessful: float


# ─── Text Similarity ───────────────────────────────────────────────

class TextSimilarity:
    """Basit TF-IDF benzeri metin benzerlik hesaplayıcı"""

    # Türkçe stop words
    STOP_WORDS = {
        "bir", "ve", "bu", "şu", "o", "de", "da", "ile", "için", "mı", "mi",
        "mu", "mü", "ne", "ama", "fakat", "veya", "ya", "hem", "çok", "az",
        "daha", "en", "gibi", "kadar", "olan", "olarak", "olan", "ancak",
        "her", "tüm", "bütün", "bazı", "hiç", "nasıl", "neden", "niçin",
        "hangi", "kim", "kime", "nerede", "var", "yok", "değil", "ise",
    }

    @staticmethod
    def tokenize(text: str) -> List[str]:
        """Metni token'lara ayır"""
        text = text.lower()
        text = re.sub(r'[^\w\sğüşıöçĞÜŞİÖÇ]', ' ', text)
        tokens = text.split()
        return [t for t in tokens if len(t) > 2 and t not in TextSimilarity.STOP_WORDS]

    @staticmethod
    def cosine_similarity(tokens_a: List[str], tokens_b: List[str]) -> float:
        """İki token listesi arasında cosine benzerlik"""
        if not tokens_a or not tokens_b:
            return 0.0

        counter_a = Counter(tokens_a)
        counter_b = Counter(tokens_b)

        all_tokens = set(counter_a.keys()) | set(counter_b.keys())

        dot_product = sum(counter_a.get(t, 0) * counter_b.get(t, 0) for t in all_tokens)
        mag_a = math.sqrt(sum(v ** 2 for v in counter_a.values()))
        mag_b = math.sqrt(sum(v ** 2 for v in counter_b.values()))

        if mag_a == 0 or mag_b == 0:
            return 0.0

        return dot_product / (mag_a * mag_b)

    @staticmethod
    def jaccard_similarity(tokens_a: List[str], tokens_b: List[str]) -> float:
        """Jaccard benzerlik"""
        set_a = set(tokens_a)
        set_b = set(tokens_b)
        if not set_a and not set_b:
            return 0.0
        intersection = set_a & set_b
        union = set_a | set_b
        return len(intersection) / len(union)


# ─── Category Detector ─────────────────────────────────────────────

CATEGORY_KEYWORDS = {
    DecisionCategory.STRATEGIC: [
        "strateji", "stratejik", "vizyon", "misyon", "uzun vadeli", "pazar",
        "rekabet", "büyüme", "genişleme", "dönüşüm",
    ],
    DecisionCategory.OPERATIONAL: [
        "üretim", "operasyon", "süreç", "verimlilik", "kapasite", "bakım",
        "lojistik", "tedarik", "planlama", "vardiya",
    ],
    DecisionCategory.FINANCIAL: [
        "bütçe", "maliyet", "gelir", "kâr", "kar", "nakit", "finans",
        "fiyat", "ödeme", "kredi", "borç", "döviz",
    ],
    DecisionCategory.TECHNICAL: [
        "yazılım", "donanım", "teknoloji", "sistem", "otomasyon",
        "makine", "ekipman", "dijital", "altyapı",
    ],
    DecisionCategory.HR: [
        "personel", "çalışan", "işe alım", "eğitim", "performans",
        "maaş", "özlük", "kadro", "organizasyon",
    ],
    DecisionCategory.RISK: [
        "risk", "tehdit", "güvenlik", "uyum", "denetim", "kriz",
        "acil", "felaket", "sigorta",
    ],
    DecisionCategory.INVESTMENT: [
        "yatırım", "proje", "makine alım", "modernizasyon", "ar-ge",
        "inovasyon", "kuruluş",
    ],
}


def detect_category(text: str) -> DecisionCategory:
    """Metin içeriğinden karar kategorisi tespit et"""
    text_lower = text.lower()
    scores: Dict[DecisionCategory, int] = {}

    for cat, keywords in CATEGORY_KEYWORDS.items():
        scores[cat] = sum(1 for kw in keywords if kw in text_lower)

    if not scores or max(scores.values()) == 0:
        return DecisionCategory.OTHER

    return max(scores, key=scores.get)


# ─── Tag Extractor ──────────────────────────────────────────────────

TAG_KEYWORDS = [
    "verimlilik", "maliyet", "kalite", "fire", "üretim", "satış",
    "yatırım", "risk", "personel", "enerji", "stok", "tedarik",
    "müşteri", "ihracat", "kapasite", "bakım", "teknoloji", "otomasyon",
    "dijital", "sürdürülebilirlik", "inovasyon", "pazar", "rekabet",
]


def extract_tags(text: str) -> List[str]:
    """Metinden etiketler çıkar"""
    text_lower = text.lower()
    return [tag for tag in TAG_KEYWORDS if tag in text_lower]


# ─── Decision Memory Store ─────────────────────────────────────────

class DecisionMemory:
    """Karar hafızası ana sınıfı"""

    MAX_RECORDS = 1000

    def __init__(self):
        self._records: Dict[str, DecisionRecord] = {}  # id → record
        self._chronological: List[str] = []  # id listesi (sıralı)
        self._dept_index: Dict[str, List[str]] = {}  # dept → [id, ...]
        self._category_index: Dict[str, List[str]] = {}  # category → [id, ...]
        self._tag_index: Dict[str, List[str]] = {}  # tag → [id, ...]
        self._similarity = TextSimilarity()

    def _generate_id(self, question: str) -> str:
        """Benzersiz karar ID'si"""
        raw = f"{question}_{time.time()}"
        return hashlib.md5(raw.encode()).hexdigest()[:12]

    def _trim_if_needed(self):
        """Kayıt limitini aşarsa eski kayıtları sil"""
        while len(self._chronological) > self.MAX_RECORDS:
            old_id = self._chronological.pop(0)
            if old_id in self._records:
                del self._records[old_id]

    def store_decision(
        self,
        question: str,
        ai_recommendation: str,
        department: str = "",
        quality_score: float = 0,
        quality_band: str = "",
        kpi_impacts: Optional[List[Dict]] = None,
        risk_level: str = "unknown",
        gate_verdict: str = "unknown",
        uncertainty: float = 50,
        confidence: float = 50,
        user_id: Optional[str] = None,
    ) -> DecisionRecord:
        """Yeni karar kaydet"""
        decision_id = self._generate_id(question)
        category = detect_category(question + " " + ai_recommendation)
        tags = extract_tags(question + " " + ai_recommendation)

        record = DecisionRecord(
            decision_id=decision_id,
            question=question,
            ai_recommendation=ai_recommendation,
            department=department,
            category=category,
            quality_score=quality_score,
            quality_band=quality_band,
            kpi_impacts=kpi_impacts or [],
            risk_level=risk_level,
            gate_verdict=gate_verdict,
            uncertainty=uncertainty,
            confidence=confidence,
            user_id=user_id,
            tags=tags,
        )

        self._records[decision_id] = record
        self._chronological.append(decision_id)

        # İndeksle
        if department:
            self._dept_index.setdefault(department, []).append(decision_id)
        self._category_index.setdefault(category.value, []).append(decision_id)
        for tag in tags:
            self._tag_index.setdefault(tag, []).append(decision_id)

        self._trim_if_needed()
        return record

    def update_outcome(
        self,
        decision_id: str,
        outcome: DecisionOutcome,
        notes: str = "",
        actual_impact: Optional[Dict[str, Any]] = None,
    ) -> Optional[DecisionRecord]:
        """Karar sonucunu güncelle"""
        record = self._records.get(decision_id)
        if not record:
            return None

        record.outcome = outcome
        record.outcome_notes = notes
        record.outcome_timestamp = time.time()
        if actual_impact:
            record.actual_impact = actual_impact

        return record

    def find_similar(
        self,
        question: str,
        department: Optional[str] = None,
        top_n: int = 5,
        min_similarity: float = 0.15,
    ) -> List[SimilarDecision]:
        """Benzer geçmiş kararları bul"""
        query_tokens = self._similarity.tokenize(question)
        if not query_tokens:
            return []

        candidates = []

        for record_id, record in self._records.items():
            # Departman filtresi
            if department and record.department != department:
                continue

            record_tokens = self._similarity.tokenize(record.question + " " + record.ai_recommendation)

            # Cosine + Jaccard birleşik benzerlik
            cosine = self._similarity.cosine_similarity(query_tokens, record_tokens)
            jaccard = self._similarity.jaccard_similarity(query_tokens, record_tokens)
            combined = cosine * 0.6 + jaccard * 0.4

            # Departman bonus
            if department and record.department == department:
                combined += 0.05

            # Kategori bonus
            query_cat = detect_category(question)
            if query_cat == record.category:
                combined += 0.05

            if combined >= min_similarity:
                match_reasons = []
                if cosine > 0.2:
                    match_reasons.append(f"Konu benzerliği: %{cosine*100:.0f}")
                if department == record.department:
                    match_reasons.append(f"Aynı departman: {department}")
                if query_cat == record.category:
                    match_reasons.append(f"Aynı kategori: {record.category.value}")

                # Ortak anahtar kelimeler
                common = set(query_tokens) & set(record_tokens)
                if len(common) >= 2:
                    match_reasons.append(f"Ortak konular: {', '.join(list(common)[:5])}")

                candidates.append(SimilarDecision(
                    record=record,
                    similarity_score=combined,
                    match_reasons=match_reasons,
                ))

        # En benzer N tane
        candidates.sort(key=lambda x: x.similarity_score, reverse=True)
        return candidates[:top_n]

    def get_accuracy_report(self) -> AccuracyReport:
        """AI öneri doğruluk raporu"""
        all_records = list(self._records.values())
        with_outcome = [r for r in all_records if r.outcome not in (DecisionOutcome.PENDING, DecisionOutcome.APPLIED)]

        successful = sum(1 for r in with_outcome if r.outcome == DecisionOutcome.SUCCESSFUL)
        partial = sum(1 for r in with_outcome if r.outcome == DecisionOutcome.PARTIALLY_SUCCESSFUL)
        unsuccessful = sum(1 for r in with_outcome if r.outcome == DecisionOutcome.UNSUCCESSFUL)
        cancelled = sum(1 for r in with_outcome if r.outcome == DecisionOutcome.CANCELLED)

        total_outcome = len(with_outcome)
        if total_outcome > 0:
            accuracy = (successful + 0.5 * partial) / total_outcome
        else:
            accuracy = 0

        # Departman bazlı doğruluk
        dept_acc: Dict[str, float] = {}
        for dept, ids in self._dept_index.items():
            dept_records = [self._records[i] for i in ids if i in self._records and self._records[i].outcome not in (DecisionOutcome.PENDING, DecisionOutcome.APPLIED)]
            if dept_records:
                dept_succ = sum(1 for r in dept_records if r.outcome == DecisionOutcome.SUCCESSFUL)
                dept_part = sum(1 for r in dept_records if r.outcome == DecisionOutcome.PARTIALLY_SUCCESSFUL)
                dept_acc[dept] = (dept_succ + 0.5 * dept_part) / len(dept_records)

        # Kategori bazlı doğruluk
        cat_acc: Dict[str, float] = {}
        for cat_val, ids in self._category_index.items():
            cat_records = [self._records[i] for i in ids if i in self._records and self._records[i].outcome not in (DecisionOutcome.PENDING, DecisionOutcome.APPLIED)]
            if cat_records:
                cat_succ = sum(1 for r in cat_records if r.outcome == DecisionOutcome.SUCCESSFUL)
                cat_part = sum(1 for r in cat_records if r.outcome == DecisionOutcome.PARTIALLY_SUCCESSFUL)
                cat_acc[cat_val] = (cat_succ + 0.5 * cat_part) / len(cat_records)

        # Başarılı/başarısız kalite ortalaması
        succ_quals = [r.quality_score for r in with_outcome if r.outcome == DecisionOutcome.SUCCESSFUL]
        unsucc_quals = [r.quality_score for r in with_outcome if r.outcome == DecisionOutcome.UNSUCCESSFUL]

        avg_q_succ = sum(succ_quals) / len(succ_quals) if succ_quals else 0
        avg_q_unsucc = sum(unsucc_quals) / len(unsucc_quals) if unsucc_quals else 0

        # Trend (son 20 karar)
        recent_with_outcome = sorted(with_outcome, key=lambda r: r.timestamp)[-20:]
        if len(recent_with_outcome) >= 6:
            first_half = recent_with_outcome[:len(recent_with_outcome)//2]
            second_half = recent_with_outcome[len(recent_with_outcome)//2:]
            first_succ = sum(1 for r in first_half if r.outcome in (DecisionOutcome.SUCCESSFUL, DecisionOutcome.PARTIALLY_SUCCESSFUL)) / len(first_half)
            second_succ = sum(1 for r in second_half if r.outcome in (DecisionOutcome.SUCCESSFUL, DecisionOutcome.PARTIALLY_SUCCESSFUL)) / len(second_half)
            trend = "improving" if second_succ > first_succ + 0.1 else ("declining" if second_succ < first_succ - 0.1 else "stable")
        else:
            trend = "insufficient_data"

        return AccuracyReport(
            total_decisions=len(all_records),
            with_outcome=total_outcome,
            successful=successful,
            partial=partial,
            unsuccessful=unsuccessful,
            cancelled=cancelled,
            accuracy_rate=round(accuracy, 3),
            dept_accuracy=dept_acc,
            category_accuracy=cat_acc,
            trend=trend,
            avg_quality_of_successful=round(avg_q_succ, 1),
            avg_quality_of_unsuccessful=round(avg_q_unsucc, 1),
        )

    def get_decision_patterns(self, min_frequency: int = 3) -> List[dict]:
        """Tekrarlayan karar kalıplarını tespit et"""
        patterns = []

        # Departman × Kategori kalıpları
        dept_cat_counts: Dict[str, int] = {}
        for record in self._records.values():
            key = f"{record.department}|{record.category.value}"
            dept_cat_counts[key] = dept_cat_counts.get(key, 0) + 1

        for key, count in dept_cat_counts.items():
            if count >= min_frequency:
                dept, cat = key.split("|", 1)
                patterns.append({
                    "type": "dept_category",
                    "department": dept,
                    "category": cat,
                    "frequency": count,
                    "description": f"{dept} departmanında {cat} kararları sık tekrarlanıyor ({count} kez)",
                })

        # En çok tekrarlanan tag'ler
        tag_counts = {tag: len(ids) for tag, ids in self._tag_index.items()}
        for tag, count in sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)[:10]:
            if count >= min_frequency:
                patterns.append({
                    "type": "frequent_topic",
                    "tag": tag,
                    "frequency": count,
                    "description": f"'{tag}' konusu {count} kez karar sürecine girdi",
                })

        return patterns

    def get_recent_decisions(self, n: int = 10, department: Optional[str] = None) -> List[dict]:
        """Son N kararı listele"""
        ids = self._chronological[-n*3:] if not department else (
            self._dept_index.get(department, [])[-n*3:]
        )

        results = []
        for rid in reversed(ids):
            if rid in self._records:
                results.append(self._records[rid].to_dict())
                if len(results) >= n:
                    break

        return results

    def get_stats(self) -> dict:
        total = len(self._records)
        outcomes = Counter(r.outcome.value for r in self._records.values())
        categories = Counter(r.category.value for r in self._records.values())
        departments = Counter(r.department for r in self._records.values() if r.department)

        avg_quality = (
            sum(r.quality_score for r in self._records.values()) / total
            if total else 0
        )

        return {
            "total_decisions": total,
            "outcome_distribution": dict(outcomes),
            "category_distribution": dict(categories),
            "department_distribution": dict(departments),
            "average_quality_score": round(avg_quality, 1),
        }

    def get_dashboard(self) -> dict:
        stats = self.get_stats()
        accuracy = self.get_accuracy_report()
        patterns = self.get_decision_patterns(min_frequency=2)

        return {
            **stats,
            "accuracy_rate": accuracy.accuracy_rate,
            "accuracy_trend": accuracy.trend,
            "avg_quality_successful": accuracy.avg_quality_of_successful,
            "avg_quality_unsuccessful": accuracy.avg_quality_of_unsuccessful,
            "patterns": patterns[:5],
            "recent_decisions": self.get_recent_decisions(5),
        }


# ─── Module-Level Instance ─────────────────────────────────────────

_memory = DecisionMemory()


# ─── Public API ─────────────────────────────────────────────────────

def store_decision(
    question: str,
    ai_recommendation: str,
    department: str = "",
    quality_score: float = 0,
    quality_band: str = "",
    kpi_impacts: Optional[List[Dict]] = None,
    risk_level: str = "unknown",
    gate_verdict: str = "unknown",
    uncertainty: float = 50,
    confidence: float = 50,
    user_id: Optional[str] = None,
) -> DecisionRecord:
    """Yeni karar kaydet"""
    return _memory.store_decision(
        question=question,
        ai_recommendation=ai_recommendation,
        department=department,
        quality_score=quality_score,
        quality_band=quality_band,
        kpi_impacts=kpi_impacts,
        risk_level=risk_level,
        gate_verdict=gate_verdict,
        uncertainty=uncertainty,
        confidence=confidence,
        user_id=user_id,
    )


def find_similar_decisions(
    question: str,
    department: Optional[str] = None,
    top_n: int = 5,
) -> List[SimilarDecision]:
    """Benzer geçmiş kararları bul"""
    return _memory.find_similar(question, department, top_n)


def update_decision_outcome(
    decision_id: str,
    outcome: str,
    notes: str = "",
    actual_impact: Optional[Dict[str, Any]] = None,
) -> Optional[DecisionRecord]:
    """Karar sonucunu güncelle"""
    try:
        outcome_enum = DecisionOutcome(outcome)
    except ValueError:
        outcome_enum = DecisionOutcome.PENDING

    return _memory.update_outcome(decision_id, outcome_enum, notes, actual_impact)


def get_accuracy_report() -> dict:
    """AI öneri doğruluk raporu"""
    report = _memory.get_accuracy_report()
    return {
        "total_decisions": report.total_decisions,
        "with_outcome": report.with_outcome,
        "successful": report.successful,
        "partial": report.partial,
        "unsuccessful": report.unsuccessful,
        "cancelled": report.cancelled,
        "accuracy_rate": report.accuracy_rate,
        "trend": report.trend,
        "dept_accuracy": report.dept_accuracy,
        "category_accuracy": report.category_accuracy,
        "avg_quality_successful": report.avg_quality_of_successful,
        "avg_quality_unsuccessful": report.avg_quality_of_unsuccessful,
    }


# ─── Formatters ─────────────────────────────────────────────────────

def format_similar_decisions(similar: List[SimilarDecision]) -> str:
    """Benzer kararları Markdown formatında göster"""
    if not similar:
        return ""

    lines = [
        "\n### 🔄 Benzer Geçmiş Kararlar",
        "",
    ]

    for i, sd in enumerate(similar, 1):
        record = sd.record
        outcome_icon = {
            "successful": "✅", "partial": "⚠️", "unsuccessful": "❌",
            "pending": "⏳", "applied": "🔄", "cancelled": "🚫", "superseded": "🔀",
        }
        icon = outcome_icon.get(record.outcome.value, "❓")

        lines.append(f"**{i}. Benzerlik: %{sd.similarity_score*100:.0f}** {icon}")
        lines.append(f"   - Soru: {record.question[:120]}")
        lines.append(f"   - Öneri: {record.ai_recommendation[:150]}")
        lines.append(f"   - Kalite: {record.quality_score:.0f}/100 | Risk: {record.risk_level}")
        lines.append(f"   - Sonuç: {record.outcome.value}")
        if record.outcome_notes:
            lines.append(f"   - Not: {record.outcome_notes[:100]}")
        if sd.match_reasons:
            lines.append(f"   - Benzerlik nedeni: {', '.join(sd.match_reasons)}")
        lines.append("")

    return "\n".join(lines)


def format_accuracy_summary() -> str:
    """AI doğruluk özetini formatla"""
    report = _memory.get_accuracy_report()

    if report.total_decisions == 0:
        return ""

    lines = [
        "\n### 🎯 AI Öneri Doğruluk Raporu",
        f"",
        f"- Toplam Karar: {report.total_decisions}",
        f"- Sonucu Bilinen: {report.with_outcome}",
        f"- Başarılı: {report.successful} | Kısmen: {report.partial} | Başarısız: {report.unsuccessful}",
        f"- **Doğruluk Oranı: %{report.accuracy_rate*100:.1f}**",
        f"- Trend: {report.trend}",
    ]

    if report.avg_quality_of_successful > 0:
        lines.append(f"- Başarılı kararların ort. kalite skoru: {report.avg_quality_of_successful:.0f}/100")
    if report.avg_quality_of_unsuccessful > 0:
        lines.append(f"- Başarısız kararların ort. kalite skoru: {report.avg_quality_of_unsuccessful:.0f}/100")

    return "\n".join(lines)


# ─── Dashboard ──────────────────────────────────────────────────────

def get_dashboard() -> dict:
    return {
        "module": "decision_memory",
        "module_name": "Karar Hafızası",
        **_memory.get_dashboard(),
    }


def get_statistics() -> dict:
    return _memory.get_stats()


def get_recent_decisions(n: int = 10, department: Optional[str] = None) -> List[dict]:
    return _memory.get_recent_decisions(n, department)
