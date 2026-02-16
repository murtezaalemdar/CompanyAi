"""
CompanyAI — Observability 2.0
================================
Enterprise-grade observability katmanı.

MEVCUT monitoring.py'DEN FARKI:
  monitoring.py → "Çalışıyor mu?" (CPU, RAM, uptime, error rate)
  observability.py → "Kalitesi düşüyor mu?" (drift, latency, confidence, regret)

SORUMLULUKLAR:
  ┌──────────────────────────────────────────────────────────────────┐
  │ Katman                    │ İşlev                                │
  ├───────────────────────────┼────────────────────────────────────────┤
  │ DecisionDriftTracker      │ Karar dağılımı kayması algılama      │
  │ ConceptDriftDetector      │ Model/veri kavram kayması             │
  │ LatencyProfiler           │ End-to-end latency profiling          │
  │ ConfidenceHistogram       │ Güven dağılımı izleme                 │
  │ QualityTrendMonitor       │ Kalite trend analizi                  │
  │ AuditReplaySystem         │ Geçmiş kararları replay               │
  └───────────────────────────┴────────────────────────────────────────┘

KULLANIM:
  from app.core.observability import observability

  # Her karar sonrası kaydet
  observability.record_decision(
      confidence=0.85,
      latency_ms=1200,
      quality_score=78,
      intent="risk_analizi",
      risk_score=0.4,
  )

  # Drift kontrolü
  drift_status = observability.check_all_drifts()

  # Dashboard
  dashboard = observability.get_dashboard()
"""

import json
import math
import time
from collections import Counter, defaultdict, deque
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional

import structlog

logger = structlog.get_logger()

DATA_DIR = Path("data/observability")
DATA_DIR.mkdir(parents=True, exist_ok=True)

OBSERVABILITY_FILE = DATA_DIR / "observability_state.json"


# ═══════════════════════════════════════════════════════════════════
#  Sabitler
# ═══════════════════════════════════════════════════════════════════

WINDOW_SIZE = 200            # Sliding window boyutu
DRIFT_THRESHOLD = 2.0        # Z-score drift eşiği
TREND_MIN_SAMPLES = 20       # Trend analizi için minimum örnek
HISTOGRAM_BINS = 10          # Confidence histogram bin sayısı
LATENCY_PERCENTILES = [50, 75, 90, 95, 99]  # Percentile listesi


class DriftType(Enum):
    """Drift türleri."""
    DECISION = "decision"           # Karar dağılımı kayması
    CONCEPT = "concept"             # Kavram kayması
    CONFIDENCE = "confidence"       # Güven kayması
    LATENCY = "latency"             # Gecikme kayması
    QUALITY = "quality"             # Kalite kayması


class DriftSeverity(Enum):
    """Drift şiddeti."""
    NONE = "none"
    MILD = "mild"                   # Z-score 1.5-2.0
    MODERATE = "moderate"           # Z-score 2.0-3.0
    SEVERE = "severe"               # Z-score 3.0+


# ═══════════════════════════════════════════════════════════════════
#  Veri Yapıları
# ═══════════════════════════════════════════════════════════════════

@dataclass
class DriftAlert:
    """Drift algılama uyarısı."""
    drift_type: str
    severity: str
    current_value: float
    baseline_value: float
    z_score: float
    description: str
    detected_at: str
    recommendation: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class LatencyProfile:
    """Latency profil sonucu."""
    p50: float = 0.0
    p75: float = 0.0
    p90: float = 0.0
    p95: float = 0.0
    p99: float = 0.0
    mean: float = 0.0
    min_ms: float = 0.0
    max_ms: float = 0.0
    count: int = 0
    by_intent: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ConfidenceProfile:
    """Confidence histogram profili."""
    histogram: dict = field(default_factory=dict)    # bin → count
    mean: float = 0.0
    std: float = 0.0
    median: float = 0.0
    below_50_pct: float = 0.0                       # %50 altı oran
    count: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


# ═══════════════════════════════════════════════════════════════════
#  İstatistik Yardımcıları
# ═══════════════════════════════════════════════════════════════════

