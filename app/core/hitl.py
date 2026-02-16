"""Human-in-the-Loop (HITL) — AI Karar Onay Sistemi

Özellikleri:
- Yüksek riskli AI kararları için onay kuyruğu
- İnsan geri bildirimi (onayla / reddet / düzelt)
- Feedback'ten öğrenme (onaylanan/reddedilen kalıplar)
- Yapılandırılabilir eşikler (hangi kararlar onay gerektirir)

v5.5.0 Enterprise Eklemeleri:
  • Role-based override (admin/manager/analyst yetkileri)
  • Override justification logging (gerekçe zorunluluğu)
  • Post-override performance tracking (override sonrası performans analizi)
  • Escalation chain (otomatik yükseltme zinciri)
"""

import json
import uuid
import time
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from pathlib import Path
from collections import deque
import structlog

logger = structlog.get_logger()

_HITL_QUEUE_FILE = Path("data/hitl_queue.json")
_HITL_FEEDBACK_FILE = Path("data/hitl_feedback.json")
_HITL_CONFIG_FILE = Path("data/hitl_config.json")
_HITL_OVERRIDE_LOG = Path("data/hitl_override_log.jsonl")

# ── Role Yetkileri ──────────────────────────────────────────────
ROLE_PERMISSIONS = {
    "admin": {
        "can_approve": True,
        "can_reject": True,
        "can_modify": True,
        "can_escalate": True,
        "can_override_block": True,     # Policy Engine block'unu override edebilir
        "max_risk_level": "kritik",     # Tüm risk seviyeleri
        "requires_justification": False, # Gerekçe zorunlu değil
    },
    "manager": {
        "can_approve": True,
        "can_reject": True,
        "can_modify": True,
        "can_escalate": True,
        "can_override_block": False,
        "max_risk_level": "yüksek",
        "requires_justification": True,  # Gerekçe zorunlu
    },
    "analyst": {
        "can_approve": True,
        "can_reject": False,             # Reddedemez, yükseltmeli
        "can_modify": False,
        "can_escalate": True,
        "can_override_block": False,
        "max_risk_level": "orta",
        "requires_justification": True,
    },
    "viewer": {
        "can_approve": False,
        "can_reject": False,
        "can_modify": False,
        "can_escalate": False,
        "can_override_block": False,
        "max_risk_level": "düşük",
        "requires_justification": True,
    },
}

# Risk seviye sıralaması
RISK_LEVELS = {"düşük": 1, "orta": 2, "yüksek": 3, "kritik": 4, "bilinmiyor": 2}


def _utcnow_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load_json(path: Path) -> dict:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _save_json(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


# ── Varsayılan Yapılandırma ─────────────────────────────────────
DEFAULT_CONFIG = {
    # Bu koşullardan herhangi biri doğruysa AI kararı onay kuyruğuna girer
    "require_approval_when": {
        "confidence_below": 0.6,      # Güven skoru bu değerin altındaysa
        "risk_level": "yüksek",       # Risk seviyesi yüksek veya kritikse
        "contains_financial": True,    # Finansal tavsiye içeriyorsa
        "contains_personnel": True,    # Personel kararı içeriyorsa
    },
    "auto_approve_when": {
        "confidence_above": 0.9,      # Çok yüksek güven → otomatik onayla
        "risk_level": "düşük",        # Düşük risk → otomatik onayla
    },
    "feedback_learning": True,         # Feedback'lerden öğrenme aktif mi
    "max_queue_size": 500,             # Kuyruk boyutu limiti
}


class HITLTask:
    """Onay kuyruğundaki bir görev."""

    STATUS_PENDING = "pending"
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"
    STATUS_MODIFIED = "modified"
    STATUS_EXPIRED = "expired"

    def __init__(self, data: Dict):
        self.id = data.get("id", str(uuid.uuid4())[:8])
        self.query = data.get("query", "")
        self.ai_response = data.get("ai_response", "")
        self.confidence = data.get("confidence", 0.0)
        self.risk_level = data.get("risk_level", "bilinmiyor")
        self.department = data.get("department", "")
        self.reason = data.get("reason", "")
        self.status = data.get("status", self.STATUS_PENDING)
        self.created_at = data.get("created_at", _utcnow_str())
        self.reviewed_by = data.get("reviewed_by")
        self.reviewed_at = data.get("reviewed_at")
        self.reviewer_comment = data.get("reviewer_comment", "")
        self.modified_response = data.get("modified_response")
        self.user_id = data.get("user_id")
        self.metadata = data.get("metadata", {})

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "query": self.query,
            "ai_response": self.ai_response,
            "confidence": self.confidence,
            "risk_level": self.risk_level,
            "department": self.department,
            "reason": self.reason,
            "status": self.status,
            "created_at": self.created_at,
            "reviewed_by": self.reviewed_by,
            "reviewed_at": self.reviewed_at,
            "reviewer_comment": self.reviewer_comment,
            "modified_response": self.modified_response,
            "user_id": self.user_id,
            "metadata": self.metadata,
        }


