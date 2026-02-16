"""
Decision Risk Gatekeeper v1.0 — Karar Risk Kapısı
CompanyAI v5.1.0

Sistemdeki tüm risk sinyallerini (governance, risk_analyzer, monte_carlo,
decision_ranking, reflection, causal_inference) birleştirerek kararları
ENGELLER veya UYARI ile geçirir.

Akış:
  1. RiskSignalCollector  → Tüm modüllerden risk sinyali topla
  2. RiskAggregator       → Sinyalleri ağırlıklı skora birleştir
  3. GateDecisionEngine   → Geç / Uyarılı Geç / Engelle kararı ver
  4. EscalationManager    → Engellenen kararlar için yükseltme yönetimi
  5. GateTracker          → İstatistik ve geçmiş takibi
  6. DecisionGatekeeper   → Orkestratör singleton
"""

from __future__ import annotations

import time
import hashlib
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
from collections import deque


# ═══════════════════════════════════════════════════════════════
# Enum'lar
# ═══════════════════════════════════════════════════════════════

class GateVerdict(Enum):
    """Kapı kararı."""
    PASS = "pass"                      # Sorunsuz geç
    PASS_WITH_WARNING = "pass_warning" # Uyarıyla geç
    BLOCK = "block"                    # Engelle
    ESCALATE = "escalate"              # Yetkili onayına yükselt


class RiskDomain(Enum):
    """Risk sinyal kaynağı."""
    GOVERNANCE = "governance"
    RISK_ANALYSIS = "risk_analysis"
    MONTE_CARLO = "monte_carlo"
    DECISION_RANKING = "decision_ranking"
    REFLECTION = "reflection"
    CAUSAL = "causal"
    CONFIDENCE = "confidence"
    CONTENT = "content"


class EscalationLevel(Enum):
    """Yükseltme seviyesi."""
    NONE = "none"
    REVIEW = "review"          # İnceleme önerisi
    APPROVAL = "approval"      # Onay gerekli
    EXECUTIVE = "executive"    # Üst yönetim onayı


# ═══════════════════════════════════════════════════════════════
# Veri Yapıları
# ═══════════════════════════════════════════════════════════════

@dataclass
class RiskSignal:
    """Tek bir risk sinyali."""
    domain: RiskDomain
    severity: float           # 0.0 – 1.0
    description: str
    source_module: str
    details: dict = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


@dataclass
class GateResult:
    """Kapı kararı sonucu."""
    verdict: GateVerdict
    composite_risk_score: float       # 0.0 – 1.0
    risk_level: str                   # Kritik / Yüksek / Orta / Düşük
    signals: list[RiskSignal] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    blocking_reasons: list[str] = field(default_factory=list)
    escalation_level: EscalationLevel = EscalationLevel.NONE
    recommendations: list[str] = field(default_factory=list)
    gate_duration_ms: float = 0.0

    def to_dict(self) -> dict:
        return {
            "verdict": self.verdict.value,
            "composite_risk_score": round(self.composite_risk_score, 3),
            "risk_level": self.risk_level,
            "signal_count": len(self.signals),
            "signals": [
                {
                    "domain": s.domain.value,
                    "severity": round(s.severity, 3),
                    "description": s.description,
                    "source": s.source_module,
                }
                for s in self.signals
            ],
            "warnings": self.warnings,
            "blocking_reasons": self.blocking_reasons,
            "escalation_level": self.escalation_level.value,
            "recommendations": self.recommendations,
            "gate_duration_ms": round(self.gate_duration_ms, 2),
        }


@dataclass
class GateConfig:
    """Kapı eşik ayarları."""
    # Risk skoru eşikleri
    block_threshold: float = 0.80       # Bu ve üstü → BLOCK
    warning_threshold: float = 0.50     # Bu ve üstü → PASS_WITH_WARNING
    escalate_threshold: float = 0.90    # Bu ve üstü → ESCALATE (yetkiliye)

    # Domain ağırlıkları (toplam = 1.0 olmalı)
    weights: dict = field(default_factory=lambda: {
        RiskDomain.GOVERNANCE: 0.25,
        RiskDomain.RISK_ANALYSIS: 0.20,
        RiskDomain.MONTE_CARLO: 0.15,
        RiskDomain.REFLECTION: 0.15,
        RiskDomain.CONFIDENCE: 0.10,
        RiskDomain.DECISION_RANKING: 0.08,
        RiskDomain.CAUSAL: 0.05,
        RiskDomain.CONTENT: 0.02,
    })

    # Tek sinyal veto kuralları (severity bu değeri aşarsa tek başına BLOCK)
    single_veto_threshold: float = 0.95

    # Minimum sinyal sayısı (daha az sinyalde sadece uyarı verilebilir)
    min_signals_for_block: int = 2


