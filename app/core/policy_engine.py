"""
CompanyAI — Policy Engine
============================
Enterprise policy enforcement katmanı.

SORUMLULUKLAR:
  ┌──────────────────────────────────────────────────────────────────┐
  │ Katman                │ İşlev                                    │
  ├───────────────────────┼────────────────────────────────────────────┤
  │ PolicyRule            │ Deklaratif kural tanımı (JSON)           │
  │ PolicyEngine          │ Kural değerlendirme motoru               │
  │ PolicyEnforcer        │ Karar öncesi zorlayıcı katman            │
  │ PolicyAudit           │ Kural ihlali/onay kayıtları              │
  │ PolicyVersioning      │ Kural versiyonlama                       │
  └───────────────────────┴────────────────────────────────────────────┘

KULLANIM:
  from app.core.policy_engine import policy_engine

  # Karar öncesi policy kontrolü
  result = policy_engine.evaluate({
      "confidence": 0.65,
      "risk_score": 0.8,
      "department": "finans",
      "budget_impact": 150000,
  })

  if result["action"] == "block":
      raise PolicyViolation(result["violations"])
  elif result["action"] == "require_approval":
      await hitl_manager.submit_for_approval(...)

KURAL ÖRNEKLERİ:
  • risk_score > 0.7 → insan onayı zorunlu
  • budget_impact > 100000 → müdür onayı
  • confidence < 0.5 → karar bloke
  • department == "finans" AND amount > 50000 → ek doğrulama
  • drift_detected == true → karar beklet + uyarı
"""

import json
import re
import time
import uuid
from collections import defaultdict, deque
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional

import structlog

logger = structlog.get_logger()

DATA_DIR = Path("data/policies")
DATA_DIR.mkdir(parents=True, exist_ok=True)

POLICY_FILE = DATA_DIR / "policy_rules.json"
POLICY_HISTORY_FILE = DATA_DIR / "policy_history.json"
POLICY_AUDIT_FILE = DATA_DIR / "policy_audit.jsonl"


# ═══════════════════════════════════════════════════════════════════
#  Sabitler & Enum'lar
# ═══════════════════════════════════════════════════════════════════

class PolicyAction(Enum):
    """Policy ihlali sonucu aksiyonlar."""
    ALLOW = "allow"                 # İzin ver
    BLOCK = "block"                 # Engelle
    REQUIRE_APPROVAL = "require_approval"   # İnsan onayı zorunlu
    WARN = "warn"                   # Uyarı ver, devam et
    ESCALATE = "escalate"           # Üst yönetime bildir
    RATE_LIMIT = "rate_limit"       # Hız sınırla
    AUDIT_ONLY = "audit_only"       # Sadece kaydet


class PolicyCategory(Enum):
    """Policy kategorileri."""
    RISK = "risk"                   # Risk limitleri
    BUDGET = "budget"               # Bütçe kontrolleri
    CONFIDENCE = "confidence"       # Güven eşikleri
    COMPLIANCE = "compliance"       # Uyumluluk
    SECURITY = "security"           # Güvenlik kuralları
    QUALITY = "quality"             # Kalite standartları
    OPERATIONAL = "operational"     # Operasyonel kurallar
    DATA = "data"                   # Veri politikaları


