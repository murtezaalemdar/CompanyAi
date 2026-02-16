"""Module Synapse Network — Modüller Arası Öz-Öğrenen Zeka Ağı (v5.4.0)

Nöral sinaps ilhamıyla 43 AI modülü arasında otomatik sinyal yönlendirme,
kaskad tetikleme ve Hebbian öğrenme ile bağlantı ağırlıklarını optimize eder.

ÇÖZÜLEN SORUNLAR:
  1.  60 manuel kablolama       → Otomatik sinyal yönlendirme
  2.  5 hayalet modül           → Kaskad tetikleme ile otomatik aktivasyon
  3.  18 kaçırılan bağlantı     → Sinyal tipi eşleşmesiyle otomatik keşif
  4.  Triple confidence override→ Merkezi sinyal birleştirme
  5.  meta_data/risk_data=None  → Sinaps zinciri otomatik bağlantı

MİMARİ:
  Signal          → Tip güvenli modül çıktısı (tip + veri + güç + kaynak)
  Synapse         → İki modül arası ağırlıklı bağlantı (0.0 – 1.0)
  PipelineContext → Tüm sinyalleri taşıyan paylaşımlı durum
  SynapseNetwork  → Merkezi yönlendirme + öğrenme koordinatörü
  CascadeRule     → Kaskad tetikleme koşulu
  HebbianLearner  → Plastik öğrenme (güçlendirme / zayıflatma / çürüme)

SİNYAL AKIŞI:
  1. Modül çalışır → ctx.emit(module, signal, value, strength)
  2. SynapseNetwork hangi modüllerin bu sinyali tükettiğini bulur
  3. Sinaps ağırlığı > eşik  → kaskad tetikleme kuyruğuna ekle
  4. Karar sonucu bilinince → Hebbian güncelleme
     (başarılı = güçlendir, başarısız = zayıflat, kullanılmayan = çürüt)

HEBBIAN ÖĞRENME:
  Δw = η × signal_strength × outcome_factor
  outcome_factor: başarılı=+1.0, kısmen=+0.3, başarısız=-0.5
  Decay: w_new = max(w × (1 − decay_rate), MIN_WEIGHT)  — kullanılmayan sinapslar
"""

import time
import logging
import hashlib
from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Tuple, Set
from collections import defaultdict

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
# SABİTLER
# ═══════════════════════════════════════════════════════════════

MAX_CASCADE_DEPTH = 3             # Sonsuz kaskad önleme
LEARNING_RATE = 0.05              # Hebbian öğrenme hızı
DECAY_RATE = 0.008                # Kullanılmayan sinapsların çürüme hızı
MIN_WEIGHT = 0.05                 # Minimum sinaps ağırlığı
MAX_WEIGHT = 1.0                  # Maksimum sinaps ağırlığı
CASCADE_THRESHOLD = 0.40          # Kaskad tetikleme eşik ağırlığı
STRENGTH_DEFAULT = 0.70           # Varsayılan sinyal gücü
MAX_QUERY_HISTORY = 500           # Hafızada tutulan sorgu aktivasyon geçmişi
CONFIDENCE_MERGE_STRATEGY = "weighted"  # mean | max | weighted | latest


# ═══════════════════════════════════════════════════════════════
# VERİ YAPILARI
# ═══════════════════════════════════════════════════════════════

class SignalCategory(str, Enum):
    """Sinyal kategorileri — gruplama ve filtreleme için"""
    CORE = "core"
    QUALITY = "quality"
    RISK = "risk"
    INTELLIGENCE = "intelligence"
    KNOWLEDGE = "knowledge"
    EXECUTIVE = "executive"
    ANALYSIS = "analysis"


@dataclass
class Signal:
    """Tek bir modül çıktı sinyali"""
    signal_type: str
    value: Any
    source_module: str
    strength: float = STRENGTH_DEFAULT
    timestamp: float = field(default_factory=time.time)


@dataclass
class Synapse:
    """İki modül arası ağırlıklı bağlantı — nöral sinaps"""
    source: str                    # Kaynak modül adı
    target: str                    # Hedef modül adı
    signal_types: List[str]        # Bu sinaps üzerinden akan sinyal tipleri
    weight: float = 0.50           # Bağlantı gücü (0.0 – 1.0)
    activations: int = 0           # Toplam aktive olma sayısı
    successful_activations: int = 0  # Başarılı sonuçla biten aktivasyonlar
    last_activated: float = 0.0    # Son aktivasyon zamanı

    @property
    def success_rate(self) -> float:
        """Başarı oranı"""
        return self.successful_activations / max(self.activations, 1)

    @property
    def effectiveness(self) -> float:
        """Efektiflik = ağırlık × başarı oranı"""
        if self.activations == 0:
            return self.weight
        return self.weight * self.success_rate

    def activate(self, strength: float = 1.0):
        """Sinapsı aktive et"""
        self.activations += 1
        self.last_activated = time.time()

    def reinforce(self, amount: float):
        """Ağırlığı güçlendir (pozitif outcome)"""
        self.weight = min(MAX_WEIGHT, self.weight + amount)
        self.successful_activations += 1

    def weaken(self, amount: float):
        """Ağırlığı zayıflat (negatif outcome)"""
        self.weight = max(MIN_WEIGHT, self.weight - abs(amount))

    def decay(self):
        """Kullanılmayan sinapslar için zamana bağlı çürüme"""
        self.weight = max(MIN_WEIGHT, self.weight * (1 - DECAY_RATE))


