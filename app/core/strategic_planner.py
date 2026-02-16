"""Strategic Planner v1.0 — Kurumsal Stratejik Planlama Motoru

Mevcut analiz modüllerinin (risk_analyzer, forecasting, kpi_engine,
scenario_engine, decision_ranking) çıktılarını birleştirerek
bütüncül stratejik planlar oluşturur.

Bileşenler:
  1. EnvironmentScanner     → PESTEL + 5 Forces iç/dış çevre taraması
  2. StrategicGoalEngine    → SMART hedef üretimi + OKR dönüşümü
  3. StrategyFormulator     → Mevcut durum × Hedef → Strateji alternatifleri
  4. ActionPlanBuilder      → Strateji → Zaman çizelgesi + sorumlu + KPI
  5. RiskMitigationPlanner  → Her stratejiye risk overlay + B/C planları
  6. StrategicTracker       → Geçmiş planlar ve başarı takibi

Kullanım Alanları:
  - "5 yıllık büyüme planı oluştur"
  - "Dijital dönüşüm stratejisi öner"
  - "Yeni pazara giriş planı hazırla"
  - "Maliyet optimizasyonu yol haritası çıkar"

v5.0.0 — CompanyAI Enterprise
"""

from __future__ import annotations

import uuid
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

import structlog

logger = structlog.get_logger(__name__)

# ═══════════════════════════════════════════════════════════════════
# SABİTLER
# ═══════════════════════════════════════════════════════════════════

MAX_GOALS = 7
MAX_STRATEGIES_PER_GOAL = 4
MAX_ACTIONS_PER_STRATEGY = 8
MAX_PLAN_HISTORY = 200
STRATEGIC_TRIGGER_MIN_LENGTH = 30

STRATEGIC_TRIGGER_KEYWORDS = [
    "strateji", "plan", "hedef", "vizyon", "misyon", "yol haritası",
    "roadmap", "büyüme", "dönüşüm", "genişleme", "yatırım",
    "5 yıl", "3 yıl", "uzun vadeli", "kısa vadeli", "orta vadeli",
    "strategy", "strategic", "OKR", "KPI hedef",
    "pazar", "rekabet", "avantaj", "fırsat", "pozisyon",
]

PESTEL_DIMENSIONS = [
    "Politik (Political)",
    "Ekonomik (Economic)",
    "Sosyal (Social)",
    "Teknolojik (Technological)",
    "Çevresel (Environmental)",
    "Yasal (Legal)",
]

PORTER_FORCES = [
    "Sektördeki Rekabet Yoğunluğu",
    "Yeni Giriş Tehdidi",
    "İkame Ürün/Hizmet Tehdidi",
    "Tedarikçilerin Pazarlık Gücü",
    "Alıcıların Pazarlık Gücü",
]


def _utcnow_str() -> str:
    return datetime.now(timezone.utc).isoformat()


# ═══════════════════════════════════════════════════════════════════
# ENUM & VERİ YAPILARI
# ═══════════════════════════════════════════════════════════════════

class TimeHorizon(str, Enum):
    SHORT = "short_term"       # 0-6 ay
    MEDIUM = "medium_term"     # 6-18 ay
    LONG = "long_term"         # 18-60 ay
    VISIONARY = "visionary"    # 5+ yıl


class StrategyType(str, Enum):
    GROWTH = "growth"                 # Büyüme
    COST_LEADERSHIP = "cost_leadership"  # Maliyet liderliği
    DIFFERENTIATION = "differentiation"  # Farklılaşma
    FOCUS = "focus"                   # Odaklanma / Niş
    DIGITAL_TRANSFORM = "digital_transform"  # Dijital dönüşüm
    INNOVATION = "innovation"         # İnovasyon
    TURNAROUND = "turnaround"         # Kriz yönetimi / dönüş
    DIVERSIFICATION = "diversification"  # Çeşitlendirme


class GoalStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    DEFERRED = "deferred"


class Priority(str, Enum):
    CRITICAL = "critical"    # P0
    HIGH = "high"            # P1
    MEDIUM = "medium"        # P2
    LOW = "low"              # P3


# ─── Veri yapıları ───

@dataclass
class PESTELFactor:
    """PESTEL analizinde bir faktör."""
    dimension: str
    factor: str
    impact: str           # "olumlu" / "olumsuz" / "belirsiz"
    impact_score: float   # -1.0 (çok olumsuz) — +1.0 (çok olumlu)
    probability: float    # 0-1
    time_horizon: TimeHorizon = TimeHorizon.MEDIUM
    description: str = ""

    def to_dict(self) -> dict:
        return {
            "dimension": self.dimension,
            "factor": self.factor,
            "impact": self.impact,
            "impact_score": round(self.impact_score, 2),
            "probability": round(self.probability, 2),
            "time_horizon": self.time_horizon.value,
            "description": self.description,
        }


@dataclass
class PorterForce:
    """Porter 5 Forces analizinde bir güç."""
    force: str
    intensity: float           # 0-1 (düşük-yüksek)
    key_drivers: List[str] = field(default_factory=list)
    strategic_implication: str = ""

    def to_dict(self) -> dict:
        return {
            "force": self.force,
            "intensity": round(self.intensity, 2),
            "key_drivers": self.key_drivers,
            "strategic_implication": self.strategic_implication,
        }


@dataclass
class SWOTItem:
    """SWOT analizinde bir madde."""
    category: str   # Strengths / Weaknesses / Opportunities / Threats
    item: str
    importance: float = 0.5  # 0-1
    related_pestel: str = ""

    def to_dict(self) -> dict:
        return {
            "category": self.category,
            "item": self.item,
            "importance": round(self.importance, 2),
            "related_pestel": self.related_pestel,
        }