def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _std(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    m = _mean(values)
    return math.sqrt(sum((x - m) ** 2 for x in values) / (len(values) - 1))


def _percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    sorted_v = sorted(values)
    k = (len(sorted_v) - 1) * (p / 100)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return sorted_v[int(k)]
    return sorted_v[f] * (c - k) + sorted_v[c] * (k - f)


def _z_score(current: float, baseline_mean: float, baseline_std: float) -> float:
    if baseline_std < 1e-9:
        return 0.0
    return abs(current - baseline_mean) / baseline_std


# ═══════════════════════════════════════════════════════════════════
#  Decision Drift Tracker
# ═══════════════════════════════════════════════════════════════════

class DecisionDriftTracker:
    """
    Karar dağılımı kayma algılama.
    Kararların intent dağılımı, risk dağılımı, sonuç dağılımının
    zaman içinde kayıp kaymadığını izler.
    """

    def __init__(self, window: int = WINDOW_SIZE):
        self._window = window
        self._intent_history: deque = deque(maxlen=window * 2)
        self._risk_history: deque[float] = deque(maxlen=window * 2)
        self._outcome_history: deque = deque(maxlen=window * 2)

    def record(self, intent: str, risk_score: float, outcome: str = ""):
        self._intent_history.append(intent)
        self._risk_history.append(risk_score)
        if outcome:
            self._outcome_history.append(outcome)

    def check_drift(self) -> Optional[DriftAlert]:
        """İki yarım (baseline vs recent) karşılaştırma ile drift algıla."""
        n = len(self._risk_history)
        if n < self._window:
            return None

        mid = n // 2
        baseline = list(self._risk_history)[:mid]
        recent = list(self._risk_history)[mid:]

        base_mean = _mean(baseline)
        base_std = _std(baseline)
        recent_mean = _mean(recent)

        z = _z_score(recent_mean, base_mean, base_std)

        if z < 1.5:
            return None

        severity = (
            DriftSeverity.SEVERE if z >= 3.0
            else DriftSeverity.MODERATE if z >= 2.0
            else DriftSeverity.MILD
        )

        return DriftAlert(
            drift_type=DriftType.DECISION.value,
            severity=severity.value,
            current_value=round(recent_mean, 3),
            baseline_value=round(base_mean, 3),
            z_score=round(z, 2),
            description=f"Karar risk dağılımı kayması: baseline={base_mean:.3f} → current={recent_mean:.3f}",
            detected_at=datetime.now(timezone.utc).isoformat(),
            recommendation="Risk dağılımındaki değişimi inceleyin. Model veya veri kalitesi değişmiş olabilir.",
        )

    def get_intent_distribution(self) -> dict:
        """Intent dağılımı."""
        if not self._intent_history:
            return {}
        counter = Counter(self._intent_history)
        total = len(self._intent_history)
        return {k: round(v / total, 3) for k, v in counter.most_common(20)}


# ═══════════════════════════════════════════════════════════════════
#  Concept Drift Detector
# ═══════════════════════════════════════════════════════════════════

class ConceptDriftDetector:
    """
    Kavram kayması algılama.
    Model çıktılarının anlamsal tutarlılığını izler:
    - Yanıt uzunluğu drift'i
    - Confidence trend drift'i
    - Quality score drift'i
    """

    def __init__(self, window: int = WINDOW_SIZE):
        self._window = window
        self._response_lengths: deque[int] = deque(maxlen=window * 2)
        self._confidences: deque[float] = deque(maxlen=window * 2)
        self._quality_scores: deque[float] = deque(maxlen=window * 2)

    def record(self, response_length: int, confidence: float, quality_score: float):
        self._response_lengths.append(response_length)
        self._confidences.append(confidence)
        self._quality_scores.append(quality_score)

    def check_confidence_drift(self) -> Optional[DriftAlert]:
        """Confidence drift algıla."""
        return self._check_metric_drift(
            list(self._confidences),
            DriftType.CONFIDENCE,
            "Güven skoru",
        )

    def check_quality_drift(self) -> Optional[DriftAlert]:
        """Quality drift algıla."""
        return self._check_metric_drift(
            list(self._quality_scores),
            DriftType.QUALITY,
            "Kalite skoru",
        )

    def check_concept_drift(self) -> Optional[DriftAlert]:
        """Yanıt uzunluğu drift'i (concept proxy)."""
        return self._check_metric_drift(
            [float(x) for x in self._response_lengths],
            DriftType.CONCEPT,
            "Yanıt uzunluğu",
        )

    def _check_metric_drift(
        self, values: list[float], drift_type: DriftType, label: str,
    ) -> Optional[DriftAlert]:
        n = len(values)
        if n < self._window:
            return None

        mid = n // 2
        baseline = values[:mid]
        recent = values[mid:]

        base_mean = _mean(baseline)
        base_std = _std(baseline)
        recent_mean = _mean(recent)

        z = _z_score(recent_mean, base_mean, base_std)

        if z < DRIFT_THRESHOLD:
            return None

        severity = (
            DriftSeverity.SEVERE if z >= 3.0
            else DriftSeverity.MODERATE if z >= 2.0
            else DriftSeverity.MILD
        )

        direction = "düşüş" if recent_mean < base_mean else "artış"

        return DriftAlert(
            drift_type=drift_type.value,
            severity=severity.value,
            current_value=round(recent_mean, 2),
            baseline_value=round(base_mean, 2),
            z_score=round(z, 2),
            description=f"{label} kayması ({direction}): {base_mean:.2f} → {recent_mean:.2f}",
            detected_at=datetime.now(timezone.utc).isoformat(),
            recommendation=f"{label} trendini kontrol edin. Model güncellemesi veya veri kalitesi sorunu olabilir.",
        )


# ═══════════════════════════════════════════════════════════════════
#  Latency Profiler
# ═══════════════════════════════════════════════════════════════════

class LatencyProfiler:
    """
    End-to-end latency profiling.
    İstek-yanıt sürelerini izler, percentile hesaplar,
    intent bazlı latency kırılımı sağlar.
    """

    def __init__(self, window: int = WINDOW_SIZE * 5):
        self._window = window
        self._latencies: deque[float] = deque(maxlen=window)
        self._by_intent: dict[str, deque] = defaultdict(lambda: deque(maxlen=200))
        self._slow_queries: deque = deque(maxlen=50)     # P95 üstü
        self._latency_threshold_ms = 5000.0              # "Yavaş" eşiği

    def record(self, latency_ms: float, intent: str = ""):
        self._latencies.append(latency_ms)
        if intent:
            self._by_intent[intent].append(latency_ms)

        # Yavaş sorgu kaydı
        if latency_ms > self._latency_threshold_ms:
            self._slow_queries.append({
                "latency_ms": round(latency_ms, 1),
                "intent": intent,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

    def get_profile(self) -> LatencyProfile:
        """Mevcut latency profili."""
        values = list(self._latencies)
        if not values:
            return LatencyProfile()

        by_intent = {}
        for intent, vals in self._by_intent.items():
            v = list(vals)
            if v:
                by_intent[intent] = {
                    "p50": round(_percentile(v, 50), 1),
                    "p95": round(_percentile(v, 95), 1),
                    "mean": round(_mean(v), 1),
                    "count": len(v),
                }

        return LatencyProfile(
            p50=round(_percentile(values, 50), 1),
            p75=round(_percentile(values, 75), 1),
            p90=round(_percentile(values, 90), 1),
            p95=round(_percentile(values, 95), 1),
            p99=round(_percentile(values, 99), 1),
            mean=round(_mean(values), 1),
            min_ms=round(min(values), 1),
            max_ms=round(max(values), 1),
            count=len(values),
            by_intent=by_intent,
        )

    def check_latency_drift(self) -> Optional[DriftAlert]:
        """Latency drift algılama."""
        values = list(self._latencies)
        n = len(values)
        if n < WINDOW_SIZE:
            return None

        mid = n // 2
        baseline = values[:mid]
        recent = values[mid:]

        base_mean = _mean(baseline)
        base_std = _std(baseline)
        recent_mean = _mean(recent)

        z = _z_score(recent_mean, base_mean, base_std)

        if z < DRIFT_THRESHOLD:
            return None

        severity = (
            DriftSeverity.SEVERE if z >= 3.0
            else DriftSeverity.MODERATE if z >= 2.0
            else DriftSeverity.MILD
        )

        return DriftAlert(
            drift_type=DriftType.LATENCY.value,
            severity=severity.value,
            current_value=round(recent_mean, 1),
            baseline_value=round(base_mean, 1),
            z_score=round(z, 2),
            description=f"Latency kayması: {base_mean:.0f}ms → {recent_mean:.0f}ms",
            detected_at=datetime.now(timezone.utc).isoformat(),
            recommendation="Yanıt süresi artıyor. GPU yükü, model boyutu veya context uzunluğunu kontrol edin.",
        )

    def get_slow_queries(self) -> list[dict]:
        return list(self._slow_queries)


# ═══════════════════════════════════════════════════════════════════
#  Confidence Histogram
# ═══════════════════════════════════════════════════════════════════

class ConfidenceHistogramTracker:
    """
    Güven skoru dağılımı izleme.
    Histogram, trend, düşük-güven oranı takibi.
    """

    def __init__(self, window: int = WINDOW_SIZE * 5):
        self._confidences: deque[float] = deque(maxlen=window)

    def record(self, confidence: float):
        self._confidences.append(confidence)

    def get_profile(self) -> ConfidenceProfile:
        """Mevcut confidence profili."""
        values = list(self._confidences)
        if not values:
            return ConfidenceProfile()

        # Histogram (0-10, 10-20, ..., 90-100)
        bin_size = 100 / HISTOGRAM_BINS
        histogram = {}
        for i in range(HISTOGRAM_BINS):
            low = i * bin_size
            high = (i + 1) * bin_size
            label = f"{int(low)}-{int(high)}"
            count = sum(1 for v in values if low <= v < high)
            if i == HISTOGRAM_BINS - 1:
                count += sum(1 for v in values if v == high)  # 100 dahil
            histogram[label] = count

        below_50 = sum(1 for v in values if v < 50)

        return ConfidenceProfile(
            histogram=histogram,
            mean=round(_mean(values), 1),
            std=round(_std(values), 1),
            median=round(_percentile(values, 50), 1),
            below_50_pct=round(below_50 / len(values) * 100, 1) if values else 0.0,
            count=len(values),
        )


# ═══════════════════════════════════════════════════════════════════
#  Quality Trend Monitor
# ═══════════════════════════════════════════════════════════════════

class QualityTrendMonitor:
    """
    Kalite trend izleme — "improving / stable / degrading".
    """

    def __init__(self, window: int = WINDOW_SIZE):
        self._quality_scores: deque[float] = deque(maxlen=window * 2)
        self._timestamps: deque[str] = deque(maxlen=window * 2)

    def record(self, quality_score: float):
        self._quality_scores.append(quality_score)
        self._timestamps.append(datetime.now(timezone.utc).isoformat())

    def get_trend(self) -> dict:
        """Kalite trendi analizi."""
        values = list(self._quality_scores)
        n = len(values)

        if n < TREND_MIN_SAMPLES:
            return {
                "trend": "insufficient_data",
                "sample_count": n,
                "min_required": TREND_MIN_SAMPLES,
            }

        mid = n // 2
        first_half = values[:mid]
        second_half = values[mid:]

        first_mean = _mean(first_half)
        second_mean = _mean(second_half)
        diff = second_mean - first_mean
        pct_change = (diff / first_mean * 100) if first_mean > 0 else 0

        if pct_change > 5:
            trend = "improving"
        elif pct_change < -5:
            trend = "degrading"
        else:
            trend = "stable"

        return {
            "trend": trend,
            "first_half_mean": round(first_mean, 1),
            "second_half_mean": round(second_mean, 1),
            "change_pct": round(pct_change, 1),
            "sample_count": n,
            "current_mean": round(_mean(values[-20:]), 1) if n >= 20 else round(_mean(values), 1),
            "overall_mean": round(_mean(values), 1),
            "overall_std": round(_std(values), 1),
        }


# ═══════════════════════════════════════════════════════════════════
#  Ana Observability Sınıfı
# ═══════════════════════════════════════════════════════════════════

class Observability:
    """
    Enterprise Observability 2.0 — Tüm alt modülleri orkestre eder.

    Özellikler:
      • Decision drift tracking
      • Concept drift detection
      • Latency profiling (percentile-based)
      • Confidence histogram & trend
      • Quality trend monitoring
      • Integrated drift alerting
      • Dashboard & reporting
    """

    def __init__(self):
        self.decision_drift = DecisionDriftTracker()
        self.concept_drift = ConceptDriftDetector()
        self.latency_profiler = LatencyProfiler()
        self.confidence_histogram = ConfidenceHistogramTracker()
        self.quality_trend = QualityTrendMonitor()
        self._alert_history: deque[dict] = deque(maxlen=200)
        self._total_records = 0

    # ── Record ──

    def record_decision(
        self,
        confidence: float = 0.0,
        latency_ms: float = 0.0,
        quality_score: float = 0.0,
        intent: str = "",
        risk_score: float = 0.0,
        response_length: int = 0,
        outcome: str = "",
    ):
        """
        Her karar sonrası tüm metrikleri kaydet.
        Engine'den her istek sonunda çağrılır.
        """
        self._total_records += 1

        # Decision drift
        self.decision_drift.record(intent, risk_score, outcome)

        # Concept drift
        self.concept_drift.record(response_length, confidence, quality_score)

        # Latency
        if latency_ms > 0:
            self.latency_profiler.record(latency_ms, intent)

        # Confidence
        if confidence > 0:
            self.confidence_histogram.record(confidence)

        # Quality
        if quality_score > 0:
            self.quality_trend.record(quality_score)

    # ── Drift Kontrolü ──

    def check_all_drifts(self) -> dict:
        """Tüm drift türlerini kontrol et."""
        alerts: list[dict] = []

        checks = [
            self.decision_drift.check_drift(),
            self.concept_drift.check_confidence_drift(),
            self.concept_drift.check_quality_drift(),
            self.concept_drift.check_concept_drift(),
            self.latency_profiler.check_latency_drift(),
        ]

        for alert in checks:
            if alert:
                alert_dict = alert.to_dict()
                alerts.append(alert_dict)
                self._alert_history.append(alert_dict)

        any_drift = len(alerts) > 0
        max_severity = "none"
        if alerts:
            severity_order = {"none": 0, "mild": 1, "moderate": 2, "severe": 3}
            max_severity = max(alerts, key=lambda a: severity_order.get(a["severity"], 0))["severity"]

        return {
            "drift_detected": any_drift,
            "max_severity": max_severity,
            "alert_count": len(alerts),
            "alerts": alerts,
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }

    # ── Dashboard ──

    def get_dashboard(self) -> dict:
        """Observability 2.0 dashboard — admin paneli için."""
        latency = self.latency_profiler.get_profile()
        confidence = self.confidence_histogram.get_profile()
        quality_trend = self.quality_trend.get_trend()
        drift_status = self.check_all_drifts()
        intent_dist = self.decision_drift.get_intent_distribution()

        return {
            "status": "active",
            "total_records": self._total_records,
            "latency_profile": latency.to_dict(),
            "confidence_profile": confidence.to_dict(),
            "quality_trend": quality_trend,
            "drift_status": drift_status,
            "intent_distribution": intent_dist,
            "slow_queries": self.latency_profiler.get_slow_queries()[-10:],
            "alert_history": list(self._alert_history)[-10:],
        }


# ═══════════════════════════════════════════════════════════════════
#  Singleton
# ═══════════════════════════════════════════════════════════════════

observability = Observability()