@dataclass
class CascadeRule:
    """Kaskad tetikleme kuralı — belirli sinyalde koşul sağlanınca hedef modülleri tetikle"""
    source: str                    # Kaynak modül
    signal_type: str               # Kontrol edilecek sinyal
    operator: str                  # "in", "gt", "lt", "eq", "exists", "truthy"
    threshold: Any                 # Karşılaştırma değeri
    targets: List[str]             # Tetiklenecek hedef modüller
    priority: int = 1              # Öncelik (1=en yüksek)


# ═══════════════════════════════════════════════════════════════
# PIPELINE CONTEXT — Tüm sinyallerin aktığı paylaşımlı durum
# ═══════════════════════════════════════════════════════════════

class PipelineContext:
    """
    Pipeline boyunca akan paylaşımlı durum objesi.
    60 adet manuel değişken bağlamasını tek bir context ile değiştirir.
    """

    def __init__(self, question: str, department: str = "", query_id: str = ""):
        self.query_id = query_id or self._generate_id(question)
        self.question = question
        self.department = department
        self.signals: Dict[str, Dict[str, Signal]] = {}  # {module: {signal_type: Signal}}
        self.trace: List[Dict[str, Any]] = []             # Sinyal akış izi
        self.cascade_queue: List[str] = []                # Kaskad bekleyen modüller
        self.cascade_depth: int = 0
        self.cascades_triggered: List[Dict] = []          # Tetiklenen kaskadlar
        self.started_at: float = time.time()
        self.activated_synapse_ids: Set[int] = set()      # Bu sorgu için aktive olan sinapslar

    @staticmethod
    def _generate_id(question: str) -> str:
        """Sorgu için benzersiz ID oluştur"""
        raw = f"{question[:100]}:{time.time()}"
        return hashlib.md5(raw.encode()).hexdigest()[:12]

    def emit(self, module: str, signal_type: str, value: Any,
             strength: float = STRENGTH_DEFAULT) -> None:
        """Modülden sinyal yayınla"""
        signal = Signal(
            signal_type=signal_type,
            value=value,
            source_module=module,
            strength=strength,
            timestamp=time.time(),
        )
        if module not in self.signals:
            self.signals[module] = {}
        self.signals[module][signal_type] = signal

        # İzi kaydet
        self.trace.append({
            "action": "emit",
            "module": module,
            "signal": signal_type,
            "strength": round(strength, 2),
            "t": round(time.time() - self.started_at, 3),
        })

    def get(self, module: str, signal_type: str, default: Any = None) -> Any:
        """Belirli modülün belirli sinyalini oku"""
        sig = self.signals.get(module, {}).get(signal_type)
        return sig.value if sig else default

    def get_strength(self, module: str, signal_type: str) -> float:
        """Sinyalin gücünü oku"""
        sig = self.signals.get(module, {}).get(signal_type)
        return sig.strength if sig else 0.0

    def has_signal(self, module: str, signal_type: str) -> bool:
        """Sinyal mevcut mu?"""
        return module in self.signals and signal_type in self.signals[module]

    def get_all_of_type(self, signal_type: str) -> Dict[str, Any]:
        """Belirli tipte tüm sinyalleri tüm modüllerden topla"""
        result = {}
        for mod, sigs in self.signals.items():
            if signal_type in sigs:
                result[mod] = sigs[signal_type].value
        return result

    def get_all_strengths_of_type(self, signal_type: str) -> Dict[str, float]:
        """Belirli tipte tüm sinyal güçlerini topla"""
        result = {}
        for mod, sigs in self.signals.items():
            if signal_type in sigs:
                result[mod] = sigs[signal_type].strength
        return result

    def signal_count(self) -> int:
        """Toplam sinyal sayısı"""
        return sum(len(sigs) for sigs in self.signals.values())

    def active_modules(self) -> List[str]:
        """Sinyal yayınlamış modüller"""
        return list(self.signals.keys())

    def elapsed_ms(self) -> float:
        """Pipeline başlangıcından geçen süre (ms)"""
        return (time.time() - self.started_at) * 1000

    def add_cascade(self, source: str, target: str, reason: str):
        """Kaskad olayını kaydet"""
        self.cascades_triggered.append({
            "source": source,
            "target": target,
            "reason": reason,
            "t": round(time.time() - self.started_at, 3),
            "depth": self.cascade_depth,
        })
        self.trace.append({
            "action": "cascade",
            "source": source,
            "target": target,
            "reason": reason,
            "t": round(time.time() - self.started_at, 3),
        })

    def merge_confidence(self) -> float:
        """
        Tüm confidence sinyallerini ağırlıklı birleştir.
        Triple override sorununu çözer — her modülün confidence'ı
        sinyal gücüne göre ağırlıklandırılır.
        """
        values = self.get_all_of_type("confidence")
        strengths = self.get_all_strengths_of_type("confidence")

        if not values:
            return 50.0

        if CONFIDENCE_MERGE_STRATEGY == "max":
            return max(values.values())
        elif CONFIDENCE_MERGE_STRATEGY == "latest":
            # En son yayınlanan
            latest_mod = max(values.keys(),
                             key=lambda m: self.signals[m]["confidence"].timestamp)
            return values[latest_mod]
        elif CONFIDENCE_MERGE_STRATEGY == "mean":
            return sum(values.values()) / len(values)
        else:  # weighted
            total_w = sum(strengths.values()) or 1.0
            return sum(
                values[m] * strengths.get(m, STRENGTH_DEFAULT)
                for m in values
            ) / total_w

    def apply_confidence_adjustments(self, base: float) -> float:
        """Confidence adjustment sinyallerini merkezi olarak uygula"""
        adjustments = self.get_all_of_type("confidence_adjustment")
        strengths = self.get_all_strengths_of_type("confidence_adjustment")

        total_adj = 0.0
        for mod, adj in adjustments.items():
            w = strengths.get(mod, STRENGTH_DEFAULT)
            total_adj += adj * w

        return max(5.0, min(100.0, base + total_adj))

    def summary(self) -> Dict[str, Any]:
        """Context özeti"""
        return {
            "query_id": self.query_id,
            "signals": self.signal_count(),
            "modules": len(self.active_modules()),
            "cascades": len(self.cascades_triggered),
            "elapsed_ms": round(self.elapsed_ms(), 1),
        }


