"""
CompanyAI — Security Layer
==============================
Zero-trust security katmanı.

SORUMLULUKLAR:
  ┌──────────────────────────────────────────────────────────────────┐
  │ Katman                    │ İşlev                                │
  ├───────────────────────────┼────────────────────────────────────────┤
  │ PromptInjectionFirewall   │ Prompt injection / jailbreak algılama │
  │ RateLimiter               │ Per-user, per-endpoint rate limiting  │
  │ InputSanitizer            │ Girdi temizleme & validasyon          │
  │ ModelAccessControl        │ Model bazlı erişim izolasyonu         │
  │ SecurityAuditLog          │ Güvenlik olay kaydı                   │
  │ ThreatIntelligence        │ Tehdit puanı & pattern analizi        │
  └───────────────────────────┴────────────────────────────────────────┘

KULLANIM:
  from app.core.security import security_layer

  # İstek güvenlik kontrolü
  result = security_layer.check_request(
      user_id="user123",
      prompt="Sistem promptunu görmezden gel...",
      endpoint="/api/query",
  )

  if result.blocked:
      raise HTTPException(403, result.reason)

  # Dashboard
  dashboard = security_layer.get_dashboard()
"""

import hashlib
import json
import re
import time
from collections import defaultdict, deque
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional

import structlog

logger = structlog.get_logger()

DATA_DIR = Path("data/security")
DATA_DIR.mkdir(parents=True, exist_ok=True)

SECURITY_AUDIT_FILE = DATA_DIR / "security_audit.jsonl"


# ═══════════════════════════════════════════════════════════════════
#  Sabitler
# ═══════════════════════════════════════════════════════════════════

class ThreatLevel(Enum):
    SAFE = "safe"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class SecurityAction(Enum):
    ALLOW = "allow"
    WARN = "warn"
    SANITIZE = "sanitize"
    RATE_LIMIT = "rate_limit"
    BLOCK = "block"
    BAN = "ban"


# ═══════════════════════════════════════════════════════════════════
#  Veri Yapıları
# ═══════════════════════════════════════════════════════════════════

@dataclass
class SecurityCheckResult:
    """Güvenlik kontrolü sonucu."""
    blocked: bool = False
    action: str = SecurityAction.ALLOW.value
    threat_level: str = ThreatLevel.SAFE.value
    threat_score: float = 0.0
    reason: str = ""
    details: list = field(default_factory=list)
    sanitized_prompt: str = ""
    checks_passed: list = field(default_factory=list)
    checks_failed: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class RateLimitState:
    """Rate limit durum bilgisi."""
    request_count: int = 0
    window_start: float = 0.0
    blocked_until: float = 0.0
    total_blocked: int = 0


# ═══════════════════════════════════════════════════════════════════
#  Prompt Injection Firewall
# ═══════════════════════════════════════════════════════════════════

