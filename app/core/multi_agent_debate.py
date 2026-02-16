"""Multi-Agent Debate System v1.0 — Çok Perspektifli Tartışma Motoru

Mevcut agent_pipeline'ın ÜSTÜNE inşa edilen ileri seviye tartışma sistemi.
Sequential pipeline yerine paralel perspektif ajanları bir konuyu FARKLI
açılardan analiz eder, birbirlerinin argümanlarını çürütür/destekler,
ve sentez ajanı final kararı oluşturur.

Mimari:
  1. PerspectiveAgent'lar → Bağımsız analiz (paralel)
  2. DebateRound'lar → Argüman/Karşı-argüman (round-robin)
  3. ConsensusDetector → Uzlaşma/ayrışma tespiti
  4. SynthesisEngine → Final sentez + confidence boost/penalty
  5. DebateTracker → Geçmiş tartışma performans analizi

Perspektif Ajanları:
  - DevilsAdvocateAgent → Karşıt görüş, zayıf noktalar
  - RiskAnalystAgent    → Risk/fırsat değerlendirmesi
  - OptimistAgent       → En iyi senaryo, büyüme fırsatları
  - DomainExpertAgent   → Sektör-spesifik teknik analiz
  - EthicistAgent       → Etik, sürdürülebilirlik, sosyal etki
  - PragmatistAgent     → Uygulama fizibilitesi, kaynak/zaman

v4.7.0 — CompanyAI Enterprise
"""

from __future__ import annotations

import hashlib
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import structlog

logger = structlog.get_logger(__name__)


# ═══════════════════════════════════════════════════════════════════
# SABİTLER
# ═══════════════════════════════════════════════════════════════════

MAX_DEBATE_ROUNDS = 3              # Maksimum tartışma turu
MIN_PERSPECTIVES = 3               # Minimum perspektif sayısı
MAX_PERSPECTIVES = 6               # Maksimum perspektif sayısı
CONSENSUS_THRESHOLD = 0.70         # Uzlaşma eşiği (0-1)
STRONG_CONSENSUS_THRESHOLD = 0.85  # Güçlü uzlaşma
CONFIDENCE_BOOST_ON_CONSENSUS = 8  # Uzlaşmada confidence artışı
CONFIDENCE_PENALTY_ON_SPLIT = 5    # Ayrışmada confidence düşüşü
MAX_DEBATE_HISTORY = 200           # Saklanan tartışma sayısı
DEBATE_TRIGGER_KEYWORDS = [
    "analiz", "değerlendir", "karşılaştır", "risk", "strateji",
    "yatırım", "karar", "seçenek", "alternatif", "fırsat",
    "tehdit", "etki", "projeksiyon", "tahmin", "öneri",
    "avantaj", "dezavantaj", "swot", "maliyet", "fayda",
]
DEBATE_TRIGGER_MODES = ["Üst Düzey Analiz", "CEO Raporu", "Risk Analizi"]
DEBATE_TRIGGER_MIN_LENGTH = 40  # Kısa sorular debate'e girmez


# ═══════════════════════════════════════════════════════════════════
# ENUM & VERİ YAPILARI
# ═══════════════════════════════════════════════════════════════════

class PerspectiveType(str, Enum):
    DEVILS_ADVOCATE = "devils_advocate"
    RISK_ANALYST = "risk_analyst"
    OPTIMIST = "optimist"
    DOMAIN_EXPERT = "domain_expert"
    ETHICIST = "ethicist"
    PRAGMATIST = "pragmatist"


class DebateOutcome(str, Enum):
    CONSENSUS = "consensus"            # Tüm perspektifler uyumlu
    STRONG_CONSENSUS = "strong_consensus"  # Çok güçlü uyum
    MAJORITY = "majority"              # Çoğunluk uyumlu
    SPLIT = "split"                    # Bölünmüş görüşler
    DEADLOCK = "deadlock"              # Çözümsüz ayrışma


class ArgumentStrength(str, Enum):
    STRONG = "strong"
    MODERATE = "moderate"
    WEAK = "weak"


def _utcnow_str() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Argument:
    """Bir perspektif ajanının tek bir argümanı."""
    perspective: PerspectiveType
    claim: str
    evidence: List[str] = field(default_factory=list)
    strength: ArgumentStrength = ArgumentStrength.MODERATE
    confidence: float = 0.5
    supports: List[str] = field(default_factory=list)   # Desteklediği diğer perspektif claim'leri
    counters: List[str] = field(default_factory=list)    # Çürüttüğü diğer perspektif claim'leri
    round_number: int = 1

    def to_dict(self) -> dict:
        return {
            "perspective": self.perspective.value,
            "claim": self.claim,
            "evidence": self.evidence,
            "strength": self.strength.value,
            "confidence": self.confidence,
            "supports_count": len(self.supports),
            "counters_count": len(self.counters),
            "round": self.round_number,
        }


@dataclass
class PerspectiveAnalysis:
    """Bir perspektif ajanının tam analizi."""
    perspective: PerspectiveType
    label: str
    summary: str
    arguments: List[Argument] = field(default_factory=list)
    recommendation: str = ""
    risk_level: float = 0.0      # 0-1, bu perspektifin gördüğü risk
    opportunity_level: float = 0.0  # 0-1, bu perspektifin gördüğü fırsat
    confidence: float = 0.5
    generation_time_ms: float = 0.0

    def to_dict(self) -> dict:
        return {
            "perspective": self.perspective.value,
            "label": self.label,
            "summary": self.summary,
            "arguments": [a.to_dict() for a in self.arguments],
            "recommendation": self.recommendation,
            "risk_level": round(self.risk_level, 2),
            "opportunity_level": round(self.opportunity_level, 2),
            "confidence": round(self.confidence, 2),
            "generation_time_ms": round(self.generation_time_ms, 1),
        }


@dataclass
class DebateRound:
    """Bir tartışma turu — tüm perspektiflerin argümanları."""
    round_number: int
    arguments: List[Argument] = field(default_factory=list)
    agreements: List[Tuple[str, str]] = field(default_factory=list)  # (perspektif1, perspektif2)
    disagreements: List[Tuple[str, str, str]] = field(default_factory=list)  # (p1, p2, konu)

    def to_dict(self) -> dict:
        return {
            "round": self.round_number,
            "arguments_count": len(self.arguments),
            "arguments": [a.to_dict() for a in self.arguments],
            "agreements": len(self.agreements),
            "disagreements": len(self.disagreements),
        }