# ═══════════════════════════════════════════════════════════════
# MODÜL KAYIT DEFTERİ — Her modülün ne tüketip ne ürettiği
# ═══════════════════════════════════════════════════════════════

MODULE_SPECS: Dict[str, Dict[str, Any]] = {
    "reflection": {
        "consumes": ["answer", "question", "context"],
        "produces": ["reflection_score", "confidence", "hallucination_flag"],
        "category": "quality",
    },
    "numerical_validation": {
        "consumes": ["answer", "question", "context"],
        "produces": ["numerical_valid", "numerical_score"],
        "category": "quality",
    },
    "governance": {
        "consumes": ["answer", "question", "department", "confidence"],
        "produces": ["bias_flags", "drift_status", "policy_violations",
                     "compliance_score", "risk_level"],
        "category": "risk",
    },
    "explainability": {
        "consumes": ["answer", "question", "confidence", "reflection_score"],
        "produces": ["xai_factors", "weighted_confidence", "risk_assessment"],
        "category": "intelligence",
    },
    "uncertainty_quantification": {
        "consumes": ["question", "reflection_data", "confidence", "governance_data"],
        "produces": ["uncertainty", "ensemble_confidence", "margin_of_error",
                     "confidence_adjustment"],
        "category": "quality",
    },
    "risk_analyzer": {
        "consumes": ["question", "answer", "department"],
        "produces": ["risk_level", "risk_factors", "risk_score"],
        "category": "risk",
    },
    "decision_gatekeeper": {
        "consumes": ["question", "answer", "governance_data", "reflection_data",
                     "confidence", "risk_data", "ranking_data", "quality_score"],
        "produces": ["gate_verdict", "composite_risk_score", "escalation_required",
                     "risk_signals"],
        "category": "risk",
    },
    "ood_detector": {
        "consumes": ["question", "department"],
        "produces": ["ood_score", "ood_severity", "confidence_adjustment",
                     "uncertainty_adjustment"],
        "category": "quality",
    },
    "decision_quality": {
        "consumes": ["reflection_data", "uncertainty_data", "gate_data", "meta_data",
                     "governance_data", "debate_data", "causal_data", "rag_used",
                     "web_searched", "sources", "source_citation_valid"],
        "produces": ["quality_score", "quality_band", "confidence_interval",
                     "executive_line"],
        "category": "quality",
    },
    "kpi_impact": {
        "consumes": ["question", "answer", "department"],
        "produces": ["kpi_impacts", "domino_effects", "impact_score",
                     "financial_estimate", "kpi_executive_summary"],
        "category": "analysis",
    },
    "decision_memory": {
        "consumes": ["question", "department", "quality_score", "risk_level",
                     "gate_verdict", "uncertainty", "confidence"],
        "produces": ["similar_decisions", "accuracy_data"],
        "category": "intelligence",
    },
    "executive_digest": {
        "consumes": ["question", "answer", "quality_score", "quality_band",
                     "kpi_impacts", "gate_verdict", "gate_risks", "uncertainty",
                     "confidence", "reflection_score", "ood_severity"],
        "produces": ["executive_digest", "digest_priority", "impact_level"],
        "category": "executive",
    },
    "meta_learning": {
        "consumes": ["question", "department", "confidence", "reflection_data",
                     "governance_data"],
        "produces": ["meta_strategy", "knowledge_gaps", "quality_trend",
                     "failure_patterns"],
        "category": "intelligence",
    },
    "multi_agent_debate": {
        "consumes": ["question", "answer", "risk_level", "confidence"],
        "produces": ["debate_consensus", "perspectives", "synthesized_answer"],
        "category": "intelligence",
    },
    "causal_inference": {
        "consumes": ["question", "answer", "risk_factors"],
        "produces": ["causal_factors", "root_causes", "intervention_suggestions"],
        "category": "intelligence",
    },
    "strategic_planner": {
        "consumes": ["question", "answer", "causal_factors", "kpi_impacts",
                     "risk_level"],
        "produces": ["strategic_alignment", "strategic_recommendations",
                     "action_plan"],
        "category": "executive",
    },
    "executive_intelligence": {
        "consumes": ["answer", "strategic_recommendations", "kpi_impacts",
                     "risk_level", "quality_score"],
        "produces": ["executive_briefing", "board_report", "kpi_correlation"],
        "category": "executive",
    },
    "knowledge_graph": {
        "consumes": ["question", "answer", "context"],
        "produces": ["knowledge_entities", "relationships", "enriched_context"],
        "category": "knowledge",
    },
    "self_improvement": {
        "consumes": ["meta_strategy", "knowledge_gaps", "failure_patterns"],
        "produces": ["optimization_applied", "threshold_changes"],
        "category": "intelligence",
    },
}


