"""Decision Quality Scoring — Karar Kalitesi Puanlama Motoru

Her AI önerisine bütünleşik bir kalite skoru atar.
Patron sorusu: "Bu öneriye ne kadar güvenebilirim?" → Net cevap üretir.

v5.5.0 Enterprise Eklemeleri:
  • Outcome comparison — tahmin vs gerçekleşen sonuç karşılaştırma
  • Regret metric — "keşke farklı karar verseydik" ölçümü
  • Counterfactual performance — alternatif senaryo analizi

Toplanan sinyaller:
  1. Reflection kalitesi     — 5 kriter puanı (data_accuracy, logical_consistency, ...)
  2. Belirsizlik seviyesi    — Uncertainty Quantification ensemble skoru
  3. Risk seviyesi           — Decision Gatekeeper composite risk
  4. Tarihsel başarı oranı   — Meta Learning strateji profili
  5. Veri güvenirliği        — RAG kaynak kalitesi, web doğrulama
  6. Governance uyumu        — Bias, drift, compliance
  7. Konsensüs derecesi      — Multi-agent debate uyuşması
  8. Nedensel güç            — Causal inference kanıt gücü

Çıktı: 0-100 arası bütünleşik kalite skoru + güven bandı + açıklama
"""

from __future__ import annotations
import time
import json
import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
from collections import deque
import structlog

logger = structlog.get_logger()

_OUTCOME_DIR = Path("data/decision_outcomes")
_OUTCOME_DIR.mkdir(parents=True, exist_ok=True)


# ─── Enums ──────────────────────────────────────────────────────────

class QualityBand(Enum):
    """Kalite skor bandı"""
    EXCEPTIONAL = "exceptional"      # 90-100
    HIGH = "high"                    # 75-89
    MODERATE = "moderate"            # 55-74
    LOW = "low"                      # 35-54
    INSUFFICIENT = "insufficient"    # 0-34


class SignalReliability(Enum):
    """Sinyal güvenirlik seviyesi"""
    STRONG = "strong"          # Modül aktif, veri zengin
    MODERATE = "moderate"      # Modül aktif ama veri sınırlı
    WEAK = "weak"              # Modül inaktif, varsayılan kullanıldı
    UNAVAILABLE = "unavailable"  # Modül yok


# ─── Data Classes ───────────────────────────────────────────────────

@dataclass
class QualitySignal:
    """Tek bir kalite sinyali"""
    name: str
    source_module: str
    raw_value: float           # 0-100 normalize edilmiş
    weight: float              # 0-1
    reliability: SignalReliability
    description: str = ""
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class QualityBreakdown:
    """Kalite skor kırılımı"""
    data_reliability: float = 0.0       # Veri güvenilirliği (0-100)
    uncertainty_level: float = 0.0      # Belirsizlik seviyesi (0-100, düşük=iyi)
    risk_level: float = 0.0            # Risk seviyesi (0-100, düşük=iyi)
    historical_success: float = 0.0    # Tarihsel başarı oranı (0-100)
    governance_compliance: float = 0.0  # Governance uyumu (0-100)
    reasoning_depth: float = 0.0       # Muhakeme derinliği (0-100)
    consensus_degree: float = 0.0      # Konsensüs derecesi (0-100)
    evidence_strength: float = 0.0     # Kanıt gücü (0-100)


@dataclass
class QualityResult:
    """Nihai kalite skoru sonucu"""
    overall_score: float                # 0-100
    band: QualityBand
    band_label_tr: str                  # Türkçe band etiketi
    confidence_interval: Tuple[float, float]  # (low, high)
    breakdown: QualityBreakdown
    signals: List[QualitySignal]
    signal_coverage: float              # Kaç sinyal aktif (0-1)
    recommendation_tr: str              # Türkçe güven açıklaması
    executive_line: str                 # Tek satır yönetici özeti
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "overall_score": round(self.overall_score, 1),
            "band": self.band.value,
            "band_label": self.band_label_tr,
            "confidence_interval": {
                "low": round(self.confidence_interval[0], 1),
                "high": round(self.confidence_interval[1], 1),
            },
            "breakdown": {
                "data_reliability": round(self.breakdown.data_reliability, 1),
                "uncertainty_level": round(self.breakdown.uncertainty_level, 1),
                "risk_level": round(self.breakdown.risk_level, 1),
                "historical_success": round(self.breakdown.historical_success, 1),
                "governance_compliance": round(self.breakdown.governance_compliance, 1),
                "reasoning_depth": round(self.breakdown.reasoning_depth, 1),
                "consensus_degree": round(self.breakdown.consensus_degree, 1),
                "evidence_strength": round(self.breakdown.evidence_strength, 1),
            },
            "signal_coverage": round(self.signal_coverage, 2),
            "recommendation": self.recommendation_tr,
            "executive_line": self.executive_line,
            "signal_count": len(self.signals),
        }


# ─── Sinyal Ağırlıkları ────────────────────────────────────────────