class HITLManager:
    """Human-in-the-Loop yöneticisi."""

    def __init__(self):
        self._queue = self._load_queue()
        self._feedback = self._load_feedback()
        self._config = self._load_config()

    def _load_queue(self) -> List[HITLTask]:
        data = _load_json(_HITL_QUEUE_FILE)
        tasks = data.get("tasks", [])
        return [HITLTask(t) for t in tasks]

    def _load_feedback(self) -> List[Dict]:
        data = _load_json(_HITL_FEEDBACK_FILE)
        return data.get("feedback_history", [])

    def _load_config(self) -> Dict:
        data = _load_json(_HITL_CONFIG_FILE)
        if not data:
            data = DEFAULT_CONFIG.copy()
            _save_json(_HITL_CONFIG_FILE, data)
        return data

    def _save_queue(self):
        _save_json(_HITL_QUEUE_FILE, {
            "tasks": [t.to_dict() for t in self._queue],
            "updated_at": _utcnow_str(),
        })

    def _save_feedback(self):
        _save_json(_HITL_FEEDBACK_FILE, {
            "feedback_history": self._feedback,
            "updated_at": _utcnow_str(),
        })

    def needs_approval(self, confidence: float, risk_level: str, query: str) -> tuple[bool, str]:
        """AI kararının insan onayı gerektirip gerektirmediğini kontrol et."""
        rules = self._config.get("require_approval_when", {})
        auto = self._config.get("auto_approve_when", {})

        # Otomatik onay kuralları (öncelikli)
        if confidence >= auto.get("confidence_above", 0.95):
            return False, "Yüksek güven — otomatik onaylandı"
        if risk_level == auto.get("risk_level", "düşük"):
            return False, "Düşük risk — otomatik onaylandı"

        # Onay gerektiren kurallar
        if confidence < rules.get("confidence_below", 0.6):
            return True, f"Düşük güven skoru ({confidence:.2f} < {rules['confidence_below']})"
        if risk_level in ("yüksek", "kritik") and rules.get("risk_level") in ("yüksek", "kritik"):
            return True, f"Yüksek risk seviyesi: {risk_level}"

        financial_keywords = ["maliyet", "bütçe", "fiyat", "gelir", "kar", "zarar", "yatırım", "finans"]
        if rules.get("contains_financial") and any(kw in query.lower() for kw in financial_keywords):
            return True, "Finansal içerik tespit edildi"

        personnel_keywords = ["işten çıkar", "terfi", "maaş", "personel", "kadro", "pozisyon"]
        if rules.get("contains_personnel") and any(kw in query.lower() for kw in personnel_keywords):
            return True, "Personel kararı tespit edildi"

        return False, "Onay gerekmez"

    def submit_for_approval(
        self,
        query: str,
        ai_response: str,
        confidence: float,
        risk_level: str = "orta",
        department: str = "",
        reason: str = "",
        user_id: Optional[int] = None,
        metadata: Optional[Dict] = None,
    ) -> HITLTask:
        """AI kararını onay kuyruğuna ekle."""
        task = HITLTask({
            "query": query,
            "ai_response": ai_response,
            "confidence": confidence,
            "risk_level": risk_level,
            "department": department,
            "reason": reason,
            "user_id": user_id,
            "metadata": metadata or {},
        })

        # Kuyruk boyutu kontrolü
        max_size = self._config.get("max_queue_size", 500)
        if len(self._queue) >= max_size:
            # En eski expired/reviewed görevleri temizle
            self._queue = [t for t in self._queue if t.status == HITLTask.STATUS_PENDING]

        self._queue.append(task)
        self._save_queue()

        logger.info("hitl_task_submitted", task_id=task.id, confidence=confidence, risk=risk_level)
        return task

    def review(
        self,
        task_id: str,
        action: str,  # "approve", "reject", "modify"
        reviewer_id: str = "admin",
        comment: str = "",
        modified_response: Optional[str] = None,
    ) -> HITLTask:
        """Bir görevi onayla, reddet veya düzelt."""
        task = None
        for t in self._queue:
            if t.id == task_id:
                task = t
                break
        if not task:
            raise KeyError(f"Görev bulunamadı: {task_id}")

        if action == "approve":
            task.status = HITLTask.STATUS_APPROVED
        elif action == "reject":
            task.status = HITLTask.STATUS_REJECTED
        elif action == "modify":
            task.status = HITLTask.STATUS_MODIFIED
            task.modified_response = modified_response
        else:
            raise ValueError(f"Geçersiz aksiyon: {action}")

        task.reviewed_by = reviewer_id
        task.reviewed_at = _utcnow_str()
        task.reviewer_comment = comment
        self._save_queue()

        # Feedback öğrenme
        if self._config.get("feedback_learning", True):
            self._learn_from_feedback(task)

        logger.info("hitl_task_reviewed", task_id=task_id, action=action, reviewer=reviewer_id)
        return task

    def _learn_from_feedback(self, task: HITLTask):
        """Geri bildirimden öğren — kalıpları kaydet."""
        feedback_entry = {
            "task_id": task.id,
            "query": task.query[:200],
            "ai_response_preview": task.ai_response[:200],
            "action": task.status,
            "confidence": task.confidence,
            "risk_level": task.risk_level,
            "department": task.department,
            "reviewer": task.reviewed_by,
            "comment": task.reviewer_comment,
            "has_modification": task.modified_response is not None,
            "timestamp": _utcnow_str(),
        }

        self._feedback.append(feedback_entry)

        # Feedback listesini 1000 ile sınırla
        if len(self._feedback) > 1000:
            self._feedback = self._feedback[-1000:]

        self._save_feedback()

    def get_pending_tasks(self, limit: int = 50) -> List[Dict]:
        """Bekleyen görevleri listele."""
        pending = [t for t in self._queue if t.status == HITLTask.STATUS_PENDING]
        return [t.to_dict() for t in pending[-limit:]]

    def get_reviewed_tasks(self, limit: int = 50) -> List[Dict]:
        """İncelenmiş görevleri listele."""
        reviewed = [t for t in self._queue if t.status != HITLTask.STATUS_PENDING]
        return [t.to_dict() for t in reviewed[-limit:]]

    def get_feedback_stats(self) -> Dict:
        """Feedback istatistikleri."""
        total = len(self._feedback)
        if total == 0:
            return {"total": 0}

        approved = sum(1 for f in self._feedback if f["action"] == "approved")
        rejected = sum(1 for f in self._feedback if f["action"] == "rejected")
        modified = sum(1 for f in self._feedback if f["action"] == "modified")

        # Departman bazlı analiz
        dept_stats = {}
        for f in self._feedback:
            dept = f.get("department", "Genel")
            if dept not in dept_stats:
                dept_stats[dept] = {"approved": 0, "rejected": 0, "modified": 0}
            if f["action"] == "approved":
                dept_stats[dept]["approved"] += 1
            elif f["action"] == "rejected":
                dept_stats[dept]["rejected"] += 1
            elif f["action"] == "modified":
                dept_stats[dept]["modified"] += 1

        # Ortalama güven (reddedilen vs onaylanan)
        approved_conf = [f["confidence"] for f in self._feedback if f["action"] == "approved" and f.get("confidence")]
        rejected_conf = [f["confidence"] for f in self._feedback if f["action"] == "rejected" and f.get("confidence")]

        return {
            "total_feedback": total,
            "approved": approved,
            "rejected": rejected,
            "modified": modified,
            "approval_rate": round(approved / total * 100, 1) if total > 0 else 0,
            "avg_confidence_approved": round(sum(approved_conf) / len(approved_conf), 3) if approved_conf else 0,
            "avg_confidence_rejected": round(sum(rejected_conf) / len(rejected_conf), 3) if rejected_conf else 0,
            "department_stats": dept_stats,
        }

    def get_config(self) -> Dict:
        """Mevcut HITL yapılandırmasını döndür."""
        return self._config.copy()

    def update_config(self, updates: Dict) -> Dict:
        """HITL yapılandırmasını güncelle."""
        for key in ["require_approval_when", "auto_approve_when", "feedback_learning", "max_queue_size"]:
            if key in updates:
                self._config[key] = updates[key]
        _save_json(_HITL_CONFIG_FILE, self._config)
        logger.info("hitl_config_updated", keys=list(updates.keys()))
        return self._config

    def get_dashboard(self) -> Dict:
        """HITL dashboard özeti."""
        pending = [t for t in self._queue if t.status == HITLTask.STATUS_PENDING]
        reviewed = [t for t in self._queue if t.status != HITLTask.STATUS_PENDING]

        return {
            "pending_count": len(pending),
            "reviewed_count": len(reviewed),
            "total_queue": len(self._queue),
            "feedback_stats": self.get_feedback_stats(),
            "config": self._config,
            "recent_pending": [t.to_dict() for t in pending[-5:]],
            # v5.5.0
            "override_stats": self.get_override_stats(),
        }

    # ── v5.5.0 Enterprise: Role-Based Override ──────────────────

    def check_permission(self, reviewer_role: str, action: str, task: HITLTask) -> tuple[bool, str]:
        """Rol bazlı yetki kontrolü.

        Args:
            reviewer_role: admin | manager | analyst | viewer
            action: approve | reject | modify | escalate
            task: Kontrol edilecek görev

        Returns:
            (allowed, reason)
        """
        perms = ROLE_PERMISSIONS.get(reviewer_role)
        if not perms:
            return False, f"Bilinmeyen rol: {reviewer_role}"

        # Aksiyon yetkisi
        action_map = {
            "approve": "can_approve",
            "reject": "can_reject",
            "modify": "can_modify",
            "escalate": "can_escalate",
        }
        perm_key = action_map.get(action)
        if not perm_key or not perms.get(perm_key, False):
            return False, f"'{reviewer_role}' rolü '{action}' aksiyonuna yetkili değil"

        # Risk seviyesi kontrolü
        task_risk = RISK_LEVELS.get(task.risk_level, 2)
        max_risk = RISK_LEVELS.get(perms.get("max_risk_level", "düşük"), 1)
        if task_risk > max_risk:
            return False, f"'{reviewer_role}' rolü '{task.risk_level}' risk seviyesini değerlendiremez (max: {perms['max_risk_level']})"

        return True, "Yetkili"

    def review_with_role(
        self,
        task_id: str,
        action: str,
        reviewer_id: str = "admin",
        reviewer_role: str = "admin",
        justification: str = "",
        comment: str = "",
        modified_response: Optional[str] = None,
    ) -> Dict:
        """Rol tabanlı review — yetki kontrolü + gerekçe zorunluluğu.

        Returns:
            {"success": bool, "task": dict | None, "error": str | None}
        """
        task = None
        for t in self._queue:
            if t.id == task_id:
                task = t
                break
        if not task:
            return {"success": False, "error": f"Görev bulunamadı: {task_id}"}

        # Yetki kontrolü
        allowed, reason = self.check_permission(reviewer_role, action, task)
        if not allowed:
            self._log_override_attempt(task_id, reviewer_id, reviewer_role, action, False, reason)
            return {"success": False, "error": reason}

        # Gerekçe zorunluluğu
        perms = ROLE_PERMISSIONS.get(reviewer_role, {})
        if perms.get("requires_justification", True) and not justification.strip():
            return {"success": False, "error": f"'{reviewer_role}' rolü için gerekçe zorunludur"}

        # Review işlemi
        reviewed_task = self.review(
            task_id=task_id,
            action=action,
            reviewer_id=reviewer_id,
            comment=comment,
            modified_response=modified_response,
        )

        # Override log
        self._log_override_attempt(
            task_id, reviewer_id, reviewer_role, action, True,
            justification=justification,
            original_response=task.ai_response[:200],
            modified_response=modified_response[:200] if modified_response else "",
        )

        return {"success": True, "task": reviewed_task.to_dict()}

    def _log_override_attempt(
        self, task_id: str, reviewer_id: str, role: str,
        action: str, success: bool, reason: str = "",
        justification: str = "", original_response: str = "",
        modified_response: str = "",
    ):
        """Override girişimini logla (başarılı/başarısız)."""
        entry = {
            "task_id": task_id,
            "reviewer_id": reviewer_id,
            "role": role,
            "action": action,
            "success": success,
            "reason": reason,
            "justification": justification,
            "original_response": original_response,
            "modified_response": modified_response,
            "timestamp": _utcnow_str(),
        }
        try:
            _HITL_OVERRIDE_LOG.parent.mkdir(parents=True, exist_ok=True)
            with open(_HITL_OVERRIDE_LOG, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.error("override_log_failed", error=str(e))

    def get_override_stats(self) -> Dict:
        """Override istatistikleri — post-override performans analizi."""
        if not _HITL_OVERRIDE_LOG.exists():
            return {"total_overrides": 0, "total_denied": 0}

        overrides = []
        try:
            for line in _HITL_OVERRIDE_LOG.read_text(encoding="utf-8").strip().split("\n"):
                if line.strip():
                    overrides.append(json.loads(line))
        except Exception:
            return {"total_overrides": 0, "total_denied": 0}

        total = len(overrides)
        successful = [o for o in overrides if o.get("success")]
        denied = [o for o in overrides if not o.get("success")]

        # Role bazlı kırılım
        role_stats = {}
        for o in overrides:
            role = o.get("role", "unknown")
            if role not in role_stats:
                role_stats[role] = {"total": 0, "approved": 0, "rejected": 0, "modified": 0, "denied": 0}
            role_stats[role]["total"] += 1
            if o.get("success"):
                action = o.get("action", "")
                if action in role_stats[role]:
                    role_stats[role][action] += 1
            else:
                role_stats[role]["denied"] += 1

        # Override yapılan kararların performans karşılaştırması
        modifications = [o for o in successful if o.get("action") == "modify"]

        return {
            "total_overrides": len(successful),
            "total_denied": len(denied),
            "total_modifications": len(modifications),
            "by_role": role_stats,
            "justification_rate": round(
                sum(1 for o in successful if o.get("justification")) / len(successful) * 100, 1
            ) if successful else 0.0,
            "recent_overrides": overrides[-5:],
        }

    def escalate(self, task_id: str, from_role: str, reason: str = "") -> Dict:
        """Görevi bir üst role yükselt.

        Escalation zinciri: viewer → analyst → manager → admin
        """
        escalation_chain = ["viewer", "analyst", "manager", "admin"]
        task = None
        for t in self._queue:
            if t.id == task_id:
                task = t
                break
        if not task:
            return {"success": False, "error": f"Görev bulunamadı: {task_id}"}

        try:
            idx = escalation_chain.index(from_role)
        except ValueError:
            return {"success": False, "error": f"Bilinmeyen rol: {from_role}"}

        if idx >= len(escalation_chain) - 1:
            return {"success": False, "error": "En üst role ulaşıldı, daha fazla yükseltilemez"}

        target_role = escalation_chain[idx + 1]
        task.metadata["escalated_from"] = from_role
        task.metadata["escalated_to"] = target_role
        task.metadata["escalation_reason"] = reason
        task.metadata["escalated_at"] = _utcnow_str()
        self._save_queue()

        logger.info("hitl_task_escalated", task_id=task_id, from_role=from_role, to_role=target_role)
        return {
            "success": True,
            "task_id": task_id,
            "escalated_to": target_role,
            "reason": reason,
        }


# Singleton instance
hitl_manager = HITLManager()