# ═══════════════════════════════════════════════════════════════
# İLK SİNAPS HARİTASI — 43 modül arası bağlantılar
# Her tuple: (kaynak, hedef, [sinyal_tipleri], başlangıç_ağırlık)
# Ağırlıklar mantıksal analiz ile belirlenmiştir.
# ═══════════════════════════════════════════════════════════════

INITIAL_SYNAPSE_MAP: List[Tuple[str, str, List[str], float]] = [
    # ── Reflection çıktıları ──
    ("reflection", "decision_quality",
     ["reflection_score", "confidence"], 0.85),
    ("reflection", "uncertainty_quantification",
     ["confidence"], 0.70),
    ("reflection", "decision_gatekeeper",
     ["reflection_score", "confidence"], 0.75),

    # ── Numerical Validation çıktıları ──
    ("numerical_validation", "reflection",
     ["numerical_valid", "numerical_score"], 0.70),
    ("numerical_validation", "decision_quality",
     ["numerical_valid"], 0.55),

    # ── Risk Analyzer çıktıları ──
    ("risk_analyzer", "decision_quality",
     ["risk_level", "risk_score"], 0.80),
    ("risk_analyzer", "decision_gatekeeper",
     ["risk_level", "risk_factors"], 0.90),
    ("risk_analyzer", "causal_inference",
     ["risk_factors"], 0.65),
    ("risk_analyzer", "strategic_planner",
     ["risk_level"], 0.60),
    ("risk_analyzer", "executive_digest",
     ["risk_level"], 0.55),

    # ── Governance çıktıları ──
    ("governance", "decision_gatekeeper",
     ["bias_flags", "policy_violations", "compliance_score"], 0.85),
    ("governance", "decision_quality",
     ["bias_flags", "compliance_score"], 0.60),
    ("governance", "uncertainty_quantification",
     ["drift_status"], 0.50),

    # ── Uncertainty çıktıları ──
    ("uncertainty_quantification", "decision_quality",
     ["uncertainty", "ensemble_confidence"], 0.80),
    ("uncertainty_quantification", "decision_gatekeeper",
     ["uncertainty"], 0.75),
    ("uncertainty_quantification", "executive_digest",
     ["uncertainty", "margin_of_error"], 0.65),

    # ── OOD Detector çıktıları ──
    ("ood_detector", "decision_quality",
     ["ood_score", "ood_severity"], 0.70),
    ("ood_detector", "executive_digest",
     ["ood_severity"], 0.75),
    ("ood_detector", "decision_gatekeeper",
     ["ood_score", "confidence_adjustment"], 0.65),

    # ── Decision Quality çıktıları ──
    ("decision_quality", "executive_digest",
     ["quality_score", "quality_band"], 0.85),
    ("decision_quality", "decision_gatekeeper",
     ["quality_score"], 0.80),
    ("decision_quality", "decision_memory",
     ["quality_score", "quality_band"], 0.60),

    # ── Decision Gatekeeper çıktıları ──
    ("decision_gatekeeper", "executive_digest",
     ["gate_verdict", "risk_signals"], 0.90),
    ("decision_gatekeeper", "executive_intelligence",
     ["gate_verdict", "escalation_required"], 0.70),

    # ── KPI Impact çıktıları ──
    ("kpi_impact", "executive_digest",
     ["kpi_impacts", "financial_estimate", "kpi_executive_summary"], 0.80),
    ("kpi_impact", "strategic_planner",
     ["kpi_impacts", "impact_score"], 0.65),
    ("kpi_impact", "decision_memory",
     ["kpi_impacts"], 0.50),

    # ── Decision Memory çıktıları ──
    ("decision_memory", "decision_quality",
     ["similar_decisions", "accuracy_data"], 0.60),
    ("decision_memory", "executive_digest",
     ["similar_decisions"], 0.55),

    # ── Meta Learning çıktıları ──
    ("meta_learning", "decision_quality",
     ["meta_strategy", "quality_trend"], 0.65),
    ("meta_learning", "self_improvement",
     ["knowledge_gaps", "failure_patterns"], 0.70),

    # ── Causal Inference çıktıları ──
    ("causal_inference", "strategic_planner",
     ["causal_factors", "root_causes"], 0.75),
    ("causal_inference", "executive_intelligence",
     ["root_causes"], 0.60),
    ("causal_inference", "executive_digest",
     ["causal_factors"], 0.50),

    # ── Strategic Planner çıktıları ──
    ("strategic_planner", "executive_intelligence",
     ["strategic_recommendations", "action_plan"], 0.80),
    ("strategic_planner", "executive_digest",
     ["strategic_alignment"], 0.65),

    # ── Knowledge Graph çıktıları ──
    ("knowledge_graph", "causal_inference",
     ["knowledge_entities", "relationships"], 0.55),
    ("knowledge_graph", "strategic_planner",
     ["enriched_context"], 0.50),

    # ── Multi-Agent Debate çıktıları ──
    ("multi_agent_debate", "decision_quality",
     ["debate_consensus"], 0.70),
    ("multi_agent_debate", "executive_digest",
     ["debate_consensus", "synthesized_answer"], 0.55),
    ("multi_agent_debate", "causal_inference",
     ["perspectives"], 0.45),

    # ── Explainability çıktıları ──
    ("explainability", "executive_digest",
     ["xai_factors"], 0.60),
    ("explainability", "decision_quality",
     ["weighted_confidence"], 0.50),

    # ── Executive Intelligence çıktıları ──
    ("executive_intelligence", "executive_digest",
     ["executive_briefing"], 0.70),
]