# Şirket içi karar destek odaklı ağırlıklar
SIGNAL_WEIGHTS = {
    "reflection_quality": 0.20,       # Temel kalite
    "uncertainty": 0.15,              # Belirsizlik
    "risk": 0.15,                     # Risk seviyesi
    "historical_success": 0.12,       # Geçmiş başarı
    "data_reliability": 0.12,         # Veri kalitesi
    "governance": 0.10,               # Uyum
    "consensus": 0.08,                # Konsensüs
    "evidence_strength": 0.08,        # Kanıt gücü
}

BAND_LABELS_TR = {
    QualityBand.EXCEPTIONAL: "Çok Yüksek Güvenilirlik",
    QualityBand.HIGH: "Yüksek Güvenilirlik",
    QualityBand.MODERATE: "Orta Güvenilirlik",
    QualityBand.LOW: "Düşük Güvenilirlik",
    QualityBand.INSUFFICIENT: "Yetersiz Güvenilirlik",
}


# ─── Signal Collectors ─────────────────────────────────────────────

class SignalCollector:
    """Pipeline çıktılarından kalite sinyalleri toplar"""

    @staticmethod
    def from_reflection(reflection_data: Optional[dict]) -> QualitySignal:
        """Reflection modülünden kalite sinyali"""
        if not reflection_data or not isinstance(reflection_data, dict):
            return QualitySignal(
                name="reflection_quality",
                source_module="reflection",
                raw_value=50.0,
                weight=SIGNAL_WEIGHTS["reflection_quality"],
                reliability=SignalReliability.UNAVAILABLE,
                description="Reflection verisi mevcut değil",
            )

        confidence = reflection_data.get("confidence", 50)
        criteria = reflection_data.get("criteria_scores", {})
        issues = reflection_data.get("issues", [])

        # Kriter bazlı ortalama
        if criteria:
            criteria_avg = sum(criteria.values()) / len(criteria)
        else:
            criteria_avg = confidence

        # Sayısal doğrulama cezası
        num_val = reflection_data.get("numerical_validation", {})
        num_penalty = 0
        if isinstance(num_val, dict):
            mismatches = num_val.get("mismatches", 0)
            num_penalty = min(mismatches * 5, 20)

        score = max(0, min(100, (confidence * 0.5 + criteria_avg * 0.5) - num_penalty - len(issues) * 3))

        return QualitySignal(
            name="reflection_quality",
            source_module="reflection",
            raw_value=score,
            weight=SIGNAL_WEIGHTS["reflection_quality"],
            reliability=SignalReliability.STRONG if criteria else SignalReliability.MODERATE,
            description=f"Güven: {confidence}, Kriter ort: {criteria_avg:.0f}, Sorun: {len(issues)}",
            details={"confidence": confidence, "criteria_avg": criteria_avg, "issues_count": len(issues)},
        )

    @staticmethod
    def from_uncertainty(uncertainty_data: Optional[dict]) -> QualitySignal:
        """Uncertainty Quantification'dan sinyal — düşük belirsizlik = yüksek kalite"""
        if not uncertainty_data or not isinstance(uncertainty_data, dict):
            return QualitySignal(
                name="uncertainty",
                source_module="uncertainty_quantification",
                raw_value=50.0,
                weight=SIGNAL_WEIGHTS["uncertainty"],
                reliability=SignalReliability.UNAVAILABLE,
                description="Belirsizlik verisi mevcut değil",
            )

        ensemble = uncertainty_data.get("ensemble_confidence", 50)
        margin = uncertainty_data.get("margin_of_error", 15)
        agreement = uncertainty_data.get("source_agreement", 0.5)

        # Düşük belirsizlik = yüksek kalite
        # ensemble zaten 0-100 güven, doğrudan kullan
        # margin yüksekse cezala
        score = max(0, min(100, ensemble - margin * 0.5 + agreement * 10))

        return QualitySignal(
            name="uncertainty",
            source_module="uncertainty_quantification",
            raw_value=score,
            weight=SIGNAL_WEIGHTS["uncertainty"],
            reliability=SignalReliability.STRONG,
            description=f"Ensemble: %{ensemble:.0f} ± {margin:.0f}, Kaynak uyumu: {agreement:.2f}",
            details={"ensemble": ensemble, "margin": margin, "agreement": agreement},
        )

    @staticmethod
    def from_risk(gate_data: Optional[dict]) -> QualitySignal:
        """Decision Gatekeeper'dan risk sinyali — düşük risk = yüksek kalite"""
        if not gate_data or not isinstance(gate_data, dict):
            return QualitySignal(
                name="risk",
                source_module="decision_gatekeeper",
                raw_value=65.0,
                weight=SIGNAL_WEIGHTS["risk"],
                reliability=SignalReliability.UNAVAILABLE,
                description="Risk kapısı verisi mevcut değil",
            )

        composite = gate_data.get("composite_risk_score", 0.3)
        verdict = gate_data.get("verdict", "PASS")
        risk_level = gate_data.get("risk_level", "unknown")
        signal_count = gate_data.get("signal_count", 0)

        # Risk skoru ters çevir (düşük risk = yüksek kalite)
        risk_quality = max(0, min(100, (1 - composite) * 100))

        # Verdict bazlı bonus/ceza
        verdict_mod = {
            "PASS": 5, "PASS_WITH_WARNING": 0,
            "BLOCK": -20, "ESCALATE": -30,
        }
        risk_quality += verdict_mod.get(verdict, 0)
        risk_quality = max(0, min(100, risk_quality))

        return QualitySignal(
            name="risk",
            source_module="decision_gatekeeper",
            raw_value=risk_quality,
            weight=SIGNAL_WEIGHTS["risk"],
            reliability=SignalReliability.STRONG if signal_count > 2 else SignalReliability.MODERATE,
            description=f"Composite risk: {composite:.2f}, Karar: {verdict}",
            details={"composite": composite, "verdict": verdict, "risk_level": risk_level},
        )

    @staticmethod
    def from_meta_learning(meta_data: Optional[dict]) -> QualitySignal:
        """Meta Learning'den tarihsel başarı sinyali"""
        if not meta_data or not isinstance(meta_data, dict):
            return QualitySignal(
                name="historical_success",
                source_module="meta_learning",
                raw_value=60.0,
                weight=SIGNAL_WEIGHTS["historical_success"],
                reliability=SignalReliability.UNAVAILABLE,
                description="Meta öğrenme verisi mevcut değil",
            )

        quality_trend = meta_data.get("quality_trend", {})
        strategy_success = meta_data.get("strategy_success_rate", 0.6)
        domain_perf = meta_data.get("domain_performance", {})

        avg_quality = quality_trend.get("avg_confidence", 60)
        trend_slope = quality_trend.get("slope", 0)

        # Trend yönü bonus: pozitif slope = iyileşme
        trend_bonus = min(10, max(-10, trend_slope * 100))

        score = max(0, min(100, avg_quality + trend_bonus + strategy_success * 10))

        return QualitySignal(
            name="historical_success",
            source_module="meta_learning",
            raw_value=score,
            weight=SIGNAL_WEIGHTS["historical_success"],
            reliability=SignalReliability.STRONG if isinstance(quality_trend, dict) and quality_trend else SignalReliability.WEAK,
            description=f"Ort kalite: {avg_quality:.0f}, Trend: {trend_slope:+.3f}",
            details={"avg_quality": avg_quality, "trend_slope": trend_slope},
        )

    @staticmethod
    def from_data_sources(
        rag_used: bool = False,
        web_searched: bool = False,
        sources: Optional[list] = None,
        source_citation_valid: Optional[bool] = None,
    ) -> QualitySignal:
        """Veri kaynaklarının güvenilirliği"""
        score = 40.0  # Temel (LLM bilgisi)

        if rag_used:
            score += 20  # RAG veri tabanından bilgi
        if web_searched:
            score += 10  # Web araması yapıldı
        if sources and len(sources) > 0:
            score += min(15, len(sources) * 3)  # Kaynak sayısı
        if source_citation_valid is True:
            score += 15  # Kaynak doğrulaması geçti
        elif source_citation_valid is False:
            score -= 10  # Kaynak doğrulaması başarısız

        score = max(0, min(100, score))

        reliability = SignalReliability.STRONG if rag_used else (
            SignalReliability.MODERATE if web_searched else SignalReliability.WEAK
        )

        return QualitySignal(
            name="data_reliability",
            source_module="data_sources",
            raw_value=score,
            weight=SIGNAL_WEIGHTS["data_reliability"],
            reliability=reliability,
            description=f"RAG: {'✓' if rag_used else '✗'}, Web: {'✓' if web_searched else '✗'}, Kaynak: {len(sources or [])}",
            details={"rag": rag_used, "web": web_searched, "source_count": len(sources or [])},
        )

    @staticmethod
    def from_governance(governance_data: Optional[dict]) -> QualitySignal:
        """AI Governance'dan uyum sinyali"""
        if not governance_data or not isinstance(governance_data, dict):
            return QualitySignal(
                name="governance",
                source_module="governance",
                raw_value=70.0,
                weight=SIGNAL_WEIGHTS["governance"],
                reliability=SignalReliability.UNAVAILABLE,
                description="Governance verisi mevcut değil",
            )

        compliance = governance_data.get("compliance_score", 0.7)
        bias_score = governance_data.get("bias_score", 0)
        drift = governance_data.get("drift_detected", False)
        alert = governance_data.get("alert_triggered", False)

        # Compliance zaten 0-1 arası
        score = compliance * 100

        # Bias cezası
        if bias_score > 0.3:
            score -= bias_score * 20

        # Drift cezası
        if drift:
            score -= 15

        # Alert cezası
        if alert:
            score -= 10

        score = max(0, min(100, score))

        return QualitySignal(
            name="governance",
            source_module="governance",
            raw_value=score,
            weight=SIGNAL_WEIGHTS["governance"],
            reliability=SignalReliability.STRONG,
            description=f"Uyum: %{compliance*100:.0f}, Bias: {bias_score:.2f}, Drift: {'Var' if drift else 'Yok'}",
            details={"compliance": compliance, "bias": bias_score, "drift": drift, "alert": alert},
        )

    @staticmethod
    def from_debate(debate_data: Optional[dict]) -> QualitySignal:
        """Multi-Agent Debate'den konsensüs sinyali"""
        if not debate_data or not isinstance(debate_data, dict):
            return QualitySignal(
                name="consensus",
                source_module="multi_agent_debate",
                raw_value=60.0,
                weight=SIGNAL_WEIGHTS["consensus"],
                reliability=SignalReliability.UNAVAILABLE,
                description="Tartışma verisi mevcut değil",
            )

        consensus_score = debate_data.get("consensus_score", 0.5)
        agreement_ratio = debate_data.get("agreement_ratio", 0.5)
        perspectives = debate_data.get("perspectives_count", 0)

        score = max(0, min(100, consensus_score * 50 + agreement_ratio * 50))

        return QualitySignal(
            name="consensus",
            source_module="multi_agent_debate",
            raw_value=score,
            weight=SIGNAL_WEIGHTS["consensus"],
            reliability=SignalReliability.STRONG if perspectives >= 3 else SignalReliability.MODERATE,
            description=f"Konsensüs: {consensus_score:.2f}, Uzlaşma: %{agreement_ratio*100:.0f}, Perspektif: {perspectives}",
            details={"consensus": consensus_score, "agreement": agreement_ratio, "perspectives": perspectives},
        )

    @staticmethod
    def from_causal(causal_data: Optional[dict]) -> QualitySignal:
        """Causal Inference'dan kanıt gücü sinyali"""
        if not causal_data or not isinstance(causal_data, dict):
            return QualitySignal(
                name="evidence_strength",
                source_module="causal_inference",
                raw_value=50.0,
                weight=SIGNAL_WEIGHTS["evidence_strength"],
                reliability=SignalReliability.UNAVAILABLE,
                description="Nedensel analiz verisi mevcut değil",
            )

        root_causes = causal_data.get("root_causes_found", 0)
        evidence_score = causal_data.get("evidence_score", 0.5)
        confidence = causal_data.get("confidence", 0.5)

        score = max(0, min(100, evidence_score * 50 + confidence * 30 + min(root_causes * 5, 20)))

        return QualitySignal(
            name="evidence_strength",
            source_module="causal_inference",
            raw_value=score,
            weight=SIGNAL_WEIGHTS["evidence_strength"],
            reliability=SignalReliability.STRONG if root_causes > 0 else SignalReliability.WEAK,
            description=f"Kanıt: {evidence_score:.2f}, Güven: {confidence:.2f}, Kök neden: {root_causes}",
            details={"evidence": evidence_score, "confidence": confidence, "root_causes": root_causes},
        )