@dataclass
class StrategicGoal:
    """SMART stratejik hedef."""
    goal_id: str = ""
    title: str = ""
    description: str = ""
    specific: str = ""       # Ne yapılacak?
    measurable: str = ""     # Nasıl ölçülecek?
    achievable: str = ""     # Neden ulaşılabilir?
    relevant: str = ""       # Neden önemli?
    time_bound: str = ""     # Ne zamana kadar?
    time_horizon: TimeHorizon = TimeHorizon.MEDIUM
    priority: Priority = Priority.MEDIUM
    department: str = ""
    kpis: List[str] = field(default_factory=list)
    status: GoalStatus = GoalStatus.DRAFT

    def __post_init__(self):
        if not self.goal_id:
            self.goal_id = f"SG-{uuid.uuid4().hex[:6]}"

    def to_dict(self) -> dict:
        return {
            "goal_id": self.goal_id,
            "title": self.title,
            "description": self.description,
            "smart": {
                "specific": self.specific,
                "measurable": self.measurable,
                "achievable": self.achievable,
                "relevant": self.relevant,
                "time_bound": self.time_bound,
            },
            "time_horizon": self.time_horizon.value,
            "priority": self.priority.value,
            "department": self.department,
            "kpis": self.kpis,
            "status": self.status.value,
        }


@dataclass
class StrategyAlternative:
    """Bir stratejik alternatif."""
    strategy_id: str = ""
    name: str = ""
    strategy_type: StrategyType = StrategyType.GROWTH
    description: str = ""
    target_goal_id: str = ""
    pros: List[str] = field(default_factory=list)
    cons: List[str] = field(default_factory=list)
    estimated_cost: str = ""       # "Düşük" / "Orta" / "Yüksek"
    estimated_roi: str = ""        # "x1.5", "%20 artış" vb.
    implementation_time: str = ""  # "3-6 ay"
    risk_level: float = 0.5
    feasibility: float = 0.5      # 0-1
    selected: bool = False

    def __post_init__(self):
        if not self.strategy_id:
            self.strategy_id = f"SA-{uuid.uuid4().hex[:6]}"

    def to_dict(self) -> dict:
        return {
            "strategy_id": self.strategy_id,
            "name": self.name,
            "type": self.strategy_type.value,
            "description": self.description,
            "target_goal_id": self.target_goal_id,
            "pros": self.pros,
            "cons": self.cons,
            "estimated_cost": self.estimated_cost,
            "estimated_roi": self.estimated_roi,
            "implementation_time": self.implementation_time,
            "risk_level": round(self.risk_level, 2),
            "feasibility": round(self.feasibility, 2),
            "selected": self.selected,
        }


@dataclass
class ActionItem:
    """Bir eylem planı maddesi."""
    action_id: str = ""
    title: str = ""
    description: str = ""
    strategy_id: str = ""
    responsible: str = ""    # Departman veya rol
    deadline: str = ""       # "Q1 2026", "Mart 2026"
    resources_needed: List[str] = field(default_factory=list)
    success_criteria: str = ""
    dependencies: List[str] = field(default_factory=list)
    priority: Priority = Priority.MEDIUM
    estimated_effort: str = "" # "2 kişi × 4 hafta"

    def __post_init__(self):
        if not self.action_id:
            self.action_id = f"ACT-{uuid.uuid4().hex[:6]}"

    def to_dict(self) -> dict:
        return {
            "action_id": self.action_id,
            "title": self.title,
            "description": self.description,
            "strategy_id": self.strategy_id,
            "responsible": self.responsible,
            "deadline": self.deadline,
            "resources_needed": self.resources_needed,
            "success_criteria": self.success_criteria,
            "dependencies": self.dependencies,
            "priority": self.priority.value,
            "estimated_effort": self.estimated_effort,
        }


@dataclass
class RiskMitigation:
    """Bir risk ve azaltma planı."""
    risk_id: str = ""
    risk_description: str = ""
    probability: float = 0.5
    impact: float = 0.5
    strategy_id: str = ""
    mitigation_plan: str = ""        # Plan A
    contingency_plan: str = ""       # Plan B
    early_warning_signs: List[str] = field(default_factory=list)
    owner: str = ""

    def __post_init__(self):
        if not self.risk_id:
            self.risk_id = f"RM-{uuid.uuid4().hex[:6]}"

    @property
    def risk_score(self) -> float:
        return round(self.probability * self.impact, 2)

    def to_dict(self) -> dict:
        return {
            "risk_id": self.risk_id,
            "risk_description": self.risk_description,
            "probability": round(self.probability, 2),
            "impact": round(self.impact, 2),
            "risk_score": self.risk_score,
            "strategy_id": self.strategy_id,
            "mitigation_plan": self.mitigation_plan,
            "contingency_plan": self.contingency_plan,
            "early_warning_signs": self.early_warning_signs,
            "owner": self.owner,
        }


@dataclass
class StrategicPlan:
    """Tam stratejik plan."""
    plan_id: str = ""
    title: str = ""
    question: str = ""
    department: str = ""
    mode: str = ""
    timestamp: str = ""
    time_horizon: TimeHorizon = TimeHorizon.MEDIUM
    # Analiz bileşenleri
    pestel: List[PESTELFactor] = field(default_factory=list)
    porter_forces: List[PorterForce] = field(default_factory=list)
    swot: List[SWOTItem] = field(default_factory=list)
    goals: List[StrategicGoal] = field(default_factory=list)
    strategies: List[StrategyAlternative] = field(default_factory=list)
    action_plan: List[ActionItem] = field(default_factory=list)
    risk_mitigations: List[RiskMitigation] = field(default_factory=list)
    # Meta
    confidence_adjustment: float = 0.0
    total_time_ms: float = 0.0
    triggered_by: str = "auto"

    def __post_init__(self):
        if not self.plan_id:
            self.plan_id = f"SP-{uuid.uuid4().hex[:8]}"
        if not self.timestamp:
            self.timestamp = _utcnow_str()

    def to_dict(self) -> dict:
        return {
            "plan_id": self.plan_id,
            "title": self.title,
            "question": self.question[:200],
            "department": self.department,
            "mode": self.mode,
            "timestamp": self.timestamp,
            "time_horizon": self.time_horizon.value,
            "pestel": [p.to_dict() for p in self.pestel],
            "porter_forces": [f.to_dict() for f in self.porter_forces],
            "swot": [s.to_dict() for s in self.swot],
            "goals": [g.to_dict() for g in self.goals],
            "strategies": [s.to_dict() for s in self.strategies],
            "action_plan": [a.to_dict() for a in self.action_plan],
            "risk_mitigations": [r.to_dict() for r in self.risk_mitigations],
            "summary": self._build_summary(),
            "confidence_adjustment": self.confidence_adjustment,
            "total_time_ms": round(self.total_time_ms, 1),
            "triggered_by": self.triggered_by,
        }

    def _build_summary(self) -> dict:
        """Plan özet metrikleri."""
        critical_risks = [r for r in self.risk_mitigations if r.risk_score >= 0.6]
        return {
            "total_goals": len(self.goals),
            "total_strategies": len(self.strategies),
            "total_actions": len(self.action_plan),
            "total_risks": len(self.risk_mitigations),
            "critical_risks": len(critical_risks),
            "selected_strategies": sum(1 for s in self.strategies if s.selected),
        }