# ═══════════════════════════════════════════════════════════════
# KASKAD KURALLARI — Belirli sinyaller belirli modülleri tetikler
# ═══════════════════════════════════════════════════════════════

CASCADE_RULES: List[CascadeRule] = [
    # Yüksek risk → nedensellik + strateji analizi
    CascadeRule(
        source="risk_analyzer",
        signal_type="risk_level",
        operator="in",
        threshold=["HIGH", "CRITICAL"],
        targets=["causal_inference", "strategic_planner"],
        priority=1,
    ),
    # OOD tespit → reflection yeniden değerlendir
    CascadeRule(
        source="ood_detector",
        signal_type="ood_severity",
        operator="in",
        threshold=["OOD", "HIGHLY_OOD"],
        targets=["reflection"],
        priority=1,
    ),
    # Governance bias → gatekeeper
    CascadeRule(
        source="governance",
        signal_type="bias_flags",
        operator="truthy",
        threshold=None,
        targets=["decision_gatekeeper"],
        priority=2,
    ),
    # Gate BLOCK/ESCALATE → executive intelligence
    CascadeRule(
        source="decision_gatekeeper",
        signal_type="gate_verdict",
        operator="in",
        threshold=["BLOCK", "ESCALATE"],
        targets=["executive_intelligence"],
        priority=1,
    ),
    # Düşük debate consensus → nedensellik araştır
    CascadeRule(
        source="multi_agent_debate",
        signal_type="debate_consensus",
        operator="lt",
        threshold=50,
        targets=["causal_inference"],
        priority=2,
    ),
    # Düşük quality → meta learning tetikle
    CascadeRule(
        source="decision_quality",
        signal_type="quality_score",
        operator="lt",
        threshold=40,
        targets=["meta_learning"],
        priority=2,
    ),
    # Yüksek KPI etki → strategic planner
    CascadeRule(
        source="kpi_impact",
        signal_type="impact_score",
        operator="gt",
        threshold=70,
        targets=["strategic_planner", "executive_intelligence"],
        priority=2,
    ),
    # Knowledge entities bulundu → causal inference'ı zenginleştir
    CascadeRule(
        source="knowledge_graph",
        signal_type="knowledge_entities",
        operator="truthy",
        threshold=None,
        targets=["causal_inference"],
        priority=3,
    ),
]


# ═══════════════════════════════════════════════════════════════
# AĞ İSTATİSTİKLERİ
# ═══════════════════════════════════════════════════════════════

class NetworkStats:
    """Ağ genelinde istatistik izleyici"""

    def __init__(self):
        self.total_signals: int = 0
        self.total_routes: int = 0
        self.total_cascades: int = 0
        self.total_queries: int = 0
        self.learning_updates: int = 0
        self.decay_cycles: int = 0
        self.module_emit_counts: Dict[str, int] = defaultdict(int)
        self.signal_type_counts: Dict[str, int] = defaultdict(int)
        self.cascade_trigger_counts: Dict[str, int] = defaultdict(int)
        self.recent_traces: List[Dict] = []  # Son 10 sorgu özeti

    def record_emit(self, module: str, signal_type: str):
        self.total_signals += 1
        self.module_emit_counts[module] += 1
        self.signal_type_counts[signal_type] += 1

    def record_route(self):
        self.total_routes += 1

    def record_cascade(self, source: str):
        self.total_cascades += 1
        self.cascade_trigger_counts[source] += 1

    def record_query(self, ctx_summary: Dict):
        self.total_queries += 1
        self.recent_traces.append(ctx_summary)
        if len(self.recent_traces) > 10:
            self.recent_traces = self.recent_traces[-10:]


# ═══════════════════════════════════════════════════════════════
# SYNAPSE NETWORK — Ana koordinasyon sınıfı
# ═══════════════════════════════════════════════════════════════

