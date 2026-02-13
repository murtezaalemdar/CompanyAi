"""
AI Governance Framework — v4.0.0
==================================
Enterprise-grade AI yönetişim:

- Bias detection (keyword + istatistiksel yanlılık tespiti)
- Multi-dimensional drift (confidence, data, concept, performance)
- Decision traceability (tam karar izlenebilirliği + reasoning chain)
- Prompt versioning (sistem prompt versiyonlama)
- Policy rules engine (yapılandırılabilir 12 kural)
- Compliance scoring (uyumluluk puanlama)
- Audit trail (denetim izi)
- Dashboard (özet gösterge paneli)
"""

from __future__ import annotations

import hashlib
import json
import math
import time
from collections import Counter, deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

try:
    import structlog
    logger = structlog.get_logger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)

# ──────────────────── Sabitler ────────────────────
CONFIDENCE_ALERT_THRESHOLD = 75
DRIFT_WINDOW_SIZE = 50
DRIFT_ALERT_THRESHOLD = 15.0
COMPLIANCE_PASS_THRESHOLD = 0.7
DATA_DRIFT_Z_THRESHOLD = 2.5
CONCEPT_DRIFT_THRESHOLD = 0.25
PERF_DRIFT_THRESHOLD = 1.5

BIAS_KEYWORDS_POSITIVE = [
    "kesinlikle", "şüphesiz", "tartışmasız", "mükemmel", "harika",
    "sorunsuz", "risksiz", "garanti", "mutlaka olacak", "kusursuz",
    "olağanüstü", "en iyi", "ideal", "muhteşem",
]
BIAS_KEYWORDS_NEGATIVE = [
    "imkansız", "asla", "kesinlikle olmaz", "felaket", "çöküş",
    "iflas", "tamamen başarısız", "korkunç", "berbat",
    "kötü", "tehlikeli", "sorun",
]

_GOVERNANCE_DATA_DIR = Path("data/governance")


# ──────────────────── Veri Yapıları ────────────────────

@dataclass
class DecisionTrace:
    """Tek bir kararın tam izlenebilirlik kaydı."""
    trace_id: str = ""
    timestamp: float = 0.0
    question: str = ""
    mode: str = ""
    confidence: float = 0.0
    answer_hash: str = ""
    prompt_version: str = ""
    model_name: str = ""
    reasoning_steps: list[str] = field(default_factory=list)
    modules_invoked: list[str] = field(default_factory=list)
    governance_flags: list[str] = field(default_factory=list)
    compliance_score: float = 1.0
    bias_score: float = 0.0
    drift_flags: list[str] = field(default_factory=list)
    elapsed_ms: float = 0.0


@dataclass
class GovernanceRecord:
    """Tek bir yanıt için yönetişim kaydı."""
    timestamp: float = 0.0
    question: str = ""
    mode: str = ""
    confidence: float = 0.0
    bias_score: float = 0.0
    bias_flags: list[str] = field(default_factory=list)
    drift_detected: bool = False
    alert_triggered: bool = False
    alert_reason: str = ""
    # ── v4.0 eklentileri ──
    trace_id: str = ""
    prompt_version: str = ""
    compliance_score: float = 1.0
    policy_violations: list[str] = field(default_factory=list)
    drift_types: list[str] = field(default_factory=list)


@dataclass
class GovernanceDashboard:
    """Yönetişim paneli özet verisi."""
    total_queries: int = 0
    avg_confidence: float = 0.0
    confidence_trend: str = ""
    drift_detected: bool = False
    drift_magnitude: float = 0.0
    bias_alerts: int = 0
    low_confidence_alerts: int = 0
    last_alert: str = ""
    # ── v4.0 eklentileri ──
    compliance_score: float = 1.0
    policy_violations_count: int = 0
    prompt_version: str = ""
    active_drift_types: list[str] = field(default_factory=list)
    decision_trace_count: int = 0
    risk_level: str = "Düşük"


# ──────────────────── Prompt Versioning ────────────────────