# ═══════════════════════════════════════════════════════════════════
# TETİKLEME KARARI
# ═══════════════════════════════════════════════════════════════════

def should_trigger_strategic_planning(
    question: str,
    mode: str,
    intent: str,
    force: bool = False,
) -> Tuple[bool, str]:
    """Bu soru stratejik planlama gerektirir mi?"""
    if force:
        return True, "manual_trigger"

    if len(question.strip()) < STRATEGIC_TRIGGER_MIN_LENGTH:
        return False, "too_short"

    if intent in ("sohbet", "selamlama"):
        return False, "casual_intent"

    q_lower = question.lower()
    keyword_hits = sum(1 for kw in STRATEGIC_TRIGGER_KEYWORDS if kw in q_lower)

    if keyword_hits >= 2:
        return True, f"keyword_trigger:{keyword_hits}_hits"

    if mode in ("Üst Düzey Analiz", "CEO Raporu"):
        if keyword_hits >= 1:
            return True, f"mode_trigger:{mode}"

    import re
    patterns = [
        r"strateji\w*\s+plan",
        r"yol\s*haritası",
        r"roadmap",
        r"büyüme\s+plan",
        r"\d+\s*yıllık\s+plan",
        r"hedef\w*\s+belirle",
        r"vizyon\w*\s+(oluştur|belirle|çiz)",
        r"dönüşüm\s+strateji",
    ]
    for pattern in patterns:
        if re.search(pattern, q_lower):
            return True, f"pattern_trigger:{pattern}"

    return False, "no_trigger"


# ═══════════════════════════════════════════════════════════════════
# ÇEVRE TARAMASI — PESTEL + Porter
# ═══════════════════════════════════════════════════════════════════