class SynapseNetwork:
    """
    43 AI modülü arasında öz-öğrenen sinyal yönlendirme ağı.

    Sorumluluklar:
    - Sinyal yönlendirme (emit → route → consume)
    - Kaskad tetikleme (koşul sağlanınca hedef modülleri tetikle)
    - Hebbian öğrenme (başarılı çıktıları güçlendir)
    - Input toplama (modül için gerekli tüm girdileri otomatik birleştir)
    """

    def __init__(self):
        self.synapses: List[Synapse] = []
        self.cascade_rules: List[CascadeRule] = list(CASCADE_RULES)
        self.stats = NetworkStats()
        self._query_activations: Dict[str, Set[int]] = {}
        self._initialize_synapses()

    def _initialize_synapses(self):
        """İlk sinaps haritasından Synapse nesneleri oluştur"""
        for source, target, signals, weight in INITIAL_SYNAPSE_MAP:
            self.synapses.append(Synapse(
                source=source,
                target=target,
                signal_types=signals,
                weight=weight,
            ))
        logger.info("synapse_network_initialized",
                     synapses=len(self.synapses),
                     cascade_rules=len(self.cascade_rules))

    # ── Sinyal Yönlendirme ────────────────────────────────────

    def emit(self, ctx: PipelineContext, module: str, signal_type: str,
             value: Any, strength: float = STRENGTH_DEFAULT) -> int:
        """
        Modülden sinyal yayınla ve ilgili sinapsları aktive et.
        Returns: aktive olan sinaps sayısı.
        """
        # Context'e kaydet
        ctx.emit(module, signal_type, value, strength)
        self.stats.record_emit(module, signal_type)

        # İlgili sinapsları bul ve aktive et
        activated = 0
        for idx, syn in enumerate(self.synapses):
            if syn.source == module and signal_type in syn.signal_types:
                syn.activate(strength)
                activated += 1

                # Sorgu aktivasyonlarını kaydet (öğrenme için)
                if ctx.query_id not in self._query_activations:
                    self._query_activations[ctx.query_id] = set()
                self._query_activations[ctx.query_id].add(idx)
                ctx.activated_synapse_ids.add(idx)

                # İzi kaydet
                ctx.trace.append({
                    "action": "route",
                    "from": module,
                    "to": syn.target,
                    "signal": signal_type,
                    "weight": round(syn.weight, 3),
                    "t": round(time.time() - ctx.started_at, 3),
                })
                self.stats.record_route()

        # Aktivasyon hafızasını temizle (eski sorgular)
        if len(self._query_activations) > MAX_QUERY_HISTORY:
            oldest = sorted(self._query_activations.keys())[:100]
            for k in oldest:
                del self._query_activations[k]

        return activated

    def gather_inputs(self, ctx: PipelineContext,
                      target_module: str) -> Dict[str, Any]:
        """
        Belirli bir modülün ihtiyaç duyduğu tüm input sinyallerini
        sinaps ağı üzerinden otomatik toplar.

        Aynı sinyal tipi birden fazla modülden geliyorsa,
        en yüksek sinaps ağırlığına sahip kaynağı seçer.

        Returns: {signal_type: value, ...}
        """
        inputs: Dict[str, Tuple[Any, float]] = {}  # {signal_type: (value, best_weight)}

        for syn in self.synapses:
            if syn.target != target_module:
                continue
            for sig_type in syn.signal_types:
                if ctx.has_signal(syn.source, sig_type):
                    current_weight = inputs.get(sig_type, (None, -1.0))[1]
                    effective_weight = syn.weight * ctx.get_strength(syn.source, sig_type)
                    if effective_weight > current_weight:
                        inputs[sig_type] = (
                            ctx.get(syn.source, sig_type),
                            effective_weight,
                        )

        return {k: v[0] for k, v in inputs.items()}

    def get_incoming_modules(self, target_module: str) -> List[str]:
        """Bir modüle sinyal gönderen tüm modülleri listele"""
        sources = set()
        for syn in self.synapses:
            if syn.target == target_module:
                sources.add(syn.source)
        return sorted(sources)

    def get_outgoing_modules(self, source_module: str) -> List[str]:
        """Bir modülün sinyal gönderdiği tüm modülleri listele"""
        targets = set()
        for syn in self.synapses:
            if syn.source == source_module:
                targets.add(syn.target)
        return sorted(targets)

    # ── Kaskad Tetikleme ──────────────────────────────────────

    def check_cascade(self, ctx: PipelineContext,
                      source_module: str) -> List[str]:
        """
        Kaynak modülün sinyallerini cascade kurallarıyla karşılaştır.
        Koşul sağlanırsa hedef modülleri döndür.
        """
        if ctx.cascade_depth >= MAX_CASCADE_DEPTH:
            return []

        triggered: List[str] = []

        for rule in self.cascade_rules:
            if rule.source != source_module:
                continue

            value = ctx.get(source_module, rule.signal_type)
            if value is None:
                continue

            if self._evaluate_rule(rule, value):
                # Sinaps ağırlığı eşiğini kontrol et
                for syn in self.synapses:
                    if (syn.source == source_module and
                            syn.weight >= CASCADE_THRESHOLD):
                        for target in rule.targets:
                            if target not in triggered:
                                triggered.append(target)
                                ctx.add_cascade(source_module, target,
                                                f"{rule.signal_type}={value}")
                                self.stats.record_cascade(source_module)
                        break  # Bir sinaps yeterli

        return triggered

    def _evaluate_rule(self, rule: CascadeRule, value: Any) -> bool:
        """Kaskad kuralını değerlendir"""
        try:
            if rule.operator == "in":
                return value in rule.threshold
            elif rule.operator == "gt":
                return float(value) > float(rule.threshold)
            elif rule.operator == "lt":
                return float(value) < float(rule.threshold)
            elif rule.operator == "eq":
                return value == rule.threshold
            elif rule.operator == "exists":
                return value is not None
            elif rule.operator == "truthy":
                return bool(value)
        except (TypeError, ValueError):
            pass
        return False

    # ── Hebbian Öğrenme ───────────────────────────────────────

    def learn_from_outcome(self, query_id: str, success: bool,
                           partial: bool = False) -> int:
        """
        Karar sonucuna göre aktive olan sinapsların ağırlıklarını güncelle.

        Hebbian kuralı: Δw = η × strength × outcome_factor
          - success=True:  outcome_factor = +1.0  (güçlendir)
          - partial=True:  outcome_factor = +0.3  (hafif güçlendir)
          - success=False: outcome_factor = -0.5  (zayıflat)

        Returns: güncellenen sinaps sayısı
        """
        activated_ids = self._query_activations.get(query_id, set())
        if not activated_ids:
            return 0

        if success:
            factor = 1.0
        elif partial:
            factor = 0.3
        else:
            factor = -0.5

        updated = 0
        for idx in activated_ids:
            if idx >= len(self.synapses):
                continue
            syn = self.synapses[idx]
            delta = LEARNING_RATE * STRENGTH_DEFAULT * factor

            if factor > 0:
                syn.reinforce(delta)
            else:
                syn.weaken(delta)
            updated += 1

        self.stats.learning_updates += 1

        # Kullanılmayan sinapsları çürüt
        used_ids = activated_ids
        for idx, syn in enumerate(self.synapses):
            if idx not in used_ids and syn.activations > 0:
                syn.decay()

        self.stats.decay_cycles += 1
        logger.info("synapse_learning_applied",
                     query_id=query_id,
                     success=success,
                     updated=updated)
        return updated

    # ── Sorgulama ve Analiz ───────────────────────────────────

    def get_top_synapses(self, n: int = 10) -> List[Synapse]:
        """En güçlü n sinapsı döndür"""
        return sorted(self.synapses, key=lambda s: s.weight, reverse=True)[:n]

    def get_weakest_synapses(self, n: int = 5) -> List[Synapse]:
        """En zayıf n sinapsı döndür"""
        return sorted(self.synapses, key=lambda s: s.weight)[:n]

    def get_module_connectivity(self, module: str) -> Dict[str, Any]:
        """Bir modülün bağlantı haritası"""
        incoming = []
        outgoing = []
        for syn in self.synapses:
            if syn.target == module:
                incoming.append({
                    "from": syn.source,
                    "weight": round(syn.weight, 3),
                    "signals": syn.signal_types,
                    "activations": syn.activations,
                })
            if syn.source == module:
                outgoing.append({
                    "to": syn.target,
                    "weight": round(syn.weight, 3),
                    "signals": syn.signal_types,
                    "activations": syn.activations,
                })
        return {
            "module": module,
            "incoming": sorted(incoming, key=lambda x: x["weight"], reverse=True),
            "outgoing": sorted(outgoing, key=lambda x: x["weight"], reverse=True),
            "total_connections": len(incoming) + len(outgoing),
        }

    def get_network_graph(self) -> Dict[str, Any]:
        """Tüm ağı düğüm + kenar olarak döndür"""
        modules = set()
        edges = []
        for syn in self.synapses:
            modules.add(syn.source)
            modules.add(syn.target)
            edges.append({
                "source": syn.source,
                "target": syn.target,
                "weight": round(syn.weight, 3),
                "activations": syn.activations,
                "signals": syn.signal_types,
            })
        return {
            "nodes": sorted(modules),
            "edges": edges,
            "total_nodes": len(modules),
            "total_edges": len(edges),
            "avg_weight": round(
                sum(s.weight for s in self.synapses) / max(len(self.synapses), 1), 3
            ),
        }

    # ── Formatlama ────────────────────────────────────────────

    def format_signal_trace(self, ctx: PipelineContext) -> str:
        """Pipeline sinyal akışını okunabilir metin olarak formatla"""
        if not ctx.trace:
            return ""

        lines = ["", "🧠 **Sinaps Ağı — Sinyal Akış İzi**", "━" * 42]

        for entry in ctx.trace:
            t = entry.get("t", 0)
            action = entry.get("action", "")

            if action == "emit":
                mod = entry["module"]
                sig = entry["signal"]
                strength = entry.get("strength", 0)
                bar = _strength_bar(strength)
                lines.append(f"  [{t:.2f}s] {mod} → {sig} {bar}")

            elif action == "route":
                src = entry["from"]
                tgt = entry["to"]
                sig = entry["signal"]
                w = entry.get("weight", 0)
                lines.append(f"  [{t:.2f}s]   ↳ {src} ──({w:.2f})──▶ {tgt} [{sig}]")

            elif action == "cascade":
                src = entry["source"]
                tgt = entry["target"]
                reason = entry.get("reason", "")
                lines.append(f"  [{t:.2f}s] ⚡ KASKAD: {src} → {tgt} ({reason})")

        # Özet
        lines.append("")
        sc = ctx.signal_count()
        mc = len(ctx.active_modules())
        cc = len(ctx.cascades_triggered)
        lines.append(f"  📊 {sc} sinyal, {mc} modül, {cc} kaskad, "
                     f"{ctx.elapsed_ms():.0f}ms")

        # En güçlü bağlantı
        top = self.get_top_synapses(1)
        if top:
            t = top[0]
            lines.append(f"  💪 En güçlü sinaps: {t.source} → {t.target} ({t.weight:.2f})")

        return "\n".join(lines)

    def format_network_summary(self, ctx: PipelineContext) -> str:
        """Kısa ağ özeti — result dict için"""
        sc = ctx.signal_count()
        mc = len(ctx.active_modules())
        cc = len(ctx.cascades_triggered)

        if sc == 0:
            return ""

        parts = [f"🧠 Sinaps: {sc} sinyal"]
        if cc > 0:
            parts.append(f"{cc} kaskad")
        parts.append(f"{mc} modül")

        if ctx.cascades_triggered:
            cascade_str = ", ".join(
                f"{c['source']}→{c['target']}" for c in ctx.cascades_triggered[:3]
            )
            parts.append(f"[{cascade_str}]")

        return " | ".join(parts)