@dataclass
class ConsensusResult:
    """Uzlaşma analizi sonucu."""
    outcome: DebateOutcome
    consensus_score: float           # 0-1
    agreed_points: List[str] = field(default_factory=list)
    disputed_points: List[str] = field(default_factory=list)
    minority_views: List[str] = field(default_factory=list)
    risk_warnings: List[str] = field(default_factory=list)
    confidence_adjustment: float = 0.0

    def to_dict(self) -> dict:
        return {
            "outcome": self.outcome.value,
            "consensus_score": round(self.consensus_score, 3),
            "agreed_points": self.agreed_points,
            "disputed_points": self.disputed_points,
            "minority_views": self.minority_views,
            "risk_warnings": self.risk_warnings,
            "confidence_adjustment": self.confidence_adjustment,
        }


@dataclass
class DebateResult:
    """Tam tartışma sonucu."""
    debate_id: str
    question: str
    department: str
    mode: str
    timestamp: str
    perspectives_used: List[PerspectiveType] = field(default_factory=list)
    analyses: List[PerspectiveAnalysis] = field(default_factory=list)
    rounds: List[DebateRound] = field(default_factory=list)
    consensus: Optional[ConsensusResult] = None
    synthesis: str = ""
    final_recommendation: str = ""
    confidence_before: float = 0.0
    confidence_after: float = 0.0
    total_time_ms: float = 0.0
    triggered_by: str = "auto"

    def to_dict(self) -> dict:
        return {
            "debate_id": self.debate_id,
            "question": self.question[:200],
            "department": self.department,
            "mode": self.mode,
            "timestamp": self.timestamp,
            "perspectives": [p.value for p in self.perspectives_used],
            "perspectives_count": len(self.perspectives_used),
            "analyses": [a.to_dict() for a in self.analyses],
            "rounds_count": len(self.rounds),
            "rounds": [r.to_dict() for r in self.rounds],
            "consensus": self.consensus.to_dict() if self.consensus else None,
            "synthesis": self.synthesis,
            "final_recommendation": self.final_recommendation,
            "confidence_before": round(self.confidence_before, 1),
            "confidence_after": round(self.confidence_after, 1),
            "confidence_delta": round(self.confidence_after - self.confidence_before, 1),
            "total_time_ms": round(self.total_time_ms, 1),
            "triggered_by": self.triggered_by,
        }


# ═══════════════════════════════════════════════════════════════════
# PERSPEKTİF TANIMLARI — Her ajana özel bakış açısı
# ═══════════════════════════════════════════════════════════════════

PERSPECTIVE_CONFIGS: Dict[PerspectiveType, Dict[str, Any]] = {
    PerspectiveType.DEVILS_ADVOCATE: {
        "label": "Şeytan'ın Avukatı",
        "description": "Karşıt görüş üretir, zayıf noktaları bulur",
        "system_prompt": (
            "Sen bir Şeytan'ın Avukatı analiz ajanısın. Görevin:\n"
            "1. Önerilen çözümün/analizin ZAYıF noktalarını bul\n"
            "2. Gözden kaçabilecek RİSKLERİ tespit et\n"
            "3. Varsayımları SORGULA — hangi varsayımlar yanlışsa sonuç değişir?\n"
            "4. Alternatif senaryoları düşün — tam tersi olursa ne olur?\n"
            "5. Bias (önyargı) tespiti yap — karar vericiler neyi görmezden geliyor?\n"
            "\nHer zaman yapıcı eleştiri yap. Sadece sorun bulma değil, çözüm de öner."
        ),
        "focus_areas": ["zayıf_nokta", "varsayım", "önyargı", "alternatif_senaryo"],
        "risk_weight": 0.8,
        "opportunity_weight": 0.2,
    },
    PerspectiveType.RISK_ANALYST: {
        "label": "Risk Analisti",
        "description": "Risk/fırsat değerlendirmesi, olasılık analizi",
        "system_prompt": (
            "Sen bir Risk Analisti ajanısın. Görevin:\n"
            "1. Tüm riskleri TANIMLA ve kategorize et (operasyonel, finansal, stratejik, uyumluluk)\n"
            "2. Her risk için OLASILIK (düşük/orta/yüksek) ve ETKİ (düşük/orta/yüksek) belirle\n"
            "3. Risk azaltma STRATEJİLERİ öner — her risk için en az 1 azaltma planı\n"
            "4. Fırsatları da belirle — risk almak ne kazandırabilir?\n"
            "5. Risk/ödül DENGESİNİ değerlendir\n"
            "\nSayısal risk skorları kullan (1-10) ve öncelik sıralaması yap."
        ),
        "focus_areas": ["risk_tanımlama", "olasılık", "etki", "azaltma", "risk_ödül"],
        "risk_weight": 0.7,
        "opportunity_weight": 0.3,
    },
    PerspectiveType.OPTIMIST: {
        "label": "Fırsatçı Optimist",
        "description": "En iyi senaryolar, büyüme fırsatları, potansiyel kazançlar",
        "system_prompt": (
            "Sen bir Stratejik Optimist ajanısın. Görevin:\n"
            "1. En İYİ SENARYO'yu detaylı analiz et — her şey yolunda giderse ne olur?\n"
            "2. Büyüme FIRSATLARINI tespit et — pazar, teknoloji, inovasyon\n"
            "3. Rekabet avantajı potansiyelini değerlendir\n"
            "4. Sinerjileri bul — hangi alanlarda çarpan etkisi oluşur?\n"
            "5. Hızlı kazanımları (quick wins) belirle — düşük eforla yüksek getiri\n"
            "\nGerçekçi iyimserlik — temelsiz umut değil, veriye dayalı fırsat analizi."
        ),
        "focus_areas": ["fırsat", "büyüme", "sinerji", "quick_win", "rekabet_avantajı"],
        "risk_weight": 0.2,
        "opportunity_weight": 0.8,
    },
    PerspectiveType.DOMAIN_EXPERT: {
        "label": "Sektör Uzmanı",
        "description": "Tekstil/üretim sektörüne özel teknik analiz",
        "system_prompt": (
            "Sen bir Tekstil ve Üretim Sektörü Uzmanı ajanısın. Görevin:\n"
            "1. Sektöre ÖZGÜ faktörleri analiz et — tedarik zinciri, hammadde, mevsimsellik\n"
            "2. Sektör BENCHMARK'ları ile karşılaştır — rakipler ne yapıyor?\n"
            "3. Teknolojik TRENDLERİ değerlendir — Endüstri 4.0, otomasyon, dijitalleşme\n"
            "4. Regülasyon ve uyumluluk gereksinimlerini kontrol et\n"
            "5. Sektör-spesifik KPI'ları öner ve hedef değerler belirle\n"
            "\nHer öneride sektör referansı ver — 'tekstil sektöründe bu oran genelde X-Y arasıdır'."
        ),
        "focus_areas": ["sektör_bilgisi", "benchmark", "trend", "regülasyon", "kpi"],
        "risk_weight": 0.5,
        "opportunity_weight": 0.5,
    },
    PerspectiveType.ETHICIST: {
        "label": "Etik Değerlendirici",
        "description": "Etik, sürdürülebilirlik, sosyal sorumluluk perspektifi",
        "system_prompt": (
            "Sen bir İş Etiği ve Sürdürülebilirlik Uzmanı ajanısın. Görevin:\n"
            "1. ETİK boyutu analiz et — çalışan hakları, adil ticaret, şeffaflık\n"
            "2. SÜRDÜRÜLEBİLİRLİK etkisini değerlendir — çevresel ayak izi, karbon\n"
            "3. Sosyal SORUMLULUK perspektifini ekle — toplum etkisi, istihdam\n"
            "4. Uzun vadeli İTİBAR risklerini belirle\n"
            "5. ESG (Çevresel, Sosyal, Yönetişim) uyumluluğunu kontrol et\n"
            "\nPratik öneriler sun — etik olan aynı zamanda kârlı mı?"
        ),
        "focus_areas": ["etik", "sürdürülebilirlik", "esg", "itibar", "sosyal_sorumluluk"],
        "risk_weight": 0.4,
        "opportunity_weight": 0.4,
    },
    PerspectiveType.PRAGMATIST: {
        "label": "Pragmatist Uygulayıcı",
        "description": "Uygulama fizibilitesi, kaynak/zaman/bütçe gerçekçiliği",
        "system_prompt": (
            "Sen bir Pragmatist Uygulama Uzmanı ajanısın. Görevin:\n"
            "1. Uygulama FİZİBİLİTESİNİ değerlendir — gerçekten yapılabilir mi?\n"
            "2. KAYNAK gereksinimlerini belirle — insan, para, zaman, teknoloji\n"
            "3. Uygulama ADIMLARI öner — önceliklendirme, milestone, timeline\n"
            "4. DARBOĞAZLARI tespit et — nerede takılabiliriz?\n"
            "5. Hızlı prototip / MVP yaklaşımı öner — küçük başla, hızlı öğren\n"
            "\nHer öneride 'NASIL yapılır' sorusunu cevapla — strateji değil taktik."
        ),
        "focus_areas": ["fizibilite", "kaynak", "zaman", "darboğaz", "uygulama_planı"],
        "risk_weight": 0.4,
        "opportunity_weight": 0.5,
    },
}