class EnvironmentScanner:
    """Dış çevre analizi: PESTEL + Porter 5 Forces + SWOT."""

    @staticmethod
    def build_pestel_prompt(
        problem: str,
        department: str,
        industry: str = "Tekstil",
    ) -> Tuple[str, str]:
        dims = "\n".join(f"  - {d}" for d in PESTEL_DIMENSIONS)
        system_prompt = (
            "Sen bir Stratejik Çevre Analizi Uzmanısın. PESTEL analizi yapıyorsun.\n\n"
            f"Boyutlar:\n{dims}\n\n"
            "Her boyut için:\n"
            "1. Önemli faktörü belirt\n"
            "2. Etki yönünü: olumlu / olumsuz / belirsiz\n"
            "3. Etki puanı: -1.0 (çok olumsuz) — +1.0 (çok olumlu)\n"
            "4. Gerçekleşme olasılığı: %0-100\n"
            "5. Zaman ufku: kısa / orta / uzun\n\n"
            f"Sektör: {industry} | Departman: {department}\n\n"
            "Format:\n"
            "### Politik\n"
            "- [Faktör]: [açıklama] | Etki: [olumlu/olumsuz] | Skor: [±X.X] | Olasılık: [%X] | Vade: [kısa/orta/uzun]\n"
        )
        user_prompt = f"Konu: {problem}"
        return system_prompt, user_prompt

    @staticmethod
    def build_porter_prompt(
        problem: str,
        department: str,
        industry: str = "Tekstil",
    ) -> Tuple[str, str]:
        forces = "\n".join(f"  - {f}" for f in PORTER_FORCES)
        system_prompt = (
            "Sen bir Rekabet Analizi Uzmanısın. Porter'ın 5 Güç modelini uyguluyorsun.\n\n"
            f"5 Güç:\n{forces}\n\n"
            "Her güç için:\n"
            "1. Yoğunluk: 0.0 (düşük) — 1.0 (yüksek)\n"
            "2. Ana etkenler (2-3 madde)\n"
            "3. Stratejik çıkarım\n\n"
            f"Sektör: {industry} | Departman: {department}\n\n"
            "Format:\n"
            "### [Güç Adı]\n"
            "Yoğunluk: [X.X]\n"
            "Etkenler: [madde1], [madde2]\n"
            "Çıkarım: [stratejik sonuç]"
        )
        user_prompt = f"Konu: {problem}"
        return system_prompt, user_prompt

    @staticmethod
    def build_swot_prompt(
        problem: str,
        department: str,
        pestel_summary: str = "",
    ) -> Tuple[str, str]:
        system_prompt = (
            "Sen bir SWOT Analiz Uzmanısın. İç ve dış faktörleri değerlendiriyorsun.\n\n"
            "4 kategori:\n"
            "- Strengths (Güçlü Yönler): İç, olumlu\n"
            "- Weaknesses (Zayıf Yönler): İç, olumsuz\n"
            "- Opportunities (Fırsatlar): Dış, olumlu\n"
            "- Threats (Tehditler): Dış, olumsuz\n\n"
            "Her madde için önem puanı (0.0-1.0) ver.\n\n"
            f"Departman: {department}\n\n"
            "Format:\n"
            "### Strengths\n"
            "- [Madde] | Önem: [X.X]\n"
        )
        user_prompt = f"Konu: {problem}"
        if pestel_summary:
            user_prompt += f"\n\nPESTEL özeti:\n{pestel_summary[:600]}"
        return system_prompt, user_prompt

    @staticmethod
    def parse_pestel_response(raw_text: str) -> List[PESTELFactor]:
        """PESTEL LLM yanıtını parse et."""
        import re
        factors = []
        current_dim = ""
        for line in raw_text.strip().split("\n"):
            clean = line.strip()
            if not clean:
                continue
            cat_match = re.match(r"#{1,3}\s*(.+)", clean)
            if cat_match:
                dim_text = cat_match.group(1).strip().lower()
                for pd in PESTEL_DIMENSIONS:
                    if any(p.lower() in dim_text for p in pd.split()):
                        current_dim = pd
                        break
                continue
            if clean.startswith(("-", "•", "*")) and current_dim:
                text = clean.lstrip("-•* ").strip()
                impact = "belirsiz"
                score = 0.0
                prob = 0.5
                horizon = TimeHorizon.MEDIUM

                if "olumlu" in text.lower():
                    impact = "olumlu"
                    score = 0.5
                elif "olumsuz" in text.lower():
                    impact = "olumsuz"
                    score = -0.5

                score_match = re.search(r"skor\s*[:.]\s*([+-]?\d+\.?\d*)", text, re.IGNORECASE)
                if score_match:
                    score = max(-1.0, min(1.0, float(score_match.group(1))))

                prob_match = re.search(r"olasılık\s*[:.]\s*%?(\d+)", text, re.IGNORECASE)
                if prob_match:
                    prob = min(int(prob_match.group(1)), 100) / 100.0

                if "kısa" in text.lower():
                    horizon = TimeHorizon.SHORT
                elif "uzun" in text.lower():
                    horizon = TimeHorizon.LONG

                name_part = text.split("|")[0].split(":")[0].strip()[:100]
                factors.append(PESTELFactor(
                    dimension=current_dim,
                    factor=name_part,
                    impact=impact,
                    impact_score=score,
                    probability=prob,
                    time_horizon=horizon,
                    description=text[:200],
                ))
        return factors

    @staticmethod
    def parse_porter_response(raw_text: str) -> List[PorterForce]:
        """Porter 5 Forces yanıtını parse et."""
        import re
        forces = []
        current_force = ""
        intensity = 0.5
        drivers: List[str] = []
        implication = ""

        def _save():
            if current_force:
                forces.append(PorterForce(
                    force=current_force,
                    intensity=intensity,
                    key_drivers=drivers.copy(),
                    strategic_implication=implication,
                ))

        for line in raw_text.strip().split("\n"):
            clean = line.strip()
            if not clean:
                continue
            cat_match = re.match(r"#{1,3}\s*(.+)", clean)
            if cat_match:
                _save()
                current_force = cat_match.group(1).strip()
                intensity = 0.5
                drivers = []
                implication = ""
                continue
            lower = clean.lower()
            if "yoğunluk" in lower or "intensity" in lower:
                val_match = re.search(r"(\d+\.?\d*)", clean)
                if val_match:
                    intensity = min(float(val_match.group(1)), 1.0)
            elif "etken" in lower or "driver" in lower:
                parts = clean.split(":", 1)
                if len(parts) > 1:
                    drivers = [d.strip() for d in parts[1].split(",")]
            elif "çıkarım" in lower or "implication" in lower:
                parts = clean.split(":", 1)
                if len(parts) > 1:
                    implication = parts[1].strip()

        _save()
        return forces

    @staticmethod
    def parse_swot_response(raw_text: str) -> List[SWOTItem]:
        """SWOT yanıtını parse et."""
        import re
        items = []
        current_cat = ""
        cat_map = {
            "strength": "Strengths",
            "güçlü": "Strengths",
            "weakness": "Weaknesses",
            "zayıf": "Weaknesses",
            "opportunit": "Opportunities",
            "fırsat": "Opportunities",
            "threat": "Threats",
            "tehdit": "Threats",
        }
        for line in raw_text.strip().split("\n"):
            clean = line.strip()
            if not clean:
                continue
            cat_match = re.match(r"#{1,3}\s*(.+)", clean)
            if cat_match:
                cat_text = cat_match.group(1).strip().lower()
                for key, val in cat_map.items():
                    if key in cat_text:
                        current_cat = val
                        break
                continue
            if clean.startswith(("-", "•", "*")) and current_cat:
                text = clean.lstrip("-•* ").strip()
                importance = 0.5
                imp_match = re.search(r"önem\s*[:.]\s*(\d+\.?\d*)", text, re.IGNORECASE)
                if imp_match:
                    importance = min(float(imp_match.group(1)), 1.0)
                name = text.split("|")[0].strip()[:120]
                items.append(SWOTItem(
                    category=current_cat,
                    item=name,
                    importance=importance,
                ))
        return items


# ═══════════════════════════════════════════════════════════════════
# HEDEF MOTORU — SMART Hedef + OKR
# ═══════════════════════════════════════════════════════════════════