class PromptVersionManager:
    """Sistem prompt versiyonlarını izler ve karşılaştırır."""

    def __init__(self):
        self._versions: dict[str, dict[str, Any]] = {}
        self._current_version: str = "1.0.0"
        self._version_history: deque[dict] = deque(maxlen=100)

    def register_prompt(self, version: str, prompt_text: str, description: str = "") -> str:
        prompt_hash = hashlib.sha256(prompt_text.encode()).hexdigest()[:12]
        entry = {
            "version": version,
            "hash": prompt_hash,
            "description": description,
            "registered_at": time.time(),
            "char_count": len(prompt_text),
            "word_count": len(prompt_text.split()),
        }
        self._versions[version] = entry
        self._current_version = version
        self._version_history.append(entry)
        logger.info("prompt_version_registered", version=version, hash=prompt_hash)
        return prompt_hash

    @property
    def current_version(self) -> str:
        return self._current_version

    def get_version_info(self, version: str = "") -> dict:
        v = version or self._current_version
        return self._versions.get(v, {"version": v, "hash": "unknown"})

    def get_history(self) -> list[dict]:
        return list(self._version_history)


# ──────────────────── Policy Rules Engine ────────────────────

@dataclass
class PolicyRule:
    """Tek bir yönetişim politikası kuralı."""
    rule_id: str = ""
    name: str = ""
    description: str = ""
    category: str = ""
    severity: str = "info"
    check_fn_name: str = ""
    enabled: bool = True
    threshold: float = 0.0


DEFAULT_POLICY_RULES: list[PolicyRule] = [
    PolicyRule("GOV-001", "Düşük Güven Skoru", "Confidence eşik altında",
               "quality", "warning", "check_low_confidence", threshold=CONFIDENCE_ALERT_THRESHOLD),
    PolicyRule("GOV-002", "Pozitif Bias", "Aşırı iyimser ifade",
               "bias", "warning", "check_positive_bias", threshold=0.6),
    PolicyRule("GOV-003", "Negatif Bias", "Aşırı kötümser ifade",
               "bias", "warning", "check_negative_bias", threshold=-0.6),
    PolicyRule("GOV-004", "Genelleme Bias", "Aşırı genelleme kullanımı",
               "bias", "info", "check_generalization"),
    PolicyRule("GOV-005", "Confidence Drift", "Model confidence kayması",
               "quality", "critical", "check_confidence_drift", threshold=DRIFT_ALERT_THRESHOLD),
    PolicyRule("GOV-006", "Data Drift", "Input dağılım kayması",
               "quality", "warning", "check_data_drift", threshold=DATA_DRIFT_Z_THRESHOLD),
    PolicyRule("GOV-007", "Concept Drift", "Output pattern değişimi",
               "quality", "warning", "check_concept_drift", threshold=CONCEPT_DRIFT_THRESHOLD),
    PolicyRule("GOV-008", "Performans Degradasyonu", "Yanıt süresi trendsel artış",
               "quality", "warning", "check_perf_drift", threshold=PERF_DRIFT_THRESHOLD),
    PolicyRule("GOV-009", "Kısa Cevap", "Yanıt çok kısa (< 50 karakter)",
               "quality", "info", "check_short_answer", threshold=50),
    PolicyRule("GOV-010", "Uzun Cevap", "Yanıt çok uzun (> 5000 karakter)",
               "quality", "info", "check_long_answer", threshold=5000),
    PolicyRule("GOV-011", "Hassas Veri", "Cevap olası hassas bilgi içeriyor",
               "security", "critical", "check_sensitive_data"),
    PolicyRule("GOV-012", "Hallucination Risk", "Düşük confidence + yüksek bias",
               "quality", "critical", "check_hallucination_risk"),
]


