"""
Uncertainty Quantification v1.0 — Belirsizlik Ölçümleme Katmanı
CompanyAI v5.1.0

Mevcut modüllerin (reflection, monte_carlo, governance, meta_learning)
güven/belirsizlik çıkışlarını birleştirerek ensemble uncertainty skoru üretir.

Çıktı formatı: "Bu yanıtın %72 ± 8 doğru olduğunu tahmin ediyorum"

Bileşenler:
  1. ConfidenceAggregator  → Farklı kaynaklardan güven değerlerini topla
  2. UncertaintyEstimator  → Epistemic vs Aleatoric ayrımı
  3. EnsembleScorer        → Ağırlıklı ensemble skoru üret
  4. UncertaintyTracker    → İstatistik takibi
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
from collections import deque


# ═══════════════════════════════════════════════════════════════
# Enum & Veri Yapıları
# ═══════════════════════════════════════════════════════════════

class UncertaintyType(Enum):
    """Belirsizlik türü."""
    EPISTEMIC = "epistemic"      # Bilgi eksikliği (azaltılabilir)
    ALEATORIC = "aleatoric"      # Doğal rastgelelik (azaltılamaz)
    MIXED = "mixed"


class ConfidenceBand(Enum):
    """Güven bandı."""
    VERY_HIGH = "very_high"     # 90-100
    HIGH = "high"               # 75-89
    MODERATE = "moderate"       # 55-74
    LOW = "low"                 # 35-54
    VERY_LOW = "very_low"       # 0-34


@dataclass
class ConfidenceSource:
    """Tek bir güven kaynağı."""
    name: str
    value: float           # 0-100
    weight: float          # 0-1 arası ağırlık
    reliability: float     # Kaynağın güvenilirliği (0-1)


@dataclass
class UncertaintyResult:
    """Belirsizlik ölçüm sonucu."""
    ensemble_confidence: float     # 0-100: birleşik güven
    margin_of_error: float         # ± hata payı
    confidence_band: ConfidenceBand
    uncertainty_type: UncertaintyType
    sources: list[ConfidenceSource] = field(default_factory=list)
    epistemic_score: float = 0.0   # 0-1 (bilgi eksikliği)
    aleatoric_score: float = 0.0   # 0-1 (doğal belirsizlik)
    source_agreement: float = 0.0  # 0-1 (kaynaklar arası uyum)
    explanation: str = ""

    def to_dict(self) -> dict:
        return {
            "ensemble_confidence": round(self.ensemble_confidence, 1),
            "margin_of_error": round(self.margin_of_error, 1),
            "confidence_interval": {
                "lower": round(max(0, self.ensemble_confidence - self.margin_of_error), 1),
                "upper": round(min(100, self.ensemble_confidence + self.margin_of_error), 1),
            },
            "confidence_band": self.confidence_band.value,
            "uncertainty_type": self.uncertainty_type.value,
            "epistemic_score": round(self.epistemic_score, 3),
            "aleatoric_score": round(self.aleatoric_score, 3),
            "source_agreement": round(self.source_agreement, 3),
            "source_count": len(self.sources),
            "explanation": self.explanation,
        }

    def human_readable(self) -> str:
        """İnsan okunabilir format."""
        lower = max(0, self.ensemble_confidence - self.margin_of_error)
        upper = min(100, self.ensemble_confidence + self.margin_of_error)
        return (
            f"Bu yanıtın %{self.ensemble_confidence:.0f} ± {self.margin_of_error:.0f} "
            f"doğru olduğunu tahmin ediyorum (aralık: %{lower:.0f}–%{upper:.0f})"
        )


# ═══════════════════════════════════════════════════════════════
# 1. Confidence Aggregator — Kaynaklardan güven topla
# ═══════════════════════════════════════════════════════════════

class ConfidenceAggregator:
    """Farklı modüllerden güven değerlerini toplar."""

    # Kaynak ağırlık ve güvenilirlik tablosu
    SOURCE_PROFILES = {
        "reflection": {"weight": 0.30, "reliability": 0.85},
        "engine_confidence": {"weight": 0.25, "reliability": 0.75},
        "governance_compliance": {"weight": 0.20, "reliability": 0.80},
        "monte_carlo": {"weight": 0.15, "reliability": 0.90},
        "meta_learning_trend": {"weight": 0.10, "reliability": 0.70},
    }

    def collect(
        self,
        reflection_data: dict | None = None,
        engine_confidence: float | None = None,
        governance_data: dict | None = None,
        mc_data: dict | None = None,
        meta_data: dict | None = None,
    ) -> list[ConfidenceSource]:
        """Tüm kaynaklardan ConfidenceSource listesi topla."""
        sources = []

        # 1. Reflection skoru
        if reflection_data:
            score = reflection_data.get("score")
            if score is not None:
                profile = self.SOURCE_PROFILES["reflection"]
                sources.append(ConfidenceSource(
                    name="reflection",
                    value=float(score),
                    weight=profile["weight"],
                    reliability=profile["reliability"],
                ))

        # 2. Engine confidence
        if engine_confidence is not None:
            conf = float(engine_confidence)
            if conf <= 1.0:
                conf *= 100
            profile = self.SOURCE_PROFILES["engine_confidence"]
            sources.append(ConfidenceSource(
                name="engine_confidence",
                value=conf,
                weight=profile["weight"],
                reliability=profile["reliability"],
            ))

        # 3. Governance compliance
        if governance_data:
            compliance = governance_data.get("compliance_score")
            if compliance is not None:
                profile = self.SOURCE_PROFILES["governance_compliance"]
                sources.append(ConfidenceSource(
                    name="governance_compliance",
                    value=float(compliance),
                    weight=profile["weight"],
                    reliability=profile["reliability"],
                ))

        # 4. Monte Carlo (1 - failure_probability) × 100
        if mc_data:
            fp = mc_data.get("failure_probability")
            if fp is not None:
                mc_confidence = (1.0 - float(fp)) * 100
                profile = self.SOURCE_PROFILES["monte_carlo"]
                sources.append(ConfidenceSource(
                    name="monte_carlo",
                    value=mc_confidence,
                    weight=profile["weight"],
                    reliability=profile["reliability"],
                ))

        # 5. Meta learning quality trend
        if meta_data:
            quality = meta_data.get("average_quality") or meta_data.get("quality_score")
            if quality is not None:
                profile = self.SOURCE_PROFILES["meta_learning_trend"]
                sources.append(ConfidenceSource(
                    name="meta_learning_trend",
                    value=float(quality),
                    weight=profile["weight"],
                    reliability=profile["reliability"],
                ))

        return sources


# ═══════════════════════════════════════════════════════════════
# 2. Uncertainty Estimator — Epistemic vs Aleatoric
# ═══════════════════════════════════════════════════════════════

class UncertaintyEstimator:
    """Belirsizlik türünü ve seviyesini tahmin eder."""

    def estimate(self, sources: list[ConfidenceSource]) -> tuple[float, float, UncertaintyType]:
        """
        Epistemic ve aleatoric belirsizlik tahmini.

        Epistemic (bilgi eksikliği):
          - Kaynak azlığı → epistemic yüksek
          - Kaynaklar arası büyük fark → epistemic yüksek

        Aleatoric (doğal belirsizlik):
          - Monte carlo volatilite yüksek → aleatoric yüksek
          - Tüm kaynaklar düşük güven → aleatoric yüksek
        """
        if not sources:
            return 0.5, 0.5, UncertaintyType.MIXED

        values = [s.value for s in sources]
        n = len(values)

        # Epistemic: kaynak azlığı + çeşitlilik
        source_scarcity = max(0, (5 - n) / 5)  # 5 kaynak ideal
        if n >= 2:
            variance = sum((v - sum(values) / n) ** 2 for v in values) / n
            std_dev = math.sqrt(variance)
            disagreement = min(1.0, std_dev / 30)  # 30 puan std_dev = tam anlaşmazlık
        else:
            disagreement = 0.3  # Tek kaynak — belirsiz

        epistemic = (source_scarcity * 0.5 + disagreement * 0.5)

        # Aleatoric: doğal düşük güven
        avg_confidence = sum(values) / n
        inherent_uncertainty = max(0, (50 - avg_confidence) / 50) if avg_confidence < 50 else 0
        aleatoric = min(1.0, inherent_uncertainty)

        # Monte carlo varsa volatilitesini aleatoric'e ekle
        mc_source = next((s for s in sources if s.name == "monte_carlo"), None)
        if mc_source and mc_source.value < 70:
            aleatoric = min(1.0, aleatoric + 0.15)

        # Tip belirleme
        if epistemic > aleatoric * 1.5:
            u_type = UncertaintyType.EPISTEMIC
        elif aleatoric > epistemic * 1.5:
            u_type = UncertaintyType.ALEATORIC
        else:
            u_type = UncertaintyType.MIXED

        return round(epistemic, 3), round(aleatoric, 3), u_type


# ═══════════════════════════════════════════════════════════════
# 3. Ensemble Scorer — Birleşik skor üretimi
# ═══════════════════════════════════════════════════════════════

class EnsembleScorer:
    """Ağırlıklı ensemble güven skoru ve hata payı üretir."""

    def score(self, sources: list[ConfidenceSource]) -> tuple[float, float, float]:
        """
        Returns:
            (ensemble_confidence, margin_of_error, source_agreement)
        """
        if not sources:
            return 50.0, 25.0, 0.0

        # Ağırlıklı ortalama
        total_weight = sum(s.weight * s.reliability for s in sources)
        if total_weight == 0:
            return 50.0, 25.0, 0.0

        weighted_sum = sum(s.value * s.weight * s.reliability for s in sources)
        ensemble = weighted_sum / total_weight

        # Hata payı: kaynaklar arası std_dev
        values = [s.value for s in sources]
        n = len(values)
        if n >= 2:
            mean = sum(values) / n
            variance = sum((v - mean) ** 2 for v in values) / n
            std_dev = math.sqrt(variance)
            # Hata payı = std_dev, min 3, max 25
            margin = max(3.0, min(25.0, std_dev))
        else:
            # Tek kaynak → yüksek belirsizlik
            margin = 15.0

        # Source agreement: 1 - normalized_std_dev
        if n >= 2:
            agreement = max(0, 1.0 - (std_dev / 40))  # 40 puan fark = sıfır uyum
        else:
            agreement = 0.5  # Tek kaynak, nötr

        return round(ensemble, 1), round(margin, 1), round(agreement, 3)

    def get_band(self, confidence: float) -> ConfidenceBand:
        """Güven bandını belirle."""
        if confidence >= 90:
            return ConfidenceBand.VERY_HIGH
        elif confidence >= 75:
            return ConfidenceBand.HIGH
        elif confidence >= 55:
            return ConfidenceBand.MODERATE
        elif confidence >= 35:
            return ConfidenceBand.LOW
        else:
            return ConfidenceBand.VERY_LOW


# ═══════════════════════════════════════════════════════════════
# 4. Uncertainty Tracker
# ═══════════════════════════════════════════════════════════════

class UncertaintyTracker:
    """Belirsizlik ölçüm geçmişi ve istatistikleri."""

    def __init__(self, max_history: int = 500):
        self.history: deque[dict] = deque(maxlen=max_history)
        self.total: int = 0
        self.confidence_sum: float = 0.0
        self.margin_sum: float = 0.0
        self.band_counts: dict[str, int] = {}

    def record(self, result: UncertaintyResult, question: str):
        self.total += 1
        self.confidence_sum += result.ensemble_confidence
        self.margin_sum += result.margin_of_error
        band = result.confidence_band.value
        self.band_counts[band] = self.band_counts.get(band, 0) + 1

        self.history.append({
            "timestamp": time.time(),
            "confidence": round(result.ensemble_confidence, 1),
            "margin": round(result.margin_of_error, 1),
            "band": band,
            "type": result.uncertainty_type.value,
            "source_count": len(result.sources),
            "question_preview": question[:80],
        })

    def get_statistics(self) -> dict:
        avg_conf = (self.confidence_sum / self.total) if self.total > 0 else 0
        avg_margin = (self.margin_sum / self.total) if self.total > 0 else 0
        return {
            "total_measurements": self.total,
            "average_confidence": round(avg_conf, 1),
            "average_margin_of_error": round(avg_margin, 1),
            "band_distribution": dict(self.band_counts),
        }

    def get_recent(self, limit: int = 20) -> list[dict]:
        return list(self.history)[-limit:]


# ═══════════════════════════════════════════════════════════════
# Ana Orkestratör
# ═══════════════════════════════════════════════════════════════

class UncertaintyQuantifier:
    """
    Belirsizlik ölçümleme orkestratörü.
    Mevcut modüllerin güven çıkışlarını birleştirerek
    ensemble uncertainty skoru üretir.
    """

    def __init__(self):
        self.enabled: bool = True
        self.aggregator = ConfidenceAggregator()
        self.estimator = UncertaintyEstimator()
        self.scorer = EnsembleScorer()
        self.tracker = UncertaintyTracker()

    def quantify(
        self,
        question: str,
        reflection_data: dict | None = None,
        engine_confidence: float | None = None,
        governance_data: dict | None = None,
        mc_data: dict | None = None,
        meta_data: dict | None = None,
    ) -> UncertaintyResult:
        """Ana belirsizlik ölçümü."""
        if not self.enabled:
            return UncertaintyResult(
                ensemble_confidence=85.0,
                margin_of_error=5.0,
                confidence_band=ConfidenceBand.HIGH,
                uncertainty_type=UncertaintyType.MIXED,
                explanation="Uncertainty quantification devre dışı.",
            )

        # 1. Kaynakları topla
        sources = self.aggregator.collect(
            reflection_data=reflection_data,
            engine_confidence=engine_confidence,
            governance_data=governance_data,
            mc_data=mc_data,
            meta_data=meta_data,
        )

        # 2. Ensemble skor
        ensemble_conf, margin, agreement = self.scorer.score(sources)
        band = self.scorer.get_band(ensemble_conf)

        # 3. Epistemic / Aleatoric
        epistemic, aleatoric, u_type = self.estimator.estimate(sources)

        # 4. Açıklama üret
        explanation = self._build_explanation(ensemble_conf, margin, band, u_type, epistemic, aleatoric, len(sources))

        result = UncertaintyResult(
            ensemble_confidence=ensemble_conf,
            margin_of_error=margin,
            confidence_band=band,
            uncertainty_type=u_type,
            sources=sources,
            epistemic_score=epistemic,
            aleatoric_score=aleatoric,
            source_agreement=agreement,
            explanation=explanation,
        )

        # 5. Kaydet
        self.tracker.record(result, question)

        return result

    def _build_explanation(
        self, conf: float, margin: float, band: ConfidenceBand,
        u_type: UncertaintyType, epistemic: float, aleatoric: float,
        source_count: int,
    ) -> str:
        """İnsan okunabilir açıklama üret."""
        parts = []

        # Band açıklaması
        band_labels = {
            ConfidenceBand.VERY_HIGH: "Çok yüksek güvenle",
            ConfidenceBand.HIGH: "Yüksek güvenle",
            ConfidenceBand.MODERATE: "Orta düzey güvenle",
            ConfidenceBand.LOW: "Düşük güvenle",
            ConfidenceBand.VERY_LOW: "Çok düşük güvenle",
        }
        parts.append(f"{band_labels.get(band, 'Orta güvenle')} yanıt verildi.")

        # Belirsizlik türü
        if u_type == UncertaintyType.EPISTEMIC:
            parts.append("Belirsizlik bilgi eksikliğinden kaynaklanıyor — daha fazla veri ile azaltılabilir.")
        elif u_type == UncertaintyType.ALEATORIC:
            parts.append("Belirsizlik konunun doğasından kaynaklanıyor — ek veri ile azaltılamaz.")
        else:
            parts.append("Hem bilgi eksikliği hem doğal belirsizlik mevcut.")

        # Kaynak sayısı
        if source_count < 3:
            parts.append(f"Yalnızca {source_count} güven kaynağı kullanıldı — daha fazla sinyal güvenilirliği artırır.")

        return " ".join(parts)

    def set_enabled(self, enabled: bool) -> dict:
        self.enabled = enabled
        return {"enabled": self.enabled}

    def reset(self):
        self.tracker = UncertaintyTracker()


# ═══════════════════════════════════════════════════════════════
# Singleton & Convenience
# ═══════════════════════════════════════════════════════════════

uncertainty_quantifier = UncertaintyQuantifier()


def check_uncertainty_trigger(
    question: str = "",
    mode: str = "",
    intent: str = "",
    **kwargs,
) -> tuple[bool, str]:
    """Her sorgu için otomatik tetiklenir — belirsizlik her yanıtta ölçülür."""
    if not uncertainty_quantifier.enabled:
        return False, "disabled"
    # Her sorguda çalışır (thin layer)
    return True, "always_on"


def get_uncertainty_dashboard() -> dict:
    """Dashboard verisi."""
    stats = uncertainty_quantifier.tracker.get_statistics()
    return {
        "available": True,
        "enabled": uncertainty_quantifier.enabled,
        "statistics": stats,
    }
