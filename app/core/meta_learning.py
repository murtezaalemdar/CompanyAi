"""
Meta Learning Engine — v1.0.0
==================================
Sistemin kendi performansından öğrenen üst-seviye analiz motoru.

Yetenek haritası:
- Strategy Profiling: soru tipi × departman × pipeline config → başarı oranı
- Knowledge Gap Tracking: RAG'da eksik bilgi alanlarının tespiti
- Quality Trend Analysis: Zaman serisi kalite eğilimi, regresyon/iyileşme tespiti
- Prompt Effectiveness: Hangi prompt stratejileri daha yüksek confidence üretir
- Domain Performance: Departman/mod bazlı performans profilleme
- Failure Pattern Mining: Tekrarlayan başarısızlık kalıplarının keşfi

Entegrasyon noktaları:
- engine.py process_question() → her yanıtta record_outcome() çağrılır
- reflection.py → kalite metrikleri (confidence, criteria_scores, issues)
- governance.py → drift verisi, policy violations
- monitoring.py → anomaly log, performance trend
- knowledge_extractor.py → öğrenme başarı/başarısızlık oranı
- self_improvement.py → analiz sonuçlarını aksiyona dönüştürür

v4.6.0 — CompanyAi
"""

from __future__ import annotations

import hashlib
import math
import time
from collections import Counter, defaultdict, deque
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple

try:
    import structlog
    logger = structlog.get_logger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════
# SABİTLER
# ═══════════════════════════════════════════════════════════════════

# Geçmiş kayıt limiti
MAX_OUTCOME_HISTORY = 5000
MAX_STRATEGY_PROFILES = 500
MAX_KNOWLEDGE_GAPS = 200
MAX_FAILURE_PATTERNS = 200

# Kalite eşikleri
HIGH_QUALITY_THRESHOLD = 75        # confidence >= bu → başarılı
LOW_QUALITY_THRESHOLD = 45         # confidence < bu  → başarısız
TREND_WINDOW_SIZE = 50             # eğilim hesabı pencere boyutu
TREND_MIN_SAMPLES = 10             # eğilim hesabı minimum örnek
GAP_FREQUENCY_THRESHOLD = 3       # bir bilgi boşluğu kaç kez tekrarlanırsa raporlanır

# Strateji profili decay — eski kayıtlar zaman ağırlıklı düşer
DECAY_HALF_LIFE_HOURS = 168       # 1 hafta (168 saat)


# ═══════════════════════════════════════════════════════════════════
# VERİ YAPILARI
# ═══════════════════════════════════════════════════════════════════

@dataclass
class QueryOutcome:
    """Tek bir sorgu sonucunun tam kaydı — meta öğrenme ham verisi."""
    timestamp: str
    question_hash: str          # SHA-256 kısaltma
    department: str
    mode: str
    intent: str
    confidence: float           # 0-100
    had_rag: bool
    had_web: bool
    had_tools: bool
    reflection_pass: bool
    reflection_confidence: float
    governance_compliance: float
    response_time_ms: float
    knowledge_learned: bool
    knowledge_type: Optional[str]
    criteria_scores: Dict[str, float] = field(default_factory=dict)
    issues: List[str] = field(default_factory=list)
    retry_count: int = 0
    numerical_valid: bool = True
    source_citation_valid: bool = True


@dataclass
class StrategyProfile:
    """Belirli bir soru tipi + departman + strateji kombinasyonunun performans profili."""
    key: str                           # f"{department}:{mode}:{strategy_hash}"
    department: str
    mode: str
    strategy_signature: str            # pipeline konfigürasyon özeti (ör: "rag+reflection+governance")
    total_queries: int = 0
    success_count: int = 0             # confidence >= HIGH_QUALITY_THRESHOLD
    failure_count: int = 0             # confidence <  LOW_QUALITY_THRESHOLD
    avg_confidence: float = 0.0
    avg_response_time_ms: float = 0.0
    last_used: str = ""
    confidence_sum: float = 0.0        # running sum — ortalama hesabı için
    response_time_sum: float = 0.0

    @property
    def success_rate(self) -> float:
        return (self.success_count / self.total_queries * 100) if self.total_queries > 0 else 0.0

    @property
    def failure_rate(self) -> float:
        return (self.failure_count / self.total_queries * 100) if self.total_queries > 0 else 0.0

    def to_dict(self) -> dict:
        d = asdict(self)
        d["success_rate"] = round(self.success_rate, 1)
        d["failure_rate"] = round(self.failure_rate, 1)
        d["avg_confidence"] = round(self.avg_confidence, 1)
        d["avg_response_time_ms"] = round(self.avg_response_time_ms, 0)
        return d