# ═══════════════════════════════════════════════════════════════
# 1. Risk Signal Collector — Modüllerden sinyal toplama
# ═══════════════════════════════════════════════════════════════

class RiskSignalCollector:
    """Mevcut modüllerden risk sinyallerini toplar."""

    def collect_governance_signals(self, governance_data: dict | None) -> list[RiskSignal]:
        """Governance modülünden sinyal topla."""
        signals = []
        if not governance_data:
            return signals

        violations = governance_data.get("violations", [])
        if violations:
            violation_count = len(violations)
            severity = min(1.0, violation_count * 0.25)
            signals.append(RiskSignal(
                domain=RiskDomain.GOVERNANCE,
                severity=severity,
                description=f"{violation_count} governance ihlali tespit edildi",
                source_module="governance",
                details={"violations": violations[:5], "count": violation_count},
            ))

        compliance = governance_data.get("compliance_score", 100)
        if compliance < 70:
            severity = (70 - compliance) / 70
            signals.append(RiskSignal(
                domain=RiskDomain.GOVERNANCE,
                severity=min(1.0, severity),
                description=f"Düşük uyumluluk skoru: {compliance:.0f}/100",
                source_module="governance",
                details={"compliance_score": compliance},
            ))

        drift_alerts = governance_data.get("drift_alerts", [])
        if drift_alerts:
            severity = min(1.0, len(drift_alerts) * 0.20)
            signals.append(RiskSignal(
                domain=RiskDomain.GOVERNANCE,
                severity=severity,
                description=f"{len(drift_alerts)} drift uyarısı",
                source_module="governance",
                details={"drift_types": drift_alerts[:3]},
            ))

        return signals

    def collect_risk_signals(self, risk_data: dict | None) -> list[RiskSignal]:
        """Risk analyzer modülünden sinyal topla."""
        signals = []
        if not risk_data:
            return signals

        risk_level = risk_data.get("risk_level", "").lower()
        severity_map = {"kritik": 0.95, "yüksek": 0.70, "orta": 0.40, "düşük": 0.15}
        severity = severity_map.get(risk_level, 0.0)

        if severity > 0:
            signals.append(RiskSignal(
                domain=RiskDomain.RISK_ANALYSIS,
                severity=severity,
                description=f"Risk seviyesi: {risk_level.capitalize()}",
                source_module="risk_analyzer",
                details=risk_data,
            ))

        return signals

    def collect_monte_carlo_signals(self, mc_data: dict | None) -> list[RiskSignal]:
        """Monte Carlo simülasyonundan sinyal topla."""
        signals = []
        if not mc_data:
            return signals

        failure_prob = mc_data.get("failure_probability", 0)
        if failure_prob > 0.20:
            signals.append(RiskSignal(
                domain=RiskDomain.MONTE_CARLO,
                severity=min(1.0, failure_prob),
                description=f"Başarısızlık olasılığı: %{failure_prob*100:.1f}",
                source_module="monte_carlo",
                details={"failure_probability": failure_prob},
            ))

        var_95 = mc_data.get("var_95", 0)
        if var_95 > 0:
            severity = min(1.0, var_95 / 100)
            signals.append(RiskSignal(
                domain=RiskDomain.MONTE_CARLO,
                severity=severity,
                description=f"VaR %95: {var_95:.2f}",
                source_module="monte_carlo",
                details={"var_95": var_95},
            ))

        volatility = mc_data.get("volatility_index", 0)
        if volatility > 0.50:
            signals.append(RiskSignal(
                domain=RiskDomain.MONTE_CARLO,
                severity=min(1.0, volatility),
                description=f"Yüksek volatilite: {volatility:.2f}",
                source_module="monte_carlo",
                details={"volatility_index": volatility},
            ))

        return signals

    def collect_reflection_signals(self, reflection_data: dict | None) -> list[RiskSignal]:
        """Reflection (kendini değerlendirme) modülünden sinyal topla."""
        signals = []
        if not reflection_data:
            return signals

        score = reflection_data.get("score", 100)
        if score < 60:
            severity = (60 - score) / 60
            signals.append(RiskSignal(
                domain=RiskDomain.REFLECTION,
                severity=min(1.0, severity),
                description=f"Düşük kalite skoru: {score}/100",
                source_module="reflection",
                details={"quality_score": score},
            ))

        hallucination = reflection_data.get("hallucination_risk", 0)
        if hallucination > 0.3:
            signals.append(RiskSignal(
                domain=RiskDomain.REFLECTION,
                severity=min(1.0, hallucination),
                description=f"Hallüsinasyon riski: %{hallucination*100:.0f}",
                source_module="reflection",
                details={"hallucination_risk": hallucination},
            ))

        retry_count = reflection_data.get("retry_count", 0)
        if retry_count >= 2:
            signals.append(RiskSignal(
                domain=RiskDomain.REFLECTION,
                severity=0.60,
                description=f"Maksimum retry'a ulaşıldı ({retry_count} deneme)",
                source_module="reflection",
                details={"retry_count": retry_count},
            ))

        return signals

    def collect_confidence_signals(self, confidence: float | None) -> list[RiskSignal]:
        """Genel güven skoru sinyali."""
        signals = []
        if confidence is None:
            return signals

        conf_val = confidence if isinstance(confidence, (int, float)) else 0.85
        if conf_val <= 1.0:
            conf_val *= 100  # 0-1 → 0-100

        if conf_val < 50:
            severity = (50 - conf_val) / 50
            signals.append(RiskSignal(
                domain=RiskDomain.CONFIDENCE,
                severity=min(1.0, severity),
                description=f"Düşük güven: %{conf_val:.0f}",
                source_module="engine",
                details={"confidence": conf_val},
            ))

        return signals

    def collect_decision_ranking_signals(self, ranking_data: dict | None) -> list[RiskSignal]:
        """Decision ranking sinyali."""
        signals = []
        if not ranking_data:
            return signals

        decisions = ranking_data.get("decisions", [])
        if decisions:
            low_score = [d for d in decisions if d.get("priority_score", 100) < 25]
            if low_score:
                signals.append(RiskSignal(
                    domain=RiskDomain.DECISION_RANKING,
                    severity=0.55,
                    description=f"{len(low_score)} karar düşük öncelik skoruna sahip",
                    source_module="decision_ranking",
                    details={"low_priority_count": len(low_score)},
                ))

        return signals

    def collect_all(
        self,
        governance_data: dict | None = None,
        risk_data: dict | None = None,
        mc_data: dict | None = None,
        reflection_data: dict | None = None,
        confidence: float | None = None,
        ranking_data: dict | None = None,
    ) -> list[RiskSignal]:
        """Tüm kaynaklardan sinyalleri topla."""
        signals = []
        signals.extend(self.collect_governance_signals(governance_data))
        signals.extend(self.collect_risk_signals(risk_data))
        signals.extend(self.collect_monte_carlo_signals(mc_data))
        signals.extend(self.collect_reflection_signals(reflection_data))
        signals.extend(self.collect_confidence_signals(confidence))
        signals.extend(self.collect_decision_ranking_signals(ranking_data))
        return signals