class StrategicGoalEngine:
    """SMART hedef üretimi."""

    @staticmethod
    def build_goals_prompt(
        problem: str,
        department: str,
        swot_summary: str = "",
        time_horizon: str = "orta vadeli",
    ) -> Tuple[str, str]:
        system_prompt = (
            "Sen bir Stratejik Hedef Belirleme Uzmanısın.\n\n"
            "SMART formülüne göre hedefler oluştur:\n"
            "- S (Specific): Net ve somut\n"
            "- M (Measurable): Ölçülebilir (sayısal metrik)\n"
            "- A (Achievable): Ulaşılabilir (kaynaklara uygun)\n"
            "- R (Relevant): İlgili (stratejik öneme sahip)\n"
            "- T (Time-bound): Zamana bağlı (tarih/dönem)\n\n"
            f"Maksimum {MAX_GOALS} hedef belirle.\n"
            f"Departman: {department}\n"
            f"Zaman ufku: {time_horizon}\n\n"
            "Her hedef için öncelik belirt: critical / high / medium / low\n\n"
            "Format:\n"
            "HEDEF 1: [Başlık]\n"
            "  S: [Specific]\n"
            "  M: [Measurable]\n"
            "  A: [Achievable]\n"
            "  R: [Relevant]\n"
            "  T: [Time-bound]\n"
            "  Öncelik: [critical/high/medium/low]\n"
            "  KPI: [ölçüm metrikleri, virgülle]"
        )
        user_prompt = f"Konu: {problem}"
        if swot_summary:
            user_prompt += f"\n\nSWOT özeti:\n{swot_summary[:600]}"
        return system_prompt, user_prompt

    @staticmethod
    def parse_goals_response(raw_text: str) -> List[StrategicGoal]:
        """Hedef yanıtını parse et."""
        import re
        goals = []
        blocks = re.split(r"\n(?=(?:hedef|goal)\s*\d)", raw_text, flags=re.IGNORECASE)
        for block in blocks:
            if not block.strip():
                continue
            title = ""
            specific, measurable, achievable, relevant, time_bound = "", "", "", "", ""
            priority = Priority.MEDIUM
            kpis: List[str] = []

            lines = block.strip().split("\n")
            for line in lines:
                clean = line.strip()
                lower = clean.lower()
                title_match = re.match(r"(?:hedef|goal)\s*\d+\s*[:.]\s*(.*)", clean, re.IGNORECASE)
                if title_match:
                    title = title_match.group(1).strip()
                    continue
                if lower.startswith("s:") or lower.startswith("specific"):
                    specific = clean.split(":", 1)[-1].strip()
                elif lower.startswith("m:") or lower.startswith("measurable"):
                    measurable = clean.split(":", 1)[-1].strip()
                elif lower.startswith("a:") or lower.startswith("achievable"):
                    achievable = clean.split(":", 1)[-1].strip()
                elif lower.startswith("r:") or lower.startswith("relevant"):
                    relevant = clean.split(":", 1)[-1].strip()
                elif lower.startswith("t:") or lower.startswith("time"):
                    time_bound = clean.split(":", 1)[-1].strip()
                elif "öncelik" in lower or "priority" in lower:
                    if "critical" in lower:
                        priority = Priority.CRITICAL
                    elif "high" in lower or "yüksek" in lower:
                        priority = Priority.HIGH
                    elif "low" in lower or "düşük" in lower:
                        priority = Priority.LOW
                elif "kpi" in lower:
                    kpi_text = clean.split(":", 1)[-1].strip()
                    kpis = [k.strip() for k in kpi_text.split(",") if k.strip()]

            if title:
                goals.append(StrategicGoal(
                    title=title,
                    description=specific or title,
                    specific=specific,
                    measurable=measurable,
                    achievable=achievable,
                    relevant=relevant,
                    time_bound=time_bound,
                    priority=priority,
                    kpis=kpis,
                ))
        return goals[:MAX_GOALS]


# ═══════════════════════════════════════════════════════════════════
# STRATEJİ FORMÜLASYONU
# ═══════════════════════════════════════════════════════════════════

class StrategyFormulator:
    """Hedefler + çevre analizi → strateji alternatifleri."""

    @staticmethod
    def build_strategy_prompt(
        problem: str,
        department: str,
        goals_summary: str,
        swot_summary: str = "",
    ) -> Tuple[str, str]:
        types_str = ", ".join(t.value for t in StrategyType)
        system_prompt = (
            "Sen bir Strateji Formülasyon Uzmanısın.\n\n"
            "Belirlenen hedeflere ulaşmak için strateji alternatifleri üret.\n\n"
            f"Strateji tipleri: {types_str}\n\n"
            "Her alternatif için:\n"
            "1. Ad ve tip\n"
            "2. Açıklama\n"
            "3. Artılar (2-3 madde)\n"
            "4. Eksiler (1-2 madde)\n"
            "5. Tahmini maliyet: Düşük / Orta / Yüksek\n"
            "6. Tahmini ROI\n"
            "7. Uygulama süresi\n"
            "8. Risk seviyesi: 0.0-1.0\n"
            "9. Fizibilite: 0.0-1.0\n\n"
            f"Departman: {department}\n"
            f"Her hedef için max {MAX_STRATEGIES_PER_GOAL} alternatif.\n\n"
            "Format:\n"
            "STRATEJİ 1: [Ad] (Tip: [growth/cost_leadership/...])\n"
            "Hedef: [hedef adı]\n"
            "Açıklama: [detay]\n"
            "Artılar: [+madde1], [+madde2]\n"
            "Eksiler: [-madde1]\n"
            "Maliyet: [Düşük/Orta/Yüksek] | ROI: [xN] | Süre: [X ay]\n"
            "Risk: [0.X] | Fizibilite: [0.X]"
        )
        user_prompt = f"Konu: {problem}\n\nHedefler:\n{goals_summary}"
        if swot_summary:
            user_prompt += f"\n\nSWOT:\n{swot_summary[:400]}"
        return system_prompt, user_prompt

    @staticmethod
    def parse_strategy_response(raw_text: str) -> List[StrategyAlternative]:
        """Strateji yanıtını parse et."""
        import re
        strategies = []
        blocks = re.split(r"\n(?=(?:strateji|strategy)\s*\d)", raw_text, flags=re.IGNORECASE)

        type_map = {t.value: t for t in StrategyType}

        for block in blocks:
            if not block.strip():
                continue
            name = ""
            s_type = StrategyType.GROWTH
            desc = ""
            pros: List[str] = []
            cons: List[str] = []
            cost = "Orta"
            roi = ""
            impl_time = ""
            risk = 0.5
            feasibility = 0.5

            lines = block.strip().split("\n")
            for line in lines:
                clean = line.strip()
                lower = clean.lower()

                name_match = re.match(r"(?:strateji|strategy)\s*\d+\s*[:.]\s*(.*)", clean, re.IGNORECASE)
                if name_match:
                    title_text = name_match.group(1).strip()
                    type_match = re.search(r"\((?:tip|type)\s*[:.]\s*(\w+)\)", title_text, re.IGNORECASE)
                    if type_match:
                        tp = type_match.group(1).lower()
                        s_type = type_map.get(tp, StrategyType.GROWTH)
                        name = re.sub(r"\s*\((?:tip|type).*?\)", "", title_text).strip()
                    else:
                        name = title_text
                    continue

                if "açıklama" in lower or "description" in lower:
                    desc = clean.split(":", 1)[-1].strip()
                elif "artı" in lower or "pro" in lower:
                    items = clean.split(":", 1)[-1].strip()
                    pros = [p.strip().lstrip("+") for p in items.split(",") if p.strip()]
                elif "eksi" in lower or "con" in lower:
                    items = clean.split(":", 1)[-1].strip()
                    cons = [c.strip().lstrip("-") for c in items.split(",") if c.strip()]
                elif "maliyet" in lower or "cost" in lower:
                    if "düşük" in lower or "low" in lower:
                        cost = "Düşük"
                    elif "yüksek" in lower or "high" in lower:
                        cost = "Yüksek"
                    roi_match = re.search(r"ROI\s*[:.]\s*([^\|]+)", clean, re.IGNORECASE)
                    if roi_match:
                        roi = roi_match.group(1).strip()
                    time_match = re.search(r"süre\s*[:.]\s*([^\|]+)", clean, re.IGNORECASE)
                    if time_match:
                        impl_time = time_match.group(1).strip()
                elif "risk" in lower:
                    val = re.search(r"(\d+\.?\d*)", clean)
                    if val:
                        risk = min(float(val.group(1)), 1.0)
                    feas = re.search(r"fizibilite\s*[:.]\s*(\d+\.?\d*)", clean, re.IGNORECASE)
                    if feas:
                        feasibility = min(float(feas.group(1)), 1.0)

            if name:
                strategies.append(StrategyAlternative(
                    name=name,
                    strategy_type=s_type,
                    description=desc or name,
                    pros=pros,
                    cons=cons,
                    estimated_cost=cost,
                    estimated_roi=roi,
                    implementation_time=impl_time,
                    risk_level=risk,
                    feasibility=feasibility,
                ))
        return strategies