# ═══════════════════════════════════════════════════════════════════
# PERSPEKTİF SEÇİCİ — Soruya göre hangi ajanlar aktif olacak
# ═══════════════════════════════════════════════════════════════════

def select_perspectives(
    question: str,
    department: str,
    mode: str,
    intent: str,
    explicit_perspectives: Optional[List[str]] = None,
) -> List[PerspectiveType]:
    """Soruya en uygun perspektif ajanlarını seç.

    Args:
        question: Kullanıcı sorusu
        department: Departman
        mode: Analiz modu
        intent: Router intent
        explicit_perspectives: Admin tarafından belirtilen perspektifler

    Returns:
        Seçilen perspektif listesi (3-6 arası)
    """
    # Açıkça belirtilmişse doğrudan kullan
    if explicit_perspectives:
        selected = []
        for p in explicit_perspectives:
            try:
                selected.append(PerspectiveType(p))
            except ValueError:
                continue
        if len(selected) >= MIN_PERSPECTIVES:
            return selected[:MAX_PERSPECTIVES]

    q_lower = question.lower()
    scores: Dict[PerspectiveType, float] = {p: 0.0 for p in PerspectiveType}

    # ─── Anahtar kelime eşleştirmesi ───
    risk_keywords = ["risk", "tehlike", "tehdit", "zarar", "kayıp", "kriz", "sorun"]
    opportunity_keywords = ["fırsat", "büyüme", "kazanç", "potansiyel", "yatırım", "genişleme"]
    ethics_keywords = ["etik", "sürdürülebilir", "çevre", "sorumluluk", "esg", "karbon", "adil"]
    execution_keywords = ["uygula", "plan", "bütçe", "kaynak", "zaman", "süreç", "nasıl"]
    comparison_keywords = ["karşılaştır", "alternatif", "seçenek", "vs", "avantaj", "dezavantaj"]
    sector_keywords = ["sektör", "pazar", "rekabet", "benchmark", "trend", "endüstri"]

    for kw in risk_keywords:
        if kw in q_lower:
            scores[PerspectiveType.RISK_ANALYST] += 2.0
            scores[PerspectiveType.DEVILS_ADVOCATE] += 1.0

    for kw in opportunity_keywords:
        if kw in q_lower:
            scores[PerspectiveType.OPTIMIST] += 2.0
            scores[PerspectiveType.PRAGMATIST] += 1.0

    for kw in ethics_keywords:
        if kw in q_lower:
            scores[PerspectiveType.ETHICIST] += 3.0

    for kw in execution_keywords:
        if kw in q_lower:
            scores[PerspectiveType.PRAGMATIST] += 2.0

    for kw in comparison_keywords:
        if kw in q_lower:
            scores[PerspectiveType.DEVILS_ADVOCATE] += 2.0
            scores[PerspectiveType.OPTIMIST] += 1.0

    for kw in sector_keywords:
        if kw in q_lower:
            scores[PerspectiveType.DOMAIN_EXPERT] += 2.0

    # ─── Mod bazlı boost ───
    if mode in ("Üst Düzey Analiz", "CEO Raporu"):
        scores[PerspectiveType.DEVILS_ADVOCATE] += 2.0
        scores[PerspectiveType.RISK_ANALYST] += 1.5
        scores[PerspectiveType.OPTIMIST] += 1.0
        scores[PerspectiveType.PRAGMATIST] += 1.0
    elif mode == "Risk Analizi":
        scores[PerspectiveType.RISK_ANALYST] += 3.0
        scores[PerspectiveType.DEVILS_ADVOCATE] += 2.0
    elif mode in ("Strateji", "Tahmin"):
        scores[PerspectiveType.OPTIMIST] += 2.0
        scores[PerspectiveType.PRAGMATIST] += 1.5
        scores[PerspectiveType.DOMAIN_EXPERT] += 1.0

    # ─── Departman bazlı boost ───
    if department in ("üretim", "kalite", "tedarik"):
        scores[PerspectiveType.DOMAIN_EXPERT] += 2.0
    if department in ("finans", "muhasebe"):
        scores[PerspectiveType.RISK_ANALYST] += 1.5
    if department in ("insan_kaynakları", "ik"):
        scores[PerspectiveType.ETHICIST] += 1.5

    # ─── Her zaman devşil avukatı dahil et (karşıt görüş bel kemiği) ───
    scores[PerspectiveType.DEVILS_ADVOCATE] += 1.0

    # Skor sırasına göre en iyi perspektifleri seç
    sorted_perspectives = sorted(scores.items(), key=lambda x: x[1], reverse=True)

    # Minimum skor eşiği — en az 0.5 puan almış olmalı
    selected = [p for p, s in sorted_perspectives if s >= 0.5]

    # Minimum 3, maksimum 6
    if len(selected) < MIN_PERSPECTIVES:
        # Eksik kalanları skor sırasıyla doldur
        for p, _ in sorted_perspectives:
            if p not in selected:
                selected.append(p)
            if len(selected) >= MIN_PERSPECTIVES:
                break

    return selected[:MAX_PERSPECTIVES]