# ═══════════════════════════════════════════════════════════════
# 2. Risk Aggregator — Sinyalleri birleştirme
# ═══════════════════════════════════════════════════════════════

class RiskAggregator:
    """Risk sinyallerini ağırlıklı composite skora birleştirir."""

    def aggregate(self, signals: list[RiskSignal], config: GateConfig) -> float:
        """
        Ağırlıklı risk skoru hesapla.
        Her domain'den en yüksek severity değeri alınır,
        sonra domain ağırlıklarıyla çarpılıp toplanır.
        """
        if not signals:
            return 0.0

        # Her domain'den en yüksek severity'yi al
        domain_max: dict[RiskDomain, float] = {}
        for sig in signals:
            current = domain_max.get(sig.domain, 0.0)
            domain_max[sig.domain] = max(current, sig.severity)

        # Ağırlıklı toplam
        total_score = 0.0
        total_weight = 0.0
        for domain, max_severity in domain_max.items():
            weight = config.weights.get(domain, 0.05)
            total_score += max_severity * weight
            total_weight += weight

        if total_weight == 0:
            return 0.0

        # Normalize (aktif domainlerin ağırlıklarına göre)
        composite = total_score / total_weight

        # Çok sayıda sinyal varsa boost (3+ sinyalde +%10)
        signal_count_boost = min(0.10, len(signals) * 0.02) if len(signals) >= 3 else 0
        composite = min(1.0, composite + signal_count_boost)

        return composite