# ═══════════════════════════════════════════════════════════════════
# EYLEM PLANI OLUŞTURUCU
# ═══════════════════════════════════════════════════════════════════

class ActionPlanBuilder:
    """Strateji → somut aksiyon planı."""

    @staticmethod
    def build_action_prompt(
        strategies_summary: str,
        department: str,
    ) -> Tuple[str, str]:
        system_prompt = (
            "Sen bir Eylem Planı Uzmanısın. Seçilen stratejileri somut aksiyonlara dönüştürüyorsun.\n\n"
            "Her aksiyon için:\n"
            "1. BAŞLIK: Kısa ve aksiyon odaklı\n"
            "2. AÇIKLAMA: Detaylı adımlar\n"
            "3. SORUMLU: Departman veya rol\n"
            "4. TARİH: Tamamlanma tarihi/dönemi\n"
            "5. KAYNAKLAR: Gereken insan/bütçe/araç\n"
            "6. BAŞARI KRİTERİ: Nasıl ölçülecek\n"
            "7. BAĞIMLILIKLAR: Önce tamamlanması gereken aksiyonlar\n"
            "8. ÖNCELİK: critical / high / medium / low\n\n"
            f"Departman: {department}\n"
            f"Her strateji için max {MAX_ACTIONS_PER_STRATEGY} aksiyon.\n\n"
            "Format:\n"
            "AKSİYON 1: [Başlık]\n"
            "Strateji: [ilgili strateji adı]\n"
            "Açıklama: [detay]\n"
            "Sorumlu: [departman/rol]\n"
            "Tarih: [Q1 2026 / Mart 2026]\n"
            "Kaynaklar: [madde1, madde2]\n"
            "Başarı Kriteri: [ölçüt]\n"
            "Bağımlılık: [aksiyon referansı]\n"
            "Öncelik: [critical/high/medium/low]"
        )
        user_prompt = f"Stratejiler:\n{strategies_summary}"
        return system_prompt, user_prompt

    @staticmethod
    def parse_action_response(raw_text: str) -> List[ActionItem]:
        """Aksiyon planı yanıtını parse et."""
        import re
        actions = []
        blocks = re.split(r"\n(?=(?:aksiyon|action)\s*\d)", raw_text, flags=re.IGNORECASE)

        for block in blocks:
            if not block.strip():
                continue
            title = ""
            desc = ""
            responsible = ""
            deadline = ""
            resources: List[str] = []
            criteria = ""
            deps: List[str] = []
            priority = Priority.MEDIUM

            lines = block.strip().split("\n")
            for line in lines:
                clean = line.strip()
                lower = clean.lower()
                t_match = re.match(r"(?:aksiyon|action)\s*\d+\s*[:.]\s*(.*)", clean, re.IGNORECASE)
                if t_match:
                    title = t_match.group(1).strip()
                    continue
                if "açıklama" in lower or "description" in lower:
                    desc = clean.split(":", 1)[-1].strip()
                elif "sorumlu" in lower or "responsible" in lower:
                    responsible = clean.split(":", 1)[-1].strip()
                elif "tarih" in lower or "date" in lower or "deadline" in lower:
                    deadline = clean.split(":", 1)[-1].strip()
                elif "kaynak" in lower or "resource" in lower:
                    res_text = clean.split(":", 1)[-1].strip()
                    resources = [r.strip() for r in res_text.split(",") if r.strip()]
                elif "başarı" in lower or "criteria" in lower:
                    criteria = clean.split(":", 1)[-1].strip()
                elif "bağımlılık" in lower or "depend" in lower:
                    dep_text = clean.split(":", 1)[-1].strip()
                    deps = [d.strip() for d in dep_text.split(",") if d.strip()]
                elif "öncelik" in lower or "priority" in lower:
                    if "critical" in lower:
                        priority = Priority.CRITICAL
                    elif "high" in lower or "yüksek" in lower:
                        priority = Priority.HIGH
                    elif "low" in lower or "düşük" in lower:
                        priority = Priority.LOW

            if title:
                actions.append(ActionItem(
                    title=title,
                    description=desc or title,
                    responsible=responsible,
                    deadline=deadline,
                    resources_needed=resources,
                    success_criteria=criteria,
                    dependencies=deps,
                    priority=priority,
                ))
        return actions