# ═══════════════════════════════════════════════════════════════════
# TETİKLEME KARARI — Bu soru debate gerektirir mi?
# ═══════════════════════════════════════════════════════════════════

def should_trigger_debate(
    question: str,
    mode: str,
    intent: str,
    confidence: float = 100.0,
    force: bool = False,
) -> Tuple[bool, str]:
    """Bu soru multi-agent debate gerektirir mi?

    Returns:
        (trigger: bool, reason: str)
    """
    if force:
        return True, "manual_trigger"

    # Kısa sorular debate'e girmez
    if len(question.strip()) < DEBATE_TRIGGER_MIN_LENGTH:
        return False, "too_short"

    # Sohbet/selamlama debate'e girmez
    if intent in ("sohbet", "selamlama"):
        return False, "casual_intent"

    # Mod bazlı otomatik tetikleme
    if mode in DEBATE_TRIGGER_MODES:
        return True, f"mode_trigger:{mode}"

    # Anahtar kelime bazlı tetikleme
    q_lower = question.lower()
    keyword_hits = sum(1 for kw in DEBATE_TRIGGER_KEYWORDS if kw in q_lower)
    if keyword_hits >= 2:
        return True, f"keyword_trigger:{keyword_hits}_hits"

    # Düşük confidence ise debate ile güçlendir
    if confidence < 55:
        return True, f"low_confidence:{confidence}"

    return False, "no_trigger"


# ═══════════════════════════════════════════════════════════════════
# PERSPEKTİF ANALİZ OLUŞTURUCU
# ═══════════════════════════════════════════════════════════════════

def generate_perspective_analysis(
    perspective: PerspectiveType,
    question: str,
    department: str,
    mode: str,
    existing_answer: str = "",
    rag_context: str = "",
    other_perspectives: Optional[List[PerspectiveAnalysis]] = None,
    round_number: int = 1,
) -> PerspectiveAnalysis:
    """Bir perspektif ajanı için analiz prompt'u oluştur ve analiz yap.

    Bu fonksiyon LLM çağrısı yapmaz — prompt ve yapıyı hazırlar.
    Gerçek LLM çağrısı engine.py'den yapılır.

    Args:
        perspective: Perspektif tipi
        question: Kullanıcı sorusu
        department: Departman
        mode: Analiz modu
        existing_answer: Varsa mevcut cevap (round 2+ için)
        rag_context: RAG bağlamı
        other_perspectives: Diğer perspektiflerin analizleri (round 2+ için)
        round_number: Tartışma turu numarası

    Returns:
        Boş PerspectiveAnalysis (LLM sonrası doldurulacak)
    """
    config = PERSPECTIVE_CONFIGS.get(perspective, {})
    t0 = time.time()

    analysis = PerspectiveAnalysis(
        perspective=perspective,
        label=config.get("label", perspective.value),
        summary="",
        arguments=[],
        recommendation="",
        risk_level=0.0,
        opportunity_level=0.0,
        confidence=0.5,
        generation_time_ms=0.0,
    )

    return analysis


def build_perspective_prompt(
    perspective: PerspectiveType,
    question: str,
    department: str,
    mode: str,
    existing_answer: str = "",
    rag_context: str = "",
    other_perspectives_text: str = "",
    round_number: int = 1,
) -> Tuple[str, str]:
    """Perspektif ajanı için system + user prompt oluştur.

    Returns:
        (system_prompt, user_prompt)
    """
    config = PERSPECTIVE_CONFIGS[perspective]

    system_prompt = config["system_prompt"]
    system_prompt += f"\n\nDepartman: {department}\nAnaliz Modu: {mode}"
    system_prompt += (
        "\n\nYanıtını şu yapıda ver:"
        "\n1. ÖZET (2-3 cümle)"
        "\n2. ANA ARGÜMANLAR (en az 2, en fazla 4)"
        "\n   - Her argüman için: Argüman + Kanıt/Gerekçe + Güç (güçlü/orta/zayıf)"
        "\n3. RİSK SEVİYESİ (0-10)"
        "\n4. FIRSAT SEVİYESİ (0-10)"
        "\n5. ÖNERİ (1 paragraf)"
    )

    user_prompt = f"Soru: {question}"

    if existing_answer:
        user_prompt += f"\n\nMevcut Analiz:\n{existing_answer[:1500]}"

    if rag_context:
        user_prompt += f"\n\nBilgi Tabanı:\n{rag_context[:1000]}"

    if other_perspectives_text and round_number > 1:
        user_prompt += (
            f"\n\n--- DİĞER PERSPEKTİFLER (Tur {round_number - 1}) ---\n"
            f"{other_perspectives_text[:2000]}\n"
            "Yukarıdaki perspektifleri dikkate alarak kendi görüşünü güncelle. "
            "Desteklediğin noktaları belirt, karşı olduklarını gerekçesiyle çürüt."
        )

    return system_prompt, user_prompt


