"""
Self-Improvement Loop — v1.0.0
==================================
Meta Learning Engine bulgularını OTOMATİK aksiyona dönüştüren kapalı döngü sistemi.

Yetenek haritası:
- ThresholdOptimizer: Reflection threshold'larını domain bazlı otomatik ayar
- RAGTuner: Retrieval parametrelerini performansa göre uyarla
- PromptEvolver: Düşük performanslı domain'ler için prompt template önerileri
- ImprovementTracker: Her iyileştirmenin before/after etkisini ölç
- AutoPrioritizer: Knowledge gap + failure pattern'lere göre öğrenme önceliği
- ImprovementScheduler: Periyodik iyileştirme döngüsü zamanlama

Entegrasyon noktaları:
- meta_learning.py → get_improvement_opportunities() → apply_improvements()
- reflection.py → threshold değerleri dinamik güncelleme
- engine.py → pipeline konfigürasyon önerileri
- knowledge_extractor.py → MIN_QUALITY_SCORE ayarı
- monitoring.py → iyileştirme sonrası performans takibi

Döngü akışı:
  1. Meta Learning Engine → iyileştirme fırsatları toplar
  2. AutoPrioritizer → en etkili fırsatları seçer
  3. ThresholdOptimizer / RAGTuner / PromptEvolver → aksiyonları uygular
  4. ImprovementTracker → önceki/sonraki metrikleri karşılaştırır
  5. Başarısız iyileştirmeler otomatik geri alınır (rollback)

v4.6.0 — CompanyAi
"""

from __future__ import annotations

import copy
import hashlib
import json
import time
from collections import deque
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

try:
    import structlog
    logger = structlog.get_logger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════
# SABİTLER
# ═══════════════════════════════════════════════════════════════════

MAX_IMPROVEMENT_HISTORY = 500
MAX_ACTIVE_ADJUSTMENTS = 50
ROLLBACK_OBSERVATION_QUERIES = 30     # Bu kadar sorgu sonrası before/after karşılaştır
MIN_IMPROVEMENT_PERCENT = 3.0         # Bu yüzdeden az iyileşme → geri al
AUTO_IMPROVE_INTERVAL_QUERIES = 100   # Her N sorguda otomatik iyileştirme döngüsü
MAX_CONCURRENT_EXPERIMENTS = 3        # Aynı anda en fazla N iyileştirme deneyimi

# Threshold sınırları (reflection)
CONFIDENCE_THRESHOLD_MIN = 35
CONFIDENCE_THRESHOLD_MAX = 85
RETRY_THRESHOLD_MIN = 40
RETRY_THRESHOLD_MAX = 75

# RAG tuning sınırları
RAG_TOP_K_MIN = 2
RAG_TOP_K_MAX = 10
RAG_SIMILARITY_MIN = 0.3
RAG_SIMILARITY_MAX = 0.9


# ═══════════════════════════════════════════════════════════════════
# VERİ YAPILARI
# ═══════════════════════════════════════════════════════════════════

class ImprovementStatus(str, Enum):
    PENDING = "pending"
    ACTIVE = "active"           # uygulandı, gözlem süreci
    SUCCESSFUL = "successful"   # before/after iyileşme onaylandı
    FAILED = "failed"           # iyileşme yok, geri alındı
    ROLLED_BACK = "rolled_back" # manuel geri alım


class ImprovementType(str, Enum):
    THRESHOLD = "threshold"
    RAG = "rag"
    PROMPT = "prompt"
    KNOWLEDGE = "knowledge"
    PIPELINE = "pipeline"


def _utcnow_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class ImprovementAction:
    """Tek bir iyileştirme aksiyonunun tam kaydı."""
    action_id: str
    improvement_type: str       # ImprovementType value
    target: str                 # etkilenen alan (ör: "tekstil/Analiz", "data_accuracy" kriteri)
    description: str
    priority: int               # 1-10

    # Önceki durum (rollback için)
    previous_value: Any = None
    new_value: Any = None
    parameter_path: str = ""    # ör: "reflection.AUTO_REANALYZE_THRESHOLD"

    # Before / After metrikleri
    before_metrics: Dict[str, float] = field(default_factory=dict)
    after_metrics: Dict[str, float] = field(default_factory=dict)

    # Durum
    status: str = ImprovementStatus.PENDING
    created_at: str = ""
    applied_at: str = ""
    evaluated_at: str = ""
    queries_since_applied: int = 0
    observation_target: int = ROLLBACK_OBSERVATION_QUERIES

    # Sonuç
    improvement_percent: float = 0.0
    rollback_reason: str = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        d["improvement_percent"] = round(d["improvement_percent"], 2)
        return d


