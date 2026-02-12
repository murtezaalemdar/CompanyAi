"""
Decision Impact Ranking Engine — v3.1.0
=========================================
Stratejik kararları ROI, Risk Azaltma, Stratejik Uyum ve
Uygulama Zorluğu kriterlerine göre puanlar ve sıralar.

Formül:
  PriorityScore = (ROI × RiskReduction × StrategicAlignment) / ImplementationDifficulty

Her kriter 1-10 arasında bir skorla değerlendirilir.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

try:
    import structlog
    logger = structlog.get_logger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)

# ──────────────────── Ağırlıklar & Sabitler ────────────────────
CRITERIA_WEIGHTS = {
    "roi_estimate": 1.0,
    "risk_reduction": 1.0,
    "strategic_alignment": 1.0,
    "implementation_difficulty": 1.0,   # bölen olarak kullanılır
}

PRIORITY_BANDS = [
    (80, "🔴 KRİTİK — Hemen Uygula"),
    (50, "🟠 YÜKSEK — Bu Çeyrek Planla"),
    (25, "🟡 ORTA — Gelecek Çeyrek Değerlendir"),
    (10, "🟢 DÜŞÜK — İzle"),
    (0,  "⚪ ÇOK DÜŞÜK — Beklet"),
]

# ──────────────────── Veri Yapısı ────────────────────


@dataclass
class Decision:
    """Sıralanacak tek bir karar / aksiyon."""
    title: str
    description: str = ""
    roi_estimate: float = 5.0          # 1-10
    risk_reduction: float = 5.0       # 1-10
    strategic_alignment: float = 5.0  # 1-10
    implementation_difficulty: float = 5.0  # 1-10 (yüksek = zor)
    department: str = "Genel"
    priority_score: float = 0.0
    priority_band: str = ""
    rank: int = 0


@dataclass
class RankingResult:
    """Sıralama sonucu."""
    decisions: list[Decision] = field(default_factory=list)
    top_action: str = ""
    summary: str = ""
    total_evaluated: int = 0


# ──────────────────── Skor Hesaplama ────────────────────

def _clamp(value: float, lo: float = 1.0, hi: float = 10.0) -> float:
    """Değeri 1-10 arasına sınırla."""
    return max(lo, min(hi, value))


def calculate_priority_score(decision: Decision) -> float:
    """
    PriorityScore = (ROI × RiskReduction × StrategicAlignment) / ImplementationDifficulty
    
    Sonuç 0.1 — 1000 aralığında; normalize edilip 0-100 bandına çekilir.
    """
    roi = _clamp(decision.roi_estimate)
    risk = _clamp(decision.risk_reduction)
    alignment = _clamp(decision.strategic_alignment)
    difficulty = _clamp(decision.implementation_difficulty)
    
    raw = (roi * risk * alignment) / difficulty
    # Normalize: max raw = 10*10*10/1 = 1000, min = 1*1*1/10 = 0.1
    # Log-scale benzeri normalize
    normalized = (raw / 1000.0) * 100.0
    return round(normalized, 2)


def get_priority_band(score: float) -> str:
    """Skora göre öncelik bandı getir."""
    for threshold, label in PRIORITY_BANDS:
        if score >= threshold:
            return label
    return PRIORITY_BANDS[-1][1]


# ──────────────────── Ana Sıralama Fonksiyonu ────────────────────

def rank_decisions(decisions_data: list[dict[str, Any]]) -> RankingResult:
    """
    Verilen karar listesini puanla ve sırala.
    
    Args:
        decisions_data: Her biri Decision alanlarını içeren dict listesi
        
    Returns:
        RankingResult — sıralanmış kararlar, en iyi aksiyon, özet
    """
    decisions: list[Decision] = []
    
    for item in decisions_data:
        d = Decision(
            title=item.get("title", "Bilinmeyen Karar"),
            description=item.get("description", ""),
            roi_estimate=float(item.get("roi_estimate", 5)),
            risk_reduction=float(item.get("risk_reduction", 5)),
            strategic_alignment=float(item.get("strategic_alignment", 5)),
            implementation_difficulty=float(item.get("implementation_difficulty", 5)),
            department=item.get("department", "Genel"),
        )
        d.priority_score = calculate_priority_score(d)
        d.priority_band = get_priority_band(d.priority_score)
        decisions.append(d)
    
    # Skora göre azalan sırala
    decisions.sort(key=lambda x: x.priority_score, reverse=True)
    
    # Rank ata
    for i, d in enumerate(decisions, 1):
        d.rank = i
    
    top_action = decisions[0].title if decisions else "—"
    
    summary = _build_summary(decisions)
    
    result = RankingResult(
        decisions=decisions,
        top_action=top_action,
        summary=summary,
        total_evaluated=len(decisions),
    )
    
    logger.info("decisions_ranked",
                total=len(decisions),
                top_action=top_action,
                top_score=decisions[0].priority_score if decisions else 0)
    
    return result


def _build_summary(decisions: list[Decision]) -> str:
    """Sıralama özeti oluştur."""
    if not decisions:
        return "Değerlendirilecek karar bulunamadı."
    
    lines = [f"**{len(decisions)} karar değerlendirildi.**\n"]
    
    critical = [d for d in decisions if d.priority_score >= 80]
    high = [d for d in decisions if 50 <= d.priority_score < 80]
    
    if critical:
        lines.append(f"🔴 Kritik öncelikli: {len(critical)} karar — hemen uygulanmalı")
    if high:
        lines.append(f"🟠 Yüksek öncelikli: {len(high)} karar — bu çeyrek planlanmalı")
    
    lines.append(f"\n**En Önemli Aksiyon:** {decisions[0].title} (Skor: {decisions[0].priority_score})")
    
    return "\n".join(lines)


# ──────────────────── LLM Yanıtından Otomatik Çıkarım ────────────────────

def extract_decisions_from_llm(llm_text: str, question: str) -> list[dict[str, Any]]:
    """
    LLM analiz çıktısından karar önerileri çıkar ve default skorlar ata.
    
    LLM eğer JSON formatında kararlar döndürmediyse,
    metin tabanlı basit çıkarım yapar.
    """
    # ── Önce JSON array dene ──
    try:
        json_match = re.search(r'\[[\s\S]*?\]', llm_text)
        if json_match:
            parsed = json.loads(json_match.group())
            if isinstance(parsed, list) and parsed:
                valid = []
                for item in parsed:
                    if isinstance(item, dict) and "title" in item:
                        valid.append(item)
                if valid:
                    return valid
    except (json.JSONDecodeError, Exception):
        pass
    
    # ── Satır bazlı basit çıkarım ──
    decisions = []
    lines = llm_text.split("\n")
    
    # Numbered list items veya bullet items
    for line in lines:
        line = line.strip()
        # "1. ...", "- ...", "• ..."
        clean = re.sub(r'^[\d]+[\.\)]\s*', '', line)
        clean = re.sub(r'^[-•*]\s*', '', clean)
        clean = clean.strip()
        
        if len(clean) > 15 and any(k in clean.lower() for k in [
            "öneri", "aksiyon", "yapılmalı", "uygulan", "karar",
            "yatırım", "değişiklik", "strateji", "plan", "geliştir"
        ]):
            decisions.append({
                "title": clean[:100],
                "description": clean,
                "roi_estimate": 5,
                "risk_reduction": 5,
                "strategic_alignment": 5,
                "implementation_difficulty": 5,
                "department": "Genel",
            })
    
    return decisions[:10]  # max 10 karar


# ──────────────────── Formatlama ────────────────────

def format_ranking_table(result: RankingResult) -> str:
    """Markdown tablo olarak sıralama sonucu döndür."""
    if not result.decisions:
        return "_Sıralanacak karar bulunamadı._"
    
    lines = [
        "\n### 🏆 Karar Etki Sıralaması\n",
        "| Sıra | Karar | Skor | Öncelik | Departman |",
        "|------|-------|------|---------|-----------|",
    ]
    
    for d in result.decisions:
        lines.append(
            f"| {d.rank} | {d.title[:50]} | {d.priority_score} | {d.priority_band} | {d.department} |"
        )
    
    lines.append("")
    
    # Detay kartları (ilk 3)
    lines.append("\n#### 📊 Detay Kartları\n")
    for d in result.decisions[:3]:
        lines.append(f"**#{d.rank} — {d.title}**")
        lines.append(f"- ROI Tahmini: {d.roi_estimate}/10")
        lines.append(f"- Risk Azaltma: {d.risk_reduction}/10")
        lines.append(f"- Stratejik Uyum: {d.strategic_alignment}/10")
        lines.append(f"- Uygulama Zorluğu: {d.implementation_difficulty}/10")
        lines.append(f"- **Öncelik Skoru: {d.priority_score}** — {d.priority_band}")
        lines.append("")
    
    # Özet
    lines.append(result.summary)
    
    return "\n".join(lines)


# ──────────────────── Formül Açıklaması ────────────────────

FORMULA_EXPLANATION = """
### 📐 Karar Etki Formülü

**PriorityScore = (ROI × RiskReduction × StrategicAlignment) / ImplementationDifficulty**

| Kriter | Açıklama | Aralık |
|--------|----------|--------|
| ROI Tahmini | Yatırım getirisi beklentisi | 1-10 |
| Risk Azaltma | Riski ne kadar düşüreceği | 1-10 |
| Stratejik Uyum | Şirket stratejisine uygunluk | 1-10 |
| Uygulama Zorluğu | Implementasyon karmaşıklığı | 1-10 |

**Öncelik Bantları:**
- 🔴 ≥80: Hemen Uygula
- 🟠 ≥50: Bu Çeyrek Planla
- 🟡 ≥25: Gelecek Çeyrek
- 🟢 ≥10: İzle
- ⚪ <10: Beklet
"""


# ──────────────────── Tool Wrapper ────────────────────

def decision_ranking_tool(question: str, context: str = "", llm_output: str = "") -> str:
    """Tool registry'den çağrılabilir wrapper."""
    decisions = extract_decisions_from_llm(llm_output, question)
    
    if not decisions:
        return "Analiz çıktısından sıralanacak karar bulunamadı."
    
    result = rank_decisions(decisions)
    return format_ranking_table(result)