# ═══════════════════════════════════════════════════════════════
# YARDIMCI FONKSİYONLAR
# ═══════════════════════════════════════════════════════════════

def _strength_bar(strength: float) -> str:
    """Sinyal gücü görsel çubuğu"""
    filled = int(strength * 5)
    empty = 5 - filled
    return "▰" * filled + "▱" * empty


# ═══════════════════════════════════════════════════════════════
# GLOBAL TEKTON (SINGLETON)
# ═══════════════════════════════════════════════════════════════

_network = SynapseNetwork()


# ═══════════════════════════════════════════════════════════════
# KAMUSAL API — engine.py ve diğer modüllerden çağrılacak
# ═══════════════════════════════════════════════════════════════

def create_pipeline_context(question: str, department: str = "") -> PipelineContext:
    """
    Yeni bir pipeline context oluştur.
    Her sorgu başında engine.py'den çağrılır.
    """
    ctx = PipelineContext(question=question, department=department)
    return ctx


def emit_signal(ctx: PipelineContext, module: str, signal_type: str,
                value: Any, strength: float = STRENGTH_DEFAULT) -> int:
    """
    Modülden sinyal yayınla ve sinapsları aktive et.
    Returns: aktive olan sinaps sayısı.
    """
    return _network.emit(ctx, module, signal_type, value, strength)


