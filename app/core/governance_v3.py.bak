"""
AI Governance Framework — v3.1.0
==================================
Model drift detection, output bias monitoring, confidence tracking,
audit logging, otomatik alert sistemi.

Enterprise Package ai_governance_framework.json referanslı.
"""

from __future__ import annotations

import time
import json
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Optional

try:
    import structlog
    logger = structlog.get_logger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)

# ──────────────────── Sabitler ────────────────────
CONFIDENCE_ALERT_THRESHOLD = 75        # Bu altında uyarı
DRIFT_WINDOW_SIZE = 50                 # Son N yanıt üzerinden drift hesapla
DRIFT_ALERT_THRESHOLD = 15.0          # Ortalama confidence düşüşü
BIAS_KEYWORDS_POSITIVE = [
    "kesinlikle", "şüphesiz", "tartışmasız", "mükemmel", "harika",
    "sorunsuz", "risksiz", "garanti", "mutlaka olacak",
]
BIAS_KEYWORDS_NEGATIVE = [
    "imkansız", "asla", "kesinlikle olmaz", "felaket", "çöküş",
    "iflas", "tamamen başarısız",
]


# ──────────────────── Veri Yapıları ────────────────────

@dataclass
class GovernanceRecord:
    """Tek bir yanıt için yönetişim kaydı."""
    timestamp: float = 0.0
    question: str = ""
    mode: str = ""
    confidence: float = 0.0
    bias_score: float = 0.0        # -1.0 (negatif bias) to +1.0 (pozitif bias)
    bias_flags: list[str] = field(default_factory=list)
    drift_detected: bool = False
    alert_triggered: bool = False
    alert_reason: str = ""


@dataclass
class GovernanceDashboard:
    """Yönetişim özet panosu."""
    total_queries: int = 0
    avg_confidence: float = 0.0
    confidence_trend: str = ""      # "stable", "rising", "declining"
    drift_detected: bool = False
    drift_magnitude: float = 0.0
    bias_alerts: int = 0
    low_confidence_alerts: int = 0
    last_alert: str = ""


# ──────────────────── Governance Engine ────────────────────