# ═══════════════════════════════════════════════════════════════════
# ARGÜMAN PARSER — LLM çıktısından yapısal argüman çıkarma
# ═══════════════════════════════════════════════════════════════════

def parse_perspective_response(
    raw_text: str,
    perspective: PerspectiveType,
    round_number: int = 1,
) -> PerspectiveAnalysis:
    """LLM yanıtını yapısal PerspectiveAnalysis'e dönüştür.

    Heuristic parser — LLM'in yapısal çıktı vermesi garanti değil,
    bu yüzden regex + keyword tabanlı esnek parsing yapar.
    """
    import re

    config = PERSPECTIVE_CONFIGS[perspective]
    lines = raw_text.strip().split("\n")
    text_lower = raw_text.lower()

    # ── Özet çıkarma ──
    summary = ""
    for i, line in enumerate(lines):
        if any(kw in line.lower() for kw in ["özet", "summary", "genel değerlendirme"]):
            # Sonraki 2-3 satırı özet olarak al
            summary_lines = []
            for j in range(i + 1, min(i + 4, len(lines))):
                clean = lines[j].strip().lstrip("-•*")
                if clean and not any(kw in clean.lower() for kw in ["argüman", "risk", "öneri", "fırsat"]):
                    summary_lines.append(clean)
                else:
                    break
            summary = " ".join(summary_lines)
            break
    if not summary and lines:
        # İlk anlamlı satırı özet olarak kullan
        for line in lines[:5]:
            clean = line.strip().lstrip("-•*#123456789. ")
            if len(clean) > 20:
                summary = clean[:300]
                break

    # ── Argüman çıkarma ──
    arguments = []
    arg_pattern = re.compile(
        r"(?:argüman|argument|nokta|madde|claim|iddia|görüş)\s*[:\-]?\s*(.+)",
        re.IGNORECASE
    )

    current_claim = ""
    for line in lines:
        clean = line.strip()
        # Numaralı madde veya bullet point
        if re.match(r"^[\d]+[.)]\s+", clean) or clean.startswith(("- ", "• ", "* ")):
            claim_text = re.sub(r"^[\d]+[.)]\s+|^[-•*]\s+", "", clean).strip()
            # Çok kısa veya başlık ise atla
            if len(claim_text) > 15 and not any(
                kw in claim_text.lower() for kw in
                ["özet", "risk seviyesi", "fırsat seviyesi", "öneri"]
            ):
                if current_claim:
                    arguments.append(Argument(
                        perspective=perspective,
                        claim=current_claim,
                        strength=ArgumentStrength.MODERATE,
                        confidence=0.6,
                        round_number=round_number,
                    ))
                current_claim = claim_text
            else:
                current_claim = ""
        elif current_claim and clean:
            # Devam satırı — evidence olarak ekle
            if arguments and arguments[-1].claim == current_claim:
                arguments[-1].evidence.append(clean[:200])

    # Son argümanı ekle
    if current_claim:
        arguments.append(Argument(
            perspective=perspective,
            claim=current_claim,
            strength=ArgumentStrength.MODERATE,
            confidence=0.6,
            round_number=round_number,
        ))

    # ── Argüman gücü belirleme ──
    strong_markers = ["kesinlikle", "mutlaka", "kritik", "hayati", "zorunlu", "kanıtlanmış"]
    weak_markers = ["belki", "olabilir", "düşünülebilir", "ihtimal", "spekülasyon"]
    for arg in arguments:
        claim_lower = arg.claim.lower()
        if any(m in claim_lower for m in strong_markers):
            arg.strength = ArgumentStrength.STRONG
            arg.confidence = 0.8
        elif any(m in claim_lower for m in weak_markers):
            arg.strength = ArgumentStrength.WEAK
            arg.confidence = 0.4

    # ── Risk/Fırsat seviyesi ──
    risk_level = 0.5
    opportunity_level = 0.5
    risk_match = re.search(r"risk\s*(?:seviye|skor|puan)\s*[:\-]?\s*(\d+)", text_lower)
    if risk_match:
        risk_level = min(int(risk_match.group(1)), 10) / 10.0
    opp_match = re.search(r"fırsat\s*(?:seviye|skor|puan)\s*[:\-]?\s*(\d+)", text_lower)
    if opp_match:
        opportunity_level = min(int(opp_match.group(1)), 10) / 10.0

    # Perspektif tipine göre varsayılan risk/fırsat ağırlığı
    if not risk_match:
        risk_level = config.get("risk_weight", 0.5)
    if not opp_match:
        opportunity_level = config.get("opportunity_weight", 0.5)

    # ── Öneri çıkarma ──
    recommendation = ""
    for i, line in enumerate(lines):
        if any(kw in line.lower() for kw in ["öneri", "tavsiye", "recommendation", "sonuç"]):
            rec_lines = []
            for j in range(i + 1, min(i + 5, len(lines))):
                clean = lines[j].strip().lstrip("-•*")
                if clean:
                    rec_lines.append(clean)
                else:
                    break
            recommendation = " ".join(rec_lines)
            break
    if not recommendation and lines:
        recommendation = lines[-1].strip()[:300]

    # ── Confidence hesapla ──
    arg_count = len(arguments)
    evidence_count = sum(len(a.evidence) for a in arguments)
    strong_count = sum(1 for a in arguments if a.strength == ArgumentStrength.STRONG)

    confidence = 0.5
    if arg_count > 0:
        confidence = min(0.9, 0.4 + (arg_count * 0.1) + (evidence_count * 0.05) + (strong_count * 0.1))

    return PerspectiveAnalysis(
        perspective=perspective,
        label=config.get("label", perspective.value),
        summary=summary,
        arguments=arguments[:6],  # Max 6 argüman
        recommendation=recommendation,
        risk_level=risk_level,
        opportunity_level=opportunity_level,
        confidence=round(confidence, 2),
    )


# ═══════════════════════════════════════════════════════════════════
# KONSENSÜS TESPİTİ
# ═══════════════════════════════════════════════════════════════════