# ═══════════════════════════════════════════════════════════════════
# RİSK AZALTMA PLANLAMACISI
# ═══════════════════════════════════════════════════════════════════

class RiskMitigationPlanner:
    """Her stratejiye risk overlay ve B planı."""

    @staticmethod
    def build_risk_prompt(
        strategies_summary: str,
        department: str,
    ) -> Tuple[str, str]:
        system_prompt = (
            "Sen bir Stratejik Risk Yönetimi Uzmanısın.\n\n"
            "Her strateji için potansiyel riskleri ve azaltma planlarını belirle.\n\n"
            "Her risk için:\n"
            "1. RİSK: Tanımı\n"
            "2. OLASILIK: 0.0-1.0\n"
            "3. ETKİ: 0.0-1.0\n"
            "4. PLAN A (Azaltma): Riski azaltma stratejisi\n"
            "5. PLAN B (Acil Durum): Risk gerçekleşirse ne yapılacak\n"
            "6. ERKEN UYARI: Riskin yaklaştığını gösteren işaretler\n"
            "7. SAHİP: Risk yönetiminden sorumlu kişi/departman\n\n"
            f"Departman: {department}\n\n"
            "Format:\n"
            "RİSK 1: [Risk tanımı]\n"
            "Strateji: [ilgili strateji]\n"
            "Olasılık: [0.X] | Etki: [0.X]\n"
            "Plan A: [azaltma stratejisi]\n"
            "Plan B: [acil durum planı]\n"
            "Erken Uyarı: [işaret1, işaret2]\n"
            "Sahip: [departman/rol]"
        )
        user_prompt = f"Stratejiler:\n{strategies_summary}"
        return system_prompt, user_prompt

    @staticmethod
    def parse_risk_response(raw_text: str) -> List[RiskMitigation]:
        """Risk yanıtını parse et."""
        import re
        risks = []
        blocks = re.split(r"\n(?=(?:risk)\s*\d)", raw_text, flags=re.IGNORECASE)
        for block in blocks:
            if not block.strip():
                continue
            desc = ""
            prob = 0.5
            impact = 0.5
            plan_a = ""
            plan_b = ""
            warnings: List[str] = []
            owner = ""

            lines = block.strip().split("\n")
            for line in lines:
                clean = line.strip()
                lower = clean.lower()
                r_match = re.match(r"risk\s*\d+\s*[:.]\s*(.*)", clean, re.IGNORECASE)
                if r_match:
                    desc = r_match.group(1).strip()
                    continue
                if "olasılık" in lower or "probability" in lower:
                    val = re.search(r"(\d+\.?\d*)", clean)
                    if val:
                        prob = min(float(val.group(1)), 1.0)
                    imp = re.search(r"etki\s*[:.]\s*(\d+\.?\d*)", clean, re.IGNORECASE)
                    if imp:
                        impact = min(float(imp.group(1)), 1.0)
                elif "plan a" in lower or "azaltma" in lower:
                    plan_a = clean.split(":", 1)[-1].strip()
                elif "plan b" in lower or "acil" in lower:
                    plan_b = clean.split(":", 1)[-1].strip()
                elif "erken uyarı" in lower or "early warning" in lower:
                    w_text = clean.split(":", 1)[-1].strip()
                    warnings = [w.strip() for w in w_text.split(",") if w.strip()]
                elif "sahip" in lower or "owner" in lower:
                    owner = clean.split(":", 1)[-1].strip()

            if desc:
                risks.append(RiskMitigation(
                    risk_description=desc,
                    probability=prob,
                    impact=impact,
                    mitigation_plan=plan_a,
                    contingency_plan=plan_b,
                    early_warning_signs=warnings,
                    owner=owner,
                ))
        return risks


# ═══════════════════════════════════════════════════════════════════
# PLAN TAKİPÇİSİ
# ═══════════════════════════════════════════════════════════════════

class StrategicTracker:
    """Geçmiş planlar ve takip."""

    def __init__(self):
        self._plans: List[StrategicPlan] = []
        self._dept_stats: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {"plans": 0, "avg_goals": 0.0, "avg_strategies": 0.0}
        )

    def record(self, plan: StrategicPlan):
        self._plans.append(plan)
        if len(self._plans) > MAX_PLAN_HISTORY:
            self._plans = self._plans[-MAX_PLAN_HISTORY:]

        ds = self._dept_stats[plan.department]
        ds["plans"] += 1
        n = ds["plans"]
        ds["avg_goals"] = round(((ds["avg_goals"] * (n - 1)) + len(plan.goals)) / n, 1)
        ds["avg_strategies"] = round(((ds["avg_strategies"] * (n - 1)) + len(plan.strategies)) / n, 1)

        logger.info("strategic_plan_recorded",
                     plan_id=plan.plan_id,
                     goals=len(plan.goals),
                     strategies=len(plan.strategies),
                     actions=len(plan.action_plan))

    def get_recent(self, n: int = 20) -> List[dict]:
        return [p.to_dict() for p in self._plans[-n:]]

    def get_statistics(self) -> dict:
        total = len(self._plans)
        if total == 0:
            return {"total_plans": 0}
        return {
            "total_plans": total,
            "avg_goals": round(sum(len(p.goals) for p in self._plans) / total, 1),
            "avg_strategies": round(sum(len(p.strategies) for p in self._plans) / total, 1),
            "avg_actions": round(sum(len(p.action_plan) for p in self._plans) / total, 1),
            "avg_risks": round(sum(len(p.risk_mitigations) for p in self._plans) / total, 1),
            "department_stats": dict(self._dept_stats),
            "horizon_distribution": dict(defaultdict(int, {
                p.time_horizon.value: 1 for p in self._plans
            })),
        }

    def reset(self):
        self._plans.clear()
        self._dept_stats.clear()
        logger.info("strategic_tracker_reset")


# ═══════════════════════════════════════════════════════════════════
# ANA ORKESTRATÖR — StrategicPlannerEngine
# ═══════════════════════════════════════════════════════════════════