# ═══════════════════════════════════════════════════════════════
# 3. Gate Decision Engine — Geç / Uyar / Engelle kararı
# ═══════════════════════════════════════════════════════════════

class GateDecisionEngine:
    """Composite risk skorundan GateVerdict üretir."""

    def evaluate(self, signals: list[RiskSignal], composite: float, config: GateConfig) -> GateResult:
        """Risk skoru ve sinyallere göre kapı kararı."""

        warnings = []
        blocking_reasons = []
        recommendations = []

        # 1. Tek sinyal veto kontrolü
        veto_signals = [s for s in signals if s.severity >= config.single_veto_threshold]
        if veto_signals:
            for vs in veto_signals:
                blocking_reasons.append(f"[VETO] {vs.description} (severity: {vs.severity:.2f})")
            return GateResult(
                verdict=GateVerdict.BLOCK,
                composite_risk_score=composite,
                risk_level="Kritik",
                signals=signals,
                warnings=warnings,
                blocking_reasons=blocking_reasons,
                escalation_level=EscalationLevel.EXECUTIVE,
                recommendations=["Yanıt engellendi — veto eşiği aşıldı. İçerik gözden geçirilmeli."],
            )

        # 2. Escalation kontrolü
        if composite >= config.escalate_threshold:
            blocking_reasons = [f"Composite risk çok yüksek: {composite:.2f} ≥ {config.escalate_threshold}"]
            for s in sorted(signals, key=lambda x: x.severity, reverse=True)[:3]:
                warnings.append(f"{s.domain.value}: {s.description}")
            return GateResult(
                verdict=GateVerdict.ESCALATE,
                composite_risk_score=composite,
                risk_level="Kritik",
                signals=signals,
                warnings=warnings,
                blocking_reasons=blocking_reasons,
                escalation_level=EscalationLevel.EXECUTIVE,
                recommendations=[
                    "Yanıt yüksek risk taşıyor — üst yönetim onayı gerekli.",
                    "İçerik gözden geçirilmeden kullanılmamalı.",
                ],
            )

        # 3. Block kontrolü
        if composite >= config.block_threshold and len(signals) >= config.min_signals_for_block:
            for s in sorted(signals, key=lambda x: x.severity, reverse=True)[:3]:
                blocking_reasons.append(f"{s.domain.value}: {s.description}")
            return GateResult(
                verdict=GateVerdict.BLOCK,
                composite_risk_score=composite,
                risk_level="Yüksek",
                signals=signals,
                warnings=warnings,
                blocking_reasons=blocking_reasons,
                escalation_level=EscalationLevel.APPROVAL,
                recommendations=[
                    "Yanıt riskli bulundu — otomatik engellendi.",
                    "Manuel inceleme sonrası tekrar denenebilir.",
                ],
            )

        # 4. Warning kontrolü
        if composite >= config.warning_threshold:
            risk_level = "Yüksek" if composite >= 0.70 else "Orta"
            for s in sorted(signals, key=lambda x: x.severity, reverse=True)[:3]:
                warnings.append(f"{s.domain.value}: {s.description}")
            recommendations.append("Yanıt dikkatli kullanılmalı — risk sinyalleri mevcut.")
            return GateResult(
                verdict=GateVerdict.PASS_WITH_WARNING,
                composite_risk_score=composite,
                risk_level=risk_level,
                signals=signals,
                warnings=warnings,
                blocking_reasons=[],
                escalation_level=EscalationLevel.REVIEW,
                recommendations=recommendations,
            )

        # 5. Pass
        risk_level = "Düşük" if composite < 0.25 else "Orta"
        return GateResult(
            verdict=GateVerdict.PASS,
            composite_risk_score=composite,
            risk_level=risk_level,
            signals=signals,
            warnings=[],
            blocking_reasons=[],
            escalation_level=EscalationLevel.NONE,
            recommendations=[],
        )


# ═══════════════════════════════════════════════════════════════
# 4. Escalation Manager — Yükseltme yönetimi
# ═══════════════════════════════════════════════════════════════