class PolicySeverity(Enum):
    """Kural ihlali şiddeti."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# ═══════════════════════════════════════════════════════════════════
#  Veri Yapıları
# ═══════════════════════════════════════════════════════════════════

@dataclass
class PolicyRule:
    """Tek bir policy kuralı."""
    rule_id: str
    name: str
    description: str
    category: str                     # PolicyCategory value
    condition: str                    # Python eval edilebilir koşul
    action: str                       # PolicyAction value
    severity: str = "medium"          # PolicySeverity value
    enabled: bool = True
    priority: int = 50                # 0-100, yüksek = öncelikli
    message: str = ""                # İhlal mesajı
    metadata: dict = field(default_factory=dict)
    version: int = 1
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "PolicyRule":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class PolicyViolation:
    """Tespit edilen bir policy ihlali."""
    rule_id: str
    rule_name: str
    category: str
    severity: str
    action: str
    message: str
    context: dict = field(default_factory=dict)
    timestamp: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class PolicyResult:
    """Policy değerlendirme sonucu."""
    action: str                       # En yüksek seviyeli aksiyon
    passed: bool                      # Hiç bloke yok mu?
    violations: list[dict]            # İhlal listesi
    warnings: list[dict]              # Uyarı listesi
    total_rules_checked: int
    rules_passed: int
    rules_violated: int
    requires_approval: bool
    escalation_needed: bool
    evaluated_at: str = ""
    evaluation_ms: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


# ═══════════════════════════════════════════════════════════════════
#  Varsayılan Policy Kuralları
# ═══════════════════════════════════════════════════════════════════

DEFAULT_RULES: list[dict] = [
    # ── Risk Kuralları ──
    {
        "rule_id": "RISK-001",
        "name": "Yüksek Risk Onay Zorunluluğu",
        "description": "Risk skoru 0.7 üzeri kararlar insan onayı gerektirir",
        "category": "risk",
        "condition": "ctx.get('risk_score', 0) > 0.7",
        "action": "require_approval",
        "severity": "high",
        "priority": 90,
        "message": "Risk skoru yüksek ({risk_score:.2f}) — insan onayı gerekli",
    },
    {
        "rule_id": "RISK-002",
        "name": "Kritik Risk Bloklama",
        "description": "Risk skoru 0.9 üzeri kararlar bloke edilir",
        "category": "risk",
        "condition": "ctx.get('risk_score', 0) > 0.9",
        "action": "block",
        "severity": "critical",
        "priority": 100,
        "message": "Kritik risk seviyesi ({risk_score:.2f}) — karar bloke edildi",
    },
    {
        "rule_id": "RISK-003",
        "name": "Orta Risk Uyarısı",
        "description": "Risk skoru 0.5-0.7 arası uyarı verir",
        "category": "risk",
        "condition": "0.5 <= ctx.get('risk_score', 0) <= 0.7",
        "action": "warn",
        "severity": "medium",
        "priority": 40,
        "message": "Orta düzey risk ({risk_score:.2f}) — dikkatli ilerleyin",
    },

    # ── Güven Kuralları ──
    {
        "rule_id": "CONF-001",
        "name": "Düşük Güven Onay Zorunluluğu",
        "description": "Güven skoru 40 altı kararlar onay gerektirir",
        "category": "confidence",
        "condition": "ctx.get('confidence', 100) < 40",
        "action": "require_approval",
        "severity": "high",
        "priority": 80,
        "message": "Düşük güven skoru ({confidence}%) — insan onayı gerekli",
    },
    {
        "rule_id": "CONF-002",
        "name": "Çok Düşük Güven Bloklama",
        "description": "Güven skoru 20 altı kararlar bloke edilir",
        "category": "confidence",
        "condition": "ctx.get('confidence', 100) < 20",
        "action": "block",
        "severity": "critical",
        "priority": 95,
        "message": "Çok düşük güven ({confidence}%) — karar bloke edildi",
    },

    # ── Bütçe Kuralları ──
    {
        "rule_id": "BUD-001",
        "name": "Yüksek Bütçe Etkisi Onayı",
        "description": "100K TL üzeri bütçe etkisi müdür onayı gerektirir",
        "category": "budget",
        "condition": "ctx.get('budget_impact', 0) > 100000",
        "action": "require_approval",
        "severity": "high",
        "priority": 85,
        "message": "Yüksek bütçe etkisi ({budget_impact:,.0f} TL) — müdür onayı gerekli",
    },
    {
        "rule_id": "BUD-002",
        "name": "Çok Yüksek Bütçe Eskalasyon",
        "description": "500K TL üzeri bütçe etkisi üst yönetime bildirilir",
        "category": "budget",
        "condition": "ctx.get('budget_impact', 0) > 500000",
        "action": "escalate",
        "severity": "critical",
        "priority": 95,
        "message": "Çok yüksek bütçe etkisi ({budget_impact:,.0f} TL) — üst yönetim bildirimi",
    },

    # ── Kalite Kuralları ──
    {
        "rule_id": "QUAL-001",
        "name": "Düşük Kalite Uyarısı",
        "description": "Kalite skoru 50 altı uyarı verir",
        "category": "quality",
        "condition": "ctx.get('quality_score', 100) < 50",
        "action": "warn",
        "severity": "medium",
        "priority": 50,
        "message": "Düşük karar kalitesi ({quality_score}/100) — dikkat",
    },
    {
        "rule_id": "QUAL-002",
        "name": "Çok Düşük Kalite Bloklama",
        "description": "Kalite skoru 25 altında karar bloke edilir",
        "category": "quality",
        "condition": "ctx.get('quality_score', 100) < 25",
        "action": "block",
        "severity": "high",
        "priority": 88,
        "message": "Çok düşük kalite ({quality_score}/100) — karar bloke edildi",
    },

    # ── Uyumluluk Kuralları ──
    {
        "rule_id": "COMP-001",
        "name": "Drift Algılandığında Uyarı",
        "description": "Drift algılandığında karar uyarı ile devam eder",
        "category": "compliance",
        "condition": "ctx.get('drift_detected', False) == True",
        "action": "warn",
        "severity": "medium",
        "priority": 60,
        "message": "Model/veri drift algılandı — sonuçlar güvenilir olmayabilir",
    },
    {
        "rule_id": "COMP-002",
        "name": "Governance İhlali Onayı",
        "description": "Governance compliance < 0.5 ise onay gerektirir",
        "category": "compliance",
        "condition": "ctx.get('governance_compliance', 1.0) < 0.5",
        "action": "require_approval",
        "severity": "high",
        "priority": 75,
        "message": "Governance uyumluluk düşük ({governance_compliance:.2f}) — onay gerekli",
    },

    # ── Güvenlik Kuralları ──
    {
        "rule_id": "SEC-001",
        "name": "Prompt Injection Tespiti",
        "description": "Prompt injection şüphesi varsa bloke et",
        "category": "security",
        "condition": "ctx.get('prompt_injection_detected', False) == True",
        "action": "block",
        "severity": "critical",
        "priority": 100,
        "message": "Prompt injection saldırısı tespit edildi — istek bloke edildi",
    },
    {
        "rule_id": "SEC-002",
        "name": "Rate Limit Aşımı",
        "description": "Rate limit aşılırsa istek sınırla",
        "category": "security",
        "condition": "ctx.get('rate_limited', False) == True",
        "action": "rate_limit",
        "severity": "medium",
        "priority": 70,
        "message": "İstek limiti aşıldı — lütfen bekleyin",
    },

    # ── Operasyonel Kurallar ──
    {
        "rule_id": "OPS-001",
        "name": "Finans Departmanı Ek Doğrulama",
        "description": "Finans departmanı kararları ek doğrulama gerektirir",
        "category": "operational",
        "condition": "ctx.get('department', '') in ('finans', 'finance', 'muhasebe')",
        "action": "warn",
        "severity": "medium",
        "priority": 45,
        "message": "Finansal karar — ek doğrulama önerilir",
    },
    {
        "rule_id": "OPS-002",
        "name": "OOD Veri Uyarısı",
        "description": "Out-of-distribution veri algılandığında uyarı",
        "category": "operational",
        "condition": "ctx.get('ood_detected', False) == True",
        "action": "warn",
        "severity": "medium",
        "priority": 55,
        "message": "Dağılım dışı (OOD) veri algılandı — sonuç güvenilirliği düşük",
    },

    # ── Veri Politikaları ──
    {
        "rule_id": "DATA-001",
        "name": "Hassas Veri Audit",
        "description": "Hassas veri içeren kararlar denetim kaydı oluşturur",
        "category": "data",
        "condition": "ctx.get('contains_sensitive_data', False) == True",
        "action": "audit_only",
        "severity": "low",
        "priority": 30,
        "message": "Hassas veri içeren karar — denetim kaydı oluşturuldu",
    },
]


# ═══════════════════════════════════════════════════════════════════
#  Policy Engine
# ═══════════════════════════════════════════════════════════════════

# Aksiyon öncelik sırası (yüksek → düşük)
_ACTION_PRIORITY = {
    PolicyAction.BLOCK.value: 100,
    PolicyAction.ESCALATE.value: 80,
    PolicyAction.REQUIRE_APPROVAL.value: 70,
    PolicyAction.RATE_LIMIT.value: 50,
    PolicyAction.WARN.value: 30,
    PolicyAction.AUDIT_ONLY.value: 10,
    PolicyAction.ALLOW.value: 0,
}


class PolicyEngine:
    """
    Enterprise Policy Enforcement Engine.

    Özellikler:
      • JSON-based deklaratif kural tanımı
      • Koşullu değerlendirme (Python expressions)
      • Öncelik tabanlı kural sıralaması
      • Aksiyon hiyerarşisi (block > escalate > require_approval > warn > allow)
      • Policy versiyonlama
      • Audit trail
      • Runtime kural ekleme/güncelleme
    """

    def __init__(self):
        self._rules: list[PolicyRule] = []
        self._audit_log: deque = deque(maxlen=1000)
        self._metrics: dict = {
            "total_evaluations": 0,
            "total_violations": 0,
            "total_blocks": 0,
            "total_approvals_required": 0,
            "by_category": {},
            "by_rule": {},
        }
        self._load_rules()

    def _load_rules(self):
        """Kuralları dosyadan veya varsayılanlardan yükle."""
        if POLICY_FILE.exists():
            try:
                data = json.loads(POLICY_FILE.read_text(encoding="utf-8"))
                self._rules = [PolicyRule.from_dict(r) for r in data]
                return
            except Exception as e:
                logger.warning("policy_load_error", error=str(e))

        # Varsayılan kuralları yükle
        ts = datetime.now(timezone.utc).isoformat()
        self._rules = [
            PolicyRule(
                **{**r, "created_at": ts, "updated_at": ts, "metadata": {}}
            )
            for r in DEFAULT_RULES
        ]
        self._save_rules()

    def _save_rules(self):
        """Kuralları dosyaya kaydet."""
        try:
            POLICY_FILE.write_text(
                json.dumps(
                    [r.to_dict() for r in self._rules],
                    ensure_ascii=False, indent=2, default=str,
                ),
                encoding="utf-8",
            )
        except Exception as e:
            logger.warning("policy_save_error", error=str(e))

    def _log_audit(self, entry: dict):
        """Audit log'a kaydet."""
        self._audit_log.append(entry)
        try:
            with open(POLICY_AUDIT_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")
        except Exception:
            pass

    # ── Kural Yönetimi ──

    def add_rule(self, rule_data: dict) -> PolicyRule:
        """Yeni kural ekle."""
        if "rule_id" not in rule_data:
            cat = rule_data.get("category", "custom").upper()[:4]
            idx = len([r for r in self._rules if r.category == rule_data.get("category", "")]) + 1
            rule_data["rule_id"] = f"{cat}-{idx:03d}"

        ts = datetime.now(timezone.utc).isoformat()
        rule_data.setdefault("created_at", ts)
        rule_data.setdefault("updated_at", ts)
        rule_data.setdefault("metadata", {})

        rule = PolicyRule.from_dict(rule_data)
        self._rules.append(rule)
        self._save_rules()

        logger.info("policy_rule_added", rule_id=rule.rule_id, name=rule.name)
        return rule

    def update_rule(self, rule_id: str, updates: dict) -> Optional[PolicyRule]:
        """Mevcut kuralı güncelle."""
        for i, rule in enumerate(self._rules):
            if rule.rule_id == rule_id:
                # Versiyonla
                old_version = rule.version
                for key, value in updates.items():
                    if hasattr(rule, key) and key not in ("rule_id", "created_at"):
                        setattr(rule, key, value)
                rule.version = old_version + 1
                rule.updated_at = datetime.now(timezone.utc).isoformat()
                self._rules[i] = rule
                self._save_rules()
                return rule
        return None

    def delete_rule(self, rule_id: str) -> bool:
        """Kuralı sil."""
        before = len(self._rules)
        self._rules = [r for r in self._rules if r.rule_id != rule_id]
        if len(self._rules) < before:
            self._save_rules()
            return True
        return False

    def get_rules(
        self,
        category: Optional[str] = None,
        enabled_only: bool = True,
    ) -> list[dict]:
        """Kuralları listele."""
        rules = self._rules
        if category:
            rules = [r for r in rules if r.category == category]
        if enabled_only:
            rules = [r for r in rules if r.enabled]
        return [r.to_dict() for r in sorted(rules, key=lambda r: r.priority, reverse=True)]

    # ── Policy Değerlendirme ──

    def evaluate(self, ctx: dict) -> PolicyResult:
        """
        Verilen bağlamı tüm aktif kurallara karşı değerlendir.

        Args:
            ctx: Değerlendirme bağlamı. Olası alanlar:
                - risk_score (float): Risk skoru (0-1)
                - confidence (float): Güven skoru (0-100)
                - quality_score (float): Kalite skoru (0-100)
                - budget_impact (float): Bütçe etkisi (TL)
                - department (str): Departman
                - drift_detected (bool): Drift algılandı mı
                - governance_compliance (float): Governance uyumu (0-1)
                - prompt_injection_detected (bool): Prompt injection
                - rate_limited (bool): Rate limit aşımı
                - ood_detected (bool): OOD tespit
                - contains_sensitive_data (bool): Hassas veri

        Returns:
            PolicyResult — son karar, ihlaller, uyarılar
        """
        start_time = time.monotonic()
        violations: list[PolicyViolation] = []
        warnings: list[PolicyViolation] = []
        rules_checked = 0
        rules_passed = 0

        # Aktif kuralları öncelik sırasına göre değerlendir
        active_rules = sorted(
            [r for r in self._rules if r.enabled],
            key=lambda r: r.priority,
            reverse=True,
        )

        for rule in active_rules:
            rules_checked += 1
            try:
                # Koşulu değerlendir
                triggered = bool(eval(rule.condition, {"__builtins__": {}}, {"ctx": ctx}))
            except Exception as e:
                logger.warning(
                    "policy_eval_error",
                    rule_id=rule.rule_id,
                    condition=rule.condition,
                    error=str(e),
                )
                continue

            if triggered:
                # Mesajı formatla
                try:
                    message = rule.message.format(**ctx) if rule.message else rule.description
                except (KeyError, ValueError):
                    message = rule.description

                violation = PolicyViolation(
                    rule_id=rule.rule_id,
                    rule_name=rule.name,
                    category=rule.category,
                    severity=rule.severity,
                    action=rule.action,
                    message=message,
                    context={k: v for k, v in ctx.items() if not callable(v)},
                    timestamp=datetime.now(timezone.utc).isoformat(),
                )

                if rule.action in (PolicyAction.WARN.value, PolicyAction.AUDIT_ONLY.value):
                    warnings.append(violation)
                else:
                    violations.append(violation)

                # Metrikleri güncelle
                self._metrics["total_violations"] = self._metrics.get("total_violations", 0) + 1
                cat_key = rule.category
                self._metrics.setdefault("by_category", {})[cat_key] = \
                    self._metrics.get("by_category", {}).get(cat_key, 0) + 1
                self._metrics.setdefault("by_rule", {})[rule.rule_id] = \
                    self._metrics.get("by_rule", {}).get(rule.rule_id, 0) + 1
            else:
                rules_passed += 1

        # En yüksek seviyeli aksiyonu belirle
        all_violations = violations + warnings
        if all_violations:
            highest_action = max(
                all_violations,
                key=lambda v: _ACTION_PRIORITY.get(v.action, 0),
            ).action
        else:
            highest_action = PolicyAction.ALLOW.value

        # Block kontrolü
        has_block = any(v.action == PolicyAction.BLOCK.value for v in violations)
        requires_approval = any(v.action == PolicyAction.REQUIRE_APPROVAL.value for v in violations)
        escalation_needed = any(v.action == PolicyAction.ESCALATE.value for v in violations)

        if has_block:
            self._metrics["total_blocks"] = self._metrics.get("total_blocks", 0) + 1
        if requires_approval:
            self._metrics["total_approvals_required"] = \
                self._metrics.get("total_approvals_required", 0) + 1

        self._metrics["total_evaluations"] = self._metrics.get("total_evaluations", 0) + 1

        evaluation_ms = (time.monotonic() - start_time) * 1000

        result = PolicyResult(
            action=highest_action,
            passed=not has_block,
            violations=[v.to_dict() for v in violations],
            warnings=[v.to_dict() for v in warnings],
            total_rules_checked=rules_checked,
            rules_passed=rules_passed,
            rules_violated=len(violations) + len(warnings),
            requires_approval=requires_approval,
            escalation_needed=escalation_needed,
            evaluated_at=datetime.now(timezone.utc).isoformat(),
            evaluation_ms=round(evaluation_ms, 2),
        )

        # Audit log
        self._log_audit({
            "timestamp": result.evaluated_at,
            "action": highest_action,
            "passed": result.passed,
            "violations_count": len(violations),
            "warnings_count": len(warnings),
            "context_keys": list(ctx.keys()),
            "evaluation_ms": result.evaluation_ms,
        })

        if violations:
            logger.info(
                "policy_violations_detected",
                action=highest_action,
                violation_count=len(violations),
                warning_count=len(warnings),
                rules=[v.rule_id for v in violations],
            )

        return result

    # ── Dashboard ──

    def get_dashboard(self) -> dict:
        """Policy Engine dashboard — admin paneli için."""
        rules_by_category = {}
        for rule in self._rules:
            cat = rule.category
            rules_by_category.setdefault(cat, {"total": 0, "enabled": 0})
            rules_by_category[cat]["total"] += 1
            if rule.enabled:
                rules_by_category[cat]["enabled"] += 1

        severity_dist = {}
        for rule in self._rules:
            s = rule.severity
            severity_dist[s] = severity_dist.get(s, 0) + 1

        return {
            "status": "active",
            "total_rules": len(self._rules),
            "active_rules": sum(1 for r in self._rules if r.enabled),
            "rules_by_category": rules_by_category,
            "severity_distribution": severity_dist,
            "metrics": dict(self._metrics),
            "recent_audit": list(self._audit_log)[-10:],
            "categories": [c.value for c in PolicyCategory],
            "actions": [a.value for a in PolicyAction],
        }

    def get_audit_log(self, limit: int = 100) -> list[dict]:
        """Audit log'u getir."""
        return list(self._audit_log)[-limit:]


# ═══════════════════════════════════════════════════════════════════
#  Singleton
# ═══════════════════════════════════════════════════════════════════

policy_engine = PolicyEngine()