class ConsensusDetector:
    """Perspektifler arası uzlaşma/ayrışma analizi."""

    @staticmethod
    def analyze(analyses: List[PerspectiveAnalysis]) -> ConsensusResult:
        """Tüm perspektif analizlerini karşılaştırarak uzlaşma tespiti yap.

        Mantık:
        1. Risk seviyesi yakınlığı → agreement
        2. Öneri yönü benzerliği → agreement
        3. Argüman çatışması → disagreement
        4. Ortalama uyum skoru → consensus_score
        """
        if not analyses:
            return ConsensusResult(
                outcome=DebateOutcome.DEADLOCK,
                consensus_score=0.0,
            )

        n = len(analyses)
        if n == 1:
            return ConsensusResult(
                outcome=DebateOutcome.CONSENSUS,
                consensus_score=1.0,
                agreed_points=[analyses[0].summary],
            )

        # ── Risk seviyesi uyumu ──
        risk_levels = [a.risk_level for a in analyses]
        avg_risk = sum(risk_levels) / n
        risk_variance = sum((r - avg_risk) ** 2 for r in risk_levels) / n
        risk_agreement = max(0.0, 1.0 - (risk_variance * 4))  # 0-1

        # ── Fırsat seviyesi uyumu ──
        opp_levels = [a.opportunity_level for a in analyses]
        avg_opp = sum(opp_levels) / n
        opp_variance = sum((o - avg_opp) ** 2 for o in opp_levels) / n
        opp_agreement = max(0.0, 1.0 - (opp_variance * 4))

        # ── Confidence uyumu ──
        confidences = [a.confidence for a in analyses]
        avg_conf = sum(confidences) / n
        conf_variance = sum((c - avg_conf) ** 2 for c in confidences) / n
        conf_agreement = max(0.0, 1.0 - (conf_variance * 4))

        # ── Argüman yönü analizi ──
        positive_count = 0
        negative_count = 0
        neutral_count = 0

        positive_markers = [
            "fırsat", "avantaj", "büyüme", "kazanç", "olumlu", "pozitif",
            "destekle", "yap", "uygula", "başla", "ilerle",
        ]
        negative_markers = [
            "risk", "tehlike", "zarar", "kayıp", "olumsuz", "negatif",
            "dikkat", "dur", "bekle", "kaçın", "riskli",
        ]

        for analysis in analyses:
            rec_lower = analysis.recommendation.lower()
            pos_hits = sum(1 for m in positive_markers if m in rec_lower)
            neg_hits = sum(1 for m in negative_markers if m in rec_lower)

            if pos_hits > neg_hits:
                positive_count += 1
            elif neg_hits > pos_hits:
                negative_count += 1
            else:
                neutral_count += 1

        # Yön uyumu
        max_direction = max(positive_count, negative_count, neutral_count)
        direction_agreement = max_direction / n

        # ── Toplam uzlaşma skoru ──
        consensus_score = (
            risk_agreement * 0.25 +
            opp_agreement * 0.20 +
            conf_agreement * 0.15 +
            direction_agreement * 0.40
        )

        # ── Uzlaşılan ve ayrışan noktalar ──
        agreed_points = []
        disputed_points = []
        minority_views = []
        risk_warnings = []

        # Tüm önerileri topla ve benzerlik kontrol et
        all_recommendations = [(a.perspective.value, a.recommendation) for a in analyses]

        # Yüksek riskleri uyarı olarak ekle
        for a in analyses:
            if a.risk_level >= 0.7:
                risk_warnings.append(
                    f"[{a.label}] Yüksek risk uyarısı (seviye: {a.risk_level:.1f}): "
                    f"{a.summary[:100]}"
                )

        # Azınlık görüşlerini belirle
        if positive_count > 0 and negative_count > 0:
            minority_direction = "pozitif" if positive_count < negative_count else "negatif"
            for a in analyses:
                rec_lower = a.recommendation.lower()
                pos_hits = sum(1 for m in positive_markers if m in rec_lower)
                neg_hits = sum(1 for m in negative_markers if m in rec_lower)

                is_positive = pos_hits > neg_hits
                if (minority_direction == "pozitif" and is_positive) or \
                   (minority_direction == "negatif" and not is_positive):
                    minority_views.append(f"[{a.label}] {a.recommendation[:150]}")

        # Uzlaşılan noktalar — birden fazla perspektifin paylaştığı öneriler
        for a in analyses:
            if a.confidence >= 0.6:
                agreed_points.append(f"[{a.label}] {a.summary[:150]}")

        # ── Sonuç belirleme ──
        if consensus_score >= STRONG_CONSENSUS_THRESHOLD:
            outcome = DebateOutcome.STRONG_CONSENSUS
            confidence_adj = CONFIDENCE_BOOST_ON_CONSENSUS
        elif consensus_score >= CONSENSUS_THRESHOLD:
            outcome = DebateOutcome.CONSENSUS
            confidence_adj = CONFIDENCE_BOOST_ON_CONSENSUS * 0.6
        elif consensus_score >= 0.50:
            outcome = DebateOutcome.MAJORITY
            confidence_adj = 0.0
        elif consensus_score >= 0.30:
            outcome = DebateOutcome.SPLIT
            confidence_adj = -CONFIDENCE_PENALTY_ON_SPLIT
        else:
            outcome = DebateOutcome.DEADLOCK
            confidence_adj = -CONFIDENCE_PENALTY_ON_SPLIT * 1.5

        return ConsensusResult(
            outcome=outcome,
            consensus_score=round(consensus_score, 3),
            agreed_points=agreed_points,
            disputed_points=disputed_points,
            minority_views=minority_views,
            risk_warnings=risk_warnings,
            confidence_adjustment=confidence_adj,
        )


# ═══════════════════════════════════════════════════════════════════
# SENTEZ MOTORU — Tüm perspektifleri birleştiren final çıktı
# ═══════════════════════════════════════════════════════════════════