class PolicyEngine:
    """Yapılandırılabilir politika kuralları motoru."""

    def __init__(self, rules: list[PolicyRule] | None = None):
        self._rules = rules or list(DEFAULT_POLICY_RULES)
        self._violation_log: deque[dict] = deque(maxlen=500)

    def evaluate(
        self,
        answer: str,
        confidence: float,
        bias_score: float,
        bias_flags: list[str],
        drift_types: list[str],
        elapsed_ms: float = 0,
    ) -> tuple[float, list[str]]:
        """Tüm aktif kuralları kontrol et. Returns: (compliance_score, violations)."""
        violations: list[str] = []
        total_rules = 0
        passed_rules = 0

        for rule in self._rules:
            if not rule.enabled:
                continue
            total_rules += 1

            violated = False
            detail = ""

            if rule.check_fn_name == "check_low_confidence" and confidence < rule.threshold:
                violated, detail = True, f"Güven %{confidence:.0f} < %{rule.threshold:.0f}"
            elif rule.check_fn_name == "check_positive_bias" and bias_score > rule.threshold:
                violated, detail = True, f"Pozitif bias {bias_score:.2f} > {rule.threshold}"
            elif rule.check_fn_name == "check_negative_bias" and bias_score < rule.threshold:
                violated, detail = True, f"Negatif bias {bias_score:.2f} < {rule.threshold}"
            elif rule.check_fn_name == "check_generalization" and any("genelleme" in f.lower() for f in bias_flags):
                violated, detail = True, "Aşırı genelleme tespit edildi"
            elif rule.check_fn_name == "check_confidence_drift" and "confidence_drift" in drift_types:
                violated, detail = True, "Confidence drift aktif"
            elif rule.check_fn_name == "check_data_drift" and "data_drift" in drift_types:
                violated, detail = True, "Data drift tespit edildi"
            elif rule.check_fn_name == "check_concept_drift" and "concept_drift" in drift_types:
                violated, detail = True, "Concept drift tespit edildi"
            elif rule.check_fn_name == "check_perf_drift" and "perf_drift" in drift_types:
                violated, detail = True, "Performans degradasyonu"
            elif rule.check_fn_name == "check_short_answer" and len(answer) < rule.threshold:
                violated, detail = True, f"Yanıt çok kısa: {len(answer)} karakter"
            elif rule.check_fn_name == "check_long_answer" and len(answer) > rule.threshold:
                violated, detail = True, f"Yanıt çok uzun: {len(answer)} karakter"
            elif rule.check_fn_name == "check_sensitive_data":
                sensitive = ["tc kimlik", "kredi kart", "iban", "şifre", "password", "parola"]
                found = [p for p in sensitive if p in answer.lower()]
                if found:
                    violated, detail = True, f"Hassas veri: {', '.join(found)}"
            elif rule.check_fn_name == "check_hallucination_risk":
                if confidence < 60 and abs(bias_score) > 0.4:
                    violated, detail = True, f"Düşük güven ({confidence:.0f}) + yüksek bias ({bias_score:.2f})"

            if violated:
                violations.append(f"[{rule.rule_id}] {rule.name}: {detail}")
                self._violation_log.append({
                    "rule_id": rule.rule_id, "name": rule.name,
                    "severity": rule.severity, "detail": detail,
                    "timestamp": time.time(),
                })
            else:
                passed_rules += 1

        compliance = passed_rules / total_rules if total_rules > 0 else 1.0
        return round(compliance, 3), violations

    def get_violation_log(self, last_n: int = 50) -> list[dict]:
        return list(self._violation_log)[-last_n:]

    def get_rules_summary(self) -> list[dict]:
        return [
            {"rule_id": r.rule_id, "name": r.name, "category": r.category,
             "severity": r.severity, "enabled": r.enabled}
            for r in self._rules
        ]


# ──────────────────── Multi-Dimensional Drift ────────────────────