@dataclass
class KnowledgeGap:
    """RAG'da tespit edilen bilgi boşluğu."""
    topic: str                   # boşluk konusu (sorulara dayalı kümeleme)
    department: str
    first_seen: str
    last_seen: str
    frequency: int = 1           # kaç kez karşılaşıldı
    avg_confidence_when_hit: float = 0.0
    sample_questions: List[str] = field(default_factory=list)   # son 5 örnek
    resolved: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class FailurePattern:
    """Tekrarlayan başarısızlık kalıbı."""
    pattern_id: str
    description: str
    department: str
    mode: str
    frequency: int = 1
    common_issues: List[str] = field(default_factory=list)
    first_seen: str = ""
    last_seen: str = ""
    avg_confidence: float = 0.0
    sample_question_hashes: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class DomainPerformance:
    """Departman × Mod bazlı performans özeti."""
    department: str
    mode: str
    total_queries: int = 0
    avg_confidence: float = 0.0
    success_rate: float = 0.0
    avg_response_time_ms: float = 0.0
    top_issues: List[str] = field(default_factory=list)
    trend: str = "stable"     # improving | stable | degrading
    confidence_history: List[float] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["avg_confidence"] = round(d["avg_confidence"], 1)
        d["success_rate"] = round(d["success_rate"], 1)
        d["avg_response_time_ms"] = round(d["avg_response_time_ms"], 0)
        # Geçmişi kısalt — dashboard için
        d["confidence_history"] = d["confidence_history"][-20:]
        return d


@dataclass
class QualityTrend:
    """Zaman serisi kalite eğilim raporu."""
    direction: str              # "improving" | "stable" | "degrading"
    slope: float                # doğrusal regresyon eğimi per-query
    r_squared: float            # regresyon uyum kalitesi (0-1)
    current_avg: float          # son pencere ortalaması
    previous_avg: float         # önceki pencere ortalaması
    change_percent: float       # değişim yüzdesi
    sample_count: int
    window_size: int

    def to_dict(self) -> dict:
        return {
            "direction": self.direction,
            "slope": round(self.slope, 4),
            "r_squared": round(self.r_squared, 3),
            "current_avg": round(self.current_avg, 1),
            "previous_avg": round(self.previous_avg, 1),
            "change_percent": round(self.change_percent, 1),
            "sample_count": self.sample_count,
            "window_size": self.window_size,
        }


# ═══════════════════════════════════════════════════════════════════
# YARDIMCI FONKSİYONLAR
# ═══════════════════════════════════════════════════════════════════

def _utcnow_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _question_hash(question: str) -> str:
    return hashlib.sha256(question.strip().lower().encode()).hexdigest()[:16]


def _strategy_signature(had_rag: bool, had_web: bool, had_tools: bool,
                         reflection_pass: bool, retry_count: int) -> str:
    """Pipeline konfigürasyonundan bir strateji imzası üret."""
    parts = []
    if had_rag:
        parts.append("rag")
    if had_web:
        parts.append("web")
    if had_tools:
        parts.append("tools")
    if reflection_pass:
        parts.append("reflection_pass")
    if retry_count > 0:
        parts.append(f"retry_{retry_count}")
    return "+".join(parts) if parts else "direct"


def _linear_regression(values: List[float]) -> Tuple[float, float]:
    """Basit doğrusal regresyon — (slope, r_squared) döner."""
    n = len(values)
    if n < 2:
        return 0.0, 0.0

    x_mean = (n - 1) / 2.0
    y_mean = sum(values) / n
    ss_xy = sum((i - x_mean) * (v - y_mean) for i, v in enumerate(values))
    ss_xx = sum((i - x_mean) ** 2 for i in range(n))
    ss_yy = sum((v - y_mean) ** 2 for v in values)

    if ss_xx == 0:
        return 0.0, 0.0

    slope = ss_xy / ss_xx
    r_squared = (ss_xy ** 2) / (ss_xx * ss_yy) if ss_yy > 0 else 0.0
    return slope, min(r_squared, 1.0)


def _extract_topic_keywords(question: str) -> str:
    """Sorudan anahtar kelime grubu çıkar — knowledge gap kümeleme için."""
    import re
    # Türkçe stop words kaldır
    stop_words = {
        "bir", "bu", "şu", "ve", "ile", "için", "de", "da", "mi", "mı",
        "ne", "nasıl", "neden", "nerede", "kim", "hangi", "kaç", "olan",
        "olarak", "gibi", "daha", "en", "çok", "az", "var", "yok",
        "bana", "benim", "senin", "onun", "bizim", "söyle", "anlat",
    }
    words = re.findall(r"[a-züöçşığ]{3,}", question.lower())
    keywords = [w for w in words if w not in stop_words]
    return " ".join(sorted(keywords[:5]))


