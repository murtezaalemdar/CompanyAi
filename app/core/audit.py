"""Audit & Compliance Framework — v2.0.0

Enterprise-grade denetim ve uyumluluk:

- Temel audit logging (PostgreSQL AuditLog tablosu)
- ★ Compliance framework scoring (kategori bazlı)
- ★ Risk-based audit severity (low/medium/high/critical)
- ★ Decision trace linking (governance trace_id bağlantısı)
- ★ Data retention policy (otomatik temizlik)
- ★ Access control audit (rol bazlı erişim denetimi)
- ★ Compliance report generation
"""

from typing import Optional, Any
from datetime import datetime, timezone, timedelta
from collections import deque
import json
import time

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.db.models import AuditLog, User
import structlog

logger = structlog.get_logger()


# ──────────────────── Severity Levels ────────────────────

class AuditSeverity:
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# ──────────────────── Compliance Categories ────────────────────

COMPLIANCE_CATEGORIES = {
    "DATA_ACCESS": {
        "name": "Veri Erişimi",
        "description": "Hassas verilere erişim denetimi",
        "actions": ["query", "export", "document_upload", "document_delete"],
    },
    "AUTH_SECURITY": {
        "name": "Kimlik Doğrulama & Güvenlik",
        "description": "Giriş/çıkış ve güvenlik olayları",
        "actions": ["login", "logout", "login_failed", "password_change", "token_refresh"],
    },
    "ADMIN_OPS": {
        "name": "Yönetici İşlemleri",
        "description": "Admin panel işlemleri",
        "actions": ["admin_action", "user_create", "user_update", "user_delete",
                     "role_change", "settings_change"],
    },
    "AI_GOVERNANCE": {
        "name": "AI Yönetişim",
        "description": "AI model ve karar denetimi",
        "actions": ["ai_query", "ai_feedback", "ai_calibration", "governance_alert",
                     "bias_detected", "drift_detected"],
    },
    "SYSTEM_OPS": {
        "name": "Sistem İşlemleri",
        "description": "Sistem yapılandırma ve bakım",
        "actions": ["backup", "restore", "system_config", "service_restart"],
    },
}


# ──────────────────── Severity Mapping ────────────────────

ACTION_SEVERITY_MAP = {
    "login": AuditSeverity.LOW,
    "logout": AuditSeverity.LOW,
    "query": AuditSeverity.LOW,
    "ai_query": AuditSeverity.LOW,
    "token_refresh": AuditSeverity.LOW,
    "login_failed": AuditSeverity.MEDIUM,
    "export": AuditSeverity.MEDIUM,
    "document_upload": AuditSeverity.MEDIUM,
    "ai_feedback": AuditSeverity.MEDIUM,
    "admin_action": AuditSeverity.HIGH,
    "user_create": AuditSeverity.HIGH,
    "user_update": AuditSeverity.HIGH,
    "role_change": AuditSeverity.HIGH,
    "settings_change": AuditSeverity.HIGH,
    "password_change": AuditSeverity.HIGH,
    "ai_calibration": AuditSeverity.HIGH,
    "user_delete": AuditSeverity.CRITICAL,
    "document_delete": AuditSeverity.CRITICAL,
    "backup": AuditSeverity.HIGH,
    "restore": AuditSeverity.CRITICAL,
    "governance_alert": AuditSeverity.HIGH,
    "bias_detected": AuditSeverity.MEDIUM,
    "drift_detected": AuditSeverity.HIGH,
    "system_config": AuditSeverity.CRITICAL,
    "service_restart": AuditSeverity.CRITICAL,
}


def _get_severity(action: str) -> str:
    """Aksiyon tipine göre severity belirle."""
    return ACTION_SEVERITY_MAP.get(action, AuditSeverity.LOW)


def _get_compliance_category(action: str) -> str:
    """Aksiyon tipine göre compliance kategorisi belirle."""
    for cat_key, cat_info in COMPLIANCE_CATEGORIES.items():
        if action in cat_info["actions"]:
            return cat_key
    return "SYSTEM_OPS"


# ──────────────────── Core Audit Logger ────────────────────