def gather_module_inputs(ctx: PipelineContext,
                         target_module: str) -> Dict[str, Any]:
    """
    Hedef modülün ihtiyaç duyduğu tüm inputları sinaps ağından topla.
    Aynı sinyal tipi birden fazla kaynaktan geliyorsa en güçlü sinapsı seçer.
    """
    return _network.gather_inputs(ctx, target_module)


def check_cascades(ctx: PipelineContext,
                   source_module: str) -> List[str]:
    """
    Kaynak modülün sinyallerini cascade kurallarıyla kontrol et.
    Returns: tetiklenmesi gereken modül listesi.
    """
    return _network.check_cascade(ctx, source_module)


def learn_from_outcome(query_id: str, success: bool,
                       partial: bool = False) -> int:
    """
    Karar sonucuna göre Hebbian öğrenme uygula.
    decision_memory.update_outcome() ile birlikte çağrılmalı.
    Returns: güncellenen sinaps sayısı.
    """
    return _network.learn_from_outcome(query_id, success, partial)


def finalize_context(ctx: PipelineContext) -> None:
    """
    Pipeline sonunda context istatistiklerini kaydet.
    engine.py'den result dict oluşturulduktan sonra çağrılır.
    """
    _network.stats.record_query(ctx.summary())


def format_signal_trace(ctx: PipelineContext) -> str:
    """Sinyal akış izini formatla — debug ve explainability için"""
    return _network.format_signal_trace(ctx)


def format_network_summary(ctx: PipelineContext) -> str:
    """Kısa ağ özeti — result dict'e eklenir"""
    return _network.format_network_summary(ctx)


def get_module_connectivity(module: str) -> Dict[str, Any]:
    """Belirli modülün bağlantı haritası"""
    return _network.get_module_connectivity(module)


def get_network_graph() -> Dict[str, Any]:
    """Tüm ağ grafiğini döndür"""
    return _network.get_network_graph()


def get_dashboard() -> Dict[str, Any]:
    """Admin dashboard için sinaps ağı istatistikleri"""
    stats = _network.stats
    graph = _network.get_network_graph()
    top_synapses = _network.get_top_synapses(10)
    weakest = _network.get_weakest_synapses(5)

    return {
        "network": {
            "total_synapses": len(_network.synapses),
            "total_modules": graph["total_nodes"],
            "avg_weight": graph["avg_weight"],
            "cascade_rules": len(_network.cascade_rules),
        },
        "stats": {
            "total_signals": stats.total_signals,
            "total_routes": stats.total_routes,
            "total_cascades": stats.total_cascades,
            "total_queries": stats.total_queries,
            "learning_updates": stats.learning_updates,
            "decay_cycles": stats.decay_cycles,
        },
        "top_synapses": [
            {
                "source": s.source,
                "target": s.target,
                "weight": round(s.weight, 3),
                "activations": s.activations,
                "success_rate": round(s.success_rate, 2),
            }
            for s in top_synapses
        ],
        "weakest_synapses": [
            {
                "source": s.source,
                "target": s.target,
                "weight": round(s.weight, 3),
                "activations": s.activations,
            }
            for s in weakest
        ],
        "module_activity": dict(sorted(
            stats.module_emit_counts.items(),
            key=lambda x: x[1], reverse=True
        )[:15]),
        "signal_type_frequency": dict(sorted(
            stats.signal_type_counts.items(),
            key=lambda x: x[1], reverse=True
        )[:15]),
        "cascade_triggers": dict(stats.cascade_trigger_counts),
        "recent_queries": stats.recent_traces[-5:],
    }