class StrategicPlannerEngine:
    """Stratejik Planlama Motoru orkestratörü.

    Kullanım (engine.py / admin'den):
        engine = strategic_planner
        trigger, reason = engine.should_plan(question, mode, intent)
        if trigger:
            prompts = engine.build_analysis_prompts(question, dept, mode)
            # LLM çağrıları engine.py yapar
            result = engine.finalize_plan(...)
    """

    def __init__(self):
        self.env_scanner = EnvironmentScanner()
        self.goal_engine = StrategicGoalEngine()
        self.strategy_formulator = StrategyFormulator()
        self.action_builder = ActionPlanBuilder()
        self.risk_planner = RiskMitigationPlanner()
        self.tracker = StrategicTracker()
        self._enabled: bool = True
        self._started_at: str = _utcnow_str()

    def should_plan(
        self,
        question: str,
        mode: str,
        intent: str,
        force: bool = False,
    ) -> Tuple[bool, str]:
        if not self._enabled and not force:
            return False, "planner_disabled"
        return should_trigger_strategic_planning(question, mode, intent, force)

    def build_analysis_prompts(
        self,
        question: str,
        department: str,
        mode: str,
        industry: str = "Tekstil",
    ) -> Dict[str, Tuple[str, str]]:
        """İlk aşama prompt'ları: PESTEL + Porter + SWOT."""
        return {
            "pestel": self.env_scanner.build_pestel_prompt(question, department, industry),
            "porter": self.env_scanner.build_porter_prompt(question, department, industry),
            "swot": self.env_scanner.build_swot_prompt(question, department),
        }

    def build_planning_prompts(
        self,
        question: str,
        department: str,
        swot_summary: str,
        goals_summary: str = "",
        strategies_summary: str = "",
    ) -> Dict[str, Tuple[str, str]]:
        """İkinci aşama prompt'ları: Hedef + Strateji + Aksiyon + Risk."""
        prompts: Dict[str, Tuple[str, str]] = {}

        if not goals_summary:
            prompts["goals"] = self.goal_engine.build_goals_prompt(
                question, department, swot_summary
            )
        if not strategies_summary and goals_summary:
            prompts["strategies"] = self.strategy_formulator.build_strategy_prompt(
                question, department, goals_summary, swot_summary
            )
        if strategies_summary:
            prompts["actions"] = self.action_builder.build_action_prompt(
                strategies_summary, department
            )
            prompts["risks"] = self.risk_planner.build_risk_prompt(
                strategies_summary, department
            )
        return prompts

    def parse_responses(self, raw_responses: Dict[str, str]) -> Dict[str, Any]:
        parsed: Dict[str, Any] = {}
        if "pestel" in raw_responses:
            parsed["pestel"] = self.env_scanner.parse_pestel_response(raw_responses["pestel"])
        if "porter" in raw_responses:
            parsed["porter"] = self.env_scanner.parse_porter_response(raw_responses["porter"])
        if "swot" in raw_responses:
            parsed["swot"] = self.env_scanner.parse_swot_response(raw_responses["swot"])
        if "goals" in raw_responses:
            parsed["goals"] = self.goal_engine.parse_goals_response(raw_responses["goals"])
        if "strategies" in raw_responses:
            parsed["strategies"] = self.strategy_formulator.parse_strategy_response(raw_responses["strategies"])
        if "actions" in raw_responses:
            parsed["actions"] = self.action_builder.parse_action_response(raw_responses["actions"])
        if "risks" in raw_responses:
            parsed["risks"] = self.risk_planner.parse_risk_response(raw_responses["risks"])
        return parsed

    def finalize_plan(
        self,
        question: str,
        department: str,
        mode: str,
        parsed_data: Dict[str, Any],
        total_time_ms: float = 0.0,
        triggered_by: str = "auto",
    ) -> StrategicPlan:
        goals = parsed_data.get("goals", [])
        strategies = parsed_data.get("strategies", [])
        actions = parsed_data.get("actions", [])
        risks = parsed_data.get("risks", [])

        conf_adj = 0.0
        if goals:
            conf_adj += 4
        if strategies:
            conf_adj += 3
        if actions:
            conf_adj += 2

        plan = StrategicPlan(
            title=question[:100],
            question=question,
            department=department,
            mode=mode,
            pestel=parsed_data.get("pestel", []),
            porter_forces=parsed_data.get("porter", []),
            swot=parsed_data.get("swot", []),
            goals=goals,
            strategies=strategies,
            action_plan=actions,
            risk_mitigations=risks,
            confidence_adjustment=conf_adj,
            total_time_ms=total_time_ms,
            triggered_by=triggered_by,
        )
        self.tracker.record(plan)
        return plan

    def get_dashboard(self) -> dict:
        return {
            "available": True,
            "enabled": self._enabled,
            "started_at": self._started_at,
            "statistics": self.tracker.get_statistics(),
            "recent_plans": self.tracker.get_recent(10),
            "settings": {
                "max_goals": MAX_GOALS,
                "max_strategies_per_goal": MAX_STRATEGIES_PER_GOAL,
                "max_actions_per_strategy": MAX_ACTIONS_PER_STRATEGY,
                "pestel_dimensions": PESTEL_DIMENSIONS,
                "porter_forces": PORTER_FORCES,
                "strategy_types": [t.value for t in StrategyType],
            },
        }

    def set_enabled(self, enabled: bool) -> dict:
        old = self._enabled
        self._enabled = enabled
        logger.info("strategic_planner_toggled", old=old, new=enabled)
        return {"enabled": enabled, "previous": old}

    def reset(self):
        self.tracker.reset()
        self._started_at = _utcnow_str()
        logger.info("strategic_planner_reset")


# ═══════════════════════════════════════════════════════════════════
# GLOBAL SINGLETON
# ═══════════════════════════════════════════════════════════════════

strategic_planner: StrategicPlannerEngine = StrategicPlannerEngine()


def check_strategic_trigger(
    question: str, mode: str, intent: str, force: bool = False,
) -> Tuple[bool, str]:
    return strategic_planner.should_plan(question, mode, intent, force)


def get_strategic_dashboard() -> dict:
    return strategic_planner.get_dashboard()
