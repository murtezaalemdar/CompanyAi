"""Executive Digest — Üst Yönetim Karar Özeti Motoru

Pipeline'daki tüm modül çıktılarını tek sayfada özetleyen,
"5 madde + Risk + Fırsat + Net Öneri" formatında sade yönetim özeti.

executive_intelligence.py'dan farkı:
  - executive_intelligence → tam kapsamlı brifing, rapor, sunum (1100+ satır)
  - executive_digest → her AI cevabına eklenen kısa, aksiyonel özet (this)

Format:
  ┌─────────────────────────────────────────┐
  │ 📋 YÖNETİM ÖZETİ                       │
  │                                          │
  │ 1. Durum: ...                            │
  │ 2. Temel Bulgu: ...                      │
  │ 3. Tahmini Etki: ... [KPI]              │
  │ 4. Risk Profili: ...                     │
  │ 5. Alternatif: ...                       │
  │                                          │
  │ ⚠ Risk: ...                              │
  │ 💡 Fırsat: ...                           │
  │                                          │
  │ ➤ Net Öneri: ...                         │
  │ Güven: 84/100 | Etki: Orta-Yüksek       │
  └─────────────────────────────────────────┘

v5.3.0 — CompanyAI Enterprise
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Any


# ─── Enums ──────────────────────────────────────────────────────────

class DigestPriority(Enum):
    """Özet öncelik seviyesi"""
    CRITICAL = "critical"     # Acil aksiyon gerektirir
    HIGH = "high"             # Önemli, kısa vadede ele alınmalı
    MODERATE = "moderate"     # Normal seyreden
    LOW = "low"               # Bilgi amaçlı
    INFORMATIONAL = "info"    # Sadece bilgilendirme


class DigestLength(Enum):
    """Özet uzunluğu"""
    MICRO = "micro"       # 2-3 satır
    SHORT = "short"       # 5+2+1 formatı (varsayılan)
    DETAILED = "detailed" # Genişletilmiş


# ─── Data Classes ───────────────────────────────────────────────────

@dataclass
class DigestItem:
    """Özetteki tek bir madde"""
    number: int
    label: str       # "Durum", "Temel Bulgu", vb.
    content: str     # Madde içeriği
    source: str = "" # Hangi modülden geldi


@dataclass
class ExecutiveDigest:
    """Tam yönetim özeti"""
    items: List[DigestItem]
    risk_statement: str
    opportunity_statement: str
    net_recommendation: str
    quality_score: float       # 0-100
    quality_band: str
    impact_level: str          # "Yüksek", "Orta-Yüksek", vb.
    priority: DigestPriority
    department: str
    question_preview: str      # İlk 100 karakter
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "items": [{"number": it.number, "label": it.label, "content": it.content} for it in self.items],
            "risk": self.risk_statement,
            "opportunity": self.opportunity_statement,
            "net_recommendation": self.net_recommendation,
            "quality_score": round(self.quality_score, 1),
            "quality_band": self.quality_band,
            "impact_level": self.impact_level,
            "priority": self.priority.value,
            "department": self.department,
        }


# ─── Digest Builder ────────────────────────────────────────────────

class DigestBuilder:
    """Pipeline çıktılarından Executive Digest oluşturur"""

    # Varsayılan madde etiketleri
    LABELS = [
        "Durum",
        "Temel Bulgu",
        "Tahmini Etki",
        "Risk Profili",
        "Alternatif / Sonraki Adım",
    ]

    def __init__(self):
        pass

    def build(
        self,
        question: str,
        ai_answer: str,
        department: str = "",
        # decision_quality çıktısı
        quality_score: float = 0,
        quality_band: str = "",
        quality_breakdown: Optional[Dict[str, float]] = None,
        # kpi_impact çıktısı
        kpi_impacts: Optional[List[Dict]] = None,
        impact_score: float = 0,
        kpi_executive_summary: str = "",
        # decision_gatekeeper çıktısı
        gate_verdict: str = "",
        gate_risks: Optional[List[str]] = None,
        # uncertainty çıktısı
        uncertainty: float = 50,
        confidence: float = 50,
        margin_of_error: float = 0,
        # reflection çıktısı
        reflection_score: float = 0,
        reflection_notes: str = "",
        # causal çıktısı
        causal_chain: Optional[str] = None,
        # scenario çıktısı
        scenarios: Optional[List[Dict]] = None,
        # debate çıktısı
        debate_consensus: Optional[str] = None,
        # ood status
        ood_detected: bool = False,
        ood_note: str = "",
        # uzunluk
        length: DigestLength = DigestLength.SHORT,
    ) -> ExecutiveDigest:
        """Tek bir Executive Digest oluştur"""

        items = []

        # 1. DURUM
        situation = self._build_situation(question, department, ood_detected, ood_note)
        items.append(DigestItem(1, self.LABELS[0], situation, "question"))

        # 2. TEMEL BULGU
        finding = self._build_finding(ai_answer, reflection_score, reflection_notes, debate_consensus)
        items.append(DigestItem(2, self.LABELS[1], finding, "reflection"))

        # 3. TAHMİNİ ETKİ
        impact = self._build_impact(kpi_impacts, kpi_executive_summary, impact_score)
        items.append(DigestItem(3, self.LABELS[2], impact, "kpi_impact"))

        # 4. RİSK PROFİLİ
        risk_profile = self._build_risk_profile(gate_verdict, gate_risks, uncertainty, margin_of_error)
        items.append(DigestItem(4, self.LABELS[3], risk_profile, "gatekeeper"))

        # 5. ALTERNATİF / SONRAKI ADIM
        alternative = self._build_alternative(scenarios, causal_chain)
        items.append(DigestItem(5, self.LABELS[4], alternative, "scenario"))

        # RISK STATEMENT
        risk_stmt = self._extract_risk_statement(gate_verdict, gate_risks, uncertainty, ood_detected)

        # OPPORTUNITY STATEMENT
        opp_stmt = self._extract_opportunity(kpi_impacts, kpi_executive_summary, scenarios)

        # NET ÖNERİ
        net_rec = self._build_net_recommendation(
            ai_answer, gate_verdict, quality_score, impact_score, confidence
        )

        # Impact level
        impact_level = self._classify_impact(impact_score, kpi_impacts)

        # Priority
        priority = self._classify_priority(gate_verdict, quality_score, uncertainty, ood_detected)

        return ExecutiveDigest(
            items=items,
            risk_statement=risk_stmt,
            opportunity_statement=opp_stmt,
            net_recommendation=net_rec,
            quality_score=quality_score,
            quality_band=quality_band,
            impact_level=impact_level,
            priority=priority,
            department=department,
            question_preview=question[:100],
        )

    # ─── Private builders ───────────────────────────────────────

    def _build_situation(self, question: str, department: str, ood: bool, ood_note: str) -> str:
        """Madde 1: Durum"""
        dept_prefix = f"[{department}] " if department else ""
        q_short = question[:120].rstrip(".")

        parts = [f"{dept_prefix}{q_short}"]
        if ood:
            parts.append(f"⚠ Daha önce karşılaşılmamış soru tipi. {ood_note}")

        return ". ".join(parts)

    def _build_finding(self, answer: str, reflection_score: float, reflection_notes: str, consensus: Optional[str]) -> str:
        """Madde 2: Temel Bulgu"""
        # Cevabın ilk anlamlı cümlesini al
        sentences = [s.strip() for s in answer.replace("\n", ". ").split(".") if len(s.strip()) > 15]
        core = sentences[0][:150] if sentences else answer[:150]

        parts = [core]

        if reflection_score > 0:
            qual_word = "Güçlü" if reflection_score >= 80 else ("Yeterli" if reflection_score >= 60 else "Zayıf")
            parts.append(f"Analiz kalitesi: {qual_word} ({reflection_score:.0f}/100)")

        if consensus:
            parts.append(f"Uzlaşı: {consensus[:80]}")

        return ". ".join(parts)

    def _build_impact(self, kpi_impacts: Optional[List[Dict]], kpi_summary: str, impact_score: float) -> str:
        """Madde 3: Tahmini Etki"""
        if kpi_summary:
            return kpi_summary[:200]

        if kpi_impacts:
            top_impacts = kpi_impacts[:3]
            desc_parts = []
            for kpi in top_impacts:
                name = kpi.get("kpi_name", kpi.get("kpi_id", "?"))
                direction = kpi.get("direction", "?")
                magnitude = kpi.get("magnitude", "?")
                arrow = "↑" if direction in ("positive", "POSITIVE") else ("↓" if direction in ("negative", "NEGATIVE") else "↔")
                desc_parts.append(f"{name} {arrow} ({magnitude})")
            return f"Etki Skoru: {impact_score:.0f}/100 — " + ", ".join(desc_parts)

        return "KPI etki tahmini mevcut değil"

    def _build_risk_profile(self, gate_verdict: str, gate_risks: Optional[List[str]], uncertainty: float, moe: float) -> str:
        """Madde 4: Risk Profili"""
        parts = []

        verdict_map = {
            "PASS": "✅ Geçti",
            "PASS_WITH_WARNING": "⚠️ Uyarılı geçti",
            "BLOCK": "🛑 Bloklandı",
            "ESCALATE": "🔺 Eskalasyon",
        }
        if gate_verdict:
            parts.append(verdict_map.get(gate_verdict, gate_verdict))

        if uncertainty > 0:
            unc_word = "Düşük" if uncertainty < 30 else ("Orta" if uncertainty < 60 else "Yüksek")
            parts.append(f"Belirsizlik: {unc_word} (%{uncertainty:.0f})")

        if moe > 0:
            parts.append(f"±%{moe:.1f} hata payı")

        if gate_risks:
            risk_preview = gate_risks[:2]
            parts.append(f"Risk: {'; '.join(r[:60] for r in risk_preview)}")

        return ". ".join(parts) if parts else "Risk profili mevcut değil"

    def _build_alternative(self, scenarios: Optional[List[Dict]], causal_chain: Optional[str]) -> str:
        """Madde 5: Alternatif / Sonraki Adım"""
        parts = []

        if scenarios:
            for sc in scenarios[:2]:
                name = sc.get("name", sc.get("label", "Senaryo"))
                probability = sc.get("probability", sc.get("prob", 0))
                parts.append(f"{name} (%{probability*100:.0f})")

        if causal_chain:
            parts.append(f"Nedensellik: {causal_chain[:100]}")

        if not parts:
            parts.append("Alternatif senaryo bilgisi mevcut değil")

        return ". ".join(parts)

    def _extract_risk_statement(self, gate_verdict: str, gate_risks: Optional[List[str]], uncertainty: float, ood: bool) -> str:
        """Risk satırı"""
        if ood:
            return "Sistem bu tip soruyu daha önce görmedi — öneriler ekstra dikkatle değerlendirilmeli"

        if gate_verdict == "BLOCK":
            risk_detail = gate_risks[0][:100] if gate_risks else "Kritik risk tespit edildi"
            return f"Karar bloklandı: {risk_detail}"

        if gate_verdict == "ESCALATE":
            return "Üst yönetim onayı gerekli — risk seviyesi yüksek"

        if uncertainty > 70:
            return f"Yüksek belirsizlik (%{uncertainty:.0f}) — karar öncesi ek veri toplanmalı"

        if gate_risks:
            return gate_risks[0][:120]

        return "Belirgin risk tespit edilmedi"

    def _extract_opportunity(self, kpi_impacts: Optional[List[Dict]], kpi_summary: str, scenarios: Optional[List[Dict]]) -> str:
        """Fırsat satırı"""
        if kpi_impacts:
            positive = [k for k in kpi_impacts if k.get("direction") in ("positive", "POSITIVE")]
            if positive:
                top = positive[0]
                name = top.get("kpi_name", top.get("kpi_id", "KPI"))
                change = top.get("estimated_change_pct", 0)
                return f"{name} %{abs(change):.1f} iyileşebilir" if change else f"{name} pozitif etkilenebilir"

        if scenarios:
            best = max(scenarios, key=lambda s: s.get("probability", 0) * s.get("impact", 0), default=None)
            if best:
                return f"En iyi senaryo: {best.get('name', 'Olumlu')} — olasılık %{best.get('probability', 0)*100:.0f}"

        return "Mevcut bilgilerle belirgin fırsat tespit edilemedi"

    def _build_net_recommendation(self, answer: str, gate_verdict: str, quality: float, impact: float, confidence: float) -> str:
        """Net öneri satırı"""
        if gate_verdict == "BLOCK":
            return "Bu öneri uygulanmamalı — risk seviyesi kabul edilemez düzeyde"

        if gate_verdict == "ESCALATE":
            return "Öneri üst yönetim onayına sunulmalı — kritik karar eşiğinde"

        # Cevaptan ilk aksiyonel cümleyi çek
        action_keywords = ["önerilir", "yapılmalı", "uygulanmalı", "geçilmeli", "artırılmalı",
                          "azaltılmalı", "planlanmalı", "değerlendirilmeli", "başlanmalı",
                          "durdurulmalı", "optimize", "iyileştirilmeli"]

        sentences = [s.strip() for s in answer.replace("\n", ". ").split(".") if len(s.strip()) > 10]
        action_sentence = ""
        for sent in sentences:
            if any(kw in sent.lower() for kw in action_keywords):
                action_sentence = sent[:150]
                break

        if not action_sentence and sentences:
            # Son cümle genellikle öneri olur
            action_sentence = sentences[-1][:150]

        qual_suffix = ""
        if quality >= 80:
            qual_suffix = "(Güven: yüksek)"
        elif quality >= 60:
            qual_suffix = "(Güven: orta)"
        else:
            qual_suffix = "(Güven: düşük — dikkatli değerlendirin)"

        return f"{action_sentence} {qual_suffix}"

    def _classify_impact(self, impact_score: float, kpi_impacts: Optional[List[Dict]]) -> str:
        """Etki seviyesi sınıflandırması"""
        if impact_score >= 80:
            return "Çok Yüksek"
        if impact_score >= 60:
            return "Yüksek"
        if impact_score >= 40:
            return "Orta-Yüksek"
        if impact_score >= 20:
            return "Orta"

        if kpi_impacts and len(kpi_impacts) > 0:
            return "Düşük-Orta"

        return "Düşük"

    def _classify_priority(self, gate_verdict: str, quality: float, uncertainty: float, ood: bool) -> DigestPriority:
        """Öncelik seviyesi"""
        if gate_verdict in ("BLOCK", "ESCALATE"):
            return DigestPriority.CRITICAL
        if ood:
            return DigestPriority.HIGH
        if uncertainty > 70 or quality < 40:
            return DigestPriority.HIGH
        if quality >= 70 and uncertainty < 40:
            return DigestPriority.MODERATE
        return DigestPriority.LOW


# ─── Tracker ────────────────────────────────────────────────────────

class DigestTracker:
    """Oluşturulan özetleri izler"""

    MAX_HISTORY = 200

    def __init__(self):
        self._history: List[dict] = []
        self._priority_counts: Dict[str, int] = {}
        self._dept_counts: Dict[str, int] = {}

    def record(self, digest: ExecutiveDigest):
        entry = {
            "question_preview": digest.question_preview,
            "quality_score": digest.quality_score,
            "impact_level": digest.impact_level,
            "priority": digest.priority.value,
            "department": digest.department,
            "timestamp": digest.timestamp,
        }
        self._history.append(entry)
        if len(self._history) > self.MAX_HISTORY:
            self._history = self._history[-self.MAX_HISTORY:]

        self._priority_counts[digest.priority.value] = self._priority_counts.get(digest.priority.value, 0) + 1
        if digest.department:
            self._dept_counts[digest.department] = self._dept_counts.get(digest.department, 0) + 1

    def get_stats(self) -> dict:
        total = len(self._history)
        return {
            "total_digests": total,
            "priority_distribution": dict(self._priority_counts),
            "department_distribution": dict(self._dept_counts),
        }

    def get_dashboard(self) -> dict:
        stats = self.get_stats()
        recent = self._history[-5:] if self._history else []
        return {
            **stats,
            "recent_digests": list(reversed(recent)),
        }


# ─── Module Instances ──────────────────────────────────────────────

_builder = DigestBuilder()
_tracker = DigestTracker()


# ─── Public API ─────────────────────────────────────────────────────

def generate_executive_digest(
    question: str,
    ai_answer: str,
    department: str = "",
    quality_score: float = 0,
    quality_band: str = "",
    quality_breakdown: Optional[Dict[str, float]] = None,
    kpi_impacts: Optional[List[Dict]] = None,
    impact_score: float = 0,
    kpi_executive_summary: str = "",
    gate_verdict: str = "",
    gate_risks: Optional[List[str]] = None,
    uncertainty: float = 50,
    confidence: float = 50,
    margin_of_error: float = 0,
    reflection_score: float = 0,
    reflection_notes: str = "",
    causal_chain: Optional[str] = None,
    scenarios: Optional[List[Dict]] = None,
    debate_consensus: Optional[str] = None,
    ood_detected: bool = False,
    ood_note: str = "",
    length: DigestLength = DigestLength.SHORT,
) -> ExecutiveDigest:
    """Tam bir Executive Digest üret"""
    digest = _builder.build(
        question=question,
        ai_answer=ai_answer,
        department=department,
        quality_score=quality_score,
        quality_band=quality_band,
        quality_breakdown=quality_breakdown,
        kpi_impacts=kpi_impacts,
        impact_score=impact_score,
        kpi_executive_summary=kpi_executive_summary,
        gate_verdict=gate_verdict,
        gate_risks=gate_risks,
        uncertainty=uncertainty,
        confidence=confidence,
        margin_of_error=margin_of_error,
        reflection_score=reflection_score,
        reflection_notes=reflection_notes,
        causal_chain=causal_chain,
        scenarios=scenarios,
        debate_consensus=debate_consensus,
        ood_detected=ood_detected,
        ood_note=ood_note,
        length=length,
    )
    _tracker.record(digest)
    return digest


def format_executive_digest(digest: ExecutiveDigest) -> str:
    """Executive Digest'i Markdown formatında göster"""
    lines = [
        "",
        "---",
        "### 📋 YÖNETİM ÖZETİ",
        "",
    ]

    # 5 madde
    for item in digest.items:
        lines.append(f"**{item.number}. {item.label}:** {item.content}")

    lines.append("")

    # Risk & Fırsat
    lines.append(f"⚠ **Risk:** {digest.risk_statement}")
    lines.append(f"💡 **Fırsat:** {digest.opportunity_statement}")
    lines.append("")

    # Net Öneri
    lines.append(f"➤ **Net Öneri:** {digest.net_recommendation}")
    lines.append("")

    # Alt bilgi
    priority_icons = {
        "critical": "🔴", "high": "🟠", "moderate": "🟡",
        "low": "🟢", "info": "⚪",
    }
    icon = priority_icons.get(digest.priority.value, "⚪")

    lines.append(
        f"Güven: {digest.quality_score:.0f}/100 ({digest.quality_band}) "
        f"| Etki: {digest.impact_level} "
        f"| Öncelik: {icon} {digest.priority.value}"
    )
    lines.append("---")
    lines.append("")

    return "\n".join(lines)


def format_digest_micro(digest: ExecutiveDigest) -> str:
    """Çok kısa özet — tek satır"""
    priority_icons = {
        "critical": "🔴", "high": "🟠", "moderate": "🟡",
        "low": "🟢", "info": "⚪",
    }
    icon = priority_icons.get(digest.priority.value, "⚪")

    return (
        f"{icon} Güven: {digest.quality_score:.0f}/100 | "
        f"Etki: {digest.impact_level} | "
        f"Risk: {digest.risk_statement[:60]}"
    )


# ─── Dashboard ──────────────────────────────────────────────────────

def get_dashboard() -> dict:
    return {
        "module": "executive_digest",
        "module_name": "Yönetim Özeti Motoru",
        **_tracker.get_dashboard(),
    }


def get_statistics() -> dict:
    return _tracker.get_stats()