class EscalationManager:
    """Engellenen/yükseltilen kararları yönetir."""

    def __init__(self, max_history: int = 200):
        self.escalation_queue: deque[dict] = deque(maxlen=max_history)

    def record_escalation(self, gate_result: GateResult, question: str, answer: str):
        """Yükseltme kaydı oluştur."""
        entry = {
            "id": hashlib.md5(f"{question}{time.time()}".encode()).hexdigest()[:12],
            "timestamp": time.time(),
            "verdict": gate_result.verdict.value,
            "risk_score": gate_result.composite_risk_score,
            "risk_level": gate_result.risk_level,
            "escalation_level": gate_result.escalation_level.value,
            "question_preview": question[:100],
            "blocking_reasons": gate_result.blocking_reasons,
            "warnings": gate_result.warnings,
            "signal_count": len(gate_result.signals),
            "resolved": False,
            "resolution": None,
        }
        self.escalation_queue.append(entry)
        return entry

    def get_pending(self) -> list[dict]:
        """Çözülmemiş yükseltmeleri getir."""
        return [e for e in self.escalation_queue if not e.get("resolved")]

    def resolve(self, escalation_id: str, resolution: str = "approved") -> bool:
        """Yükseltmeyi çöz."""
        for entry in self.escalation_queue:
            if entry.get("id") == escalation_id:
                entry["resolved"] = True
                entry["resolution"] = resolution
                entry["resolved_at"] = time.time()
                return True
        return False


# ═══════════════════════════════════════════════════════════════
# 5. Gate Tracker — İstatistik ve geçmiş
# ═══════════════════════════════════════════════════════════════

class GateTracker:
    """Kapı kararlarının istatistik takibi."""

    def __init__(self, max_history: int = 500):
        self.history: deque[dict] = deque(maxlen=max_history)
        self.verdict_counts: dict[str, int] = {
            GateVerdict.PASS.value: 0,
            GateVerdict.PASS_WITH_WARNING.value: 0,
            GateVerdict.BLOCK.value: 0,
            GateVerdict.ESCALATE.value: 0,
        }
        self.total_evaluations: int = 0
        self.total_blocks: int = 0
        self.risk_score_sum: float = 0.0

    def record(self, gate_result: GateResult, question: str):
        """Kapı sonucunu kaydet."""
        self.total_evaluations += 1
        self.verdict_counts[gate_result.verdict.value] = (
            self.verdict_counts.get(gate_result.verdict.value, 0) + 1
        )
        self.risk_score_sum += gate_result.composite_risk_score

        if gate_result.verdict in (GateVerdict.BLOCK, GateVerdict.ESCALATE):
            self.total_blocks += 1

        self.history.append({
            "timestamp": time.time(),
            "verdict": gate_result.verdict.value,
            "risk_score": round(gate_result.composite_risk_score, 3),
            "risk_level": gate_result.risk_level,
            "signal_count": len(gate_result.signals),
            "question_preview": question[:80],
        })

    def get_statistics(self) -> dict:
        """İstatistikleri döndür."""
        avg_risk = (self.risk_score_sum / self.total_evaluations) if self.total_evaluations > 0 else 0
        block_rate = (self.total_blocks / self.total_evaluations * 100) if self.total_evaluations > 0 else 0
        return {
            "total_evaluations": self.total_evaluations,
            "verdict_distribution": dict(self.verdict_counts),
            "total_blocks": self.total_blocks,
            "block_rate_percent": round(block_rate, 1),
            "average_risk_score": round(avg_risk, 3),
        }

    def get_recent(self, limit: int = 20) -> list[dict]:
        """Son kayıtları getir."""
        items = list(self.history)
        return items[-limit:]


# ═══════════════════════════════════════════════════════════════
# 6. DecisionGatekeeper — Ana orkestratör
# ═══════════════════════════════════════════════════════════════