# Prompt injection pattern'leri — regex tabanlı
INJECTION_PATTERNS: list[dict] = [
    {
        "name": "system_override",
        "pattern": r"(?:ignore|disregard|forget|skip|bypass)\s+(?:all\s+)?(?:previous|above|prior|earlier|system)\s+(?:instructions?|prompts?|rules?|context)",
        "severity": 0.9,
        "description": "Sistem promptu geçersiz kılma girişimi",
    },
    {
        "name": "role_hijack",
        "pattern": r"(?:you\s+are\s+now|act\s+as|pretend\s+to\s+be|roleplay\s+as|switch\s+to)\s+(?:a\s+)?(?:different|new|another|hacker|admin|root)",
        "severity": 0.85,
        "description": "Rol değiştirme saldırısı",
    },
    {
        "name": "prompt_leak",
        "pattern": r"(?:show|reveal|display|print|output|repeat|tell\s+me)\s+(?:your\s+)?(?:system\s+)?(?:prompt|instructions?|rules?|initial\s+message|configuration)",
        "severity": 0.7,
        "description": "Sistem promptu sızdırma girişimi",
    },
    {
        "name": "delimiter_attack",
        "pattern": r"(?:```|---|\*\*\*|===|###)\s*(?:system|admin|root|assistant)\s*(?:```|---|\*\*\*|===|###)",
        "severity": 0.8,
        "description": "Delimiter tabanlı injection",
    },
    {
        "name": "encoding_attack",
        "pattern": r"(?:base64|hex|rot13|decode|encode)\s*[:=]\s*[A-Za-z0-9+/=]{20,}",
        "severity": 0.75,
        "description": "Encoding tabanlı kaçırma girişimi",
    },
    {
        "name": "context_manipulation",
        "pattern": r"(?:new\s+context|reset\s+context|clear\s+(?:your\s+)?memory|start\s+(?:a\s+)?new\s+(?:session|conversation))\s*[:.]",
        "severity": 0.65,
        "description": "Context manipülasyonu",
    },
    {
        "name": "sql_injection",
        "pattern": r"(?:UNION\s+SELECT|DROP\s+TABLE|DELETE\s+FROM|INSERT\s+INTO|UPDATE\s+\w+\s+SET|;\s*--|\'\s+OR\s+['\d])",
        "severity": 0.9,
        "description": "SQL injection girişimi",
    },
    {
        "name": "command_injection",
        "pattern": r"(?:;\s*(?:rm|cat|ls|wget|curl|bash|sh|python|perl|ruby)\s|`[^`]+`|\$\([^)]+\))",
        "severity": 0.95,
        "description": "Komut enjeksiyonu",
    },
    {
        "name": "jailbreak_dan",
        "pattern": r"(?:DAN|Do\s+Anything\s+Now|jailbreak|uncensored\s+mode|god\s+mode|developer\s+mode|DUDE\s+mode)",
        "severity": 0.85,
        "description": "Jailbreak / DAN modu girişimi",
    },
    {
        "name": "turkish_injection",
        "pattern": r"(?:sistem\s+(?:promptunu|talimatlarını)\s+(?:görmezden\s+gel|unut|atla|yoksay)|kuralları\s+(?:unut|sil|geçersiz\s+kıl)|yönetici\s+olarak\s+davran)",
        "severity": 0.8,
        "description": "Türkçe prompt injection girişimi",
    },
]

# Compiled patterns (performans için)
_COMPILED_PATTERNS: list[dict] = []
for p in INJECTION_PATTERNS:
    try:
        _COMPILED_PATTERNS.append({
            **p,
            "_compiled": re.compile(p["pattern"], re.IGNORECASE | re.DOTALL),
        })
    except re.error:
        pass