# ─── Quality Scorer ────────────────────────────────────────────────

class QualityScorer:
    """Sinyalleri birleştirip nihai kalite skoru üretir"""

    @staticmethod
    def _get_band(score: float) -> QualityBand:
        if score >= 90:
            return QualityBand.EXCEPTIONAL
        elif score >= 75:
            return QualityBand.HIGH
        elif score >= 55:
            return QualityBand.MODERATE
        elif score >= 35:
            return QualityBand.LOW
        return QualityBand.INSUFFICIENT

    @staticmethod
    def _confidence_interval(signals: List[QualitySignal], overall: float) -> Tuple[float, float]:
        """Sinyallerin dağılımına göre güven aralığı"""
        if not signals:
            return (max(0, overall - 15), min(100, overall + 15))

        values = [s.raw_value for s in signals if s.reliability != SignalReliability.UNAVAILABLE]
        if len(values) < 2:
            return (max(0, overall - 12), min(100, overall + 12))

        mean = sum(values) / len(values)
        variance = sum((v - mean) ** 2 for v in values) / len(values)
        std = math.sqrt(variance)

        # Kaynağı eksik sinyaller aralığı genişletir
        unavailable_count = sum(1 for s in signals if s.reliability == SignalReliability.UNAVAILABLE)
        expansion = unavailable_count * 2.5

        margin = min(20, std * 0.8 + expansion)
        return (max(0, overall - margin), min(100, overall + margin))

    @staticmethod
    def _recommendation(band: QualityBand, breakdown: QualityBreakdown) -> str:
        """Türkçe güven tavsiyesi"""
        recs = {
            QualityBand.EXCEPTIONAL: "Bu öneri çok yüksek güvenilirlikle sunulmaktadır. Veri, analiz ve risk değerlendirmesi güçlüdür.",
            QualityBand.HIGH: "Bu öneri yüksek güvenilirlikle sunulmaktadır. Birkaç küçük belirsizlik noktası mevcut olsa da genel değerlendirme sağlamdır.",
            QualityBand.MODERATE: "Bu öneriye orta düzeyde güvenle yaklaşılmalıdır. Bazı veri eksiklikleri veya belirsizlikler mevcuttur.",
            QualityBand.LOW: "Bu öneriye dikkatle yaklaşılmalıdır. Veri güvenilirliği düşük veya risk seviyesi yüksektir. Ek doğrulama önerilir.",
            QualityBand.INSUFFICIENT: "Bu öneri yetersiz veri veya yüksek belirsizlik nedeniyle düşük güvenilirlikle sunulmaktadır. Karar vermeden önce ek analiz yapılması şiddetle tavsiye edilir.",
        }

        base = recs[band]

        # Spesifik uyarılar
        warnings = []
        if breakdown.risk_level > 70:
            warnings.append("⚠️ Risk seviyesi yüksek")
        if breakdown.uncertainty_level < 40:
            warnings.append("⚠️ Belirsizlik seviyesi yüksek")
        if breakdown.data_reliability < 50:
            warnings.append("⚠️ Veri güvenilirliği düşük")
        if breakdown.historical_success < 40:
            warnings.append("⚠️ Benzer önerilerde tarihsel başarı düşük")

        if warnings:
            base += "\n" + " | ".join(warnings)

        return base

    @staticmethod
    def _executive_line(score: float, band: QualityBand) -> str:
        """Tek satır yönetici özeti"""
        band_emoji = {
            QualityBand.EXCEPTIONAL: "🟢",
            QualityBand.HIGH: "🟢",
            QualityBand.MODERATE: "🟡",
            QualityBand.LOW: "🟠",
            QualityBand.INSUFFICIENT: "🔴",
        }
        emoji = band_emoji[band]
        label = BAND_LABELS_TR[band]
        return f"{emoji} Öneri Kalite Skoru: {score:.0f}/100 — {label}"

    def score(self, signals: List[QualitySignal]) -> QualityResult:
        """Tüm sinyallerden nihai skor üret"""
        if not signals:
            bd = QualityBreakdown()
            band = QualityBand.INSUFFICIENT
            return QualityResult(
                overall_score=0,
                band=band,
                band_label_tr=BAND_LABELS_TR[band],
                confidence_interval=(0, 30),
                breakdown=bd,
                signals=[],
                signal_coverage=0,
                recommendation_tr=self._recommendation(band, bd),
                executive_line=self._executive_line(0, band),
            )

        # Ağırlıklı ortalama
        total_weight = sum(s.weight for s in signals)
        if total_weight == 0:
            total_weight = 1

        weighted_sum = sum(s.raw_value * s.weight for s in signals)
        overall = weighted_sum / total_weight

        # Signal coverage — kaç sinyal "gerçek" veri içeriyor
        active_signals = sum(1 for s in signals if s.reliability != SignalReliability.UNAVAILABLE)
        coverage = active_signals / len(signals) if signals else 0

        # Düşük coverage cezası
        if coverage < 0.5:
            overall *= 0.85 + coverage * 0.3  # %50'den az sinyal → skor düşer

        overall = max(0, min(100, overall))

        # Breakdown
        signal_map = {s.name: s.raw_value for s in signals}
        breakdown = QualityBreakdown(
            data_reliability=signal_map.get("data_reliability", 0),
            uncertainty_level=signal_map.get("uncertainty", 0),
            risk_level=signal_map.get("risk", 0),
            historical_success=signal_map.get("historical_success", 0),
            governance_compliance=signal_map.get("governance", 0),
            reasoning_depth=signal_map.get("reflection_quality", 0),
            consensus_degree=signal_map.get("consensus", 0),
            evidence_strength=signal_map.get("evidence_strength", 0),
        )

        band = self._get_band(overall)
        ci = self._confidence_interval(signals, overall)

        return QualityResult(
            overall_score=overall,
            band=band,
            band_label_tr=BAND_LABELS_TR[band],
            confidence_interval=ci,
            breakdown=breakdown,
            signals=signals,
            signal_coverage=coverage,
            recommendation_tr=self._recommendation(band, breakdown),
            executive_line=self._executive_line(overall, band),
        )