class DecisionGatekeeper:
    """
    Risk Kapısı orkestratörü.
    Tüm alt bileşenleri koordine ederek kapı kararı verir.
    """

    def __init__(self):
        self.enabled: bool = True
        self.config = GateConfig()
        self.collector = RiskSignalCollector()
        self.aggregator = RiskAggregator()
        self.decision_engine = GateDecisionEngine()
        self.escalation_manager = EscalationManager()
        self.tracker = GateTracker()

    def evaluate(
        self,
        question: str,
        answer: str,
        governance_data: dict | None = None,
        reflection_data: dict | None = None,
        confidence: float | None = None,
        risk_data: dict | None = None,
        mc_data: dict | None = None,
        ranking_data: dict | None = None,
    ) -> GateResult:
        """
        Ana kapı değerlendirmesi.
        Tüm modüllerden sinyal toplar, birleştirir ve karar verir.
        """
        start = time.time()

        if not self.enabled:
            return GateResult(
                verdict=GateVerdict.PASS,
                composite_risk_score=0.0,
                risk_level="Düşük",
            )

        # 1. Sinyal topla
        signals = self.collector.collect_all(
            governance_data=governance_data,
            risk_data=risk_data,
            mc_data=mc_data,
            reflection_data=reflection_data,
            confidence=confidence,
            ranking_data=ranking_data,
        )

        # 2. Composite risk skoru
        composite = self.aggregator.aggregate(signals, self.config)

        # 3. Kapı kararı
        result = self.decision_engine.evaluate(signals, composite, self.config)
        result.gate_duration_ms = (time.time() - start) * 1000

        # 4. Kaydet
        self.tracker.record(result, question)

        # 5. Yükseltme gerekiyorsa kayıt
        if result.verdict in (GateVerdict.BLOCK, GateVerdict.ESCALATE):
            self.escalation_manager.record_escalation(result, question, answer)

        return result

    def set_enabled(self, enabled: bool) -> dict:
        """Kapıyı aç/kapat."""
        self.enabled = enabled
        return {"enabled": self.enabled, "status": "active" if enabled else "disabled"}

    def update_thresholds(
        self,
        block_threshold: float | None = None,
        warning_threshold: float | None = None,
        escalate_threshold: float | None = None,
    ) -> dict:
        """Eşik değerlerini güncelle."""
        if block_threshold is not None:
            self.config.block_threshold = max(0.1, min(1.0, block_threshold))
        if warning_threshold is not None:
            self.config.warning_threshold = max(0.1, min(1.0, warning_threshold))
        if escalate_threshold is not None:
            self.config.escalate_threshold = max(0.1, min(1.0, escalate_threshold))
        return {
            "block_threshold": self.config.block_threshold,
            "warning_threshold": self.config.warning_threshold,
            "escalate_threshold": self.config.escalate_threshold,
        }

    def reset(self):
        """Tüm verileri sıfırla."""
        self.tracker = GateTracker()
        self.escalation_manager = EscalationManager()
        self.config = GateConfig()


# ═══════════════════════════════════════════════════════════════
# Singleton & Convenience
# ═══════════════════════════════════════════════════════════════

decision_gatekeeper = DecisionGatekeeper()


# Gate tetikleme — her sorgu sonrası çağrılır
GATE_TRIGGER_KEYWORDS = [
    "karar", "uygula", "çalıştır", "başlat", "onayla", "kabul",
    "invest", "yatırım", "harca", "aksiyon", "execute", "approve",
    "strateji uygula", "planı devreye al", "operasyona geç",
]


def check_gate_trigger(
    question: str = "",
    mode: str = "",
    intent: str = "",
    **kwargs,
) -> tuple[bool, str]:
    """
    Gate tetiklenme kontrolü.
    Her sorgu sonrası otomatik çalışır (engine.py pipeline'ında).
    """
    if not decision_gatekeeper.enabled:
        return False, "disabled"

    q_lower = question.lower()

    # Karar/aksiyon içeren sorularda tetikle
    for kw in GATE_TRIGGER_KEYWORDS:
        if kw in q_lower:
            return True, f"karar_anahtar_kelime: {kw}"

    # Yüksek riskli modlarda tetikle
    high_risk_modes = ["Üst Düzey Analiz", "CEO Raporu", "Risk Analizi", "Finansal Analiz"]
    if mode in high_risk_modes:
        return True, f"yüksek_riskli_mod: {mode}"

    # Karar intent'lerinde tetikle
    decision_intents = ["karar_destek", "risk_değerlendirme", "strateji", "yatırım"]
    if intent in decision_intents:
        return True, f"karar_intent: {intent}"

    return False, "no_trigger"


def get_gate_dashboard() -> dict:
    """Dashboard verisi."""
    stats = decision_gatekeeper.tracker.get_statistics()
    pending = decision_gatekeeper.escalation_manager.get_pending()
    return {
        "available": True,
        "enabled": decision_gatekeeper.enabled,
        "statistics": stats,
        "pending_escalations": len(pending),
        "thresholds": {
            "block": decision_gatekeeper.config.block_threshold,
            "warning": decision_gatekeeper.config.warning_threshold,
            "escalate": decision_gatekeeper.config.escalate_threshold,
        },
    }
