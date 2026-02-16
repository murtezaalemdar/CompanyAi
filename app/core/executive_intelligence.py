"""Executive Intelligence v1.0 — C-Level Karar Destek Motoru

Tüm analiz modüllerinin çıktılarını bir araya getirerek
üst yönetim seviyesinde brifing, rapor ve karar desteği sağlar.

Bileşenler:
  1. ExecutiveBriefingGenerator → Günlük/haftalık yönetim özeti
  2. KPICrossCorrelator        → Departmanlar arası KPI korelasyonu
  3. StrategicRiskAggregator    → Risk kaynaklarını üst-düzey sentez
  4. DecisionFramework         → Qk/Büyük karar şablonu (RAPID, RACI)
  5. BoardReportBuilder        → Yönetim kurulu sunumu formatı
  6. CompetitiveRadar          → Rakip hareketleri takip & değerlendirme
  7. ExecutiveTracker          → Geçmiş brifing/rapor deposu

Kullanım Alanları:
  - "Yönetim kuruluna sunum hazırla"
  - "Bu ayki KPI özetini çıkar"
  - "Departmanlar arası korelasyon analizi"
  - "CEO için durum raporu yaz"
  - "Stratejik risk özeti ver"

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

MAX_BRIEFING_HISTORY = 300
EXEC_TRIGGER_MIN_LENGTH = 20

EXEC_TRIGGER_KEYWORDS = [
    "yönetim", "rapor", "brifing", "sunum", "özet",
    "CEO", "CFO", "CTO", "COO", "CISO", "C-level", "üst yönetim",
    "yönetim kurulu", "board", "executive", "briefing",
    "KPI özet", "performans raporu", "durum raporu",
    "karar destek", "karar al", "executive summary",
    "yatırımcı", "investor", "paydaş", "stakeholder",
    "risk raporu", "strateji raporu", "board meeting",
]

BRIEFING_SECTIONS = [
    "Genel Durum Özeti",
    "Kritik KPI Değişimleri",
    "Departman Performansları",
    "Stratejik Risk Değerlendirmesi",
    "Yatırım & Kaynak Durumu",
    "Eylem Gerektiren Konular",
    "Sonraki Dönem Tahminleri",
]

DECISION_FRAMEWORKS = {
    "rapid": {
        "name": "RAPID (Bain & Company)",
        "roles": ["Recommend", "Agree", "Perform", "Input", "Decide"],
        "best_for": "Karmaşık organizasyonel kararlar",
    },
    "raci": {
        "name": "RACI Matrisi",
        "roles": ["Responsible", "Accountable", "Consulted", "Informed"],
        "best_for": "Proje/görev bazlı sorumluluk atama",
    },
    "eisenhower": {
        "name": "Eisenhower Matrisi",
        "roles": ["Acil+Önemli", "Acil+Önemsiz", "Acil değil+Önemli", "Acil değil+Önemsiz"],
        "best_for": "Zaman yönetimi ve önceliklendirme",
    },
    "ooda": {
        "name": "OODA Döngüsü",
        "roles": ["Observe", "Orient", "Decide", "Act"],
        "best_for": "Hızlı taktik karar alma",
    },
}

KPI_CATEGORIES = [
    "Finansal",
    "Operasyonel",
    "Müşteri",
    "İnsan Kaynakları",
    "Teknoloji",
    "Kalite",
    "İnovasyon",
]


def _utcnow_str() -> str:
    return datetime.now(timezone.utc).isoformat()


# ═══════════════════════════════════════════════════════════════════
# ENUM & VERİ YAPILARI
# ═══════════════════════════════════════════════════════════════════

class ReportType(str, Enum):
    DAILY_BRIEFING = "daily_briefing"
    WEEKLY_REPORT = "weekly_report"
    MONTHLY_REVIEW = "monthly_review"
    QUARTERLY_BOARD = "quarterly_board"
    STRATEGIC_REVIEW = "strategic_review"
    RISK_REPORT = "risk_report"
    KPI_DASHBOARD = "kpi_dashboard"
    AD_HOC = "ad_hoc"


class Urgency(str, Enum):
    CRITICAL = "critical"    # Hemen karar gerekli
    HIGH = "high"            # Bu hafta karar gerekli
    MEDIUM = "medium"        # Bu ay gözden geçirilmeli
    LOW = "low"              # Bilgilendirme amaçlı
    INFO = "info"            # Salt bilgi


class Sentiment(str, Enum):
    VERY_POSITIVE = "very_positive"
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"
    VERY_NEGATIVE = "very_negative"


class TrendDirection(str, Enum):
    STRONG_UP = "strong_up"
    UP = "up"
    STABLE = "stable"
    DOWN = "down"
    STRONG_DOWN = "strong_down"


# ─── Veri yapıları ───

@dataclass
class KPIMetric:
    """Bir KPI ölçümü."""
    name: str
    category: str          # Finansal, Operasyonel vb.
    current_value: str     # "15.2M TL", "%94", "3.2x"
    previous_value: str = ""
    target_value: str = ""
    trend: TrendDirection = TrendDirection.STABLE
    change_percent: float = 0.0
    department: str = ""
    commentary: str = ""
    urgency: Urgency = Urgency.INFO

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "category": self.category,
            "current_value": self.current_value,
            "previous_value": self.previous_value,
            "target_value": self.target_value,
            "trend": self.trend.value,
            "change_percent": round(self.change_percent, 2),
            "department": self.department,
            "commentary": self.commentary,
            "urgency": self.urgency.value,
        }


@dataclass
class KPICorrelation:
    """İki KPI arasındaki korelasyon."""
    kpi_a: str
    kpi_b: str
    correlation_type: str   # "positive", "negative", "inverse", "lagging"
    strength: float         # 0-1
    lag_period: str = ""    # "2 hafta gecikme"
    explanation: str = ""
    strategic_insight: str = ""

    def to_dict(self) -> dict:
        return {
            "kpi_a": self.kpi_a,
            "kpi_b": self.kpi_b,
            "correlation_type": self.correlation_type,
            "strength": round(self.strength, 2),
            "lag_period": self.lag_period,
            "explanation": self.explanation,
            "strategic_insight": self.strategic_insight,
        }


@dataclass
class RiskItem:
    """Üst-düzey risk maddesi."""
    title: str
    category: str          # "Operasyonel", "Finansal", "Siber", "Pazar"
    severity: float        # 0-1
    probability: float     # 0-1
    impact_areas: List[str] = field(default_factory=list)
    current_status: str = ""
    mitigation_summary: str = ""
    owner: str = ""
    trend: TrendDirection = TrendDirection.STABLE
    urgency: Urgency = Urgency.MEDIUM

    @property
    def risk_score(self) -> float:
        return round(self.severity * self.probability, 2)

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "category": self.category,
            "severity": round(self.severity, 2),
            "probability": round(self.probability, 2),
            "risk_score": self.risk_score,
            "impact_areas": self.impact_areas,
            "current_status": self.current_status,
            "mitigation_summary": self.mitigation_summary,
            "owner": self.owner,
            "trend": self.trend.value,
            "urgency": self.urgency.value,
        }


@dataclass
class ActionableItem:
    """Yönetici eylem gerektiren madde."""
    title: str
    description: str
    urgency: Urgency = Urgency.MEDIUM
    department: str = ""
    decision_needed: str = ""
    deadline: str = ""
    options: List[str] = field(default_factory=list)
    recommendation: str = ""

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "description": self.description,
            "urgency": self.urgency.value,
            "department": self.department,
            "decision_needed": self.decision_needed,
            "deadline": self.deadline,
            "options": self.options,
            "recommendation": self.recommendation,
        }


@dataclass
class CompetitorInfo:
    """Rakip istihbaratı."""
    competitor_name: str
    recent_move: str
    impact_assessment: str
    threat_level: float = 0.5  # 0-1
    opportunity: str = ""
    recommended_response: str = ""

    def to_dict(self) -> dict:
        return {
            "competitor_name": self.competitor_name,
            "recent_move": self.recent_move,
            "impact_assessment": self.impact_assessment,
            "threat_level": round(self.threat_level, 2),
            "opportunity": self.opportunity,
            "recommended_response": self.recommended_response,
        }


@dataclass
class ExecutiveBriefing:
    """Tam yönetici brifing belgesi."""
    briefing_id: str = ""
    report_type: ReportType = ReportType.AD_HOC
    title: str = ""
    question: str = ""
    department: str = ""
    mode: str = ""
    timestamp: str = ""
    period: str = ""
    # Bileşenler
    executive_summary: str = ""
    overall_sentiment: Sentiment = Sentiment.NEUTRAL
    kpis: List[KPIMetric] = field(default_factory=list)
    kpi_correlations: List[KPICorrelation] = field(default_factory=list)
    risks: List[RiskItem] = field(default_factory=list)
    action_items: List[ActionableItem] = field(default_factory=list)
    competitor_intel: List[CompetitorInfo] = field(default_factory=list)
    forecasts: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    # Meta
    confidence_adjustment: float = 0.0
    total_time_ms: float = 0.0
    triggered_by: str = "auto"

    def __post_init__(self):
        if not self.briefing_id:
            self.briefing_id = f"EB-{uuid.uuid4().hex[:8]}"
        if not self.timestamp:
            self.timestamp = _utcnow_str()

    def to_dict(self) -> dict:
        return {
            "briefing_id": self.briefing_id,
            "report_type": self.report_type.value,
            "title": self.title,
            "question": self.question[:200],
            "department": self.department,
            "mode": self.mode,
            "timestamp": self.timestamp,
            "period": self.period,
            "executive_summary": self.executive_summary,
            "overall_sentiment": self.overall_sentiment.value,
            "kpis": [k.to_dict() for k in self.kpis],
            "kpi_correlations": [c.to_dict() for c in self.kpi_correlations],
            "risks": [r.to_dict() for r in self.risks],
            "action_items": [a.to_dict() for a in self.action_items],
            "competitor_intel": [c.to_dict() for c in self.competitor_intel],
            "forecasts": self.forecasts,
            "recommendations": self.recommendations,
            "summary": self._build_summary(),
            "confidence_adjustment": self.confidence_adjustment,
            "total_time_ms": round(self.total_time_ms, 1),
            "triggered_by": self.triggered_by,
        }

    def _build_summary(self) -> dict:
        critical_risks = [r for r in self.risks if r.risk_score >= 0.6]
        urgent_actions = [a for a in self.action_items if a.urgency in (Urgency.CRITICAL, Urgency.HIGH)]
        return {
            "total_kpis": len(self.kpis),
            "kpi_correlations_found": len(self.kpi_correlations),
            "total_risks": len(self.risks),
            "critical_risks": len(critical_risks),
            "action_items": len(self.action_items),
            "urgent_actions": len(urgent_actions),
            "competitors_tracked": len(self.competitor_intel),
        }


# ═══════════════════════════════════════════════════════════════════
# TETİKLEME KARARI
# ═══════════════════════════════════════════════════════════════════

def should_trigger_executive_intel(
    question: str,
    mode: str,
    intent: str,
    force: bool = False,
) -> Tuple[bool, str]:
    """Bu soru executive intelligence gerektirir mi?"""
    if force:
        return True, "manual_trigger"

    if len(question.strip()) < EXEC_TRIGGER_MIN_LENGTH:
        return False, "too_short"

    if intent in ("sohbet", "selamlama"):
        return False, "casual_intent"

    q_lower = question.lower()
    keyword_hits = sum(1 for kw in EXEC_TRIGGER_KEYWORDS if kw.lower() in q_lower)

    if keyword_hits >= 2:
        return True, f"keyword_trigger:{keyword_hits}_hits"

    if mode in ("Üst Düzey Analiz", "CEO Raporu"):
        return True, f"mode_trigger:{mode}"

    import re
    patterns = [
        r"yönetim\w*\s+(?:rapor|brifing|sunum|özet)",
        r"(?:CEO|CFO|CTO|COO)\s+(?:rapor|brifing|sunum)",
        r"board\s+(?:report|meeting|sunum)",
        r"executive\s+(?:summary|brief|report)",
        r"üst\s+yönetim\w*\s+(?:rapor|brifing|özet)",
        r"KPI\s+(?:özet|rapor|durum|analiz)",
        r"performans\s+rapor",
        r"stratejik\s+risk\s+(?:rapor|özet)",
    ]
    for pattern in patterns:
        if re.search(pattern, q_lower):
            return True, f"pattern_trigger:{pattern}"

    return False, "no_trigger"


# ═══════════════════════════════════════════════════════════════════
# BRİFİNG OLUŞTURUCU
# ═══════════════════════════════════════════════════════════════════

class ExecutiveBriefingGenerator:
    """Yönetici brifing/rapor üretimi."""

    @staticmethod
    def detect_report_type(question: str) -> ReportType:
        q_lower = question.lower()
        type_map = {
            "günlük": ReportType.DAILY_BRIEFING,
            "daily": ReportType.DAILY_BRIEFING,
            "haftalık": ReportType.WEEKLY_REPORT,
            "weekly": ReportType.WEEKLY_REPORT,
            "aylık": ReportType.MONTHLY_REVIEW,
            "monthly": ReportType.MONTHLY_REVIEW,
            "çeyrek": ReportType.QUARTERLY_BOARD,
            "quarter": ReportType.QUARTERLY_BOARD,
            "board": ReportType.QUARTERLY_BOARD,
            "yönetim kurulu": ReportType.QUARTERLY_BOARD,
            "stratejik": ReportType.STRATEGIC_REVIEW,
            "strategic": ReportType.STRATEGIC_REVIEW,
            "risk": ReportType.RISK_REPORT,
            "KPI": ReportType.KPI_DASHBOARD,
        }
        for keyword, rtype in type_map.items():
            if keyword in q_lower:
                return rtype
        return ReportType.AD_HOC

    @staticmethod
    def build_briefing_prompt(
        question: str,
        department: str,
        report_type: ReportType,
    ) -> Tuple[str, str]:
        sections = "\n".join(f"  {i+1}. {s}" for i, s in enumerate(BRIEFING_SECTIONS))
        system_prompt = (
            "Sen üst düzey bir Yönetim Danışmanısın. C-level yöneticiler için "
            "profesyonel brifing hazırlıyorsun.\n\n"
            f"Rapor tipi: {report_type.value}\n"
            f"Departman: {department}\n\n"
            f"Bölümler:\n{sections}\n\n"
            "Kurallar:\n"
            "- Kısa ve öz, eylem odaklı cümleler\n"
            "- Her KPI için trend (↑/↓/→) ve sayısal değer\n"
            "- Riskler önem sırasına göre\n"
            "- En az 3 somut öneri\n"
            "- Acil eylem gerektiren konuları işaretle [ACİL]\n\n"
            "Format:\n"
            "## [Bölüm adı]\n"
            "[İçerik]\n\n"
            "### KPI Tablosu\n"
            "- [KPI adı]: [değer] (önceki: [değer]) [↑/↓/→] | Kategori: [kat]\n\n"
            "### Riskler\n"
            "- [Risk]: Şiddet: [0.X] | Olasılık: [0.X] | Kategori: [kat] | [ACİL/Normal]\n\n"
            "### Eylem Gerektiren Konular\n"
            "- [Konu]: [açıklama] | Aciliyet: [critical/high/medium] | Sorumlu: [dept]\n"
        )
        user_prompt = f"Yönetim brifing talebi: {question}"
        return system_prompt, user_prompt


# ═══════════════════════════════════════════════════════════════════
# KPI ÇAPRAZ KORELASYON
# ═══════════════════════════════════════════════════════════════════

class KPICrossCorrelator:
    """Departmanlar arası KPI korelasyon analizi."""

    @staticmethod
    def build_correlation_prompt(
        question: str,
        department: str,
        kpi_data: str = "",
    ) -> Tuple[str, str]:
        categories = ", ".join(KPI_CATEGORIES)
        system_prompt = (
            "Sen bir İş Zekası Analistisin. KPI'lar arasındaki korelasyonları "
            "ve neden-sonuç ilişkilerini analiz ediyorsun.\n\n"
            f"KPI Kategorileri: {categories}\n"
            f"Departman: {department}\n\n"
            "Her korelasyon için:\n"
            "1. İki KPI'ı belirt\n"
            "2. Korelasyon tipi: positive / negative / inverse / lagging\n"
            "3. Güç: 0.0-1.0\n"
            "4. Gecikme süresi (varsa)\n"
            "5. Açıklama\n"
            "6. Stratejik çıkarım\n\n"
            "Format:\n"
            "KORELASYON 1:\n"
            "KPI-A: [isim] | KPI-B: [isim]\n"
            "Tip: [positive/negative/inverse/lagging] | Güç: [0.X]\n"
            "Gecikme: [süre veya yok]\n"
            "Açıklama: [neden bu korelasyon var]\n"
            "Stratejik Çıkarım: [ne yapılmalı]"
        )
        user_prompt = f"Analiz talebi: {question}"
        if kpi_data:
            user_prompt += f"\n\nMevcut KPI verileri:\n{kpi_data[:800]}"
        return system_prompt, user_prompt

    @staticmethod
    def parse_correlation_response(raw_text: str) -> List[KPICorrelation]:
        """Korelasyon yanıtını parse et."""
        import re
        correlations = []
        blocks = re.split(r"\n(?=(?:korelasyon|correlation)\s*\d)", raw_text, flags=re.IGNORECASE)
        for block in blocks:
            if not block.strip():
                continue
            kpi_a = ""
            kpi_b = ""
            c_type = "positive"
            strength = 0.5
            lag = ""
            explanation = ""
            insight = ""

            for line in block.strip().split("\n"):
                clean = line.strip()
                lower = clean.lower()
                if "kpi-a" in lower or "kpi_a" in lower:
                    parts = clean.split("|")
                    if parts:
                        kpi_a = parts[0].split(":", 1)[-1].strip()
                    if len(parts) > 1:
                        kpi_b = parts[1].split(":", 1)[-1].strip()
                elif "tip" in lower or "type" in lower:
                    for t in ("positive", "negative", "inverse", "lagging"):
                        if t in lower:
                            c_type = t
                            break
                    val = re.search(r"güç\s*[:.]\s*(\d+\.?\d*)", clean, re.IGNORECASE)
                    if val:
                        strength = min(float(val.group(1)), 1.0)
                elif "gecikme" in lower or "lag" in lower:
                    lag = clean.split(":", 1)[-1].strip()
                elif "açıklama" in lower or "explanation" in lower:
                    explanation = clean.split(":", 1)[-1].strip()
                elif "stratejik" in lower or "insight" in lower:
                    insight = clean.split(":", 1)[-1].strip()

            if kpi_a and kpi_b:
                correlations.append(KPICorrelation(
                    kpi_a=kpi_a,
                    kpi_b=kpi_b,
                    correlation_type=c_type,
                    strength=strength,
                    lag_period=lag,
                    explanation=explanation,
                    strategic_insight=insight,
                ))
        return correlations


# ═══════════════════════════════════════════════════════════════════
# STRATEJİK RİSK AGREGATÖRü
# ═══════════════════════════════════════════════════════════════════

class StrategicRiskAggregator:
    """Birden fazla kaynaktan risk bilgisini toplayıp sentezler."""

    @staticmethod
    def build_risk_synthesis_prompt(
        question: str,
        department: str,
        existing_analysis: str = "",
    ) -> Tuple[str, str]:
        system_prompt = (
            "Sen bir Kurumsal Risk Yönetimi Uzmanısın (Chief Risk Officer perspektifi).\n\n"
            "Tüm risk kaynaklarını değerlendirip üst yönetim için risk özeti hazırla.\n\n"
            "Risk kategorileri:\n"
            "- Operasyonel: İş süreçleri, tedarik zinciri\n"
            "- Finansal: Nakit akışı, kur, kredi\n"
            "- Siber: Veri güvenliği, sistem arızası\n"
            "- Pazar: Rekabet, talep değişimi\n"
            "- Regülasyon: Yasal değişiklikler, uyumluluk\n"
            "- İnsan Kaynakları: Yetenek kaybı, motivasyon\n\n"
            f"Departman: {department}\n\n"
            "Her risk için:\n"
            "- Başlık\n"
            "- Kategori\n"
            "- Şiddet: 0.0-1.0\n"
            "- Olasılık: 0.0-1.0\n"
            "- Etki alanları\n"
            "- Mevcut durum\n"
            "- Azaltma özeti\n"
            "- Trend: yukarı / stabil / aşağı\n"
            "- Aciliyet: critical / high / medium / low\n\n"
            "Format:\n"
            "RİSK 1: [Başlık]\n"
            "Kategori: [kat] | Şiddet: [0.X] | Olasılık: [0.X]\n"
            "Etki: [alan1, alan2]\n"
            "Durum: [mevcut durum]\n"
            "Azaltma: [özet]\n"
            "Trend: [↑/→/↓] | Aciliyet: [critical/high/medium/low]"
        )
        user_prompt = f"Risk analizi talebi: {question}"
        if existing_analysis:
            user_prompt += f"\n\nMevcut analiz:\n{existing_analysis[:800]}"
        return system_prompt, user_prompt

    @staticmethod
    def parse_risk_response(raw_text: str) -> List[RiskItem]:
        """Risk yanıtını parse et."""
        import re
        risks = []
        blocks = re.split(r"\n(?=(?:risk)\s*\d)", raw_text, flags=re.IGNORECASE)
        for block in blocks:
            if not block.strip():
                continue
            title = ""
            category = "Operasyonel"
            severity = 0.5
            probability = 0.5
            impact_areas: List[str] = []
            status = ""
            mitigation = ""
            trend = TrendDirection.STABLE
            urgency = Urgency.MEDIUM

            for line in block.strip().split("\n"):
                clean = line.strip()
                lower = clean.lower()
                r_match = re.match(r"risk\s*\d+\s*[:.]\s*(.*)", clean, re.IGNORECASE)
                if r_match:
                    title = r_match.group(1).strip()
                    continue
                if "kategori" in lower or "category" in lower:
                    cat_text = clean.split(":", 1)[-1].strip() if ":" in clean else ""
                    cat_text = cat_text.split("|")[0].strip()
                    if cat_text:
                        category = cat_text
                    sev = re.search(r"şiddet\s*[:.]\s*(\d+\.?\d*)", clean, re.IGNORECASE)
                    if sev:
                        severity = min(float(sev.group(1)), 1.0)
                    prob = re.search(r"olasılık\s*[:.]\s*(\d+\.?\d*)", clean, re.IGNORECASE)
                    if prob:
                        probability = min(float(prob.group(1)), 1.0)
                elif "etki" in lower or "impact" in lower:
                    areas = clean.split(":", 1)[-1].strip()
                    impact_areas = [a.strip() for a in areas.split(",") if a.strip()]
                elif "durum" in lower or "status" in lower:
                    status = clean.split(":", 1)[-1].strip()
                elif "azaltma" in lower or "mitigat" in lower:
                    mitigation = clean.split(":", 1)[-1].strip()
                elif "trend" in lower:
                    if "↑" in clean or "yukarı" in lower or "up" in lower:
                        trend = TrendDirection.UP
                    elif "↓" in clean or "aşağı" in lower or "down" in lower:
                        trend = TrendDirection.DOWN
                    acl = re.search(r"aciliyet\s*[:.]\s*(\w+)", clean, re.IGNORECASE)
                    if acl:
                        urg_text = acl.group(1).lower()
                        if "critical" in urg_text:
                            urgency = Urgency.CRITICAL
                        elif "high" in urg_text or "yüksek" in urg_text:
                            urgency = Urgency.HIGH
                        elif "low" in urg_text or "düşük" in urg_text:
                            urgency = Urgency.LOW

            if title:
                risks.append(RiskItem(
                    title=title,
                    category=category,
                    severity=severity,
                    probability=probability,
                    impact_areas=impact_areas,
                    current_status=status,
                    mitigation_summary=mitigation,
                    trend=trend,
                    urgency=urgency,
                ))
        return risks


# ═══════════════════════════════════════════════════════════════════
# KARAR ÇERÇEVESİ (RAPID, RACI, OODA, Eisenhower)
# ═══════════════════════════════════════════════════════════════════

class DecisionFramework:
    """Karar çerçevesi uygulaması."""

    @staticmethod
    def select_framework(question: str) -> str:
        q_lower = question.lower()
        if any(kw in q_lower for kw in ("acil", "hızlı", "kriz", "urgent")):
            return "ooda"
        if any(kw in q_lower for kw in ("sorumluluk", "görev", "proje", "raci")):
            return "raci"
        if any(kw in q_lower for kw in ("öncelik", "zaman", "eisenhower")):
            return "eisenhower"
        return "rapid"

    @staticmethod
    def build_framework_prompt(
        question: str,
        department: str,
        framework_key: str,
    ) -> Tuple[str, str]:
        fw = DECISION_FRAMEWORKS.get(framework_key, DECISION_FRAMEWORKS["rapid"])
        roles = ", ".join(fw["roles"])
        system_prompt = (
            f"Sen bir Karar Destek Uzmanısın. {fw['name']} çerçevesini uyguluyorsun.\n\n"
            f"Çerçeve: {fw['name']}\n"
            f"Roller/Boyutlar: {roles}\n"
            f"En iyi kullanım: {fw['best_for']}\n\n"
            f"Departman: {department}\n\n"
            "Kararı bu çerçeveye göre analiz et ve yapılandırılmış öneri sun.\n\n"
            "1. Karar bağlamını özetle\n"
            "2. Her rol/boyut için atama yap\n"
            "3. Alternatif seçenekleri listele\n"
            "4. Net öneri ver\n"
            "5. Uygulama adımlarını belirt"
        )
        user_prompt = f"Karar konusu: {question}"
        return system_prompt, user_prompt


# ═══════════════════════════════════════════════════════════════════
# YÖNETİM KURULU RAPOR OLUŞTURUCU
# ═══════════════════════════════════════════════════════════════════

class BoardReportBuilder:
    """Yönetim kurulu sunumu formatında rapor üret."""

    @staticmethod
    def build_board_prompt(
        question: str,
        department: str,
        briefing_data: str = "",
    ) -> Tuple[str, str]:
        system_prompt = (
            "Sen bir Yönetim Kurulu Rapor Yazarısın.\n\n"
            "Profesyonel, net, yönetim kurulu toplantısına uygun sunum hazırla.\n\n"
            "Bölümler:\n"
            "1. YÖNETİCİ ÖZETİ (max 5 cümle)\n"
            "2. FİNANSAL PERFORMANS (gelir, gider, kâr trendleri)\n"
            "3. OPERASYONEL DURUM (üretim, kalite, müşteri memnuniyeti)\n"
            "4. STRATEJİK İLERLEME (hedeflere yaklaşım)\n"
            "5. RİSK MATRİSİ (en kritik 5 risk, tablo formatında)\n"
            "6. YATIRIM İHTİYAÇLARI (bütçe talepleri)\n"
            "7. KARAR KONULARI (yönetim kurulunun onayı gereken konular)\n"
            "8. SONRAKİ DÖNEM BEKLENTİLER\n\n"
            f"Departman: {department}\n\n"
            "Kurallar:\n"
            "- Profesyonel dil (3. tekil şahıs)\n"
            "- Sayısal veriler mümkün olduğunca\n"
            "- Net karar önerileri (Evet/Hayır seçenekleriyle)\n"
            "- Vizyon uyumluluk kontrolü"
        )
        user_prompt = f"Yönetim kurulu raporu talebi: {question}"
        if briefing_data:
            user_prompt += f"\n\nBrifing verileri:\n{briefing_data[:1000]}"
        return system_prompt, user_prompt


# ═══════════════════════════════════════════════════════════════════
# REKABETÇİ RADARI
# ═══════════════════════════════════════════════════════════════════

class CompetitiveRadar:
    """Rakip hareketleri izleme ve değerlendirme."""

    @staticmethod
    def build_competitor_prompt(
        question: str,
        department: str,
        industry: str = "Tekstil",
    ) -> Tuple[str, str]:
        system_prompt = (
            "Sen bir Rekabet İstihbaratı Uzmanısın.\n\n"
            f"Sektör: {industry}\n"
            f"Departman: {department}\n\n"
            "Rakiplerin olası hareketlerini ve bunlara karşı cevapları değerlendir.\n\n"
            "Her rakip için:\n"
            "1. Rakip adı/profili\n"
            "2. Son hamle/trendi\n"
            "3. Etki değerlendirmesi (bize etkisi)\n"
            "4. Tehdit seviyesi: 0.0-1.0\n"
            "5. Fırsat (rakibin zayıflığı bizim fırsatımız mı?)\n"
            "6. Önerilen cevap (stratejik hamle)\n\n"
            "Format:\n"
            "RAKİP 1: [Ad/Profil]\n"
            "Hamle: [son hareket]\n"
            "Etki: [değerlendirme]\n"
            "Tehdit: [0.X]\n"
            "Fırsat: [varsa]\n"
            "Cevap: [önerilen strateji]"
        )
        user_prompt = f"Rekabet analizi talebi: {question}"
        return system_prompt, user_prompt

    @staticmethod
    def parse_competitor_response(raw_text: str) -> List[CompetitorInfo]:
        """Rakip yanıtını parse et."""
        import re
        competitors = []
        blocks = re.split(r"\n(?=(?:rakip|competitor)\s*\d)", raw_text, flags=re.IGNORECASE)
        for block in blocks:
            if not block.strip():
                continue
            name = ""
            move = ""
            impact = ""
            threat = 0.5
            opportunity = ""
            response = ""

            for line in block.strip().split("\n"):
                clean = line.strip()
                lower = clean.lower()
                r_match = re.match(r"(?:rakip|competitor)\s*\d+\s*[:.]\s*(.*)", clean, re.IGNORECASE)
                if r_match:
                    name = r_match.group(1).strip()
                    continue
                if "hamle" in lower or "move" in lower:
                    move = clean.split(":", 1)[-1].strip()
                elif "etki" in lower or "impact" in lower:
                    impact = clean.split(":", 1)[-1].strip()
                elif "tehdit" in lower or "threat" in lower:
                    val = re.search(r"(\d+\.?\d*)", clean)
                    if val:
                        threat = min(float(val.group(1)), 1.0)
                elif "fırsat" in lower or "opportunity" in lower:
                    opportunity = clean.split(":", 1)[-1].strip()
                elif "cevap" in lower or "response" in lower:
                    response = clean.split(":", 1)[-1].strip()

            if name:
                competitors.append(CompetitorInfo(
                    competitor_name=name,
                    recent_move=move,
                    impact_assessment=impact,
                    threat_level=threat,
                    opportunity=opportunity,
                    recommended_response=response,
                ))
        return competitors


# ═══════════════════════════════════════════════════════════════════
# BRİFİNG YANIT PARSER
# ═══════════════════════════════════════════════════════════════════

class BriefingResponseParser:
    """LLM yanıtından brifing bileşenlerini parse et."""

    @staticmethod
    def parse_kpis(raw_text: str) -> List[KPIMetric]:
        """KPI satırlarını parse et."""
        import re
        kpis = []
        for line in raw_text.split("\n"):
            clean = line.strip()
            if not clean.startswith(("-", "•", "*")):
                continue
            text = clean.lstrip("-•* ").strip()
            if ":" not in text:
                continue
            parts = text.split(":", 1)
            name = parts[0].strip()
            rest = parts[1].strip()

            trend = TrendDirection.STABLE
            if "↑" in rest or "artış" in rest.lower():
                trend = TrendDirection.UP
            elif "↓" in rest or "düşüş" in rest.lower():
                trend = TrendDirection.DOWN

            category = "Genel"
            cat_match = re.search(r"kategori\s*[:.]\s*(\w+)", rest, re.IGNORECASE)
            if cat_match:
                category = cat_match.group(1)

            value_part = rest.split("|")[0].strip() if "|" in rest else rest.split("(")[0].strip()

            kpis.append(KPIMetric(
                name=name[:80],
                category=category,
                current_value=value_part[:50],
                trend=trend,
            ))
        return kpis

    @staticmethod
    def parse_action_items(raw_text: str) -> List[ActionableItem]:
        """Eylem maddelerini parse et."""
        import re
        items = []
        in_action_section = False
        for line in raw_text.split("\n"):
            clean = line.strip()
            lower = clean.lower()
            if "eylem" in lower or "action" in lower:
                if clean.startswith("#"):
                    in_action_section = True
                    continue
            if in_action_section and clean.startswith(("-", "•", "*")):
                text = clean.lstrip("-•* ").strip()
                urgency = Urgency.MEDIUM
                if "[acil]" in text.lower() or "[critical]" in text.lower():
                    urgency = Urgency.CRITICAL
                elif "[high]" in text.lower() or "[yüksek]" in text.lower():
                    urgency = Urgency.HIGH

                dept = ""
                dept_match = re.search(r"sorumlu\s*[:.]\s*(\w+)", text, re.IGNORECASE)
                if dept_match:
                    dept = dept_match.group(1)

                title = text.split("|")[0].split(":")[0].strip()[:100]
                desc = text[:200]
                items.append(ActionableItem(
                    title=title,
                    description=desc,
                    urgency=urgency,
                    department=dept,
                ))
            elif in_action_section and clean.startswith("#"):
                in_action_section = False
        return items


# ═══════════════════════════════════════════════════════════════════
# BRİFİNG TAKİPÇİSİ
# ═══════════════════════════════════════════════════════════════════

class ExecutiveTracker:
    """Geçmiş brifing deposu ve istatistikleri."""

    def __init__(self):
        self._briefings: List[ExecutiveBriefing] = []
        self._type_counts: Dict[str, int] = defaultdict(int)

    def record(self, briefing: ExecutiveBriefing):
        self._briefings.append(briefing)
        if len(self._briefings) > MAX_BRIEFING_HISTORY:
            self._briefings = self._briefings[-MAX_BRIEFING_HISTORY:]
        self._type_counts[briefing.report_type.value] += 1
        logger.info("executive_briefing_recorded",
                     briefing_id=briefing.briefing_id,
                     report_type=briefing.report_type.value,
                     kpis=len(briefing.kpis),
                     risks=len(briefing.risks))

    def get_recent(self, n: int = 20) -> List[dict]:
        return [b.to_dict() for b in self._briefings[-n:]]

    def get_statistics(self) -> dict:
        total = len(self._briefings)
        if total == 0:
            return {"total_briefings": 0}
        return {
            "total_briefings": total,
            "type_distribution": dict(self._type_counts),
            "avg_kpis": round(sum(len(b.kpis) for b in self._briefings) / total, 1),
            "avg_risks": round(sum(len(b.risks) for b in self._briefings) / total, 1),
            "avg_actions": round(sum(len(b.action_items) for b in self._briefings) / total, 1),
        }

    def reset(self):
        self._briefings.clear()
        self._type_counts.clear()
        logger.info("executive_tracker_reset")


# ═══════════════════════════════════════════════════════════════════
# ANA ORKESTRATÖR — ExecutiveIntelligenceEngine
# ═══════════════════════════════════════════════════════════════════

class ExecutiveIntelligenceEngine:
    """Executive Intelligence orkestratörü.

    Kullanım:
        engine = executive_intelligence
        trigger, reason = engine.should_generate(question, mode, intent)
        if trigger:
            prompts = engine.build_prompts(question, dept, mode)
            # LLM çağrıları engine.py yapar
            result = engine.finalize_briefing(...)
    """

    def __init__(self):
        self.briefing_gen = ExecutiveBriefingGenerator()
        self.kpi_correlator = KPICrossCorrelator()
        self.risk_aggregator = StrategicRiskAggregator()
        self.decision_fw = DecisionFramework()
        self.board_builder = BoardReportBuilder()
        self.competitive_radar = CompetitiveRadar()
        self.response_parser = BriefingResponseParser()
        self.tracker = ExecutiveTracker()
        self._enabled: bool = True
        self._started_at: str = _utcnow_str()

    def should_generate(
        self,
        question: str,
        mode: str,
        intent: str,
        force: bool = False,
    ) -> Tuple[bool, str]:
        if not self._enabled and not force:
            return False, "exec_intel_disabled"
        return should_trigger_executive_intel(question, mode, intent, force)

    def build_prompts(
        self,
        question: str,
        department: str,
        mode: str,
        industry: str = "Tekstil",
    ) -> Dict[str, Tuple[str, str]]:
        report_type = self.briefing_gen.detect_report_type(question)
        prompts: Dict[str, Tuple[str, str]] = {
            "briefing": self.briefing_gen.build_briefing_prompt(
                question, department, report_type
            ),
            "risk_synthesis": self.risk_aggregator.build_risk_synthesis_prompt(
                question, department
            ),
        }
        q_lower = question.lower()
        if any(kw in q_lower for kw in ("korelasyon", "correlation", "ilişki", "bağlantı")):
            prompts["kpi_correlation"] = self.kpi_correlator.build_correlation_prompt(
                question, department
            )
        if any(kw in q_lower for kw in ("board", "yönetim kurulu", "sunum")):
            prompts["board_report"] = self.board_builder.build_board_prompt(
                question, department
            )
        if any(kw in q_lower for kw in ("rakip", "rekabet", "competitor")):
            prompts["competitor"] = self.competitive_radar.build_competitor_prompt(
                question, department, industry
            )
        if any(kw in q_lower for kw in ("karar", "decision", "seçenek")):
            fw_key = self.decision_fw.select_framework(question)
            prompts["decision_framework"] = self.decision_fw.build_framework_prompt(
                question, department, fw_key
            )
        return prompts

    def parse_responses(self, raw_responses: Dict[str, str]) -> Dict[str, Any]:
        parsed: Dict[str, Any] = {}
        if "briefing" in raw_responses:
            text = raw_responses["briefing"]
            parsed["executive_summary"] = text[:500]
            parsed["kpis"] = self.response_parser.parse_kpis(text)
            parsed["action_items"] = self.response_parser.parse_action_items(text)
        if "risk_synthesis" in raw_responses:
            parsed["risks"] = self.risk_aggregator.parse_risk_response(raw_responses["risk_synthesis"])
        if "kpi_correlation" in raw_responses:
            parsed["kpi_correlations"] = self.kpi_correlator.parse_correlation_response(
                raw_responses["kpi_correlation"]
            )
        if "competitor" in raw_responses:
            parsed["competitor_intel"] = self.competitive_radar.parse_competitor_response(
                raw_responses["competitor"]
            )
        return parsed

    def finalize_briefing(
        self,
        question: str,
        department: str,
        mode: str,
        parsed_data: Dict[str, Any],
        total_time_ms: float = 0.0,
        triggered_by: str = "auto",
    ) -> ExecutiveBriefing:
        report_type = self.briefing_gen.detect_report_type(question)
        kpis = parsed_data.get("kpis", [])
        risks = parsed_data.get("risks", [])
        actions = parsed_data.get("action_items", [])

        conf_adj = 0.0
        if kpis:
            conf_adj += 3
        if risks:
            conf_adj += 3
        if actions:
            conf_adj += 2

        briefing = ExecutiveBriefing(
            report_type=report_type,
            title=question[:100],
            question=question,
            department=department,
            mode=mode,
            executive_summary=parsed_data.get("executive_summary", ""),
            kpis=kpis,
            kpi_correlations=parsed_data.get("kpi_correlations", []),
            risks=risks,
            action_items=actions,
            competitor_intel=parsed_data.get("competitor_intel", []),
            confidence_adjustment=conf_adj,
            total_time_ms=total_time_ms,
            triggered_by=triggered_by,
        )
        self.tracker.record(briefing)
        return briefing

    def get_dashboard(self) -> dict:
        return {
            "available": True,
            "enabled": self._enabled,
            "started_at": self._started_at,
            "statistics": self.tracker.get_statistics(),
            "recent_briefings": self.tracker.get_recent(10),
            "settings": {
                "briefing_sections": BRIEFING_SECTIONS,
                "kpi_categories": KPI_CATEGORIES,
                "decision_frameworks": list(DECISION_FRAMEWORKS.keys()),
                "report_types": [t.value for t in ReportType],
            },
        }

    def set_enabled(self, enabled: bool) -> dict:
        old = self._enabled
        self._enabled = enabled
        logger.info("executive_intel_toggled", old=old, new=enabled)
        return {"enabled": enabled, "previous": old}

    def reset(self):
        self.tracker.reset()
        self._started_at = _utcnow_str()
        logger.info("executive_intel_reset")


# ═══════════════════════════════════════════════════════════════════
# GLOBAL SINGLETON
# ═══════════════════════════════════════════════════════════════════

executive_intelligence: ExecutiveIntelligenceEngine = ExecutiveIntelligenceEngine()


def check_executive_trigger(
    question: str, mode: str, intent: str, force: bool = False,
) -> Tuple[bool, str]:
    return executive_intelligence.should_generate(question, mode, intent, force)


def get_executive_dashboard() -> dict:
    return executive_intelligence.get_dashboard()