class GovernanceEngine:
    """AI çıktı yönetişim motoru — singleton olarak kullanılır."""
    
    def __init__(self):
        self._confidence_history: deque[float] = deque(maxlen=DRIFT_WINDOW_SIZE)
        self._records: deque[GovernanceRecord] = deque(maxlen=200)
        self._alert_count: int = 0
        self._total_queries: int = 0
        self._bias_alert_count: int = 0
    
    # ── Ana Değerlendirme ──
    
    def evaluate(
        self,
        question: str,
        answer: str,
        mode: str,
        confidence: float,
    ) -> GovernanceRecord:
        """
        Bir LLM yanıtını yönetişim perspektifinden değerlendir.
        
        Returns:
            GovernanceRecord — bias, drift, alert bilgileri
        """
        record = GovernanceRecord(
            timestamp=time.time(),
            question=question[:200],
            mode=mode,
            confidence=confidence,
        )
        
        # 1. Bias Monitoring
        bias_score, bias_flags = self._check_bias(answer)
        record.bias_score = bias_score
        record.bias_flags = bias_flags
        
        # 2. Confidence Tracking
        self._confidence_history.append(confidence)
        self._total_queries += 1
        
        # 3. Drift Detection
        drift_detected, drift_magnitude = self._detect_drift()
        record.drift_detected = drift_detected
        
        # 4. Alert Logic
        alerts = []
        
        if confidence < CONFIDENCE_ALERT_THRESHOLD:
            alerts.append(f"Düşük güven: %{confidence:.0f} (eşik: %{CONFIDENCE_ALERT_THRESHOLD})")
            self._alert_count += 1
        
        if abs(bias_score) > 0.6:
            direction = "Pozitif" if bias_score > 0 else "Negatif"
            alerts.append(f"{direction} bias tespit edildi: {bias_score:.2f}")
            self._bias_alert_count += 1
        
        if drift_detected:
            alerts.append(f"Model drift: Confidence ortalaması {drift_magnitude:.1f} puan düştü")
        
        if alerts:
            record.alert_triggered = True
            record.alert_reason = " | ".join(alerts)
            logger.warning("governance_alert",
                           confidence=confidence,
                           bias=bias_score,
                           drift=drift_detected,
                           reason=record.alert_reason)
        
        self._records.append(record)
        
        return record
    
    # ── Bias Detection ──
    
    def _check_bias(self, answer: str) -> tuple[float, list[str]]:
        """
        Yanıttaki olası bias'ı tespit et.
        
        Returns:
            (bias_score, flags)
            bias_score: -1.0 (aşırı negatif) to +1.0 (aşırı pozitif)
        """
        answer_lower = answer.lower()
        flags = []
        
        pos_count = sum(1 for kw in BIAS_KEYWORDS_POSITIVE if kw in answer_lower)
        neg_count = sum(1 for kw in BIAS_KEYWORDS_NEGATIVE if kw in answer_lower)
        
        if pos_count >= 3:
            flags.append(f"Aşırı iyimser ifadeler ({pos_count} pozitif bias kelimesi)")
        if neg_count >= 3:
            flags.append(f"Aşırı kötümser ifadeler ({neg_count} negatif bias kelimesi)")
        
        # "Hep" / "hiç" gibi genelleme
        generalizations = len([
            w for w in ["her zaman", "hiçbir zaman", "herkes", "hiç kimse", "hep", "asla"]
            if w in answer_lower
        ])
        if generalizations >= 2:
            flags.append(f"Aşırı genelleme ({generalizations} ifade)")
        
        # Bias score hesapla
        total = pos_count + neg_count + 1  # +1 to avoid division by zero
        if total <= 1:
            bias_score = 0.0
        else:
            bias_score = (pos_count - neg_count) / total
        
        return round(bias_score, 2), flags
    
    # ── Drift Detection ──
    
    def _detect_drift(self) -> tuple[bool, float]:
        """
        Son N yanıtın confidence ortalamasında düşüş tespiti.
        İlk yarı vs ikinci yarı karşılaştırması.
        """
        history = list(self._confidence_history)
        if len(history) < 10:
            return False, 0.0
        
        mid = len(history) // 2
        first_half_avg = sum(history[:mid]) / mid
        second_half_avg = sum(history[mid:]) / (len(history) - mid)
        
        drop = first_half_avg - second_half_avg
        drift_detected = drop >= DRIFT_ALERT_THRESHOLD
        
        if drift_detected:
            logger.warning("model_drift_detected",
                           first_half_avg=round(first_half_avg, 1),
                           second_half_avg=round(second_half_avg, 1),
                           drop=round(drop, 1))
        
        return drift_detected, round(drop, 1)
    
    # ── Dashboard ──
    
    def get_dashboard(self) -> GovernanceDashboard:
        """Yönetişim özet panosu oluştur."""
        history = list(self._confidence_history)
        
        avg_conf = sum(history) / len(history) if history else 0.0
        
        # Trend hesapla
        if len(history) >= 10:
            mid = len(history) // 2
            first_avg = sum(history[:mid]) / mid
            second_avg = sum(history[mid:]) / (len(history) - mid)
            diff = second_avg - first_avg
            if diff > 3:
                trend = "📈 Yükseliyor"
            elif diff < -3:
                trend = "📉 Düşüyor"
            else:
                trend = "➡️ Stabil"
        else:
            trend = "⏳ Yeterli veri yok"
        
        drift_detected, drift_mag = self._detect_drift()
        
        last_alert = ""
        for r in reversed(self._records):
            if r.alert_triggered:
                last_alert = r.alert_reason
                break
        
        return GovernanceDashboard(
            total_queries=self._total_queries,
            avg_confidence=round(avg_conf, 1),
            confidence_trend=trend,
            drift_detected=drift_detected,
            drift_magnitude=drift_mag,
            bias_alerts=self._bias_alert_count,
            low_confidence_alerts=self._alert_count,
            last_alert=last_alert,
        )
    
    # ── Audit Log ──
    
    def get_audit_log(self, last_n: int = 20) -> list[dict[str, Any]]:
        """Son N yönetişim kaydını audit log olarak döndür."""
        records = list(self._records)[-last_n:]
        return [
            {
                "timestamp": r.timestamp,
                "mode": r.mode,
                "confidence": r.confidence,
                "bias_score": r.bias_score,
                "bias_flags": r.bias_flags,
                "drift_detected": r.drift_detected,
                "alert_triggered": r.alert_triggered,
                "alert_reason": r.alert_reason,
            }
            for r in records
        ]


# ──────────────────── Singleton Instance ────────────────────
governance_engine = GovernanceEngine()


# ──────────────────── Formatlama ────────────────────

def format_governance_dashboard(dashboard: GovernanceDashboard) -> str:
    """Dashboard'u markdown olarak formatla."""
    lines = [
        "\n### 🛡️ AI Yönetişim Panosu\n",
        f"| Metrik | Değer |",
        f"|--------|-------|",
        f"| Toplam Sorgu | {dashboard.total_queries} |",
        f"| Ortalama Güven | %{dashboard.avg_confidence:.1f} |",
        f"| Güven Trendi | {dashboard.confidence_trend} |",
        f"| Model Drift | {'⚠️ Tespit Edildi' if dashboard.drift_detected else '✅ Yok'} |",
        f"| Bias Uyarıları | {dashboard.bias_alerts} |",
        f"| Düşük Güven Uyarıları | {dashboard.low_confidence_alerts} |",
    ]
    
    if dashboard.last_alert:
        lines.append(f"\n**Son Uyarı:** {dashboard.last_alert}")
    
    if dashboard.drift_detected:
        lines.append(f"\n⚠️ **Model Drift:** Confidence ortalaması {dashboard.drift_magnitude} puan düştü. "
                      "Prompt kalitesi veya veri değişikliği kontrol edilmeli.")
    
    return "\n".join(lines)


def format_governance_alert(record: GovernanceRecord) -> str:
    """Tek bir alert için footer mesajı döndür."""
    if not record.alert_triggered:
        return ""
    
    parts = ["🛡️ **Yönetişim Uyarısı:**"]
    
    if record.bias_flags:
        parts.append(f"  - Bias: {', '.join(record.bias_flags)}")
    
    if record.confidence < CONFIDENCE_ALERT_THRESHOLD:
        parts.append(f"  - Güven: %{record.confidence:.0f} (eşik altında)")
    
    if record.drift_detected:
        parts.append("  - Model drift tespit edildi")
    
    return "\n".join(parts)