def build_synthesis_prompt(
    question: str,
    analyses: List[PerspectiveAnalysis],
    consensus: ConsensusResult,
    department: str,
    mode: str,
) -> Tuple[str, str]:
    """Sentez ajanı için prompt oluştur.

    Returns:
        (system_prompt, user_prompt)
    """
    system_prompt = (
        "Sen bir Stratejik Sentez Uzmanısın. Birden fazla uzman perspektifini "
        "birleştirerek dengeli, kapsamlı ve uygulanabilir bir final analiz üretirsin.\n\n"
        "Görevin:\n"
        "1. Tüm perspektiflerin güçlü yönlerini BİRLEŞTİR\n"
        "2. Çelişen görüşleri DENGE ile sun — 'A grubu şunu söylüyor, B grubu bunu'\n"
        "3. Risk uyarılarını VURGULA ama fırsatları da göster\n"
        "4. NET bir nihai ÖNERİ ver — evet/hayır/koşullu\n"
        "5. Aksiyon maddelerini LİSTELE — kısa/orta/uzun vade\n\n"
        f"Departman: {department}\nMod: {mode}\n"
        f"Uzlaşma Durumu: {consensus.outcome.value} (skor: {consensus.consensus_score:.2f})"
    )

    user_prompt = f"## Analiz Edilen Soru\n{question}\n\n"
    user_prompt += "## Uzman Perspektifleri\n\n"

    for analysis in analyses:
        user_prompt += f"### {analysis.label}\n"
        user_prompt += f"Özet: {analysis.summary}\n"
        user_prompt += f"Risk: {analysis.risk_level:.1f}/1.0 | Fırsat: {analysis.opportunity_level:.1f}/1.0\n"
        if analysis.arguments:
            user_prompt += "Argümanlar:\n"
            for arg in analysis.arguments[:3]:
                user_prompt += f"  - [{arg.strength.value}] {arg.claim}\n"
        user_prompt += f"Öneri: {analysis.recommendation}\n\n"

    if consensus.risk_warnings:
        user_prompt += "\n## Risk Uyarıları\n"
        for w in consensus.risk_warnings:
            user_prompt += f"⚠ {w}\n"

    if consensus.minority_views:
        user_prompt += "\n## Azınlık Görüşleri (dikkate al)\n"
        for mv in consensus.minority_views:
            user_prompt += f"📌 {mv}\n"

    user_prompt += (
        "\n\nYukarıdaki tüm perspektifleri sentezleyerek kapsamlı bir final analiz yaz. "
        "Uzlaşılan noktaları, tartışmalı alanları ve net önerileri ayrı ayrı belirt."
    )

    return system_prompt, user_prompt


# ═══════════════════════════════════════════════════════════════════
# DEBATE TRACKER — Geçmiş tartışma ve performans takibi
# ═══════════════════════════════════════════════════════════════════

class DebateTracker:
    """Tartışma geçmişi ve performans analizi."""

    def __init__(self):
        self._debates: List[DebateResult] = []
        self._perspective_stats: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {"used": 0, "avg_confidence": 0.0, "total_arguments": 0}
        )
        self._consensus_stats: Dict[str, int] = defaultdict(int)
        self._department_stats: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {"debates": 0, "avg_consensus_score": 0.0}
        )

    def record(self, result: DebateResult):
        """Tartışma sonucunu kaydet."""
        self._debates.append(result)
        if len(self._debates) > MAX_DEBATE_HISTORY:
            self._debates = self._debates[-MAX_DEBATE_HISTORY:]

        # Perspektif istatistikleri
        for analysis in result.analyses:
            key = analysis.perspective.value
            stats = self._perspective_stats[key]
            stats["used"] += 1
            n = stats["used"]
            stats["avg_confidence"] = round(
                ((stats["avg_confidence"] * (n - 1)) + analysis.confidence) / n, 3
            )
            stats["total_arguments"] += len(analysis.arguments)

        # Konsensüs istatistikleri
        if result.consensus:
            self._consensus_stats[result.consensus.outcome.value] += 1

        # Departman istatistikleri
        dept_key = result.department
        ds = self._department_stats[dept_key]
        ds["debates"] += 1
        n = ds["debates"]
        cs = result.consensus.consensus_score if result.consensus else 0.5
        ds["avg_consensus_score"] = round(
            ((ds["avg_consensus_score"] * (n - 1)) + cs) / n, 3
        )

        logger.info("debate_recorded",
                     debate_id=result.debate_id,
                     perspectives=len(result.perspectives_used),
                     outcome=result.consensus.outcome.value if result.consensus else "none",
                     confidence_delta=round(result.confidence_after - result.confidence_before, 1))

    def get_recent(self, n: int = 20) -> List[dict]:
        """Son N tartışma."""
        return [d.to_dict() for d in self._debates[-n:]]

    def get_statistics(self) -> dict:
        """Genel tartışma istatistikleri."""
        total = len(self._debates)
        if total == 0:
            return {"total_debates": 0}

        avg_confidence_delta = sum(
            d.confidence_after - d.confidence_before for d in self._debates
        ) / total

        avg_perspectives = sum(len(d.perspectives_used) for d in self._debates) / total

        avg_time = sum(d.total_time_ms for d in self._debates) / total

        return {
            "total_debates": total,
            "avg_confidence_delta": round(avg_confidence_delta, 2),
            "avg_perspectives_used": round(avg_perspectives, 1),
            "avg_debate_time_ms": round(avg_time, 1),
            "consensus_distribution": dict(self._consensus_stats),
            "perspective_stats": dict(self._perspective_stats),
            "department_stats": dict(self._department_stats),
        }

    def get_dashboard(self) -> dict:
        """Tam dashboard verisi."""
        return {
            "available": True,
            "statistics": self.get_statistics(),
            "recent_debates": self.get_recent(10),
            "perspective_configs": {
                p.value: {
                    "label": c["label"],
                    "description": c["description"],
                    "focus_areas": c["focus_areas"],
                }
                for p, c in PERSPECTIVE_CONFIGS.items()
            },
            "settings": {
                "max_rounds": MAX_DEBATE_ROUNDS,
                "min_perspectives": MIN_PERSPECTIVES,
                "max_perspectives": MAX_PERSPECTIVES,
                "consensus_threshold": CONSENSUS_THRESHOLD,
                "strong_consensus_threshold": STRONG_CONSENSUS_THRESHOLD,
                "confidence_boost": CONFIDENCE_BOOST_ON_CONSENSUS,
                "confidence_penalty": CONFIDENCE_PENALTY_ON_SPLIT,
            },
        }

    def reset(self):
        """Tüm tartışma verisini sıfırla."""
        self._debates.clear()
        self._perspective_stats.clear()
        self._consensus_stats.clear()
        self._department_stats.clear()
        logger.info("debate_tracker_reset")


# ═══════════════════════════════════════════════════════════════════
# ANA ORKESTRATÖR — MultiAgentDebateEngine
# ═══════════════════════════════════════════════════════════════════