# ═══════════════════════════════════════════════════════════════════
# META LEARNING ENGINE
# ═══════════════════════════════════════════════════════════════════

class MetaLearningEngine:
    """Sistemin kendi performansından öğrenen üst-düzey analiz motoru.

    Her process_question() çağrısından sonra ``record_outcome()`` ile
    beslenir. Topladığı veriden:
      • Strateji profilleri (hangi pipeline konfigürasyonu ne kadar başarılı)
      • Bilgi boşlukları (hangi konularda RAG yetersiz)
      • Kalite eğilimleri (zaman serisi iyileşme / kötüleşme)
      • Başarısızlık kalıpları (tekrarlayan sorun tipleri)
      • alan performans haritası (departman × mod)
    çıkarır.
    """

    def __init__(self):
        self._outcomes: deque[QueryOutcome] = deque(maxlen=MAX_OUTCOME_HISTORY)
        self._strategy_profiles: Dict[str, StrategyProfile] = {}
        self._knowledge_gaps: Dict[str, KnowledgeGap] = {}
        self._failure_patterns: Dict[str, FailurePattern] = {}
        self._domain_perf: Dict[str, DomainPerformance] = {}   # key = dept:mode
        self._started_at: str = _utcnow_str()
        self._total_recorded: int = 0

    # ─────────────────── ANA GİRDİ ───────────────────

    def record_outcome(
        self,
        question: str,
        department: str,
        mode: str,
        intent: str,
        confidence: float,
        had_rag: bool,
        had_web: bool,
        had_tools: bool,
        reflection_pass: bool,
        reflection_confidence: float,
        governance_compliance: float,
        response_time_ms: float,
        knowledge_learned: bool,
        knowledge_type: Optional[str] = None,
        criteria_scores: Optional[Dict[str, float]] = None,
        issues: Optional[List[str]] = None,
        retry_count: int = 0,
        numerical_valid: bool = True,
        source_citation_valid: bool = True,
    ) -> Dict[str, Any]:
        """Bir sorgu sonucunu kaydet ve anlık meta-analiz üret.

        Returns:
            dict: Anlık meta-öğrenme sonuçları
                - strategy_profile_updated: bool
                - knowledge_gap_detected: bool
                - failure_pattern_detected: bool
                - quality_trend: str | None
                - recommendations: list[str]
        """
        now = _utcnow_str()
        q_hash = _question_hash(question)

        outcome = QueryOutcome(
            timestamp=now,
            question_hash=q_hash,
            department=department or "genel",
            mode=mode or "Sohbet",
            intent=intent or "",
            confidence=confidence,
            had_rag=had_rag,
            had_web=had_web,
            had_tools=had_tools,
            reflection_pass=reflection_pass,
            reflection_confidence=reflection_confidence,
            governance_compliance=governance_compliance,
            response_time_ms=response_time_ms,
            knowledge_learned=knowledge_learned,
            knowledge_type=knowledge_type,
            criteria_scores=criteria_scores or {},
            issues=issues or [],
            retry_count=retry_count,
            numerical_valid=numerical_valid,
            source_citation_valid=source_citation_valid,
        )
        self._outcomes.append(outcome)
        self._total_recorded += 1

        # Anlık analizler
        strategy_updated = self._update_strategy_profile(outcome)
        gap_detected = self._check_knowledge_gap(question, outcome)
        failure_detected = self._check_failure_pattern(outcome)
        self._update_domain_performance(outcome)

        # Öneriler
        recommendations = self._generate_recommendations(outcome)

        # Periyodik eğilim hesabı (her 10 sorguda bir)
        trend_direction = None
        if self._total_recorded % 10 == 0 and len(self._outcomes) >= TREND_MIN_SAMPLES:
            trend = self.get_quality_trend()
            trend_direction = trend.direction

        result = {
            "strategy_profile_updated": strategy_updated,
            "knowledge_gap_detected": gap_detected,
            "failure_pattern_detected": failure_detected,
            "quality_trend": trend_direction,
            "recommendations": recommendations,
        }

        logger.debug("meta_learning_recorded",
                      question_hash=q_hash,
                      confidence=confidence,
                      gap=gap_detected,
                      failure=failure_detected)

        return result

    # ─────────────────── STRATEJİ PROFİLLEME ───────────────────

    def _update_strategy_profile(self, outcome: QueryOutcome) -> bool:
        """Strateji profilini güncelle veya oluştur."""
        sig = _strategy_signature(
            outcome.had_rag, outcome.had_web, outcome.had_tools,
            outcome.reflection_pass, outcome.retry_count,
        )
        key = f"{outcome.department}:{outcome.mode}:{sig}"

        if key not in self._strategy_profiles:
            if len(self._strategy_profiles) >= MAX_STRATEGY_PROFILES:
                # En eski / en az kullanılan profili sil
                oldest_key = min(self._strategy_profiles,
                                 key=lambda k: self._strategy_profiles[k].total_queries)
                del self._strategy_profiles[oldest_key]

            self._strategy_profiles[key] = StrategyProfile(
                key=key,
                department=outcome.department,
                mode=outcome.mode,
                strategy_signature=sig,
            )

        profile = self._strategy_profiles[key]
        profile.total_queries += 1
        profile.confidence_sum += outcome.confidence
        profile.response_time_sum += outcome.response_time_ms
        profile.avg_confidence = profile.confidence_sum / profile.total_queries
        profile.avg_response_time_ms = profile.response_time_sum / profile.total_queries
        profile.last_used = outcome.timestamp

        if outcome.confidence >= HIGH_QUALITY_THRESHOLD:
            profile.success_count += 1
        elif outcome.confidence < LOW_QUALITY_THRESHOLD:
            profile.failure_count += 1

        return True

    # ─────────────────── BİLGİ BOŞLUĞU TESPİTİ ───────────────────

    def _check_knowledge_gap(self, question: str, outcome: QueryOutcome) -> bool:
        """RAG yetersiz kaldığında bilgi boşluğu kaydet."""
        # Eğer RAG kullanıldı ama confidence düşükse → bilgi boşluğu olabilir
        if not outcome.had_rag:
            return False
        if outcome.confidence >= HIGH_QUALITY_THRESHOLD:
            return False

        topic = _extract_topic_keywords(question)
        if not topic:
            return False

        gap_key = f"{outcome.department}:{topic}"

        if gap_key in self._knowledge_gaps:
            gap = self._knowledge_gaps[gap_key]
            gap.frequency += 1
            gap.last_seen = outcome.timestamp
            gap.avg_confidence_when_hit = (
                (gap.avg_confidence_when_hit * (gap.frequency - 1) + outcome.confidence)
                / gap.frequency
            )
            if len(gap.sample_questions) < 5:
                gap.sample_questions.append(question[:100])
        else:
            if len(self._knowledge_gaps) >= MAX_KNOWLEDGE_GAPS:
                # Düşük frekanslı gap'i sil
                least_key = min(self._knowledge_gaps,
                                key=lambda k: self._knowledge_gaps[k].frequency)
                del self._knowledge_gaps[least_key]

            self._knowledge_gaps[gap_key] = KnowledgeGap(
                topic=topic,
                department=outcome.department,
                first_seen=outcome.timestamp,
                last_seen=outcome.timestamp,
                frequency=1,
                avg_confidence_when_hit=outcome.confidence,
                sample_questions=[question[:100]],
            )

        return self._knowledge_gaps[gap_key].frequency >= GAP_FREQUENCY_THRESHOLD

    # ─────────────────── BAŞARISIZLIK KALIP TESPİTİ ───────────────────

    def _check_failure_pattern(self, outcome: QueryOutcome) -> bool:
        """Tekrarlayan başarısızlık kalıplarını tespit et."""
        if outcome.confidence >= LOW_QUALITY_THRESHOLD:
            return False

        # Kalıp anahtarı: departman + mod + en yaygın issue
        issue_key = outcome.issues[0] if outcome.issues else "low_confidence"
        pattern_id = f"{outcome.department}:{outcome.mode}:{issue_key}"

        if pattern_id in self._failure_patterns:
            fp = self._failure_patterns[pattern_id]
            fp.frequency += 1
            fp.last_seen = outcome.timestamp
            fp.avg_confidence = (
                (fp.avg_confidence * (fp.frequency - 1) + outcome.confidence)
                / fp.frequency
            )
            # Ortak issue'ları güncelle
            for issue in outcome.issues:
                if issue not in fp.common_issues:
                    fp.common_issues.append(issue)
            if len(fp.sample_question_hashes) < 10:
                fp.sample_question_hashes.append(outcome.question_hash)
        else:
            if len(self._failure_patterns) >= MAX_FAILURE_PATTERNS:
                least_key = min(self._failure_patterns,
                                key=lambda k: self._failure_patterns[k].frequency)
                del self._failure_patterns[least_key]

            self._failure_patterns[pattern_id] = FailurePattern(
                pattern_id=pattern_id,
                description=f"{outcome.department}/{outcome.mode} — {issue_key}",
                department=outcome.department,
                mode=outcome.mode,
                frequency=1,
                common_issues=list(outcome.issues),
                first_seen=outcome.timestamp,
                last_seen=outcome.timestamp,
                avg_confidence=outcome.confidence,
                sample_question_hashes=[outcome.question_hash],
            )

        return self._failure_patterns[pattern_id].frequency >= 3

    # ─────────────────── ALAN PERFORMANSI ───────────────────

    def _update_domain_performance(self, outcome: QueryOutcome):
        """Departman × Mod bazlı performans verisini güncelle."""
        key = f"{outcome.department}:{outcome.mode}"

        if key not in self._domain_perf:
            self._domain_perf[key] = DomainPerformance(
                department=outcome.department,
                mode=outcome.mode,
            )

        dp = self._domain_perf[key]
        dp.total_queries += 1
        dp.avg_confidence = (
            (dp.avg_confidence * (dp.total_queries - 1) + outcome.confidence)
            / dp.total_queries
        )
        dp.avg_response_time_ms = (
            (dp.avg_response_time_ms * (dp.total_queries - 1) + outcome.response_time_ms)
            / dp.total_queries
        )
        success_count = dp.success_rate * (dp.total_queries - 1) / 100.0
        if outcome.confidence >= HIGH_QUALITY_THRESHOLD:
            success_count += 1
        dp.success_rate = (success_count / dp.total_queries) * 100

        # Issue akümülasyonu
        for issue in outcome.issues:
            if issue not in dp.top_issues:
                dp.top_issues.append(issue)
        dp.top_issues = dp.top_issues[-10:]  # son 10 unique issue tut

        # Confidence geçmişi (eğilim hesabı için)
        dp.confidence_history.append(outcome.confidence)
        if len(dp.confidence_history) > 200:
            dp.confidence_history = dp.confidence_history[-200:]

        # Eğilim hesabı
        if len(dp.confidence_history) >= TREND_MIN_SAMPLES:
            recent = dp.confidence_history[-TREND_WINDOW_SIZE:]
            slope, _ = _linear_regression(recent)
            if slope > 0.3:
                dp.trend = "improving"
            elif slope < -0.3:
                dp.trend = "degrading"
            else:
                dp.trend = "stable"

    # ─────────────────── ÖNERİ MOTORU ───────────────────

    def _generate_recommendations(self, outcome: QueryOutcome) -> List[str]:
        """Anlık outcome'dan aksiyon önerileri üret."""
        recs = []

        # 1. Düşük confidence + RAG yok → RAG öner
        if outcome.confidence < HIGH_QUALITY_THRESHOLD and not outcome.had_rag:
            recs.append(f"[{outcome.department}] Bu alan için RAG dokümanları eklenebilir — RAG olmadan confidence düşük.")

        # 2. RAG var ama confidence hâlâ düşük → doküman kalitesi
        if outcome.had_rag and outcome.confidence < LOW_QUALITY_THRESHOLD:
            recs.append(f"[{outcome.department}] RAG dokümanları var ama kalite düşük — dokümanlar güncellenebilir veya zenginleştirilebilir.")

        # 3. Retry count yüksek → prompt sorunlu olabilir
        if outcome.retry_count >= 2:
            recs.append(f"[{outcome.mode}] Yüksek retry sayısı ({outcome.retry_count}) — prompt template gözden geçirilmeli.")

        # 4. Numerical validation fail → veri doğruluğu
        if not outcome.numerical_valid:
            recs.append("Sayısal doğrulama başarısız — LLM halüsinasyon yapıyor olabilir, RAG verisi kontrol edilmeli.")

        # 5. Governance compliance düşük
        if outcome.governance_compliance < 0.7:
            recs.append(f"Governance uyumluluğu düşük ({outcome.governance_compliance:.0%}) — bias veya politika ihlali kontrol edilmeli.")

        # 6. Domain bazlı birikim
        dp_key = f"{outcome.department}:{outcome.mode}"
        if dp_key in self._domain_perf:
            dp = self._domain_perf[dp_key]
            if dp.total_queries >= 20 and dp.success_rate < 50:
                recs.append(f"[{outcome.department}/{outcome.mode}] Genel başarı oranı düşük ({dp.success_rate:.0f}%) — bu alan için özel prompt stratejisi gerekebilir.")

        return recs

    # ═══════════════════════════════════════════════════════════
    # ANALİZ API'leri
    # ═══════════════════════════════════════════════════════════

    def get_quality_trend(self, window: int = TREND_WINDOW_SIZE) -> QualityTrend:
        """Genel kalite eğilimini hesapla."""
        confidences = [o.confidence for o in self._outcomes]

        if len(confidences) < TREND_MIN_SAMPLES:
            return QualityTrend(
                direction="insufficient_data",
                slope=0.0, r_squared=0.0,
                current_avg=0.0, previous_avg=0.0,
                change_percent=0.0,
                sample_count=len(confidences),
                window_size=window,
            )

        recent = confidences[-window:]
        previous = confidences[-2 * window:-window] if len(confidences) >= 2 * window else confidences[:len(confidences) - window]

        current_avg = sum(recent) / len(recent)
        previous_avg = sum(previous) / len(previous) if previous else current_avg

        slope, r_squared = _linear_regression(recent)
        change_percent = ((current_avg - previous_avg) / previous_avg * 100) if previous_avg > 0 else 0.0

        if slope > 0.3 and r_squared > 0.1:
            direction = "improving"
        elif slope < -0.3 and r_squared > 0.1:
            direction = "degrading"
        else:
            direction = "stable"

        return QualityTrend(
            direction=direction,
            slope=slope,
            r_squared=r_squared,
            current_avg=current_avg,
            previous_avg=previous_avg,
            change_percent=change_percent,
            sample_count=len(confidences),
            window_size=window,
        )

    def get_strategy_rankings(self, department: Optional[str] = None,
                               mode: Optional[str] = None,
                               min_queries: int = 5) -> List[dict]:
        """Strateji profillerini başarı oranına göre sırala.

        Args:
            department: Filtre (None = tümü)
            mode: Filtre (None = tümü)
            min_queries: Minimum sorgu sayısı filtresi

        Returns:
            list[dict]: Başarı oranına göre azalan sırada profiller
        """
        profiles = []
        for p in self._strategy_profiles.values():
            if p.total_queries < min_queries:
                continue
            if department and p.department != department:
                continue
            if mode and p.mode != mode:
                continue
            profiles.append(p.to_dict())

        profiles.sort(key=lambda x: x["success_rate"], reverse=True)
        return profiles

    def get_knowledge_gaps(self, min_frequency: int = GAP_FREQUENCY_THRESHOLD,
                            department: Optional[str] = None) -> List[dict]:
        """Bilgi boşluklarını frekansa göre döndür.

        Args:
            min_frequency: Minimum tekrar sayısı
            department: Filtre (None = tümü)

        Returns:
            list[dict]: Frekansa göre azalan sırada boşluklar
        """
        gaps = []
        for g in self._knowledge_gaps.values():
            if g.frequency < min_frequency:
                continue
            if department and g.department != department:
                continue
            if g.resolved:
                continue
            gaps.append(g.to_dict())

        gaps.sort(key=lambda x: x["frequency"], reverse=True)
        return gaps

    def get_failure_patterns(self, min_frequency: int = 3,
                              department: Optional[str] = None) -> List[dict]:
        """Tekrarlayan başarısızlık kalıpları.

        Args:
            min_frequency: Minimum tekrar sayısı
            department: Filtre (None = tümü)

        Returns:
            list[dict]: Frekansa göre azalan sırada kalıplar
        """
        patterns = []
        for fp in self._failure_patterns.values():
            if fp.frequency < min_frequency:
                continue
            if department and fp.department != department:
                continue
            patterns.append(fp.to_dict())

        patterns.sort(key=lambda x: x["frequency"], reverse=True)
        return patterns

    def get_domain_performance_map(self) -> List[dict]:
        """Tüm departman × mod performans haritası."""
        return [dp.to_dict() for dp in sorted(
            self._domain_perf.values(),
            key=lambda x: x.avg_confidence,
        )]

    def get_weakest_domains(self, top_n: int = 5) -> List[dict]:
        """En düşük performanslı departman × mod kombinasyonları."""
        domains = [
            dp for dp in self._domain_perf.values()
            if dp.total_queries >= 5
        ]
        domains.sort(key=lambda x: x.avg_confidence)
        return [d.to_dict() for d in domains[:top_n]]

    def get_strongest_domains(self, top_n: int = 5) -> List[dict]:
        """En yüksek performanslı departman × mod kombinasyonları."""
        domains = [
            dp for dp in self._domain_perf.values()
            if dp.total_queries >= 5
        ]
        domains.sort(key=lambda x: x.avg_confidence, reverse=True)
        return [d.to_dict() for d in domains[:top_n]]

    def get_criteria_analysis(self) -> Dict[str, Any]:
        """Reflection kriterlerinin genel performans analizi.

        Hangi kriter sürekli düşük → iyileştirme önceliği.
        """
        criteria_totals: Dict[str, List[float]] = defaultdict(list)

        for o in self._outcomes:
            for crit, score in o.criteria_scores.items():
                criteria_totals[crit].append(score)

        analysis = {}
        for crit, scores in criteria_totals.items():
            if not scores:
                continue
            avg = sum(scores) / len(scores)
            low_count = sum(1 for s in scores if s < 60)
            analysis[crit] = {
                "avg_score": round(avg, 1),
                "total_evaluations": len(scores),
                "low_score_count": low_count,
                "low_score_rate": round(low_count / len(scores) * 100, 1),
                "trend": "improving" if len(scores) > 20 and
                         sum(scores[-10:]) / 10 > avg + 3 else
                         ("degrading" if len(scores) > 20 and
                          sum(scores[-10:]) / 10 < avg - 3 else "stable"),
            }

        return dict(sorted(analysis.items(), key=lambda x: x[1]["avg_score"]))

    def get_learning_effectiveness(self) -> Dict[str, Any]:
        """Otomatik öğrenme sisteminin etkinlik analizi."""
        total = len(self._outcomes)
        if total == 0:
            return {"total_queries": 0, "learning_rate": 0.0}

        learned_count = sum(1 for o in self._outcomes if o.knowledge_learned)
        knowledge_types = Counter(
            o.knowledge_type for o in self._outcomes
            if o.knowledge_learned and o.knowledge_type
        )

        # Öğrenme sonrası confidence iyileşmesi
        pre_learn_conf = [o.confidence for o in self._outcomes if not o.knowledge_learned]
        post_learn_conf = [o.confidence for o in self._outcomes if o.knowledge_learned]

        return {
            "total_queries": total,
            "learned_count": learned_count,
            "learning_rate": round(learned_count / total * 100, 1),
            "knowledge_type_distribution": dict(knowledge_types.most_common()),
            "avg_confidence_without_learning": round(
                sum(pre_learn_conf) / len(pre_learn_conf), 1
            ) if pre_learn_conf else 0.0,
            "avg_confidence_with_learning": round(
                sum(post_learn_conf) / len(post_learn_conf), 1
            ) if post_learn_conf else 0.0,
        }

    # ═══════════════════════════════════════════════════════════
    # DASHBOARD & EXPORT
    # ═══════════════════════════════════════════════════════════

    def get_dashboard(self) -> Dict[str, Any]:
        """Tam meta-öğrenme dashboard verisi.

        Returns:
            dict: Dashboard için gereken tüm metrikler
        """
        total = len(self._outcomes)

        if total == 0:
            return {
                "available": True,
                "total_outcomes_recorded": 0,
                "started_at": self._started_at,
                "quality_trend": QualityTrend(
                    "insufficient_data", 0, 0, 0, 0, 0, 0, 0
                ).to_dict(),
                "strategy_profiles_count": 0,
                "knowledge_gaps_count": 0,
                "failure_patterns_count": 0,
                "domain_count": 0,
            }

        avg_conf = sum(o.confidence for o in self._outcomes) / total
        avg_rt = sum(o.response_time_ms for o in self._outcomes) / total
        success_count = sum(1 for o in self._outcomes if o.confidence >= HIGH_QUALITY_THRESHOLD)

        trend = self.get_quality_trend()
        active_gaps = [g for g in self._knowledge_gaps.values()
                       if g.frequency >= GAP_FREQUENCY_THRESHOLD and not g.resolved]
        critical_failures = [f for f in self._failure_patterns.values()
                             if f.frequency >= 5]

        return {
            "available": True,
            "total_outcomes_recorded": self._total_recorded,
            "buffer_size": total,
            "started_at": self._started_at,
            "overall": {
                "avg_confidence": round(avg_conf, 1),
                "success_rate": round(success_count / total * 100, 1),
                "avg_response_time_ms": round(avg_rt, 0),
            },
            "quality_trend": trend.to_dict(),
            "strategy_profiles_count": len(self._strategy_profiles),
            "top_strategies": self.get_strategy_rankings(min_queries=3)[:5],
            "knowledge_gaps_count": len(active_gaps),
            "top_knowledge_gaps": [g.to_dict() for g in sorted(
                active_gaps, key=lambda x: x.frequency, reverse=True
            )[:5]],
            "failure_patterns_count": len(self._failure_patterns),
            "critical_failure_patterns": [f.to_dict() for f in sorted(
                critical_failures, key=lambda x: x.frequency, reverse=True
            )[:5]],
            "domain_count": len(self._domain_perf),
            "weakest_domains": self.get_weakest_domains(3),
            "strongest_domains": self.get_strongest_domains(3),
            "criteria_analysis": self.get_criteria_analysis(),
            "learning_effectiveness": self.get_learning_effectiveness(),
        }

    def get_improvement_opportunities(self) -> List[Dict[str, Any]]:
        """Self-Improvement Loop'a gönderilecek iyileştirme fırsatları.

        Her fırsat şunları içerir:
          - type: "threshold" | "rag" | "prompt" | "knowledge" | "pipeline"
          - priority: 1-10 (10 = en acil)
          - target: etkilenen departman/mod
          - current_metric: mevcut performans
          - description: insan okunabilir açıklama
          - action_hint: self_improvement modülüne ipucu
        """
        opportunities = []

        # 1. Zayıf domain'ler → prompt iyileştirme fırsatı
        for dp in self._domain_perf.values():
            if dp.total_queries >= 10 and dp.avg_confidence < 60:
                opportunities.append({
                    "type": "prompt",
                    "priority": min(10, int(10 - dp.avg_confidence / 10)),
                    "target": f"{dp.department}/{dp.mode}",
                    "current_metric": round(dp.avg_confidence, 1),
                    "description": f"{dp.department} / {dp.mode} alanında ortalama confidence {dp.avg_confidence:.0f} — prompt stratejisi iyileştirilmeli.",
                    "action_hint": "prompt_evolve",
                })

        # 2. Bilgi boşlukları → RAG iyileştirme
        for gap in self._knowledge_gaps.values():
            if gap.frequency >= GAP_FREQUENCY_THRESHOLD and not gap.resolved:
                opportunities.append({
                    "type": "knowledge",
                    "priority": min(10, gap.frequency),
                    "target": f"{gap.department}/{gap.topic}",
                    "current_metric": round(gap.avg_confidence_when_hit, 1),
                    "description": f"'{gap.topic}' konusunda {gap.frequency} kez bilgi boşluğu tespit edildi.",
                    "action_hint": "rag_expand",
                })

        # 3. Başarısızlık kalıpları → pipeline ayarı
        for fp in self._failure_patterns.values():
            if fp.frequency >= 5:
                opportunities.append({
                    "type": "pipeline",
                    "priority": min(10, fp.frequency // 2),
                    "target": f"{fp.department}/{fp.mode}",
                    "current_metric": round(fp.avg_confidence, 1),
                    "description": f"Tekrarlayan başarısızlık: {fp.description} ({fp.frequency}x)",
                    "action_hint": "threshold_adjust",
                })

        # 4. Kriter bazlı zayıflıklar → hedefli iyileştirme
        criteria = self.get_criteria_analysis()
        for crit, info in criteria.items():
            if info["avg_score"] < 55 and info["total_evaluations"] >= 10:
                opportunities.append({
                    "type": "threshold",
                    "priority": max(5, int(8 - info["avg_score"] / 10)),
                    "target": crit,
                    "current_metric": info["avg_score"],
                    "description": f"'{crit}' kriteri ortalama {info['avg_score']:.0f} puan — iyileştirme fırsatı.",
                    "action_hint": "criteria_focus",
                })

        # Önceliğe göre sırala
        opportunities.sort(key=lambda x: x["priority"], reverse=True)
        return opportunities

    def resolve_knowledge_gap(self, gap_key: str) -> bool:
        """Bir bilgi boşluğunu çözülmüş olarak işaretle (yeni doküman eklendikten sonra)."""
        if gap_key in self._knowledge_gaps:
            self._knowledge_gaps[gap_key].resolved = True
            return True
        return False

    def reset(self):
        """Tüm meta-öğrenme verisini sıfırla."""
        self._outcomes.clear()
        self._strategy_profiles.clear()
        self._knowledge_gaps.clear()
        self._failure_patterns.clear()
        self._domain_perf.clear()
        self._total_recorded = 0
        self._started_at = _utcnow_str()
        logger.info("meta_learning_reset")


# ═══════════════════════════════════════════════════════════════════
# GLOBAL SINGLETON
# ═══════════════════════════════════════════════════════════════════

meta_learning_engine: MetaLearningEngine = MetaLearningEngine()


# ═══════════════════════════════════════════════════════════════════
# KOLAYLIK FONKSİYONLARI — engine.py entegrasyonu için
# ═══════════════════════════════════════════════════════════════════

def record_query_outcome(**kwargs) -> Dict[str, Any]:
    """Kolay erişim: meta_learning_engine.record_outcome() wrapper."""
    return meta_learning_engine.record_outcome(**kwargs)


def get_meta_dashboard() -> Dict[str, Any]:
    """Kolay erişim: meta_learning_engine.get_dashboard() wrapper."""
    return meta_learning_engine.get_dashboard()


def get_improvement_opportunities() -> List[Dict[str, Any]]:
    """Kolay erişim: meta_learning_engine.get_improvement_opportunities() wrapper."""
    return meta_learning_engine.get_improvement_opportunities()