@dataclass
class ThresholdConfig:
    """Reflection threshold ayarları — domain bazlı override."""
    domain_key: str                # "department:mode"
    auto_reanalyze_threshold: int  # 0-100
    max_retry_count: int           # 0-5
    applied_at: str = ""
    source_action_id: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class RAGConfig:
    """RAG retrieval ayarları — domain bazlı override."""
    domain_key: str                # "department:mode"
    top_k: int = 5
    similarity_threshold: float = 0.5
    applied_at: str = ""
    source_action_id: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class PromptSuggestion:
    """Düşük performanslı domain için prompt iyileştirme önerisi."""
    domain_key: str
    suggestion_type: str           # "add_context" | "add_examples" | "restructure" | "simplify"
    suggestion_text: str
    reason: str
    expected_impact: str           # "low" | "medium" | "high"
    auto_applicable: bool = False  # otomatik uygulanabilir mi
    applied: bool = False
    created_at: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ImprovementCycleSummary:
    """Bir iyileştirme döngüsünün özet raporu."""
    cycle_id: int
    timestamp: str
    opportunities_found: int
    actions_taken: int
    actions_successful: int
    actions_failed: int
    actions_pending: int
    top_improvements: List[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


# ═══════════════════════════════════════════════════════════════════
# THRESHOLD OPTIMIZER
# ═══════════════════════════════════════════════════════════════════

class ThresholdOptimizer:
    """Reflection threshold'larını domain bazlı optimize et.

    Her domain (department × mode) için:
    - success rate düşük → threshold düşür (daha toleranslı)
    - success rate yüksek + retry yüksek → threshold yükselt (gereksiz retry azalt)
    - failure rate yüksek → max_retry artır
    """

    def __init__(self):
        self._overrides: Dict[str, ThresholdConfig] = {}
        self._default_threshold = 60    # reflection.py varsayılan
        self._default_max_retry = 2

    def calculate_optimal_threshold(
        self,
        domain_key: str,
        avg_confidence: float,
        success_rate: float,
        avg_retry_count: float,
        failure_rate: float,
    ) -> ThresholdConfig:
        """Domain için optimal threshold hesapla.

        Args:
            domain_key: "department:mode"
            avg_confidence: Ortalama confidence (0-100)
            success_rate: Başarı oranı (0-100)
            avg_retry_count: Ortalama retry sayısı
            failure_rate: Başarısızlık oranı (0-100)

        Returns:
            ThresholdConfig: Önerilen threshold ayarları
        """
        threshold = self._default_threshold
        max_retry = self._default_max_retry

        # Strateji 1: Düşük başarı oranı → threshold'u düşür
        if success_rate < 40:
            threshold = max(CONFIDENCE_THRESHOLD_MIN, int(avg_confidence * 0.75))
        elif success_rate < 60:
            threshold = max(CONFIDENCE_THRESHOLD_MIN, int(avg_confidence * 0.85))
        elif success_rate > 85 and avg_retry_count > 1.5:
            # Başarılı ama çok retry → threshold yükselt, retry azalt
            threshold = min(CONFIDENCE_THRESHOLD_MAX, int(avg_confidence * 0.95))
            max_retry = max(1, max_retry - 1)

        # Strateji 2: Yüksek failure rate → daha fazla retry
        if failure_rate > 30:
            max_retry = min(4, max_retry + 1)
        elif failure_rate > 50:
            max_retry = min(5, max_retry + 2)

        # Sınır kontrolü
        threshold = max(CONFIDENCE_THRESHOLD_MIN, min(CONFIDENCE_THRESHOLD_MAX, threshold))
        max_retry = max(0, min(5, max_retry))

        config = ThresholdConfig(
            domain_key=domain_key,
            auto_reanalyze_threshold=threshold,
            max_retry_count=max_retry,
            applied_at=_utcnow_str(),
        )
        return config

    def apply(self, config: ThresholdConfig, action_id: str = "") -> ThresholdConfig:
        """Threshold ayarını uygula ve önceki değeri kaydet."""
        config.source_action_id = action_id
        config.applied_at = _utcnow_str()
        self._overrides[config.domain_key] = config
        logger.info("threshold_applied",
                     domain=config.domain_key,
                     threshold=config.auto_reanalyze_threshold,
                     max_retry=config.max_retry_count)
        return config

    def get_override(self, department: str, mode: str) -> Optional[ThresholdConfig]:
        """Belirli domain için threshold override var mı?"""
        key = f"{department}:{mode}"
        return self._overrides.get(key)

    def get_all_overrides(self) -> List[dict]:
        """Tüm aktif override'ları döndür."""
        return [c.to_dict() for c in self._overrides.values()]

    def remove_override(self, domain_key: str) -> bool:
        """Bir domain override'ını kaldır."""
        if domain_key in self._overrides:
            del self._overrides[domain_key]
            return True
        return False


# ═══════════════════════════════════════════════════════════════════
# RAG TUNER
# ═══════════════════════════════════════════════════════════════════

class RAGTuner:
    """RAG retrieval parametrelerini domain bazlı optimize et.

    Stratejiler:
    - Düşük confidence + RAG kullanılmış → top_k artır, similarity düşür
    - Yüksek confidence + RAG kullanılmış → parametreleri koru
    - Halüsinasyon tespit edilmiş → similarity yükselt (daha kesin eşleşme)
    """

    def __init__(self):
        self._overrides: Dict[str, RAGConfig] = {}
        self._default_top_k = 5
        self._default_similarity = 0.5

    def calculate_optimal_config(
        self,
        domain_key: str,
        avg_confidence: float,
        numerical_valid_rate: float,
        source_citation_valid_rate: float,
        avg_rag_confidence: float,
    ) -> RAGConfig:
        """Domain için optimal RAG config hesapla.

        Args:
            domain_key: "department:mode"
            avg_confidence: Ortalama confidence
            numerical_valid_rate: Sayısal doğrulama başarı oranı (0-1)
            source_citation_valid_rate: Kaynak atıf doğrulama oranı (0-1)
            avg_rag_confidence: RAG kullanıldığında ortalama confidence

        Returns:
            RAGConfig: Önerilen RAG ayarları
        """
        top_k = self._default_top_k
        similarity = self._default_similarity

        # Strateji 1: Düşük confidence → daha fazla doküman getir
        if avg_rag_confidence < 50:
            top_k = min(RAG_TOP_K_MAX, top_k + 2)
            similarity = max(RAG_SIMILARITY_MIN, similarity - 0.1)
        elif avg_rag_confidence < 65:
            top_k = min(RAG_TOP_K_MAX, top_k + 1)

        # Strateji 2: Halüsinasyon problemi → daha kesin eşleşme
        if numerical_valid_rate < 0.7:
            similarity = min(RAG_SIMILARITY_MAX, similarity + 0.15)
            top_k = max(RAG_TOP_K_MIN, top_k - 1)  # daha az ama daha kesin

        # Strateji 3: Kaynak atıf problemi → daha fazla kaynak
        if source_citation_valid_rate < 0.8:
            top_k = min(RAG_TOP_K_MAX, top_k + 1)

        config = RAGConfig(
            domain_key=domain_key,
            top_k=top_k,
            similarity_threshold=round(similarity, 2),
            applied_at=_utcnow_str(),
        )
        return config

    def apply(self, config: RAGConfig, action_id: str = "") -> RAGConfig:
        """RAG ayarını uygula."""
        config.source_action_id = action_id
        config.applied_at = _utcnow_str()
        self._overrides[config.domain_key] = config
        logger.info("rag_tuned",
                     domain=config.domain_key,
                     top_k=config.top_k,
                     similarity=config.similarity_threshold)
        return config

    def get_override(self, department: str, mode: str) -> Optional[RAGConfig]:
        """Belirli domain için RAG override var mı?"""
        key = f"{department}:{mode}"
        return self._overrides.get(key)

    def get_all_overrides(self) -> List[dict]:
        """Tüm aktif override'ları döndür."""
        return [c.to_dict() for c in self._overrides.values()]

    def remove_override(self, domain_key: str) -> bool:
        if domain_key in self._overrides:
            del self._overrides[domain_key]
            return True
        return False


# ═══════════════════════════════════════════════════════════════════
# PROMPT EVOLVER
# ═══════════════════════════════════════════════════════════════════

class PromptEvolver:
    """Düşük performanslı domain'ler için prompt iyileştirme önerileri üret.

    Tam otomatik prompt değişikliği riskli olduğundan, bu modül
    *öneriler* üretir. Admin panelden onaylandıktan sonra uygulanır.
    """

    def __init__(self):
        self._suggestions: List[PromptSuggestion] = []
        self._max_suggestions = 100

    def generate_suggestions(
        self,
        domain_key: str,
        avg_confidence: float,
        top_issues: List[str],
        failure_rate: float,
        criteria_weaknesses: Dict[str, float],
    ) -> List[PromptSuggestion]:
        """Domain analizine göre prompt önerileri üret.

        Args:
            domain_key: "department:mode"
            avg_confidence: Domain ortalama confidence
            top_issues: En sık karşılaşılan sorunlar
            failure_rate: Başarısızlık oranı (0-100)
            criteria_weaknesses: Zayıf kriterler ve skorları

        Returns:
            list[PromptSuggestion]: Öneriler
        """
        suggestions = []
        now = _utcnow_str()
        department, mode = domain_key.split(":", 1) if ":" in domain_key else (domain_key, "genel")

        # 1. Veri doğruluğu problemi → kaynak vurgulama önerisi
        if criteria_weaknesses.get("data_accuracy", 100) < 55:
            suggestions.append(PromptSuggestion(
                domain_key=domain_key,
                suggestion_type="add_context",
                suggestion_text=(
                    f"'{department}' departmanı prompt'una şu talimatı ekle: "
                    f"'Yanıtındaki tüm sayısal değerleri MUTLAKA kaynak dokümanlardan doğrula. "
                    f"Emin olmadığın rakamları kullanma, bunun yerine \"kesin veri mevcut değil\" de.'"
                ),
                reason=f"data_accuracy kriteri düşük ({criteria_weaknesses['data_accuracy']:.0f})",
                expected_impact="high",
                auto_applicable=True,
                created_at=now,
            ))

        # 2. Mantıksal tutarlılık problemi → yapılandırılmış düşünme
        if criteria_weaknesses.get("logical_consistency", 100) < 55:
            suggestions.append(PromptSuggestion(
                domain_key=domain_key,
                suggestion_type="restructure",
                suggestion_text=(
                    f"'{department}' prompt'una adım-adım düşünme talimatı ekle: "
                    f"'Önce veriyi analiz et, sonra sonuçları çıkar, son olarak önerileri sun. "
                    f"Her adımda bir önceki adımla tutarlılığı kontrol et.'"
                ),
                reason=f"logical_consistency kriteri düşük ({criteria_weaknesses['logical_consistency']:.0f})",
                expected_impact="medium",
                auto_applicable=True,
                created_at=now,
            ))

        # 3. Risk netliği problemi → risk çerçevesi ekleme
        if criteria_weaknesses.get("risk_clarity", 100) < 55:
            suggestions.append(PromptSuggestion(
                domain_key=domain_key,
                suggestion_type="add_context",
                suggestion_text=(
                    f"'{department}' prompt'una risk çerçevesi ekle: "
                    f"'Her önerinle birlikte olasılık ve etki seviyesini belirt. "
                    f"Riskleri Düşük/Orta/Yüksek/Kritik olarak sınıflandır.'"
                ),
                reason=f"risk_clarity kriteri düşük ({criteria_weaknesses['risk_clarity']:.0f})",
                expected_impact="medium",
                auto_applicable=True,
                created_at=now,
            ))

        # 4. Yüksek failure rate → basitleştirme
        if failure_rate > 40:
            suggestions.append(PromptSuggestion(
                domain_key=domain_key,
                suggestion_type="simplify",
                suggestion_text=(
                    f"'{department}/{mode}' modunda yüksek başarısızlık ({failure_rate:.0f}%). "
                    f"Prompt'u basitleştir — daha az talimat, daha net odak. "
                    f"Karmaşık talimatlar yerine 3-5 temel kural kullan."
                ),
                reason=f"Failure rate çok yüksek: {failure_rate:.0f}%",
                expected_impact="high",
                auto_applicable=False,
                created_at=now,
            ))

        # 5. Genel düşük confidence → few-shot örnekler
        if avg_confidence < 50:
            suggestions.append(PromptSuggestion(
                domain_key=domain_key,
                suggestion_type="add_examples",
                suggestion_text=(
                    f"'{department}/{mode}' moduna domain-specific few-shot örnekleri ekle. "
                    f"En az 2-3 başarılı soru-cevap örneği prompt'a dahil edilmeli."
                ),
                reason=f"Genel confidence çok düşük: {avg_confidence:.0f}",
                expected_impact="high",
                auto_applicable=False,
                created_at=now,
            ))

        # Kaydet
        for s in suggestions:
            if len(self._suggestions) >= self._max_suggestions:
                self._suggestions.pop(0)
            self._suggestions.append(s)

        return suggestions

    def get_pending_suggestions(self, domain_key: Optional[str] = None) -> List[dict]:
        """Onay bekleyen önerileri döndür."""
        results = []
        for s in self._suggestions:
            if s.applied:
                continue
            if domain_key and s.domain_key != domain_key:
                continue
            results.append(s.to_dict())
        return results

    def get_all_suggestions(self) -> List[dict]:
        """Tüm önerileri döndür."""
        return [s.to_dict() for s in self._suggestions]

    def mark_applied(self, index: int) -> bool:
        """Bir öneriyi uygulanmış olarak işaretle."""
        if 0 <= index < len(self._suggestions):
            self._suggestions[index].applied = True
            return True
        return False


# ═══════════════════════════════════════════════════════════════════
# IMPROVEMENT TRACKER
# ═══════════════════════════════════════════════════════════════════

class ImprovementTracker:
    """Her iyileştirme aksiyonunun before/after etkisini takip eder.

    Akış:
    1. Aksiyon uygulanır → before_metrics kaydedilir
    2. ROLLBACK_OBSERVATION_QUERIES sorgu geçtikten sonra after_metrics hesaplanır
    3. Karşılaştırma yapılır → iyileşme yeterli mi?
    4. Yetersizse → rollback tetiklenir
    """

    def __init__(self):
        self._actions: deque[ImprovementAction] = deque(maxlen=MAX_IMPROVEMENT_HISTORY)
        self._active_actions: Dict[str, ImprovementAction] = {}  # action_id → action
        self._cycle_count: int = 0
        self._cycle_summaries: List[ImprovementCycleSummary] = []

    def create_action(
        self,
        improvement_type: str,
        target: str,
        description: str,
        priority: int,
        parameter_path: str = "",
        previous_value: Any = None,
        new_value: Any = None,
        before_metrics: Optional[Dict[str, float]] = None,
    ) -> ImprovementAction:
        """Yeni bir iyileştirme aksiyonu oluştur."""
        action_id = hashlib.sha256(
            f"{target}:{improvement_type}:{_utcnow_str()}".encode()
        ).hexdigest()[:12]

        action = ImprovementAction(
            action_id=action_id,
            improvement_type=improvement_type,
            target=target,
            description=description,
            priority=priority,
            parameter_path=parameter_path,
            previous_value=previous_value,
            new_value=new_value,
            before_metrics=before_metrics or {},
            status=ImprovementStatus.PENDING,
            created_at=_utcnow_str(),
        )
        self._actions.append(action)
        return action

    def activate(self, action: ImprovementAction) -> bool:
        """Aksiyonu aktif et — gözlem sürecini başlat."""
        if len(self._active_actions) >= MAX_CONCURRENT_EXPERIMENTS:
            logger.warning("max_concurrent_experiments_reached",
                           active=len(self._active_actions))
            return False

        action.status = ImprovementStatus.ACTIVE
        action.applied_at = _utcnow_str()
        action.queries_since_applied = 0
        self._active_actions[action.action_id] = action
        logger.info("improvement_activated",
                     action_id=action.action_id,
                     type=action.improvement_type,
                     target=action.target)
        return True

    def record_query_for_active(self):
        """Aktif iyileştirmeler için sorgu sayacını artır."""
        completed_ids = []
        for action_id, action in self._active_actions.items():
            action.queries_since_applied += 1
            if action.queries_since_applied >= action.observation_target:
                completed_ids.append(action_id)

        return completed_ids  # Değerlendirme bekleyen aksiyon ID'leri

    def evaluate(
        self,
        action_id: str,
        after_metrics: Dict[str, float],
    ) -> Tuple[bool, float]:
        """Bir iyileştirme aksiyonunu değerlendir.

        Args:
            action_id: Aksiyon ID
            after_metrics: Gözlem sonrası metrikler

        Returns:
            (success: bool, improvement_percent: float)
        """
        if action_id not in self._active_actions:
            return False, 0.0

        action = self._active_actions[action_id]
        action.after_metrics = after_metrics
        action.evaluated_at = _utcnow_str()

        # Ana metrik: avg_confidence karşılaştırması
        before = action.before_metrics.get("avg_confidence", 0)
        after = after_metrics.get("avg_confidence", 0)

        if before > 0:
            improvement = ((after - before) / before) * 100
        else:
            improvement = after  # before 0 ise direkt after değeri

        action.improvement_percent = improvement

        if improvement >= MIN_IMPROVEMENT_PERCENT:
            action.status = ImprovementStatus.SUCCESSFUL
            logger.info("improvement_successful",
                         action_id=action_id,
                         improvement_pct=round(improvement, 2))
            success = True
        else:
            action.status = ImprovementStatus.FAILED
            action.rollback_reason = (
                f"İyileşme yetersiz: {improvement:.1f}% (minimum: {MIN_IMPROVEMENT_PERCENT}%)"
            )
            logger.warning("improvement_failed",
                            action_id=action_id,
                            improvement_pct=round(improvement, 2))
            success = False

        # Aktif listeden kaldır
        del self._active_actions[action_id]

        return success, improvement

    def rollback(self, action_id: str, reason: str = "manual") -> Optional[dict]:
        """Bir iyileştirmeyi geri al.

        Returns:
            dict: Geri alınan aksiyonun bilgisi veya None
        """
        # Aktif listede mi?
        if action_id in self._active_actions:
            action = self._active_actions.pop(action_id)
        else:
            # Geçmiş kayıtlarda ara
            action = None
            for a in self._actions:
                if a.action_id == action_id:
                    action = a
                    break

        if not action:
            return None

        action.status = ImprovementStatus.ROLLED_BACK
        action.rollback_reason = reason
        logger.info("improvement_rolled_back",
                     action_id=action_id,
                     target=action.target,
                     reason=reason)

        return {
            "action_id": action_id,
            "target": action.target,
            "previous_value": action.previous_value,
            "new_value": action.new_value,
            "parameter_path": action.parameter_path,
        }

    def get_active_improvements(self) -> List[dict]:
        """Aktif iyileştirmeleri döndür."""
        return [a.to_dict() for a in self._active_actions.values()]

    def get_history(self, last_n: int = 50) -> List[dict]:
        """İyileştirme geçmişi."""
        items = list(self._actions)[-last_n:]
        return [a.to_dict() for a in reversed(items)]

    def get_success_rate(self) -> Dict[str, Any]:
        """İyileştirme başarı oranı istatistikleri."""
        total = len(self._actions)
        if total == 0:
            return {"total": 0, "success_rate": 0.0}

        successful = sum(1 for a in self._actions if a.status == ImprovementStatus.SUCCESSFUL)
        failed = sum(1 for a in self._actions if a.status == ImprovementStatus.FAILED)
        rolled_back = sum(1 for a in self._actions if a.status == ImprovementStatus.ROLLED_BACK)
        active = len(self._active_actions)
        pending = sum(1 for a in self._actions if a.status == ImprovementStatus.PENDING)

        return {
            "total": total,
            "successful": successful,
            "failed": failed,
            "rolled_back": rolled_back,
            "active": active,
            "pending": pending,
            "success_rate": round(successful / max(1, successful + failed) * 100, 1),
            "avg_improvement_percent": round(
                sum(a.improvement_percent for a in self._actions
                    if a.status == ImprovementStatus.SUCCESSFUL)
                / max(1, successful), 1
            ),
        }

    def record_cycle_summary(self, opportunities_found: int, actions_taken: int,
                              results: List[dict]) -> ImprovementCycleSummary:
        """Bir döngü özeti kaydet."""
        self._cycle_count += 1
        successful = sum(1 for r in results if r.get("success"))
        failed = sum(1 for r in results if not r.get("success") and r.get("evaluated"))

        summary = ImprovementCycleSummary(
            cycle_id=self._cycle_count,
            timestamp=_utcnow_str(),
            opportunities_found=opportunities_found,
            actions_taken=actions_taken,
            actions_successful=successful,
            actions_failed=failed,
            actions_pending=actions_taken - successful - failed,
            top_improvements=[r for r in results if r.get("success")][:5],
        )
        self._cycle_summaries.append(summary)
        if len(self._cycle_summaries) > 50:
            self._cycle_summaries = self._cycle_summaries[-50:]

        return summary


# ═══════════════════════════════════════════════════════════════════
# SELF-IMPROVEMENT LOOP — ANA ORKESTRATÖR
# ═══════════════════════════════════════════════════════════════════

class SelfImprovementLoop:
    """Meta-öğrenme bulgularını otomatik iyileştirmeye dönüştüren kapalı döngü.

    Kullanım:
        loop = self_improvement_loop  # singleton
        # Her sorgudan sonra (engine.py'den):
        loop.on_query_completed(meta_result, domain_metrics)

        # Periyodik veya admin tetikli:
        cycle_result = loop.run_improvement_cycle(opportunities)
    """

    def __init__(self):
        self.threshold_optimizer = ThresholdOptimizer()
        self.rag_tuner = RAGTuner()
        self.prompt_evolver = PromptEvolver()
        self.tracker = ImprovementTracker()

        self._queries_since_last_cycle: int = 0
        self._auto_improve_enabled: bool = True
        self._started_at: str = _utcnow_str()

    # ─────────────────── SORGU HOOK'U ───────────────────

    def on_query_completed(
        self,
        meta_result: Dict[str, Any],
        domain_key: str,
        current_confidence: float,
    ) -> Optional[List[str]]:
        """Her process_question() sonrası çağrılır.

        Args:
            meta_result: meta_learning_engine.record_outcome() sonucu
            domain_key: "department:mode"
            current_confidence: Bu sorgunun confidence'ı

        Returns:
            list[str] | None: Tetiklenen aksiyon ID'leri (varsa)
        """
        self._queries_since_last_cycle += 1

        # Aktif iyileştirmeler için sorgu sayacı
        ready_ids = self.tracker.record_query_for_active()

        # Otomatik döngü kontrolü
        if (self._auto_improve_enabled and
                self._queries_since_last_cycle >= AUTO_IMPROVE_INTERVAL_QUERIES):
            logger.info("auto_improvement_cycle_triggered",
                         queries_since=self._queries_since_last_cycle)
            # Not: Gerçek döngü dışarıdan tetiklenmeli (engine.py background task)

        return ready_ids if ready_ids else None

    # ─────────────────── İYİLEŞTİRME DÖNGÜSÜ ───────────────────

    def run_improvement_cycle(
        self,
        opportunities: List[Dict[str, Any]],
        domain_metrics: Optional[Dict[str, Dict[str, float]]] = None,
    ) -> Dict[str, Any]:
        """Bir tam iyileştirme döngüsü çalıştır.

        Args:
            opportunities: meta_learning_engine.get_improvement_opportunities() çıktısı
            domain_metrics: domain_key → {avg_confidence, success_rate, failure_rate, ...}

        Returns:
            dict: Döngü sonuç raporu
        """
        self._queries_since_last_cycle = 0
        domain_metrics = domain_metrics or {}

        if not opportunities:
            return {
                "cycle_triggered": True,
                "opportunities_found": 0,
                "actions_taken": 0,
                "message": "İyileştirme fırsatı bulunamadı — sistem optimum çalışıyor.",
            }

        actions_taken = 0
        results = []

        # En yüksek öncelikli fırsatları al (max 5 per cycle)
        top_opps = opportunities[:5]

        for opp in top_opps:
            opp_type = opp.get("type", "")
            target = opp.get("target", "")
            action_hint = opp.get("action_hint", "")

            try:
                if opp_type == "threshold" and action_hint == "threshold_adjust":
                    result = self._apply_threshold_improvement(opp, domain_metrics)
                elif opp_type == "threshold" and action_hint == "criteria_focus":
                    result = self._apply_criteria_improvement(opp)
                elif opp_type == "rag" or action_hint == "rag_expand":
                    result = self._apply_rag_improvement(opp, domain_metrics)
                elif opp_type == "prompt" or action_hint == "prompt_evolve":
                    result = self._apply_prompt_improvement(opp, domain_metrics)
                elif opp_type == "knowledge":
                    result = self._apply_knowledge_improvement(opp)
                elif opp_type == "pipeline":
                    result = self._apply_pipeline_improvement(opp, domain_metrics)
                else:
                    result = {"applied": False, "reason": f"Bilinmeyen tip: {opp_type}"}

                if result.get("applied"):
                    actions_taken += 1
                results.append(result)

            except Exception as e:
                logger.error("improvement_cycle_error",
                             target=target, error=str(e))
                results.append({"applied": False, "error": str(e), "target": target})

        # Döngü özeti
        summary = self.tracker.record_cycle_summary(
            opportunities_found=len(opportunities),
            actions_taken=actions_taken,
            results=results,
        )

        return {
            "cycle_triggered": True,
            "opportunities_found": len(opportunities),
            "actions_taken": actions_taken,
            "results": results,
            "summary": summary.to_dict(),
        }

    # ─────────────────── İYİLEŞTİRME UYGULAYICILARI ───────────────────

    def _apply_threshold_improvement(
        self,
        opportunity: dict,
        domain_metrics: Dict[str, Dict[str, float]],
    ) -> dict:
        """Threshold iyileştirmesi uygula."""
        target = opportunity.get("target", "")
        metrics = domain_metrics.get(target, {})

        if not metrics:
            return {"applied": False, "reason": f"'{target}' için metrik bulunamadı"}

        config = self.threshold_optimizer.calculate_optimal_threshold(
            domain_key=target,
            avg_confidence=metrics.get("avg_confidence", 60),
            success_rate=metrics.get("success_rate", 50),
            avg_retry_count=metrics.get("avg_retry_count", 0),
            failure_rate=metrics.get("failure_rate", 20),
        )

        # Aksiyon oluştur ve aktif et
        action = self.tracker.create_action(
            improvement_type=ImprovementType.THRESHOLD,
            target=target,
            description=f"Threshold: {config.auto_reanalyze_threshold}, MaxRetry: {config.max_retry_count}",
            priority=opportunity.get("priority", 5),
            parameter_path="reflection.AUTO_REANALYZE_THRESHOLD",
            previous_value=60,  # varsayılan
            new_value=config.auto_reanalyze_threshold,
            before_metrics=metrics,
        )

        self.threshold_optimizer.apply(config, action.action_id)
        activated = self.tracker.activate(action)

        return {
            "applied": activated,
            "action_id": action.action_id,
            "type": "threshold",
            "target": target,
            "new_threshold": config.auto_reanalyze_threshold,
            "new_max_retry": config.max_retry_count,
        }

    def _apply_criteria_improvement(self, opportunity: dict) -> dict:
        """Kriter odaklı iyileştirme — prompt önerisi olarak işle."""
        target = opportunity.get("target", "")
        current_metric = opportunity.get("current_metric", 0)

        action = self.tracker.create_action(
            improvement_type=ImprovementType.THRESHOLD,
            target=target,
            description=f"Kriter '{target}' iyileştirmesi — mevcut skor: {current_metric}",
            priority=opportunity.get("priority", 5),
            parameter_path=f"criteria.{target}",
            previous_value=current_metric,
            new_value=None,  # Prompt önerisi olarak işlenecek
        )

        return {
            "applied": True,
            "action_id": action.action_id,
            "type": "criteria_focus",
            "target": target,
            "current_metric": current_metric,
            "note": "Prompt önerisi olarak işlendi",
        }

    def _apply_rag_improvement(
        self,
        opportunity: dict,
        domain_metrics: Dict[str, Dict[str, float]],
    ) -> dict:
        """RAG iyileştirmesi uygula."""
        target = opportunity.get("target", "")
        # target = "department/topic" formatında olabilir
        domain_key = target.replace("/", ":")
        metrics = domain_metrics.get(domain_key, {})

        config = self.rag_tuner.calculate_optimal_config(
            domain_key=domain_key,
            avg_confidence=metrics.get("avg_confidence", 50),
            numerical_valid_rate=metrics.get("numerical_valid_rate", 0.8),
            source_citation_valid_rate=metrics.get("source_citation_valid_rate", 0.8),
            avg_rag_confidence=metrics.get("avg_rag_confidence", 50),
        )

        action = self.tracker.create_action(
            improvement_type=ImprovementType.RAG,
            target=target,
            description=f"RAG top_k: {config.top_k}, similarity: {config.similarity_threshold}",
            priority=opportunity.get("priority", 5),
            parameter_path="rag.search_config",
            previous_value={"top_k": 5, "similarity": 0.5},
            new_value={"top_k": config.top_k, "similarity": config.similarity_threshold},
            before_metrics=metrics,
        )

        self.rag_tuner.apply(config, action.action_id)
        activated = self.tracker.activate(action)

        return {
            "applied": activated,
            "action_id": action.action_id,
            "type": "rag",
            "target": target,
            "new_top_k": config.top_k,
            "new_similarity": config.similarity_threshold,
        }

    def _apply_prompt_improvement(
        self,
        opportunity: dict,
        domain_metrics: Dict[str, Dict[str, float]],
    ) -> dict:
        """Prompt iyileştirme önerisi üret."""
        target = opportunity.get("target", "")
        domain_key = target.replace("/", ":")
        metrics = domain_metrics.get(domain_key, {})

        suggestions = self.prompt_evolver.generate_suggestions(
            domain_key=domain_key,
            avg_confidence=metrics.get("avg_confidence", 50),
            top_issues=metrics.get("top_issues", []),
            failure_rate=metrics.get("failure_rate", 20),
            criteria_weaknesses=metrics.get("criteria_weaknesses", {}),
        )

        action = self.tracker.create_action(
            improvement_type=ImprovementType.PROMPT,
            target=target,
            description=f"{len(suggestions)} prompt önerisi üretildi",
            priority=opportunity.get("priority", 5),
            parameter_path="prompts",
        )

        return {
            "applied": True,
            "action_id": action.action_id,
            "type": "prompt",
            "target": target,
            "suggestions_count": len(suggestions),
            "suggestions": [s.to_dict() for s in suggestions],
        }

    def _apply_knowledge_improvement(self, opportunity: dict) -> dict:
        """Bilgi boşluğu — sadece raporla, admin aksiyon alacak."""
        target = opportunity.get("target", "")

        action = self.tracker.create_action(
            improvement_type=ImprovementType.KNOWLEDGE,
            target=target,
            description=opportunity.get("description", "Bilgi boşluğu tespit edildi"),
            priority=opportunity.get("priority", 5),
            parameter_path="knowledge_base",
        )

        return {
            "applied": True,
            "action_id": action.action_id,
            "type": "knowledge",
            "target": target,
            "description": opportunity.get("description", ""),
            "note": "Admin panelden yeni doküman eklenmeli",
        }

    def _apply_pipeline_improvement(
        self,
        opportunity: dict,
        domain_metrics: Dict[str, Dict[str, float]],
    ) -> dict:
        """Pipeline/threshold ayar iyileştirmesi."""
        target = opportunity.get("target", "")
        domain_key = target.replace("/", ":")
        metrics = domain_metrics.get(domain_key, {})

        # Failure pattern — varsayılan olarak threshold uyarlama uygula
        return self._apply_threshold_improvement(
            opportunity={**opportunity, "target": domain_key},
            domain_metrics={domain_key: metrics} if metrics else domain_metrics,
        )

    # ─────────────────── DEĞERLENDİRME ───────────────────

    def evaluate_pending_improvements(
        self,
        domain_metrics: Dict[str, Dict[str, float]],
    ) -> List[Dict[str, Any]]:
        """Gözlem süresi dolan iyileştirmeleri değerlendir.

        Args:
            domain_metrics: Güncel domain metrikleri

        Returns:
            list[dict]: Değerlendirme sonuçları
                [{action_id, success, improvement_percent, rolled_back}]
        """
        results = []
        ready_ids = []

        # Gözlem süresi dolan aksiyonları bul
        for action_id, action in list(self.tracker._active_actions.items()):
            if action.queries_since_applied >= action.observation_target:
                ready_ids.append(action_id)

        for action_id in ready_ids:
            action = self.tracker._active_actions.get(action_id)
            if not action:
                continue

            # Domain metriğini al
            target_key = action.target.replace("/", ":")
            after_metrics = domain_metrics.get(target_key, {})

            if not after_metrics:
                # Metrik yoksa genel ortalamayı kullan
                after_metrics = domain_metrics.get("_overall", {})

            success, improvement = self.tracker.evaluate(action_id, after_metrics)

            result = {
                "action_id": action_id,
                "success": success,
                "improvement_percent": round(improvement, 2),
                "evaluated": True,
                "rolled_back": False,
            }

            # Başarısız ise otomatik rollback
            if not success:
                rollback_info = self._do_rollback(action)
                result["rolled_back"] = rollback_info is not None
                result["rollback_info"] = rollback_info

            results.append(result)

        return results

    def _do_rollback(self, action: ImprovementAction) -> Optional[dict]:
        """Başarısız bir iyileştirmeyi geri al."""
        if action.previous_value is None:
            return None

        rollback_info = {
            "action_id": action.action_id,
            "parameter_path": action.parameter_path,
            "restored_value": action.previous_value,
        }

        # Tip bazlı rollback
        if action.improvement_type == ImprovementType.THRESHOLD:
            self.threshold_optimizer.remove_override(action.target)
            logger.info("threshold_rolled_back", target=action.target)
        elif action.improvement_type == ImprovementType.RAG:
            self.rag_tuner.remove_override(action.target)
            logger.info("rag_rolled_back", target=action.target)

        return rollback_info

    # ═══════════════════════════════════════════════════════════
    # DASHBOARD & AYARLAR
    # ═══════════════════════════════════════════════════════════

    def get_dashboard(self) -> Dict[str, Any]:
        """Self-Improvement Loop tam dashboard verisi."""
        return {
            "available": True,
            "started_at": self._started_at,
            "auto_improve_enabled": self._auto_improve_enabled,
            "queries_since_last_cycle": self._queries_since_last_cycle,
            "auto_improve_interval": AUTO_IMPROVE_INTERVAL_QUERIES,
            "improvement_stats": self.tracker.get_success_rate(),
            "active_improvements": self.tracker.get_active_improvements(),
            "threshold_overrides": self.threshold_optimizer.get_all_overrides(),
            "rag_overrides": self.rag_tuner.get_all_overrides(),
            "pending_prompt_suggestions": self.prompt_evolver.get_pending_suggestions(),
            "cycle_summaries": [s.to_dict() for s in self._cycle_summaries[-10:]],
            "recent_history": self.tracker.get_history(10),
        }

    def set_auto_improve(self, enabled: bool) -> dict:
        """Otomatik iyileştirme döngüsünü aç/kapat."""
        old = self._auto_improve_enabled
        self._auto_improve_enabled = enabled
        logger.info("auto_improve_toggled", old=old, new=enabled)
        return {"auto_improve_enabled": enabled, "previous": old}

    def get_config(self) -> dict:
        """Mevcut konfigürasyon."""
        return {
            "auto_improve_enabled": self._auto_improve_enabled,
            "auto_improve_interval": AUTO_IMPROVE_INTERVAL_QUERIES,
            "rollback_observation_queries": ROLLBACK_OBSERVATION_QUERIES,
            "min_improvement_percent": MIN_IMPROVEMENT_PERCENT,
            "max_concurrent_experiments": MAX_CONCURRENT_EXPERIMENTS,
            "threshold_limits": {
                "confidence_min": CONFIDENCE_THRESHOLD_MIN,
                "confidence_max": CONFIDENCE_THRESHOLD_MAX,
                "retry_min": RETRY_THRESHOLD_MIN,
                "retry_max": RETRY_THRESHOLD_MAX,
            },
            "rag_limits": {
                "top_k_min": RAG_TOP_K_MIN,
                "top_k_max": RAG_TOP_K_MAX,
                "similarity_min": RAG_SIMILARITY_MIN,
                "similarity_max": RAG_SIMILARITY_MAX,
            },
        }

    def reset(self):
        """Tüm iyileştirme verisini sıfırla."""
        self.threshold_optimizer = ThresholdOptimizer()
        self.rag_tuner = RAGTuner()
        self.prompt_evolver = PromptEvolver()
        self.tracker = ImprovementTracker()
        self._queries_since_last_cycle = 0
        self._started_at = _utcnow_str()
        logger.info("self_improvement_reset")


# ═══════════════════════════════════════════════════════════════════
# GLOBAL SINGLETON
# ═══════════════════════════════════════════════════════════════════

self_improvement_loop: SelfImprovementLoop = SelfImprovementLoop()


# ═══════════════════════════════════════════════════════════════════
# KOLAYLIK FONKSİYONLARI — engine.py entegrasyonu
# ═══════════════════════════════════════════════════════════════════

def on_query_completed(**kwargs) -> Optional[List[str]]:
    """engine.py hook: her sorgu sonrası."""
    return self_improvement_loop.on_query_completed(**kwargs)


def run_improvement_cycle(opportunities: list, domain_metrics: Optional[dict] = None) -> dict:
    """Admin veya cron: iyileştirme döngüsü çalıştır."""
    return self_improvement_loop.run_improvement_cycle(opportunities, domain_metrics)


def get_self_improvement_dashboard() -> dict:
    """Dashboard verisi."""
    return self_improvement_loop.get_dashboard()


def get_threshold_override(department: str, mode: str) -> Optional[dict]:
    """Reflection modülünden çağrılacak — domain bazlı threshold override."""
    override = self_improvement_loop.threshold_optimizer.get_override(department, mode)
    return override.to_dict() if override else None


def get_rag_override(department: str, mode: str) -> Optional[dict]:
    """RAG modülünden çağrılacak — domain bazlı RAG config override."""
    override = self_improvement_loop.rag_tuner.get_override(department, mode)
    return override.to_dict() if override else None