class MultiAgentDebateEngine:
    """Multi-Agent Debate orkestratörü.

    Kullanım (engine.py'den):
        engine = debate_engine  # singleton
        trigger, reason = engine.should_debate(question, mode, intent, confidence)
        if trigger:
            debate_result = await engine.run_debate(question, department, mode, ...)
            final_answer = debate_result.synthesis
            adjusted_confidence = debate_result.confidence_after
    """

    def __init__(self):
        self.tracker = DebateTracker()
        self._enabled: bool = True
        self._started_at: str = _utcnow_str()

    def should_debate(
        self,
        question: str,
        mode: str,
        intent: str,
        confidence: float = 100.0,
        force: bool = False,
    ) -> Tuple[bool, str]:
        """Debate tetikleme kararı."""
        if not self._enabled and not force:
            return False, "debate_disabled"
        return should_trigger_debate(question, mode, intent, confidence, force)

    def select_perspectives(
        self,
        question: str,
        department: str,
        mode: str,
        intent: str,
        explicit: Optional[List[str]] = None,
    ) -> List[PerspectiveType]:
        """Perspektif seçimi."""
        return select_perspectives(question, department, mode, intent, explicit)

    def build_perspective_prompts(
        self,
        perspectives: List[PerspectiveType],
        question: str,
        department: str,
        mode: str,
        existing_answer: str = "",
        rag_context: str = "",
        round_number: int = 1,
        previous_analyses: Optional[List[PerspectiveAnalysis]] = None,
    ) -> List[Dict[str, Any]]:
        """Her perspektif için prompt hazırla.

        Returns:
            [{perspective, label, system_prompt, user_prompt}, ...]
        """
        other_text = ""
        if previous_analyses and round_number > 1:
            parts = []
            for a in previous_analyses:
                parts.append(f"### {a.label}\n{a.summary}\nÖneri: {a.recommendation}")
            other_text = "\n\n".join(parts)

        prompts = []
        for p in perspectives:
            sys_prompt, usr_prompt = build_perspective_prompt(
                perspective=p,
                question=question,
                department=department,
                mode=mode,
                existing_answer=existing_answer,
                rag_context=rag_context,
                other_perspectives_text=other_text,
                round_number=round_number,
            )
            prompts.append({
                "perspective": p,
                "label": PERSPECTIVE_CONFIGS[p]["label"],
                "system_prompt": sys_prompt,
                "user_prompt": usr_prompt,
            })

        return prompts

    def process_responses(
        self,
        perspectives: List[PerspectiveType],
        raw_responses: List[str],
        round_number: int = 1,
    ) -> List[PerspectiveAnalysis]:
        """LLM yanıtlarını parse edip yapısal analizlere dönüştür."""
        analyses = []
        for perspective, raw_text in zip(perspectives, raw_responses):
            try:
                analysis = parse_perspective_response(raw_text, perspective, round_number)
                analyses.append(analysis)
            except Exception as e:
                logger.warning("perspective_parse_error",
                               perspective=perspective.value, error=str(e))
                # Fallback — ham metni özet olarak kullan
                analyses.append(PerspectiveAnalysis(
                    perspective=perspective,
                    label=PERSPECTIVE_CONFIGS[perspective]["label"],
                    summary=raw_text[:300],
                    confidence=0.4,
                ))
        return analyses

    def detect_consensus(self, analyses: List[PerspectiveAnalysis]) -> ConsensusResult:
        """Uzlaşma tespiti."""
        return ConsensusDetector.analyze(analyses)

    def build_synthesis(
        self,
        question: str,
        analyses: List[PerspectiveAnalysis],
        consensus: ConsensusResult,
        department: str,
        mode: str,
    ) -> Tuple[str, str]:
        """Sentez prompt'u oluştur."""
        return build_synthesis_prompt(question, analyses, consensus, department, mode)

    def finalize_debate(
        self,
        question: str,
        department: str,
        mode: str,
        perspectives: List[PerspectiveType],
        analyses: List[PerspectiveAnalysis],
        rounds: List[DebateRound],
        consensus: ConsensusResult,
        synthesis_text: str,
        confidence_before: float,
        total_time_ms: float,
        triggered_by: str = "auto",
    ) -> DebateResult:
        """Tartışmayı sonlandır, kaydet ve DebateResult döndür."""
        debate_id = f"DBT-{uuid.uuid4().hex[:8]}"

        confidence_after = min(100, max(0,
            confidence_before + consensus.confidence_adjustment
        ))

        # Sentezden final öneri çıkar
        final_recommendation = synthesis_text[:500] if synthesis_text else ""

        result = DebateResult(
            debate_id=debate_id,
            question=question,
            department=department,
            mode=mode,
            timestamp=_utcnow_str(),
            perspectives_used=perspectives,
            analyses=analyses,
            rounds=rounds,
            consensus=consensus,
            synthesis=synthesis_text,
            final_recommendation=final_recommendation,
            confidence_before=confidence_before,
            confidence_after=confidence_after,
            total_time_ms=total_time_ms,
            triggered_by=triggered_by,
        )

        self.tracker.record(result)
        return result

    def get_dashboard(self) -> dict:
        """Dashboard verisi."""
        return self.tracker.get_dashboard()

    def set_enabled(self, enabled: bool) -> dict:
        """Debate sistemini aç/kapat."""
        old = self._enabled
        self._enabled = enabled
        logger.info("debate_engine_toggled", old=old, new=enabled)
        return {"enabled": enabled, "previous": old}

    def reset(self):
        """Tüm tartışma verisini sıfırla."""
        self.tracker.reset()
        self._started_at = _utcnow_str()
        logger.info("debate_engine_reset")


# ═══════════════════════════════════════════════════════════════════
# GLOBAL SINGLETON
# ═══════════════════════════════════════════════════════════════════

debate_engine: MultiAgentDebateEngine = MultiAgentDebateEngine()


# ═══════════════════════════════════════════════════════════════════
# KOLAYLIK FONKSİYONLARI — engine.py entegrasyonu
# ═══════════════════════════════════════════════════════════════════

def check_debate_trigger(
    question: str, mode: str, intent: str, confidence: float = 100.0, force: bool = False,
) -> Tuple[bool, str]:
    """Debate tetikleme kontrolü."""
    return debate_engine.should_debate(question, mode, intent, confidence, force)


def get_debate_dashboard() -> dict:
    """Dashboard verisi."""
    return debate_engine.get_dashboard()