# ─── Tracker ────────────────────────────────────────────────────────

class QualityTracker:
    """Kalite skoru geçmişini takip eder"""

    MAX_HISTORY = 500

    def __init__(self):
        self._history: List[dict] = []
        self._band_counts: Dict[str, int] = {b.value: 0 for b in QualityBand}
        self._total = 0
        self._score_sum = 0.0

    def record(self, result: QualityResult, question: str = "", department: str = ""):
        entry = {
            "score": result.overall_score,
            "band": result.band.value,
            "coverage": result.signal_coverage,
            "question_preview": question[:80] if question else "",
            "department": department,
            "timestamp": result.timestamp,
        }
        self._history.append(entry)
        if len(self._history) > self.MAX_HISTORY:
            self._history = self._history[-self.MAX_HISTORY:]

        self._band_counts[result.band.value] = self._band_counts.get(result.band.value, 0) + 1
        self._total += 1
        self._score_sum += result.overall_score

    def get_stats(self) -> dict:
        avg = self._score_sum / self._total if self._total else 0
        recent = self._history[-20:] if self._history else []
        recent_avg = sum(r["score"] for r in recent) / len(recent) if recent else 0

        # Trend
        if len(recent) >= 5:
            first_half = recent[:len(recent)//2]
            second_half = recent[len(recent)//2:]
            first_avg = sum(r["score"] for r in first_half) / len(first_half)
            second_avg = sum(r["score"] for r in second_half) / len(second_half)
            trend = "improving" if second_avg > first_avg + 2 else ("declining" if second_avg < first_avg - 2 else "stable")
        else:
            trend = "insufficient_data"

        return {
            "total_evaluations": self._total,
            "average_score": round(avg, 1),
            "recent_average": round(recent_avg, 1),
            "trend": trend,
            "band_distribution": dict(self._band_counts),
        }

    def get_dashboard(self) -> dict:
        stats = self.get_stats()
        return {
            **stats,
            "recent_history": self._history[-10:],
        }


# ─── Main Orchestrator ─────────────────────────────────────────────

_scorer = QualityScorer()
_tracker = QualityTracker()
_collector = SignalCollector()


def evaluate_decision_quality(
    reflection_data: Optional[dict] = None,
    uncertainty_data: Optional[dict] = None,
    gate_data: Optional[dict] = None,
    meta_data: Optional[dict] = None,
    governance_data: Optional[dict] = None,
    debate_data: Optional[dict] = None,
    causal_data: Optional[dict] = None,
    rag_used: bool = False,
    web_searched: bool = False,
    sources: Optional[list] = None,
    source_citation_valid: Optional[bool] = None,
    question: str = "",
    department: str = "",
) -> QualityResult:
    """
    Tüm pipeline çıktılarından bütünleşik karar kalite skoru üretir.

    Args:
        reflection_data: Reflection modülü çıktısı
        uncertainty_data: Uncertainty Quantification çıktısı
        gate_data: Decision Gatekeeper çıktısı
        meta_data: Meta Learning istatistikleri
        governance_data: Governance değerlendirmesi
        debate_data: Multi-Agent Debate sonucu
        causal_data: Causal Inference sonucu
        rag_used: RAG kullanıldı mı
        web_searched: Web araması yapıldı mı
        sources: Kaynak listesi
        source_citation_valid: Kaynak doğrulaması sonucu
        question: Orijinal soru
        department: Departman

    Returns:
        QualityResult: Bütünleşik kalite skoru ve açıklaması
    """
    signals = [
        _collector.from_reflection(reflection_data),
        _collector.from_uncertainty(uncertainty_data),
        _collector.from_risk(gate_data),
        _collector.from_meta_learning(meta_data),
        _collector.from_data_sources(rag_used, web_searched, sources, source_citation_valid),
        _collector.from_governance(governance_data),
        _collector.from_debate(debate_data),
        _collector.from_causal(causal_data),
    ]

    result = _scorer.score(signals)
    _tracker.record(result, question, department)

    return result


# ─── Formatters ─────────────────────────────────────────────────────

def format_quality_score(result: QualityResult) -> str:
    """Kalite skorunu Markdown formatında göster"""
    lines = [
        f"\n### 📊 Karar Kalite Değerlendirmesi",
        f"",
        result.executive_line,
        f"",
        f"| Boyut | Puan |",
        f"|-------|------|",
        f"| Veri Güvenilirliği | {result.breakdown.data_reliability:.0f}/100 |",
        f"| Belirsizlik Kontrolü | {result.breakdown.uncertainty_level:.0f}/100 |",
        f"| Risk Değerlendirmesi | {result.breakdown.risk_level:.0f}/100 |",
        f"| Tarihsel Başarı | {result.breakdown.historical_success:.0f}/100 |",
        f"| Governance Uyumu | {result.breakdown.governance_compliance:.0f}/100 |",
        f"| Muhakeme Derinliği | {result.breakdown.reasoning_depth:.0f}/100 |",
        f"| Konsensüs Derecesi | {result.breakdown.consensus_degree:.0f}/100 |",
        f"| Kanıt Gücü | {result.breakdown.evidence_strength:.0f}/100 |",
        f"",
        f"**Güven Aralığı:** {result.confidence_interval[0]:.0f} — {result.confidence_interval[1]:.0f}",
        f"**Sinyal Kapsama:** %{result.signal_coverage*100:.0f}",
        f"",
        f"> {result.recommendation_tr}",
    ]
    return "\n".join(lines)


def format_quality_badge(result: QualityResult) -> str:
    """Kısa badge — yanıt altına eklenmek için"""
    return result.executive_line


# ─── Dashboard ──────────────────────────────────────────────────────

def get_dashboard() -> dict:
    base = {
        "module": "decision_quality",
        "module_name": "Karar Kalite Skoru",
        **_tracker.get_dashboard(),
    }
    # v5.5.0: Outcome & Regret istatistikleri
    base["outcome_tracking"] = _outcome_tracker.get_regret_stats()
    return base


def get_statistics() -> dict:
    return _tracker.get_stats()


# ═══════════════════════════════════════════════════════════════════
#  v5.5.0 Enterprise: Outcome Comparison & Regret Metric
# ═══════════════════════════════════════════════════════════════════

_OUTCOME_LOG = _OUTCOME_DIR / "outcome_log.jsonl"


class OutcomeTracker:
    """
    Tahmin vs gerçekleşen sonuç karşılaştırma.

    Akış:
      1. Decision yapılır → record_prediction(decision_id, predicted_outcome, confidence)
      2. Sonuç gerçekleşir → record_actual_outcome(decision_id, actual_outcome)
      3. Karşılaştırma → get_outcome_comparison(decision_id)
    """

    def __init__(self):
        self._predictions: Dict[str, dict] = {}  # decision_id → prediction
        self._outcomes: Dict[str, dict] = {}      # decision_id → actual
        self._regret_history: deque = deque(maxlen=500)
        self._accuracy_history: deque[float] = deque(maxlen=500)

    def record_prediction(
        self,
        decision_id: str,
        predicted_outcome: str,
        confidence: float,
        quality_score: float = 0.0,
        alternatives: Optional[List[Dict]] = None,
        context: Optional[Dict] = None,
    ):
        """Karar tahmini kaydet.

        Args:
            decision_id: Benzersiz karar kimliği.
            predicted_outcome: Tahmin edilen sonuç (metin).
            confidence: Tahmin güveni (0-100).
            quality_score: Karar kalite skoru.
            alternatives: Değerlendirilen alternatif seçenekler.
            context: Karar bağlamı.
        """
        self._predictions[decision_id] = {
            "decision_id": decision_id,
            "predicted_outcome": predicted_outcome,
            "confidence": confidence,
            "quality_score": quality_score,
            "alternatives": alternatives or [],
            "context": context or {},
            "timestamp": time.time(),
        }

    def record_actual_outcome(
        self,
        decision_id: str,
        actual_outcome: str,
        success: bool = True,
        impact_score: float = 0.0,
        feedback: str = "",
    ):
        """Gerçekleşen sonucu kaydet ve regret hesapla.

        Args:
            decision_id: Karar kimliği.
            actual_outcome: Gerçekleşen sonuç.
            success: Sonuç başarılı mı?
            impact_score: Etki puanı (0-100, opsiyonel).
            feedback: Kullanıcı geri bildirimi.
        """
        prediction = self._predictions.get(decision_id)
        if not prediction:
            # Tahmin kaydedilmemiş ama sonucu yine de kaydet
            prediction = {"confidence": 50, "quality_score": 50, "alternatives": []}

        self._outcomes[decision_id] = {
            "decision_id": decision_id,
            "actual_outcome": actual_outcome,
            "success": success,
            "impact_score": impact_score,
            "feedback": feedback,
            "timestamp": time.time(),
        }

        # Accuracy kaydı
        accuracy = 1.0 if success else 0.0
        self._accuracy_history.append(accuracy)

        # Regret hesaplama
        regret = self._calculate_regret(prediction, success, impact_score)
        self._regret_history.append(regret)

        # Diske yaz
        self._persist_outcome(decision_id, prediction, self._outcomes[decision_id], regret)

    def _calculate_regret(self, prediction: dict, success: bool, impact: float) -> dict:
        """
        Regret metriği hesapla.

        Regret = (1 - success) * confidence_at_decision * alternative_gap
        Yüksek güvenle yanlış karar → yüksek regret
        Düşük güvenle yanlış karar → düşük regret (beklenen)
        """
        confidence = prediction.get("confidence", 50) / 100
        alternatives = prediction.get("alternatives", [])

        if success:
            regret_score = 0.0
            regret_type = "none"
        else:
            # Temel regret: yanlış karar
            regret_score = confidence * 0.5

            # Alternatif varsa: en iyi alternatifle aradaki fark
            if alternatives:
                best_alt_score = max(
                    (a.get("expected_score", 50) for a in alternatives), default=50
                )
                alt_gap = max(0, best_alt_score - prediction.get("quality_score", 50)) / 100
                regret_score += alt_gap * 0.3

            # Etki puanı (yüksek etki = yüksek regret)
            if impact > 0:
                regret_score += (impact / 100) * 0.2

            regret_score = min(1.0, regret_score)

            if regret_score > 0.7:
                regret_type = "high"
            elif regret_score > 0.3:
                regret_type = "moderate"
            else:
                regret_type = "low"

        return {
            "regret_score": round(regret_score, 3),
            "regret_type": regret_type,
            "confidence_at_decision": confidence,
            "had_alternatives": len(alternatives) > 0,
            "timestamp": time.time(),
        }

    def _persist_outcome(self, decision_id: str, prediction: dict, outcome: dict, regret: dict):
        """Outcome log'a yaz."""
        entry = {
            "decision_id": decision_id,
            "prediction": {
                "outcome": prediction.get("predicted_outcome", ""),
                "confidence": prediction.get("confidence", 0),
                "quality_score": prediction.get("quality_score", 0),
            },
            "actual": {
                "outcome": outcome.get("actual_outcome", ""),
                "success": outcome.get("success", False),
                "impact_score": outcome.get("impact_score", 0),
            },
            "regret": regret,
            "timestamp": time.time(),
        }
        try:
            with open(_OUTCOME_LOG, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.error("outcome_persist_failed", error=str(e))

    def get_outcome_comparison(self, decision_id: str) -> Optional[dict]:
        """Tahmin vs gerçek sonuç karşılaştırması."""
        prediction = self._predictions.get(decision_id)
        outcome = self._outcomes.get(decision_id)

        if not prediction or not outcome:
            return None

        return {
            "decision_id": decision_id,
            "predicted": prediction.get("predicted_outcome", ""),
            "actual": outcome.get("actual_outcome", ""),
            "confidence_at_prediction": prediction.get("confidence", 0),
            "success": outcome.get("success", False),
            "impact_score": outcome.get("impact_score", 0),
            "feedback": outcome.get("feedback", ""),
        }

    def get_regret_stats(self) -> dict:
        """Regret istatistikleri."""
        regrets = list(self._regret_history)
        if not regrets:
            return {"total_decisions": 0, "avg_regret": 0, "trend": "insufficient_data"}

        scores = [r["regret_score"] for r in regrets]
        avg = sum(scores) / len(scores)

        # Yüksek regret sayısı
        high_regret = sum(1 for r in regrets if r["regret_type"] == "high")

        # Trend
        if len(scores) >= 10:
            first = scores[:len(scores)//2]
            second = scores[len(scores)//2:]
            f_avg = sum(first) / len(first)
            s_avg = sum(second) / len(second)
            trend = "improving" if s_avg < f_avg - 0.05 else ("worsening" if s_avg > f_avg + 0.05 else "stable")
        else:
            trend = "insufficient_data"

        # Accuracy
        acc_list = list(self._accuracy_history)
        accuracy = sum(acc_list) / len(acc_list) * 100 if acc_list else 0

        return {
            "total_decisions": len(regrets),
            "avg_regret": round(avg, 3),
            "high_regret_count": high_regret,
            "overall_accuracy_pct": round(accuracy, 1),
            "trend": trend,
        }

    def get_counterfactual_analysis(self, decision_id: str) -> Optional[dict]:
        """Counterfactual — 'alternatif seçseydik ne olurdu?' analizi.

        Tahmin edilen alternatiflerin beklenen skorları ile
        gerçekleşen sonucun karşılaştırılması.
        """
        prediction = self._predictions.get(decision_id)
        outcome = self._outcomes.get(decision_id)

        if not prediction:
            return None

        alternatives = prediction.get("alternatives", [])
        actual_success = outcome.get("success", False) if outcome else None
        actual_impact = outcome.get("impact_score", 0) if outcome else 0

        counterfactuals = []
        for alt in alternatives:
            cf = {
                "alternative": alt.get("label", "Bilinmeyen"),
                "expected_score": alt.get("expected_score", 50),
                "would_have_been_better": not actual_success and alt.get("expected_score", 50) > prediction.get("quality_score", 50),
                "score_gap": alt.get("expected_score", 50) - prediction.get("quality_score", 50),
            }
            counterfactuals.append(cf)

        best_alternative = max(counterfactuals, key=lambda x: x["expected_score"]) if counterfactuals else None

        return {
            "decision_id": decision_id,
            "chosen_confidence": prediction.get("confidence", 0),
            "chosen_quality": prediction.get("quality_score", 0),
            "actual_success": actual_success,
            "actual_impact": actual_impact,
            "alternative_count": len(counterfactuals),
            "counterfactuals": counterfactuals,
            "best_alternative": best_alternative,
            "regret_applicable": best_alternative is not None and best_alternative.get("would_have_been_better", False),
        }


# Singleton tracker instance
_outcome_tracker = OutcomeTracker()


def record_prediction(decision_id: str, predicted_outcome: str, confidence: float,
                      quality_score: float = 0.0, alternatives: Optional[List[Dict]] = None,
                      context: Optional[Dict] = None):
    """Karar tahminini kaydet (engine.py'den çağrılır)."""
    _outcome_tracker.record_prediction(
        decision_id, predicted_outcome, confidence, quality_score, alternatives, context
    )


def record_actual_outcome(decision_id: str, actual_outcome: str, success: bool = True,
                          impact_score: float = 0.0, feedback: str = ""):
    """Gerçekleşen sonucu kaydet (feedback endpoint'inden çağrılır)."""
    _outcome_tracker.record_actual_outcome(
        decision_id, actual_outcome, success, impact_score, feedback
    )


def get_outcome_comparison(decision_id: str) -> Optional[dict]:
    """Tahmin-sonuç karşılaştırması."""
    return _outcome_tracker.get_outcome_comparison(decision_id)


def get_regret_stats() -> dict:
    """Regret istatistikleri."""
    return _outcome_tracker.get_regret_stats()


def get_counterfactual(decision_id: str) -> Optional[dict]:
    """Counterfactual analizi."""
    return _outcome_tracker.get_counterfactual_analysis(decision_id)