class PromptInjectionFirewall:
    """
    Prompt injection / jailbreak algılama motoru.
    Çoklu pattern eşleştirme + risk puanlama.
    """

    def __init__(self):
        self._detection_count = 0
        self._false_positive_reports: deque = deque(maxlen=100)

    def scan(self, prompt: str) -> tuple[float, list[dict]]:
        """
        Promptu tara, tehdit skoru ve eşleşen pattern'leri döndür.

        Returns:
            (threat_score, matched_patterns)
        """
        if not prompt or not prompt.strip():
            return 0.0, []

        matched = []
        max_severity = 0.0

        for pattern_info in _COMPILED_PATTERNS:
            compiled = pattern_info["_compiled"]
            if compiled.search(prompt):
                matched.append({
                    "name": pattern_info["name"],
                    "severity": pattern_info["severity"],
                    "description": pattern_info["description"],
                })
                max_severity = max(max_severity, pattern_info["severity"])

        # Çoklu pattern eşleşmesi risk'i artırır
        if len(matched) > 1:
            max_severity = min(1.0, max_severity + 0.1 * (len(matched) - 1))

        if matched:
            self._detection_count += 1

        return max_severity, matched

    def report_false_positive(self, prompt_hash: str, reason: str):
        """Yanlış pozitif raporu."""
        self._false_positive_reports.append({
            "prompt_hash": prompt_hash,
            "reason": reason,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    @property
    def stats(self) -> dict:
        return {
            "total_detections": self._detection_count,
            "pattern_count": len(_COMPILED_PATTERNS),
            "false_positive_reports": len(self._false_positive_reports),
        }


# ═══════════════════════════════════════════════════════════════════
#  Rate Limiter
# ═══════════════════════════════════════════════════════════════════

# Varsayılan limitler
DEFAULT_LIMITS = {
    "query": {"requests": 30, "window_seconds": 60},       # 30 req/dk
    "admin": {"requests": 60, "window_seconds": 60},       # 60 req/dk
    "upload": {"requests": 10, "window_seconds": 300},     # 10 req/5dk
    "default": {"requests": 50, "window_seconds": 60},     # 50 req/dk
}


class RateLimiter:
    """
    Sliding window rate limiter.
    Per-user, per-endpoint rate limiting.
    """

    def __init__(self, limits: Optional[dict] = None):
        self._limits = limits or DEFAULT_LIMITS
        self._states: dict[str, RateLimitState] = {}     # key: user:endpoint
        self._blocked_users: dict[str, float] = {}       # user_id → blocked_until
        self._total_limited = 0

    def check(self, user_id: str, endpoint: str = "default") -> tuple[bool, str]:
        """
        Rate limit kontrolü.

        Returns:
            (is_allowed, reason)
        """
        now = time.time()

        # Kalıcı ban kontrolü
        if user_id in self._blocked_users:
            if now < self._blocked_users[user_id]:
                return False, f"Kullanıcı geçici olarak engellendi. Kalan: {int(self._blocked_users[user_id] - now)}s"
            else:
                del self._blocked_users[user_id]

        # Endpoint kategori belirleme
        category = "default"
        for cat in self._limits:
            if cat in endpoint:
                category = cat
                break

        limit_config = self._limits.get(category, self._limits["default"])
        max_requests = limit_config["requests"]
        window = limit_config["window_seconds"]

        key = f"{user_id}:{category}"
        state = self._states.get(key)

        if state is None:
            state = RateLimitState(request_count=1, window_start=now)
            self._states[key] = state
            return True, ""

        # Window süresi doldu → sıfırla
        elapsed = now - state.window_start
        if elapsed >= window:
            state.request_count = 1
            state.window_start = now
            return True, ""

        # Limit kontrolü
        state.request_count += 1
        if state.request_count > max_requests:
            state.total_blocked += 1
            self._total_limited += 1
            remaining = window - elapsed
            return False, f"Rate limit aşıldı ({category}: {max_requests}/{window}s). Kalan: {int(remaining)}s"

        return True, ""

    def block_user(self, user_id: str, duration_seconds: int = 3600):
        """Kullanıcıyı geçici olarak engelle."""
        self._blocked_users[user_id] = time.time() + duration_seconds

    def unblock_user(self, user_id: str):
        """Engeli kaldır."""
        self._blocked_users.pop(user_id, None)

    @property
    def stats(self) -> dict:
        return {
            "total_rate_limited": self._total_limited,
            "active_blocks": len(self._blocked_users),
            "tracked_keys": len(self._states),
        }


# ═══════════════════════════════════════════════════════════════════
#  Input Sanitizer
# ═══════════════════════════════════════════════════════════════════

class InputSanitizer:
    """
    Girdi temizleme & validasyon.
    """

    MAX_PROMPT_LENGTH = 10000    # Karakter
    MAX_CONTEXT_SIZE = 50000     # Karakter

    def sanitize(self, prompt: str) -> tuple[str, list[str]]:
        """
        Promptu temizle, uygulanan işlemleri döndür.

        Returns:
            (sanitized_prompt, applied_actions)
        """
        actions = []

        if not prompt:
            return "", ["empty_input"]

        # Uzunluk kontrolü
        if len(prompt) > self.MAX_PROMPT_LENGTH:
            prompt = prompt[:self.MAX_PROMPT_LENGTH]
            actions.append(f"truncated_to_{self.MAX_PROMPT_LENGTH}_chars")

        # Null byte temizleme
        if "\x00" in prompt:
            prompt = prompt.replace("\x00", "")
            actions.append("null_bytes_removed")

        # Kontrol karakterleri temizleme
        control_chars = "".join(
            chr(c) for c in range(32) if c not in (9, 10, 13)  # tab, newline, cr hariç
        )
        if any(c in prompt for c in control_chars):
            prompt = prompt.translate(str.maketrans("", "", control_chars))
            actions.append("control_chars_removed")

        # Aşırı boşluk temizleme
        clean = re.sub(r" {10,}", "    ", prompt)
        if clean != prompt:
            prompt = clean
            actions.append("excessive_spaces_reduced")

        # Aşırı newline temizleme
        clean = re.sub(r"\n{5,}", "\n\n\n", prompt)
        if clean != prompt:
            prompt = clean
            actions.append("excessive_newlines_reduced")

        return prompt.strip(), actions


# ═══════════════════════════════════════════════════════════════════
#  Model Access Control
# ═══════════════════════════════════════════════════════════════════

# Varsayılan model erişim politikası
DEFAULT_MODEL_PERMISSIONS = {
    "admin": ["*"],                                     # Tüm modellere erişim
    "manager": ["qwen2.5:72b*", "gpt-4*", "claude*"],  # Büyük modellere erişim
    "analyst": ["qwen2.5:72b*", "gpt-3.5*"],           # Standart modeller
    "viewer": [],                                       # Model erişimi yok
}


class ModelAccessControl:
    """
    Model bazlı erişim kontrolü.
    Kullanıcı rolüne göre model erişimini kısıtlar.
    """

    def __init__(self, permissions: Optional[dict] = None):
        self._permissions = permissions or DEFAULT_MODEL_PERMISSIONS
        self._access_log: deque = deque(maxlen=500)

    def check_access(
        self, user_role: str, model_name: str, user_id: str = ""
    ) -> tuple[bool, str]:
        """
        Model erişim kontrolü.

        Returns:
            (allowed, reason)
        """
        allowed_patterns = self._permissions.get(user_role, [])

        if not allowed_patterns:
            self._log_access(user_id, user_role, model_name, False)
            return False, f"'{user_role}' rolü için model erişimi tanımlı değil."

        for pattern in allowed_patterns:
            if pattern == "*":
                self._log_access(user_id, user_role, model_name, True)
                return True, ""
            # Wildcard matching
            regex = pattern.replace("*", ".*")
            if re.match(regex, model_name, re.IGNORECASE):
                self._log_access(user_id, user_role, model_name, True)
                return True, ""

        self._log_access(user_id, user_role, model_name, False)
        return False, f"'{user_role}' rolü '{model_name}' modeline erişemez."

    def _log_access(self, user_id: str, role: str, model: str, allowed: bool):
        self._access_log.append({
            "user_id": user_id,
            "role": role,
            "model": model,
            "allowed": allowed,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    def update_permissions(self, role: str, allowed_models: list[str]):
        """Rol bazlı model izinlerini güncelle."""
        self._permissions[role] = allowed_models

    @property
    def stats(self) -> dict:
        total = len(self._access_log)
        denied = sum(1 for a in self._access_log if not a["allowed"])
        return {
            "total_checks": total,
            "denied_count": denied,
            "denial_rate_pct": round(denied / total * 100, 1) if total > 0 else 0.0,
            "roles_defined": len(self._permissions),
        }


# ═══════════════════════════════════════════════════════════════════
#  Security Audit Log
# ═══════════════════════════════════════════════════════════════════

class SecurityAuditLog:
    """Güvenlik olayları audit log — append-only JSONL."""

    def __init__(self, path: Path = SECURITY_AUDIT_FILE):
        self._path = path
        self._recent: deque = deque(maxlen=200)

    def log_event(
        self,
        event_type: str,
        user_id: str = "",
        details: Optional[dict] = None,
        threat_level: str = ThreatLevel.SAFE.value,
    ):
        """Güvenlik olayını kaydet."""
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "user_id": user_id,
            "threat_level": threat_level,
            "details": details or {},
        }

        self._recent.append(entry)

        try:
            with open(self._path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.error("security_audit_write_failed", error=str(e))

    def get_recent(self, limit: int = 20) -> list[dict]:
        return list(self._recent)[-limit:]

    def get_by_threat_level(self, level: str) -> list[dict]:
        return [e for e in self._recent if e.get("threat_level") == level]


# ═══════════════════════════════════════════════════════════════════
#  Threat Intelligence
# ═══════════════════════════════════════════════════════════════════

class ThreatIntelligence:
    """
    Kullanıcı bazlı tehdit puanlama.
    Geçmiş davranışlara göre tehdit skoru hesaplar.
    """

    def __init__(self):
        self._user_threat_history: dict[str, deque] = defaultdict(
            lambda: deque(maxlen=100)
        )
        self._user_scores: dict[str, float] = {}

    def record_threat(self, user_id: str, threat_score: float, event_type: str):
        """Kullanıcı için tehdit olayı kaydet."""
        self._user_threat_history[user_id].append({
            "score": threat_score,
            "type": event_type,
            "timestamp": time.time(),
        })
        self._recalculate_score(user_id)

    def get_user_score(self, user_id: str) -> float:
        """Kullanıcı tehdit puanı (0.0-1.0)."""
        return self._user_scores.get(user_id, 0.0)

    def _recalculate_score(self, user_id: str):
        """
        Tehdit puanını yeniden hesapla.
        Recent events ağırlıklı exponential decay.
        """
        events = list(self._user_threat_history[user_id])
        if not events:
            self._user_scores[user_id] = 0.0
            return

        now = time.time()
        total_weight = 0.0
        weighted_score = 0.0

        for event in events:
            age_hours = (now - event["timestamp"]) / 3600
            # 24 saat sonra ağırlık yarıya düşer
            decay = 0.5 ** (age_hours / 24)
            weight = decay
            total_weight += weight
            weighted_score += event["score"] * weight

        if total_weight > 0:
            self._user_scores[user_id] = min(1.0, weighted_score / total_weight)
        else:
            self._user_scores[user_id] = 0.0

    def get_high_risk_users(self, threshold: float = 0.5) -> list[dict]:
        """Yüksek riskli kullanıcılar."""
        return [
            {"user_id": uid, "threat_score": round(score, 3)}
            for uid, score in self._user_scores.items()
            if score >= threshold
        ]


# ═══════════════════════════════════════════════════════════════════
#  Ana Security Layer
# ═══════════════════════════════════════════════════════════════════

class SecurityLayer:
    """
    Enterprise Security Layer — Tüm güvenlik kontrollerini orkestre eder.

    Güvenlik kontrol sırası:
      1. Rate limit → aşırı istek engelle
      2. Input sanitization → girdi temizle
      3. Prompt injection scan → saldırı algıla
      4. Model access control → erişim kontrolü
      5. Threat intelligence → kullanıcı risk puanı
      6. Audit log → her şeyi kaydet
    """

    def __init__(self):
        self.firewall = PromptInjectionFirewall()
        self.rate_limiter = RateLimiter()
        self.sanitizer = InputSanitizer()
        self.model_access = ModelAccessControl()
        self.audit_log = SecurityAuditLog()
        self.threat_intel = ThreatIntelligence()
        self._total_checks = 0
        self._total_blocked = 0

    def check_request(
        self,
        user_id: str = "",
        prompt: str = "",
        endpoint: str = "default",
        user_role: str = "analyst",
        model_name: str = "",
    ) -> SecurityCheckResult:
        """
        Tam güvenlik kontrolü pipeline'ı.

        Returns:
            SecurityCheckResult
        """
        self._total_checks += 1
        result = SecurityCheckResult(sanitized_prompt=prompt)
        failed_checks = []
        passed_checks = []

        # 1) Rate Limit
        allowed, rate_reason = self.rate_limiter.check(user_id, endpoint)
        if not allowed:
            result.blocked = True
            result.action = SecurityAction.RATE_LIMIT.value
            result.threat_level = ThreatLevel.MEDIUM.value
            result.reason = rate_reason
            failed_checks.append("rate_limit")
            self._total_blocked += 1
            self.audit_log.log_event(
                "rate_limit_exceeded",
                user_id=user_id,
                details={"endpoint": endpoint, "reason": rate_reason},
                threat_level=ThreatLevel.MEDIUM.value,
            )
            result.checks_failed = failed_checks
            return result
        passed_checks.append("rate_limit")

        # 2) Input Sanitization
        sanitized, sanitize_actions = self.sanitizer.sanitize(prompt)
        result.sanitized_prompt = sanitized
        if sanitize_actions and sanitize_actions != ["empty_input"]:
            passed_checks.append(f"sanitized:{','.join(sanitize_actions)}")
        else:
            passed_checks.append("sanitization")

        # 3) Prompt Injection Scan
        threat_score, matched_patterns = self.firewall.scan(sanitized)
        if threat_score > 0:
            result.threat_score = threat_score
            result.details = matched_patterns

            if threat_score >= 0.8:
                result.blocked = True
                result.action = SecurityAction.BLOCK.value
                result.threat_level = ThreatLevel.HIGH.value
                result.reason = f"Yüksek tehdit algılandı: {', '.join(p['name'] for p in matched_patterns)}"
                failed_checks.append("prompt_injection")
                self._total_blocked += 1

                # Tehdit kaydı
                self.threat_intel.record_threat(user_id, threat_score, "prompt_injection")

                self.audit_log.log_event(
                    "prompt_injection_blocked",
                    user_id=user_id,
                    details={
                        "prompt_hash": hashlib.sha256(prompt.encode()).hexdigest()[:16],
                        "threat_score": threat_score,
                        "patterns": [p["name"] for p in matched_patterns],
                    },
                    threat_level=ThreatLevel.HIGH.value,
                )
            elif threat_score >= 0.5:
                result.action = SecurityAction.WARN.value
                result.threat_level = ThreatLevel.MEDIUM.value
                passed_checks.append("prompt_injection_warned")

                self.threat_intel.record_threat(user_id, threat_score * 0.5, "suspicious_prompt")

                self.audit_log.log_event(
                    "prompt_injection_warning",
                    user_id=user_id,
                    details={
                        "threat_score": threat_score,
                        "patterns": [p["name"] for p in matched_patterns],
                    },
                    threat_level=ThreatLevel.MEDIUM.value,
                )
            else:
                passed_checks.append("prompt_injection_low_risk")
        else:
            passed_checks.append("prompt_injection")

        if result.blocked:
            result.checks_passed = passed_checks
            result.checks_failed = failed_checks
            return result

        # 4) Model Access Control (opsiyonel)
        if model_name:
            model_allowed, model_reason = self.model_access.check_access(
                user_role, model_name, user_id
            )
            if not model_allowed:
                result.blocked = True
                result.action = SecurityAction.BLOCK.value
                result.threat_level = ThreatLevel.MEDIUM.value
                result.reason = model_reason
                failed_checks.append("model_access")
                self._total_blocked += 1
                self.audit_log.log_event(
                    "model_access_denied",
                    user_id=user_id,
                    details={"model": model_name, "role": user_role},
                    threat_level=ThreatLevel.MEDIUM.value,
                )
                result.checks_passed = passed_checks
                result.checks_failed = failed_checks
                return result
            passed_checks.append("model_access")

        # 5) Threat Intelligence — yüksek risk puanlı kullanıcıları kontrol et
        user_threat_score = self.threat_intel.get_user_score(user_id)
        if user_threat_score >= 0.8:
            result.blocked = True
            result.action = SecurityAction.BLOCK.value
            result.threat_level = ThreatLevel.HIGH.value
            result.reason = f"Kullanıcı tehdit puanı çok yüksek: {user_threat_score:.2f}"
            failed_checks.append("threat_intelligence")
            self._total_blocked += 1
            self.audit_log.log_event(
                "high_risk_user_blocked",
                user_id=user_id,
                details={"threat_score": user_threat_score},
                threat_level=ThreatLevel.HIGH.value,
            )
        elif user_threat_score >= 0.5:
            passed_checks.append(f"threat_intel_elevated:{user_threat_score:.2f}")
        else:
            passed_checks.append("threat_intelligence")

        result.checks_passed = passed_checks
        result.checks_failed = failed_checks
        return result

    # ── Dashboard ──

    def get_dashboard(self) -> dict:
        """Security Layer dashboard — admin paneli için."""
        return {
            "status": "active",
            "total_checks": self._total_checks,
            "total_blocked": self._total_blocked,
            "block_rate_pct": round(
                self._total_blocked / self._total_checks * 100, 1
            ) if self._total_checks > 0 else 0.0,
            "firewall_stats": self.firewall.stats,
            "rate_limiter_stats": self.rate_limiter.stats,
            "model_access_stats": self.model_access.stats,
            "high_risk_users": self.threat_intel.get_high_risk_users(),
            "recent_security_events": self.audit_log.get_recent(10),
            "injection_patterns_loaded": len(_COMPILED_PATTERNS),
        }


# ═══════════════════════════════════════════════════════════════════
#  Singleton
# ═══════════════════════════════════════════════════════════════════

security_layer = SecurityLayer()