class DriftDetector:
    """Çok boyutlu drift tespiti: confidence, data, concept, performance."""

    def __init__(self, window: int = DRIFT_WINDOW_SIZE):
        self._confidence_history: deque[float] = deque(maxlen=window)
        self._input_lengths: deque[int] = deque(maxlen=window)
        self._output_lengths: deque[int] = deque(maxlen=window)
        self._mode_history: deque[str] = deque(maxlen=window)
        self._response_times: deque[float] = deque(maxlen=window)
        self._window = window

    def record(self, confidence: float, input_len: int, output_len: int,
               mode: str, elapsed_ms: float = 0):
        self._confidence_history.append(confidence)
        self._input_lengths.append(input_len)
        self._output_lengths.append(output_len)
        self._mode_history.append(mode)
        if elapsed_ms > 0:
            self._response_times.append(elapsed_ms)

    def detect_all(self) -> tuple[list[str], dict[str, Any]]:
        """Tüm drift tiplerini kontrol et."""
        drift_types: list[str] = []
        details: dict[str, Any] = {}

        cd, cd_mag = self._confidence_drift()
        if cd:
            drift_types.append("confidence_drift")
            details["confidence_drift"] = {"magnitude": cd_mag}

        dd, dd_z = self._data_drift()
        if dd:
            drift_types.append("data_drift")
            details["data_drift"] = {"z_score": dd_z}

        ccd, ccd_score = self._concept_drift()
        if ccd:
            drift_types.append("concept_drift")
            details["concept_drift"] = {"divergence": ccd_score}

        pd, pd_ratio = self._perf_drift()
        if pd:
            drift_types.append("perf_drift")
            details["perf_drift"] = {"ratio": pd_ratio}

        return drift_types, details

    def _confidence_drift(self) -> tuple[bool, float]:
        history = list(self._confidence_history)
        if len(history) < 10:
            return False, 0.0
        mid = len(history) // 2
        first_avg = sum(history[:mid]) / mid
        second_avg = sum(history[mid:]) / (len(history) - mid)
        drop = first_avg - second_avg
        return drop >= DRIFT_ALERT_THRESHOLD, round(drop, 1)

    def _data_drift(self) -> tuple[bool, float]:
        """Input length z-score: son çeyrek vs geçmiş."""
        data = list(self._input_lengths)
        if len(data) < 20:
            return False, 0.0
        q = max(len(data) // 4, 3)
        baseline, recent = data[:-q], data[-q:]
        mean_b = sum(baseline) / len(baseline)
        var_b = sum((x - mean_b) ** 2 for x in baseline) / len(baseline)
        std_b = math.sqrt(var_b) if var_b > 0 else 1.0
        z = abs(sum(recent) / len(recent) - mean_b) / std_b
        return z >= DATA_DRIFT_Z_THRESHOLD, round(z, 2)

    def _concept_drift(self) -> tuple[bool, float]:
        """Mode distribution shift."""
        modes = list(self._mode_history)
        if len(modes) < 20:
            return False, 0.0
        mid = len(modes) // 2
        first_dist, second_dist = Counter(modes[:mid]), Counter(modes[mid:])
        all_modes = set(first_dist) | set(second_dist)
        n1, n2 = sum(first_dist.values()) or 1, sum(second_dist.values()) or 1
        divergence = sum(
            abs(first_dist.get(m, 0) / n1 - second_dist.get(m, 0) / n2)
            for m in all_modes
        ) / max(len(all_modes), 1)
        return divergence >= CONCEPT_DRIFT_THRESHOLD, round(divergence, 3)

    def _perf_drift(self) -> tuple[bool, float]:
        """Response time trending: son çeyrek / ilk çeyrek."""
        data = list(self._response_times)
        if len(data) < 12:
            return False, 0.0
        q = max(len(data) // 4, 3)
        first_avg = sum(data[:q]) / q
        last_avg = sum(data[-q:]) / q
        if first_avg <= 0:
            return False, 0.0
        ratio = last_avg / first_avg
        return ratio >= PERF_DRIFT_THRESHOLD, round(ratio, 2)


# ──────────────────── Governance Engine ────────────────────

class GovernanceEngine:
    """Merkezi AI Yönetişim motoru — Enterprise v4.0."""

    VERSION = "4.0.0"

    def __init__(self):
        self._records: deque[GovernanceRecord] = deque(maxlen=500)
        self._decision_traces: deque[DecisionTrace] = deque(maxlen=500)
        self._confidence_history: deque[float] = deque(maxlen=DRIFT_WINDOW_SIZE)
        self._total_queries: int = 0
        self._alert_count: int = 0
        self._bias_alert_count: int = 0
        self._trace_counter: int = 0

        self._drift = DriftDetector()
        self._policy = PolicyEngine()
        self._prompt_mgr = PromptVersionManager()

        _GOVERNANCE_DATA_DIR.mkdir(parents=True, exist_ok=True)

    # ── Ana evaluate ──

    def evaluate(
        self,
        question: str,
        answer: str,
        mode: str,
        confidence: float,
        *,
        elapsed_ms: float = 0,
        model_name: str = "",
        modules_invoked: list[str] | None = None,
        reasoning_steps: list[str] | None = None,
    ) -> GovernanceRecord:
        """
        LLM yanıtını yönetişim açısından değerlendir.
        engine.py'den her sorgu sonrası çağrılır.

        v4.0: keyword args ile decision trace, compliance, prompt versioning.
        Eski çağrı imzası (question, answer, mode, confidence) tam uyumlu.
        """
        self._total_queries += 1
        self._confidence_history.append(confidence)
        ts = time.time()

        # Bias tespiti
        bias_score, bias_flags = self._check_bias(answer)

        # Multi-dimensional drift
        self._drift.record(confidence, len(question), len(answer), mode, elapsed_ms)
        drift_types, drift_details = self._drift.detect_all()
        drift_detected = len(drift_types) > 0
        drift_magnitude = drift_details.get("confidence_drift", {}).get("magnitude", 0.0)

        # Policy compliance
        compliance_score, policy_violations = self._policy.evaluate(
            answer, confidence, bias_score, bias_flags, drift_types, elapsed_ms
        )

        # Decision trace
        self._trace_counter += 1
        trace_id = f"DT-{int(ts)}-{self._trace_counter:04d}"
        answer_hash = hashlib.sha256(answer.encode()).hexdigest()[:16]

        record = GovernanceRecord(
            timestamp=ts,
            question=question[:200],
            mode=mode,
            confidence=confidence,
            bias_score=bias_score,
            bias_flags=bias_flags,
            drift_detected=drift_detected,
            trace_id=trace_id,
            prompt_version=self._prompt_mgr.current_version,
            compliance_score=compliance_score,
            policy_violations=policy_violations,
            drift_types=drift_types,
        )

        # Uyarı kontrolü
        alerts: list[str] = []
        if confidence < CONFIDENCE_ALERT_THRESHOLD:
            alerts.append(f"Düşük güven: %{confidence:.0f}")
            self._alert_count += 1

        if abs(bias_score) > 0.6:
            direction = "Pozitif" if bias_score > 0 else "Negatif"
            alerts.append(f"{direction} bias: {bias_score:.2f}")
            self._bias_alert_count += 1

        if "confidence_drift" in drift_types:
            alerts.append(f"Model drift: Confidence {drift_magnitude:.1f}p düştü")

        for dt in drift_types:
            if dt != "confidence_drift":
                alerts.append(f"Drift: {dt.replace('_', ' ').title()}")

        if compliance_score < COMPLIANCE_PASS_THRESHOLD:
            alerts.append(f"Compliance düşük: %{compliance_score*100:.0f}")

        critical = [v for v in policy_violations if "[GOV-011]" in v or "[GOV-012]" in v]
        alerts.extend(critical)

        if alerts:
            record.alert_triggered = True
            record.alert_reason = " | ".join(alerts[:5])
            logger.warning("governance_alert",
                           confidence=confidence, bias=bias_score,
                           drift=drift_detected, compliance=compliance_score,
                           reason=record.alert_reason)

        self._records.append(record)

        # Decision trace kaydet
        trace = DecisionTrace(
            trace_id=trace_id, timestamp=ts,
            question=question[:200], mode=mode,
            confidence=confidence, answer_hash=answer_hash,
            prompt_version=self._prompt_mgr.current_version,
            model_name=model_name,
            reasoning_steps=reasoning_steps or [],
            modules_invoked=modules_invoked or [],
            governance_flags=list(alerts),
            compliance_score=compliance_score,
            bias_score=bias_score,
            drift_flags=drift_types,
            elapsed_ms=elapsed_ms,
        )
        self._decision_traces.append(trace)

        return record

    # ── Bias Detection ──

    def _check_bias(self, answer: str) -> tuple[float, list[str]]:
        """Yanıttaki olası bias'ı tespit et."""
        answer_lower = answer.lower()
        flags: list[str] = []

        pos_count = sum(1 for kw in BIAS_KEYWORDS_POSITIVE if kw in answer_lower)
        neg_count = sum(1 for kw in BIAS_KEYWORDS_NEGATIVE if kw in answer_lower)

        if pos_count >= 3:
            flags.append(f"Aşırı iyimser ifadeler ({pos_count} pozitif bias kelimesi)")
        if neg_count >= 3:
            flags.append(f"Aşırı kötümser ifadeler ({neg_count} negatif bias kelimesi)")

        generalizations = len([
            w for w in ["her zaman", "hiçbir zaman", "herkes", "hiç kimse", "hep", "asla"]
            if w in answer_lower
        ])
        if generalizations >= 2:
            flags.append(f"Aşırı genelleme ({generalizations} ifade)")

        total = pos_count + neg_count + 1
        bias_score = 0.0 if total <= 1 else (pos_count - neg_count) / total
        return round(bias_score, 2), flags

    # ── Dashboard ──

    def get_dashboard(self) -> GovernanceDashboard:
        """Yönetişim özet panosu oluştur."""
        history = list(self._confidence_history)
        avg_conf = sum(history) / len(history) if history else 0.0

        if len(history) >= 10:
            mid = len(history) // 2
            first_avg = sum(history[:mid]) / mid
            second_avg = sum(history[mid:]) / (len(history) - mid)
            diff = second_avg - first_avg
            trend = "📈 Yükseliyor" if diff > 3 else ("📉 Düşüyor" if diff < -3 else "➡️ Stabil")
        else:
            trend = "⏳ Yeterli veri yok"

        drift_types, _ = self._drift.detect_all()
        drift_detected = len(drift_types) > 0
        _, drift_mag = self._drift._confidence_drift()

        last_alert = ""
        for r in reversed(self._records):
            if r.alert_triggered:
                last_alert = r.alert_reason
                break

        recent = list(self._records)[-50:]
        avg_compliance = sum(r.compliance_score for r in recent) / len(recent) if recent else 1.0
        total_violations = sum(len(r.policy_violations) for r in recent)

        if avg_compliance >= 0.9 and not drift_detected:
            risk_level = "Düşük"
        elif avg_compliance >= 0.7 and len(drift_types) <= 1:
            risk_level = "Orta"
        else:
            risk_level = "Yüksek"

        return GovernanceDashboard(
            total_queries=self._total_queries,
            avg_confidence=round(avg_conf, 1),
            confidence_trend=trend,
            drift_detected=drift_detected,
            drift_magnitude=drift_mag,
            bias_alerts=self._bias_alert_count,
            low_confidence_alerts=self._alert_count,
            last_alert=last_alert,
            compliance_score=round(avg_compliance, 3),
            policy_violations_count=total_violations,
            prompt_version=self._prompt_mgr.current_version,
            active_drift_types=drift_types,
            decision_trace_count=len(self._decision_traces),
            risk_level=risk_level,
        )

    # ── Audit Log ──

    def get_audit_log(self, last_n: int = 20) -> list[dict[str, Any]]:
        """Son N yönetişim kaydını döndür."""
        records = list(self._records)[-last_n:]
        return [
            {
                "timestamp": r.timestamp, "mode": r.mode,
                "confidence": r.confidence, "bias_score": r.bias_score,
                "bias_flags": r.bias_flags, "drift_detected": r.drift_detected,
                "alert_triggered": r.alert_triggered, "alert_reason": r.alert_reason,
                "trace_id": r.trace_id, "compliance_score": r.compliance_score,
                "policy_violations": r.policy_violations, "drift_types": r.drift_types,
            }
            for r in records
        ]

    # ── Decision Trace API ──

    def get_decision_traces(self, last_n: int = 20) -> list[dict[str, Any]]:
        """Son N karar izlenebilirlik kaydını döndür."""
        traces = list(self._decision_traces)[-last_n:]
        return [
            {
                "trace_id": t.trace_id, "timestamp": t.timestamp,
                "question": t.question, "mode": t.mode,
                "confidence": t.confidence, "answer_hash": t.answer_hash,
                "prompt_version": t.prompt_version, "model_name": t.model_name,
                "reasoning_steps": t.reasoning_steps,
                "modules_invoked": t.modules_invoked,
                "governance_flags": t.governance_flags,
                "compliance_score": t.compliance_score,
                "bias_score": t.bias_score, "drift_flags": t.drift_flags,
                "elapsed_ms": t.elapsed_ms,
            }
            for t in traces
        ]

    def get_trace_by_id(self, trace_id: str) -> dict[str, Any] | None:
        for t in self._decision_traces:
            if t.trace_id == trace_id:
                return {
                    "trace_id": t.trace_id, "timestamp": t.timestamp,
                    "question": t.question, "mode": t.mode,
                    "confidence": t.confidence, "answer_hash": t.answer_hash,
                    "prompt_version": t.prompt_version, "model_name": t.model_name,
                    "reasoning_steps": t.reasoning_steps,
                    "modules_invoked": t.modules_invoked,
                    "governance_flags": t.governance_flags,
                    "compliance_score": t.compliance_score,
                    "bias_score": t.bias_score, "drift_flags": t.drift_flags,
                    "elapsed_ms": t.elapsed_ms,
                }
        return None

    # ── Policy API ──

    def get_policy_rules(self) -> list[dict]:
        return self._policy.get_rules_summary()

    def get_policy_violations(self, last_n: int = 50) -> list[dict]:
        return self._policy.get_violation_log(last_n)

    # ── Prompt Version API ──

    def register_prompt_version(self, version: str, prompt_text: str, desc: str = "") -> str:
        return self._prompt_mgr.register_prompt(version, prompt_text, desc)

    def get_prompt_versions(self) -> list[dict]:
        return self._prompt_mgr.get_history()

    # ── Drift API ──

    def get_drift_status(self) -> dict[str, Any]:
        drift_types, details = self._drift.detect_all()
        return {
            "active_drifts": drift_types,
            "details": details,
            "data_points": len(self._drift._confidence_history),
            "window_size": self._drift._window,
        }

    # ── Compliance Report ──

    def get_compliance_report(self) -> dict[str, Any]:
        """Kapsamlı uyumluluk raporu oluştur."""
        records = list(self._records)
        if not records:
            return {"status": "Veri yok", "total_evaluations": 0}

        total = len(records)
        compliant = sum(1 for r in records if r.compliance_score >= COMPLIANCE_PASS_THRESHOLD)
        violations_by_rule: dict[str, int] = {}
        for r in records:
            for v in r.policy_violations:
                cat = v.split("]")[0].replace("[", "") if "]" in v else "OTHER"
                violations_by_rule[cat] = violations_by_rule.get(cat, 0) + 1

        avg_score = sum(r.compliance_score for r in records) / total
        return {
            "total_evaluations": total,
            "compliant_count": compliant,
            "compliance_rate": round(compliant / total * 100, 1),
            "avg_compliance_score": round(avg_score, 3),
            "violations_by_rule": violations_by_rule,
            "total_violations": sum(violations_by_rule.values()),
            "rules_active": len([r for r in self._policy._rules if r.enabled]),
            "generated_at": time.time(),
        }


# ──────────────────── Singleton ────────────────────
governance_engine = GovernanceEngine()


# ──────────────────── Formatlama ────────────────────

def format_governance_dashboard(dashboard: GovernanceDashboard) -> str:
    """Dashboard'u markdown olarak formatla."""
    lines = [
        "\n### 🛡️ AI Yönetişim Panosu\n",
        "| Metrik | Değer |",
        "|--------|-------|",
        f"| Toplam Sorgu | {dashboard.total_queries} |",
        f"| Ortalama Güven | %{dashboard.avg_confidence:.1f} |",
        f"| Güven Trendi | {dashboard.confidence_trend} |",
        f"| Model Drift | {'⚠️ Tespit Edildi' if dashboard.drift_detected else '✅ Yok'} |",
        f"| Bias Uyarıları | {dashboard.bias_alerts} |",
        f"| Düşük Güven Uyarıları | {dashboard.low_confidence_alerts} |",
        f"| Compliance Skoru | %{dashboard.compliance_score*100:.0f} |",
        f"| Politika İhlalleri | {dashboard.policy_violations_count} |",
        f"| Risk Seviyesi | {dashboard.risk_level} |",
        f"| Prompt Versiyon | {dashboard.prompt_version} |",
        f"| Karar İzi Sayısı | {dashboard.decision_trace_count} |",
    ]

    if dashboard.active_drift_types:
        lines.append(f"| Aktif Drift | {', '.join(dashboard.active_drift_types)} |")

    if dashboard.last_alert:
        lines.append(f"\n**Son Uyarı:** {dashboard.last_alert}")

    if dashboard.drift_detected:
        lines.append(f"\n⚠️ **Model Drift:** Confidence {dashboard.drift_magnitude}p düştü.")

    if dashboard.compliance_score < COMPLIANCE_PASS_THRESHOLD:
        lines.append(f"\n🔴 **Compliance Düşük:** %{dashboard.compliance_score*100:.0f}")

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
        parts.append(f"  - Drift: {', '.join(record.drift_types) if record.drift_types else 'Aktif'}")
    if record.compliance_score < COMPLIANCE_PASS_THRESHOLD:
        parts.append(f"  - Compliance: %{record.compliance_score*100:.0f}")
    if record.policy_violations:
        parts.append(f"  - İhlaller: {len(record.policy_violations)} kural")

    return "\n".join(parts)