async def log_action(
    db: AsyncSession,
    *,
    user: Optional[User] = None,
    user_id: Optional[int] = None,
    action: str,
    resource: Optional[str] = None,
    details: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    trace_id: Optional[str] = None,
    severity: Optional[str] = None,
) -> None:
    """
    Denetim kaydı oluşturur.

    v2.0: trace_id ile governance decision trace bağlantısı,
    otomatik severity belirleme, compliance kategorisi.
    """
    uid = user_id or (user.id if user else None)

    # Severity auto-detect
    actual_severity = severity or _get_severity(action)

    # Details'e ek bilgi ekle
    details_dict = {}
    if details:
        try:
            details_dict = json.loads(details)
        except (json.JSONDecodeError, TypeError):
            details_dict = {"raw": details}

    if trace_id:
        details_dict["trace_id"] = trace_id
    details_dict["severity"] = actual_severity
    details_dict["compliance_category"] = _get_compliance_category(action)

    enriched_details = json.dumps(details_dict, ensure_ascii=False)

    entry = AuditLog(
        user_id=uid,
        action=action,
        resource=resource,
        details=enriched_details,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    db.add(entry)

    try:
        await db.flush()
    except Exception as e:
        logger.error("audit_log_write_failed", action=action, error=str(e))

    # In-memory log for compliance engine
    audit_compliance_engine.record(action, actual_severity, uid)


# ──────────────────── Compliance Engine (In-Memory) ────────────────────

class ComplianceEngine:
    """Compliance scoring ve raporlama — in-memory, DB'den bağımsız."""

    def __init__(self):
        self._events: deque[dict] = deque(maxlen=5000)
        self._violation_flags: deque[dict] = deque(maxlen=500)

    def record(self, action: str, severity: str, user_id: Optional[int] = None):
        """Audit olayını compliance engine'e kaydet."""
        self._events.append({
            "action": action,
            "severity": severity,
            "user_id": user_id,
            "category": _get_compliance_category(action),
            "timestamp": time.time(),
        })

    def flag_violation(self, rule: str, detail: str, severity: str = AuditSeverity.HIGH):
        """Compliance ihlali kaydet."""
        self._violation_flags.append({
            "rule": rule,
            "detail": detail,
            "severity": severity,
            "timestamp": time.time(),
        })

    def get_compliance_score(self) -> dict[str, Any]:
        """Genel compliance skoru hesapla."""
        events = list(self._events)
        if not events:
            return {"score": 100, "grade": "A", "categories": {}, "total_events": 0}

        total = len(events)
        violations = list(self._violation_flags)

        # Kategori bazlı scoring
        cat_scores: dict[str, dict] = {}
        for cat_key, cat_info in COMPLIANCE_CATEGORIES.items():
            cat_events = [e for e in events if e["category"] == cat_key]
            cat_violations = [v for v in violations if v.get("rule", "").startswith(cat_key)]
            cat_count = len(cat_events)
            cat_viol_count = len(cat_violations)

            if cat_count == 0:
                score = 100
            else:
                penalty = (cat_viol_count / max(cat_count, 1)) * 100
                score = max(0, 100 - penalty)

            cat_scores[cat_key] = {
                "name": cat_info["name"],
                "score": round(score, 1),
                "events": cat_count,
                "violations": cat_viol_count,
            }

        # Genel skor (kategori ortalaması, violation ağırlıklı)
        scores = [c["score"] for c in cat_scores.values()]
        avg_score = sum(scores) / len(scores) if scores else 100

        # Severity-based penalty
        critical_count = sum(1 for v in violations if v["severity"] == AuditSeverity.CRITICAL)
        high_count = sum(1 for v in violations if v["severity"] == AuditSeverity.HIGH)
        avg_score -= critical_count * 10
        avg_score -= high_count * 3
        avg_score = max(0, min(100, avg_score))

        grade = "A" if avg_score >= 90 else "B" if avg_score >= 75 else "C" if avg_score >= 60 else "D" if avg_score >= 40 else "F"

        return {
            "score": round(avg_score, 1),
            "grade": grade,
            "categories": cat_scores,
            "total_events": total,
            "total_violations": len(violations),
            "timestamp": time.time(),
        }

    def get_violations(self, last_n: int = 50) -> list[dict]:
        return list(self._violation_flags)[-last_n:]

    def get_event_summary(self, last_hours: int = 24) -> dict[str, Any]:
        """Son N saatteki olay özeti."""
        cutoff = time.time() - (last_hours * 3600)
        recent = [e for e in self._events if e["timestamp"] > cutoff]

        by_action: dict[str, int] = {}
        by_severity: dict[str, int] = {}
        by_user: dict[str, int] = {}

        for e in recent:
            by_action[e["action"]] = by_action.get(e["action"], 0) + 1
            by_severity[e["severity"]] = by_severity.get(e["severity"], 0) + 1
            uid = str(e.get("user_id") or "system")
            by_user[uid] = by_user.get(uid, 0) + 1

        return {
            "total": len(recent),
            "period_hours": last_hours,
            "by_action": dict(sorted(by_action.items(), key=lambda x: -x[1])),
            "by_severity": by_severity,
            "by_user": dict(sorted(by_user.items(), key=lambda x: -x[1])[:10]),
            "timestamp": time.time(),
        }


# ──────────────────── Data Retention ────────────────────

class DataRetentionPolicy:
    """Veri saklama politikası — otomatik audit log temizleme."""

    DEFAULT_RETENTION_DAYS = {
        AuditSeverity.LOW: 30,
        AuditSeverity.MEDIUM: 90,
        AuditSeverity.HIGH: 365,
        AuditSeverity.CRITICAL: 730,  # 2 yıl
    }

    def __init__(self):
        self._retention_days = self.DEFAULT_RETENTION_DAYS.copy()

    async def cleanup(self, db: AsyncSession) -> dict[str, int]:
        """Saklama süresi aşılmış kayıtları temizle."""
        deleted_counts: dict[str, int] = {}
        now = datetime.now(timezone.utc)

        for severity, days in self._retention_days.items():
            cutoff = now - timedelta(days=days)
            try:
                result = await db.execute(
                    text(
                        "DELETE FROM audit_logs WHERE created_at < :cutoff "
                        "AND details::text LIKE :severity_pattern"
                    ),
                    {"cutoff": cutoff, "severity_pattern": f'%"severity": "{severity}"%'},
                )
                deleted_counts[severity] = result.rowcount or 0
            except Exception as e:
                logger.error("retention_cleanup_failed", severity=severity, error=str(e))
                deleted_counts[severity] = 0

        total = sum(deleted_counts.values())
        if total > 0:
            logger.info("retention_cleanup_complete", deleted=deleted_counts)

        return deleted_counts

    def get_policy(self) -> dict[str, int]:
        return dict(self._retention_days)

    def update_policy(self, updates: dict[str, int]) -> dict[str, int]:
        self._retention_days.update(updates)
        return dict(self._retention_days)


# ──────────────────── Singleton Instances ────────────────────
audit_compliance_engine = ComplianceEngine()
data_retention_policy = DataRetentionPolicy()
