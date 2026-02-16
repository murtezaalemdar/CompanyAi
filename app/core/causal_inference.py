"""Causal Inference Engine v1.0 — Nedensellik Analiz Motoru

Korelasyon ≠ Nedensellik: Bu modül kurumsal verilerdeki neden-sonuç
ilişkilerini analiz eder. Mevcut risk_analyzer ve forecasting
modüllerinin ÜSTÜNE inşa edilir.

Bileşenler:
  1. RootCauseAnalyzer  → 5 Whys + Ishikawa kök neden analizi
  2. CausalChainBuilder → Neden-sonuç zinciri ve DAG (Yönlü Çevrimsiz Grafı)
  3. CounterfactualEngine → "X olmasaydı ne olurdu?" analizi
  4. InterventionAnalyzer → "X yaparsak ne olur?" etki tahmini
  5. EffectEstimator    → Nicel etki büyüklüğü tahmini
  6. CausalTracker      → Geçmiş analizler ve doğrulama takibi

Kullanım Alanları:
  - Üretim arızası → kök neden (makine? hammadde? operatör?)
  - Satış düşüşü → neden zinciri (fiyat? kalite? mevsim? rakip?)
  - Maliyet artışı → müdahale analizi (hangi aksiyonla düşer?)
  - Kalite sorunu → karşı-olgusal (farklı hammadde kullansaydık?)

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
from typing import Any, Dict, List, Optional, Set, Tuple

import structlog

logger = structlog.get_logger(__name__)


# ═══════════════════════════════════════════════════════════════════
# SABİTLER
# ═══════════════════════════════════════════════════════════════════

MAX_WHY_DEPTH = 7                    # 5 Whys → max 7 derinlik
MAX_CHAIN_LENGTH = 10                # Nedensellik zinciri max uzunluk
MAX_COUNTERFACTUALS = 5              # Sorgu başına max karşı-olgusal
MAX_INTERVENTIONS = 5                # Sorgu başına max müdahale önerisi
MAX_ANALYSIS_HISTORY = 300           # Saklanan analiz sayısı
CONFIDENCE_BOOST_ON_ROOT_CAUSE = 5   # Kök neden bulunduğunda confidence artışı
CONFIDENCE_BOOST_ON_INTERVENTION = 3 # Müdahale önerisi üretildiğinde
CAUSAL_TRIGGER_KEYWORDS = [
    "neden", "sebep", "kök", "kaynak", "niçin", "nasıl oldu",
    "arıza", "sorun", "hata", "düşüş", "artış", "değişim",
    "etki", "sonuç", "bağlantı", "ilişki", "yol açtı", "factors",
    "cause", "root", "why", "impact", "effect",
]
CAUSAL_TRIGGER_MIN_LENGTH = 25       # Kısa sorular analize girmez

# Ishikawa kategorileri (6M)
ISHIKAWA_CATEGORIES = [
    "Makine (Machine)",
    "Malzeme (Material)",
    "Metot (Method)",
    "İnsan (Man)",
    "Ölçüm (Measurement)",
    "Çevre (Mother Nature / Environment)",
]


# ═══════════════════════════════════════════════════════════════════
# ENUM & VERİ YAPILARI
# ═══════════════════════════════════════════════════════════════════

class CausalDirection(str, Enum):
    CAUSE = "cause"            # A → B (A, B'nin nedeni)
    EFFECT = "effect"          # B ← A (B, A'nın sonucu)
    BIDIRECTIONAL = "bidirectional"  # A ↔ B (karşılıklı etki)
    CORRELATION = "correlation"  # A ~ B (korelasyon, nedensellik değil)


class ConfidenceLevel(str, Enum):
    HIGH = "high"         # Güçlü kanıt
    MEDIUM = "medium"     # Orta kanıt
    LOW = "low"           # Zayıf kanıt / tahmin
    SPECULATIVE = "speculative"  # Spekülasyon


class InterventionType(str, Enum):
    PREVENTIVE = "preventive"     # Önleyici
    CORRECTIVE = "corrective"     # Düzeltici
    DETECTIVE = "detective"       # Tespit edici
    ADAPTIVE = "adaptive"         # Uyarlayıcı


class AnalysisType(str, Enum):
    ROOT_CAUSE = "root_cause"         # Kök neden analizi
    CAUSAL_CHAIN = "causal_chain"     # Nedensellik zinciri
    COUNTERFACTUAL = "counterfactual" # Karşı-olgusal analiz
    INTERVENTION = "intervention"     # Müdahale analizi
    FULL = "full"                     # Tam analiz (hepsi)


def _utcnow_str() -> str:
    return datetime.now(timezone.utc).isoformat()


# ─── Temel veri yapıları ───

@dataclass
class CausalFactor:
    """Bir nedensel faktör."""
    factor_id: str = ""
    name: str = ""
    description: str = ""
    category: str = ""            # Ishikawa kategorisi
    confidence: ConfidenceLevel = ConfidenceLevel.MEDIUM
    evidence: List[str] = field(default_factory=list)
    impact_score: float = 0.5     # 0-1, etkinin büyüklüğü
    controllability: float = 0.5  # 0-1, kontrol edilebilirlik
    is_root_cause: bool = False

    def __post_init__(self):
        if not self.factor_id:
            self.factor_id = f"CF-{uuid.uuid4().hex[:6]}"

    def to_dict(self) -> dict:
        return {
            "factor_id": self.factor_id,
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "confidence": self.confidence.value,
            "evidence": self.evidence,
            "impact_score": round(self.impact_score, 2),
            "controllability": round(self.controllability, 2),
            "is_root_cause": self.is_root_cause,
        }


@dataclass
class CausalLink:
    """İki faktör arasındaki nedensel bağlantı."""
    source_id: str = ""
    target_id: str = ""
    direction: CausalDirection = CausalDirection.CAUSE
    strength: float = 0.5     # 0-1, bağlantı gücü
    lag_description: str = ""  # "2 hafta sonra etkisi görülür"
    mechanism: str = ""        # "Hammadde kalitesi → ürün kalitesi"
    confidence: ConfidenceLevel = ConfidenceLevel.MEDIUM

    def to_dict(self) -> dict:
        return {
            "source": self.source_id,
            "target": self.target_id,
            "direction": self.direction.value,
            "strength": round(self.strength, 2),
            "lag": self.lag_description,
            "mechanism": self.mechanism,
            "confidence": self.confidence.value,
        }


@dataclass
class WhyStep:
    """5 Whys analizinde bir adım."""
    depth: int
    question: str       # "Neden X oldu?"
    answer: str         # "Çünkü Y"
    factor: Optional[CausalFactor] = None
    is_root: bool = False

    def to_dict(self) -> dict:
        return {
            "depth": self.depth,
            "question": self.question,
            "answer": self.answer,
            "factor": self.factor.to_dict() if self.factor else None,
            "is_root_cause": self.is_root,
        }


@dataclass
class IshikawaDiagram:
    """Ishikawa (Balık Kılçığı) diyagramı."""
    problem: str
    categories: Dict[str, List[CausalFactor]] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "problem": self.problem,
            "categories": {
                cat: [f.to_dict() for f in factors]
                for cat, factors in self.categories.items()
            },
            "total_factors": sum(len(f) for f in self.categories.values()),
        }


@dataclass
class CausalChain:
    """Nedensellik zinciri — A → B → C → ... → Sonuç."""
    chain_id: str = ""
    factors: List[CausalFactor] = field(default_factory=list)
    links: List[CausalLink] = field(default_factory=list)
    root_causes: List[str] = field(default_factory=list)  # factor_id'ler
    final_effects: List[str] = field(default_factory=list)  # factor_id'ler
    total_impact: float = 0.0   # Zincirin toplam etki büyüklüğü

    def __post_init__(self):
        if not self.chain_id:
            self.chain_id = f"CC-{uuid.uuid4().hex[:6]}"

    def to_dict(self) -> dict:
        return {
            "chain_id": self.chain_id,
            "factors": [f.to_dict() for f in self.factors],
            "links": [l.to_dict() for l in self.links],
            "root_causes": self.root_causes,
            "final_effects": self.final_effects,
            "chain_length": len(self.factors),
            "total_impact": round(self.total_impact, 2),
        }

    def get_path_description(self) -> str:
        """Zincirin metin açıklaması."""
        if not self.factors:
            return "Boş zincir"
        names = [f.name for f in self.factors]
        return " → ".join(names)


@dataclass
class Counterfactual:
    """Karşı-olgusal senaryo — 'X olmasaydı ne olurdu?'"""
    scenario_id: str = ""
    condition: str = ""           # "Hammadde kalitesi düşmeseydi"
    original_outcome: str = ""    # "Ürün fire oranı %8'e çıktı"
    alternative_outcome: str = "" # "Fire oranı %3'te kalırdı"
    probability: float = 0.5     # Bu senaryonun gerçekleşme olasılığı
    impact_difference: float = 0.0  # Orijinal vs alternatif fark
    confidence: ConfidenceLevel = ConfidenceLevel.MEDIUM
    assumptions: List[str] = field(default_factory=list)

    def __post_init__(self):
        if not self.scenario_id:
            self.scenario_id = f"CTF-{uuid.uuid4().hex[:6]}"

    def to_dict(self) -> dict:
        return {
            "scenario_id": self.scenario_id,
            "condition": self.condition,
            "original_outcome": self.original_outcome,
            "alternative_outcome": self.alternative_outcome,
            "probability": round(self.probability, 2),
            "impact_difference": round(self.impact_difference, 2),
            "confidence": self.confidence.value,
            "assumptions": self.assumptions,
        }


@dataclass
class Intervention:
    """Müdahale önerisi — 'X yaparsak ne olur?'"""
    intervention_id: str = ""
    action: str = ""              # "Hammadde tedarikçisini değiştir"
    target_factor: str = ""       # Hedeflenen faktör adı
    intervention_type: InterventionType = InterventionType.CORRECTIVE
    expected_effect: str = ""     # "Fire oranı %3'e düşer"
    effect_magnitude: float = 0.0 # 0-1, etkinin büyüklüğü
    cost_estimate: str = ""       # "Orta maliyet"
    time_to_effect: str = ""      # "2-4 hafta"
    side_effects: List[str] = field(default_factory=list)
    prerequisites: List[str] = field(default_factory=list)
    confidence: ConfidenceLevel = ConfidenceLevel.MEDIUM
    priority: int = 5             # 1-10

    def __post_init__(self):
        if not self.intervention_id:
            self.intervention_id = f"INT-{uuid.uuid4().hex[:6]}"

    def to_dict(self) -> dict:
        return {
            "intervention_id": self.intervention_id,
            "action": self.action,
            "target_factor": self.target_factor,
            "type": self.intervention_type.value,
            "expected_effect": self.expected_effect,
            "effect_magnitude": round(self.effect_magnitude, 2),
            "cost_estimate": self.cost_estimate,
            "time_to_effect": self.time_to_effect,
            "side_effects": self.side_effects,
            "prerequisites": self.prerequisites,
            "confidence": self.confidence.value,
            "priority": self.priority,
        }


@dataclass
class CausalAnalysisResult:
    """Tam nedensellik analizi sonucu."""
    analysis_id: str = ""
    question: str = ""
    department: str = ""
    mode: str = ""
    analysis_type: AnalysisType = AnalysisType.FULL
    timestamp: str = ""
    # Bileşen sonuçları
    why_analysis: List[WhyStep] = field(default_factory=list)
    ishikawa: Optional[IshikawaDiagram] = None
    causal_chain: Optional[CausalChain] = None
    counterfactuals: List[Counterfactual] = field(default_factory=list)
    interventions: List[Intervention] = field(default_factory=list)
    # Meta
    root_causes_found: int = 0
    confidence_adjustment: float = 0.0
    total_time_ms: float = 0.0
    triggered_by: str = "auto"

    def __post_init__(self):
        if not self.analysis_id:
            self.analysis_id = f"CA-{uuid.uuid4().hex[:8]}"
        if not self.timestamp:
            self.timestamp = _utcnow_str()

    def to_dict(self) -> dict:
        return {
            "analysis_id": self.analysis_id,
            "question": self.question[:200],
            "department": self.department,
            "mode": self.mode,
            "analysis_type": self.analysis_type.value,
            "timestamp": self.timestamp,
            "why_analysis": [w.to_dict() for w in self.why_analysis],
            "ishikawa": self.ishikawa.to_dict() if self.ishikawa else None,
            "causal_chain": self.causal_chain.to_dict() if self.causal_chain else None,
            "counterfactuals": [c.to_dict() for c in self.counterfactuals],
            "interventions": [i.to_dict() for i in self.interventions],
            "root_causes_found": self.root_causes_found,
            "confidence_adjustment": self.confidence_adjustment,
            "total_time_ms": round(self.total_time_ms, 1),
            "triggered_by": self.triggered_by,
        }


# ═══════════════════════════════════════════════════════════════════
# TETİKLEME KARARI
# ═══════════════════════════════════════════════════════════════════

def should_trigger_causal_analysis(
    question: str,
    mode: str,
    intent: str,
    force: bool = False,
) -> Tuple[bool, str]:
    """Bu soru nedensellik analizi gerektirir mi?

    Returns:
        (trigger: bool, reason: str)
    """
    if force:
        return True, "manual_trigger"

    if len(question.strip()) < CAUSAL_TRIGGER_MIN_LENGTH:
        return False, "too_short"

    if intent in ("sohbet", "selamlama"):
        return False, "casual_intent"

    q_lower = question.lower()
    keyword_hits = sum(1 for kw in CAUSAL_TRIGGER_KEYWORDS if kw in q_lower)

    if keyword_hits >= 2:
        return True, f"keyword_trigger:{keyword_hits}_hits"

    # Mod bazlı — Risk Analizi ve Üst Düzey modlar
    if mode in ("Risk Analizi", "Üst Düzey Analiz"):
        return True, f"mode_trigger:{mode}"

    # Soru kalıbı — "neden X?", "X'in nedeni ne?"
    import re
    causal_patterns = [
        r"neden\s+.{5,}",
        r"niçin\s+.{5,}",
        r"sebebi?\s+ne",
        r"nedeni?\s+ne",
        r"kök\s*neden",
        r"root\s*cause",
        r"neden\s*sonuç",
        r"ne\s*yol\s*açtı",
        r"nasıl\s+oldu",
        r"etkisi?\s+ne",
    ]
    for pattern in causal_patterns:
        if re.search(pattern, q_lower):
            return True, f"pattern_trigger:{pattern}"

    return False, "no_trigger"


# ═══════════════════════════════════════════════════════════════════
# KÖK NEDEN ANALİZİ — 5 Whys + Ishikawa
# ═══════════════════════════════════════════════════════════════════

class RootCauseAnalyzer:
    """5 Whys ve Ishikawa kök neden analizi.

    Bu sınıf LLM çağrısı yapmaz — prompt ve yapıyı hazırlar.
    Gerçek LLM çağrısı engine.py veya admin endpoint'inden yapılır.
    """

    @staticmethod
    def build_five_whys_prompt(
        problem: str,
        department: str,
        context: str = "",
        max_depth: int = MAX_WHY_DEPTH,
    ) -> Tuple[str, str]:
        """5 Whys analizi için prompt oluştur.

        Returns:
            (system_prompt, user_prompt)
        """
        system_prompt = (
            "Sen bir Kök Neden Analiz Uzmanısın. 5 Whys (5 Neden) metodunu uyguluyorsun.\n\n"
            "Kurallar:\n"
            "1. Her seviyede 'NEDEN?' sorusunu sor ve cevapla\n"
            "2. Yüzeysel nedenlerden DAHA DERİN nedenlere in\n"
            "3. Her adımda somut ve spesifik ol — genel ifadelerden kaçın\n"
            "4. Kök nedene ulaştığında DURAK işareti koy\n"
            f"5. Maksimum {max_depth} seviye derinliğe in\n"
            "6. Her seviye için faktör kategorisini belirt (Makine/Malzeme/Metot/İnsan/Ölçüm/Çevre)\n"
            "7. Kök nedeni bulduğunda 'KÖK NEDEN' etiketiyle işaretle\n\n"
            f"Departman: {department}\n\n"
            "Yanıt formatı:\n"
            "Seviye 1: NEDEN [sorun]?\n"
            "→ Çünkü [neden] (Kategori: [X]) (Etki: [yüksek/orta/düşük])\n"
            "Seviye 2: NEDEN [neden]?\n"
            "→ Çünkü [daha derin neden] ...\n"
            "...\n"
            "KÖK NEDEN: [final kök neden] (Kategori: [X])"
        )

        user_prompt = f"Sorun: {problem}"
        if context:
            user_prompt += f"\n\nBağlam:\n{context[:1000]}"

        return system_prompt, user_prompt

    @staticmethod
    def parse_five_whys_response(raw_text: str) -> List[WhyStep]:
        """5 Whys LLM yanıtını yapısal WhyStep listesine dönüştür."""
        import re
        steps = []
        lines = raw_text.strip().split("\n")

        depth = 0
        current_question = ""
        current_answer = ""

        for line in lines:
            clean = line.strip()
            if not clean:
                continue

            # Seviye satırı tespit
            level_match = re.match(
                r"(?:seviye|level|adım|step)?\s*(\d+)\s*[:.]\s*(?:neden|why)?\s*(.*)",
                clean, re.IGNORECASE
            )
            if level_match:
                # Önceki adımı kaydet
                if current_question and current_answer:
                    steps.append(WhyStep(
                        depth=depth,
                        question=current_question,
                        answer=current_answer,
                    ))
                depth = int(level_match.group(1))
                current_question = level_match.group(2).strip().rstrip("?") + "?"
                current_answer = ""
                continue

            # Cevap satırı — "→ Çünkü" veya "Çünkü"
            answer_match = re.match(
                r"[→>]\s*(?:çünkü|because)?\s*(.*)",
                clean, re.IGNORECASE
            )
            if answer_match:
                current_answer = answer_match.group(1).strip()
                continue

            # Kök neden satırı
            root_match = re.match(
                r"(?:kök\s*neden|root\s*cause)\s*[:.]\s*(.*)",
                clean, re.IGNORECASE
            )
            if root_match:
                if current_question and current_answer:
                    steps.append(WhyStep(
                        depth=depth,
                        question=current_question,
                        answer=current_answer,
                    ))
                depth += 1
                steps.append(WhyStep(
                    depth=depth,
                    question="Kök neden nedir?",
                    answer=root_match.group(1).strip(),
                    is_root=True,
                ))
                current_question = ""
                current_answer = ""

        # Son adım
        if current_question and current_answer:
            steps.append(WhyStep(
                depth=depth,
                question=current_question,
                answer=current_answer,
            ))

        # Kök neden işareti yoksa son adımı root yap
        if steps and not any(s.is_root for s in steps):
            steps[-1].is_root = True

        # Faktör ata
        for step in steps:
            category = RootCauseAnalyzer._detect_category(step.answer)
            step.factor = CausalFactor(
                name=step.answer[:100],
                description=step.answer,
                category=category,
                confidence=ConfidenceLevel.MEDIUM if not step.is_root else ConfidenceLevel.HIGH,
                impact_score=0.5 + (0.1 * step.depth),  # Derin nedenler daha etkili
                is_root_cause=step.is_root,
            )

        return steps

    @staticmethod
    def _detect_category(text: str) -> str:
        """Metinden Ishikawa kategorisi tespit et."""
        text_lower = text.lower()
        category_keywords = {
            "Makine (Machine)": [
                "makine", "ekipman", "cihaz", "arıza", "bakım",
                "kalibrasyon", "yazılım", "donanım", "sistem",
            ],
            "Malzeme (Material)": [
                "malzeme", "hammadde", "kumaş", "iplik", "tedarik",
                "kalite", "parti", "lot", "stok", "boya",
            ],
            "Metot (Method)": [
                "prosedür", "süreç", "metot", "yöntem", "standart",
                "talimat", "iş akışı", "sabit olmayan", "plansız",
            ],
            "İnsan (Man)": [
                "operatör", "personel", "eğitim", "deneyim", "hata",
                "ihmal", "vardiya", "yorgunluk", "motivasyon", "insan",
            ],
            "Ölçüm (Measurement)": [
                "ölçüm", "kalibrasyon", "test", "kontrol", "muayene",
                "numune", "tolerans", "sapma", "doğruluk",
            ],
            "Çevre (Mother Nature / Environment)": [
                "sıcaklık", "nem", "ortam", "mevsim", "hava",
                "çevre", "toz", "titreşim", "aydınlatma",
            ],
        }
        best_category = "Diğer"
        best_score = 0
        for category, keywords in category_keywords.items():
            score = sum(1 for kw in keywords if kw in text_lower)
            if score > best_score:
                best_score = score
                best_category = category
        return best_category

    @staticmethod
    def build_ishikawa_prompt(
        problem: str,
        department: str,
        context: str = "",
    ) -> Tuple[str, str]:
        """Ishikawa diyagramı için prompt oluştur."""
        categories_text = "\n".join(f"  - {cat}" for cat in ISHIKAWA_CATEGORIES)

        system_prompt = (
            "Sen bir Ishikawa (Balık Kılçığı) Diyagramı uzmanısın.\n\n"
            "Her kategori için olası nedenleri listele:\n"
            f"{categories_text}\n\n"
            "Her neden için:\n"
            "1. Kısa ve spesifik bir ad ver\n"
            "2. Etki seviyesi belirt (yüksek/orta/düşük)\n"
            "3. Kontrol edilebilirlik belirt (yüksek/orta/düşük)\n"
            "4. Varsa kanıt/veri göster\n\n"
            f"Departman: {department}\n\n"
            "Yanıt formatı:\n"
            "### Makine\n"
            "- [Neden adı]: [açıklama] | Etki: [yd] | Kontrol: [yd]\n"
            "### Malzeme\n"
            "..."
        )
        user_prompt = f"Analiz edilecek sorun: {problem}"
        if context:
            user_prompt += f"\n\nBağlam:\n{context[:1000]}"

        return system_prompt, user_prompt

    @staticmethod
    def parse_ishikawa_response(raw_text: str, problem: str) -> IshikawaDiagram:
        """Ishikawa LLM yanıtını parse et."""
        import re
        diagram = IshikawaDiagram(problem=problem, categories={})

        current_category = ""
        for line in raw_text.strip().split("\n"):
            clean = line.strip()
            if not clean:
                continue

            # Kategori başlığı
            cat_match = re.match(r"#{1,3}\s*(.+)", clean)
            if cat_match:
                cat_name = cat_match.group(1).strip()
                # En yakın Ishikawa kategorisini bul
                matched_cat = None
                for ish_cat in ISHIKAWA_CATEGORIES:
                    if any(part.lower() in cat_name.lower() for part in ish_cat.split()):
                        matched_cat = ish_cat
                        break
                current_category = matched_cat or cat_name
                if current_category not in diagram.categories:
                    diagram.categories[current_category] = []
                continue

            # Faktör satırı
            if clean.startswith(("-", "•", "*")) and current_category:
                factor_text = clean.lstrip("-•* ").strip()

                # Etki ve kontrol bilgisi çıkar
                impact = 0.5
                controllability = 0.5
                if "yüksek" in factor_text.lower():
                    if "etki" in factor_text.lower():
                        impact = 0.8
                    if "kontrol" in factor_text.lower():
                        controllability = 0.8
                if "düşük" in factor_text.lower():
                    if "etki" in factor_text.lower():
                        impact = 0.3
                    if "kontrol" in factor_text.lower():
                        controllability = 0.3

                # İsim ve açıklama ayır
                parts = factor_text.split(":", 1)
                name = parts[0].strip()[:80]
                desc = parts[1].strip() if len(parts) > 1 else factor_text

                # Pipe ile ayrılmış meta bilgiyi temizle
                desc_clean = re.split(r"\|", desc)[0].strip()

                factor = CausalFactor(
                    name=name,
                    description=desc_clean[:200],
                    category=current_category,
                    impact_score=impact,
                    controllability=controllability,
                )
                diagram.categories[current_category].append(factor)

        return diagram


# ═══════════════════════════════════════════════════════════════════
# NEDENSELLİK ZİNCİRİ OLUŞTURUCU
# ═══════════════════════════════════════════════════════════════════

class CausalChainBuilder:
    """Nedensellik zinciri (DAG) oluşturucu."""

    @staticmethod
    def build_from_why_steps(why_steps: List[WhyStep]) -> CausalChain:
        """5 Whys adımlarından nedensellik zinciri oluştur."""
        chain = CausalChain()

        if not why_steps:
            return chain

        factors = []
        for step in why_steps:
            if step.factor:
                factors.append(step.factor)
            else:
                factors.append(CausalFactor(
                    name=step.answer[:80],
                    description=step.answer,
                    is_root_cause=step.is_root,
                ))

        chain.factors = factors

        # Ardışık linkler oluştur (derinlik sırasına göre)
        for i in range(len(factors) - 1):
            chain.links.append(CausalLink(
                source_id=factors[i + 1].factor_id,  # Derin neden → yüzeysel sonuç
                target_id=factors[i].factor_id,
                direction=CausalDirection.CAUSE,
                strength=0.6 + (0.05 * (len(factors) - i)),
                mechanism=f"{factors[i + 1].name} → {factors[i].name}",
            ))

        # Kök nedenler ve son etkiler
        chain.root_causes = [f.factor_id for f in factors if f.is_root_cause]
        if not chain.root_causes and factors:
            chain.root_causes = [factors[-1].factor_id]
        chain.final_effects = [factors[0].factor_id] if factors else []

        # Toplam etki
        chain.total_impact = sum(f.impact_score for f in factors) / max(1, len(factors))

        return chain

    @staticmethod
    def build_prompt_for_chain(
        problem: str,
        department: str,
        known_factors: Optional[List[str]] = None,
    ) -> Tuple[str, str]:
        """Nedensellik zinciri için LLM prompt."""
        system_prompt = (
            "Sen bir Nedensellik Analizi Uzmanısın. Bir sorunun neden-sonuç zincirini "
            "oluşturuyorsun.\n\n"
            "Kurallar:\n"
            "1. Her faktörü kısa ve spesifik adlandır\n"
            "2. Faktörler arası yönü belirt: A → B (A, B'ye neden olur)\n"
            "3. Bağlantı gücünü belirt (güçlü/orta/zayıf)\n"
            "4. Gecikme etkisini belirt (anında/kısa/orta/uzun vade)\n"
            "5. Korelasyon ≠ Nedensellik — yalnızca gerçek nedensel ilişkileri belirt\n"
            f"6. Maksimum {MAX_CHAIN_LENGTH} faktör kullan\n\n"
            f"Departman: {department}\n\n"
            "Format:\n"
            "FAKTÖR 1: [isim]\n"
            "  → FAKTÖR 2: [isim] | Güç: [g/o/z] | Gecikme: [süre] | Mekanizma: [açıklama]\n"
            "  → FAKTÖR 3: ...\n"
            "KÖK NEDENLER: [faktör1, faktör2]\n"
            "SON ETKİLER: [faktörN]"
        )

        user_prompt = f"Sorun: {problem}"
        if known_factors:
            user_prompt += "\n\nBilinen faktörler:\n" + "\n".join(f"- {f}" for f in known_factors)

        return system_prompt, user_prompt

    @staticmethod
    def parse_chain_response(raw_text: str) -> CausalChain:
        """Nedensellik zinciri LLM yanıtını parse et."""
        import re
        chain = CausalChain()
        lines = raw_text.strip().split("\n")

        factor_map: Dict[str, CausalFactor] = {}
        prev_factor_name = ""

        for line in lines:
            clean = line.strip()
            if not clean:
                continue

            # Faktör satırı
            factor_match = re.match(
                r"(?:faktör|factor)\s*\d*\s*[:.]\s*(.*)",
                clean, re.IGNORECASE
            )
            if factor_match:
                name = factor_match.group(1).strip().split("|")[0].strip()
                if name not in factor_map:
                    factor = CausalFactor(name=name)
                    factor_map[name] = factor
                prev_factor_name = name
                continue

            # Bağlantı satırı — "→ FAKTÖR 2:"
            link_match = re.match(r"[→>]\s*(?:faktör|factor)?\s*\d*\s*[:.]\s*(.*)", clean, re.IGNORECASE)
            if link_match and prev_factor_name:
                parts = link_match.group(1).split("|")
                target_name = parts[0].strip()
                if target_name not in factor_map:
                    factor_map[target_name] = CausalFactor(name=target_name)

                # Bağlantı bilgilerini parse et
                strength = 0.5
                mechanism = ""
                for part in parts[1:]:
                    part_clean = part.strip().lower()
                    if "güç" in part_clean or "strength" in part_clean:
                        if "güçlü" in part_clean or "strong" in part_clean:
                            strength = 0.8
                        elif "zayıf" in part_clean or "weak" in part_clean:
                            strength = 0.3
                    elif "mekanizma" in part_clean or "mechanism" in part_clean:
                        mechanism = part.split(":", 1)[-1].strip() if ":" in part else part.strip()

                chain.links.append(CausalLink(
                    source_id=factor_map[prev_factor_name].factor_id,
                    target_id=factor_map[target_name].factor_id,
                    direction=CausalDirection.CAUSE,
                    strength=strength,
                    mechanism=mechanism or f"{prev_factor_name} → {target_name}",
                ))
                prev_factor_name = target_name
                continue

            # Kök neden satırı
            root_match = re.match(r"kök\s*neden(?:ler)?\s*[:.]\s*(.*)", clean, re.IGNORECASE)
            if root_match:
                root_names = [n.strip() for n in root_match.group(1).split(",")]
                for rn in root_names:
                    if rn in factor_map:
                        factor_map[rn].is_root_cause = True
                        chain.root_causes.append(factor_map[rn].factor_id)

            # Son etki satırı
            effect_match = re.match(r"son\s*etki(?:ler)?\s*[:.]\s*(.*)", clean, re.IGNORECASE)
            if effect_match:
                effect_names = [n.strip() for n in effect_match.group(1).split(",")]
                for en in effect_names:
                    if en in factor_map:
                        chain.final_effects.append(factor_map[en].factor_id)

        chain.factors = list(factor_map.values())
        chain.total_impact = sum(f.impact_score for f in chain.factors) / max(1, len(chain.factors))

        return chain


# ═══════════════════════════════════════════════════════════════════
# KARŞI-OLGUSAL MOTOR
# ═══════════════════════════════════════════════════════════════════

class CounterfactualEngine:
    """'X olmasaydı ne olurdu?' analizi."""

    @staticmethod
    def build_prompt(
        problem: str,
        root_causes: List[CausalFactor],
        department: str,
        context: str = "",
    ) -> Tuple[str, str]:
        """Karşı-olgusal analiz prompt'u."""
        system_prompt = (
            "Sen bir Karşı-Olgusal (Counterfactual) Analiz Uzmanısın.\n\n"
            "Görevin: Belirlenen kök nedenler için 'bu neden olmasaydı ne olurdu?' "
            "sorusunu yanıtlamak.\n\n"
            "Her karşı-olgusal senaryo için:\n"
            "1. KOŞUL: 'Eğer [X] olmasaydı/farklı olsaydı...'\n"
            "2. ALTERNATİF SONUÇ: '...o zaman [Y] olurdu'\n"
            "3. OLASILIK: Bu alternatif senaryonun gerçekleşme olasılığı (%)\n"
            "4. ETKİ FARKI: Orijinal sonuçla fark ne kadar?\n"
            "5. VARSAYIMLAR: Bu senaryonun geçerli olması için neler doğru olmalı?\n\n"
            f"Departman: {department}\n"
            f"Maksimum {MAX_COUNTERFACTUALS} senaryo üret."
        )

        user_prompt = f"Sorun: {problem}\n\nBelirlenen kök nedenler:\n"
        for i, rc in enumerate(root_causes[:5], 1):
            user_prompt += f"{i}. {rc.name}: {rc.description[:100]}\n"
        if context:
            user_prompt += f"\nBağlam:\n{context[:800]}"

        return system_prompt, user_prompt

    @staticmethod
    def parse_response(raw_text: str) -> List[Counterfactual]:
        """Karşı-olgusal LLM yanıtını parse et."""
        import re
        counterfactuals = []
        blocks = re.split(r"\n(?=(?:senaryo|koşul|eğer|\d+[.)]\s))", raw_text, flags=re.IGNORECASE)

        for block in blocks:
            if not block.strip():
                continue

            condition = ""
            alternative = ""
            probability = 0.5
            assumptions = []

            lines = block.strip().split("\n")
            for line in lines:
                clean = line.strip().lstrip("-•* ")
                lower = clean.lower()

                if any(kw in lower for kw in ["koşul", "eğer", "olmasaydı", "condition"]):
                    condition = re.sub(r"^(koşul|eğer|condition)\s*[:.]\s*", "", clean, flags=re.IGNORECASE)
                elif any(kw in lower for kw in ["alternatif", "sonuç", "olurdu", "outcome"]):
                    alternative = re.sub(r"^(alternatif|sonuç|outcome)\s*[:.]\s*", "", clean, flags=re.IGNORECASE)
                elif any(kw in lower for kw in ["olasılık", "probability", "%"]):
                    prob_match = re.search(r"(\d+)\s*%", clean)
                    if prob_match:
                        probability = min(int(prob_match.group(1)), 100) / 100.0
                elif any(kw in lower for kw in ["varsayım", "assumption"]):
                    assumptions.append(re.sub(r"^(varsayım|assumption)\s*[:.]\s*", "", clean, flags=re.IGNORECASE))

            # Koşul veya alternatif yoksa blok metninden al
            if not condition and lines:
                condition = lines[0].strip()[:200]
            if not alternative and len(lines) > 1:
                alternative = lines[1].strip()[:200]

            if condition:
                counterfactuals.append(Counterfactual(
                    condition=condition,
                    alternative_outcome=alternative,
                    probability=probability,
                    confidence=ConfidenceLevel.MEDIUM,
                    assumptions=assumptions,
                ))

        return counterfactuals[:MAX_COUNTERFACTUALS]


# ═══════════════════════════════════════════════════════════════════
# MÜDAHALE ANALİZİ
# ═══════════════════════════════════════════════════════════════════

class InterventionAnalyzer:
    """'X yaparsak ne olur?' müdahale analizi."""

    @staticmethod
    def build_prompt(
        problem: str,
        root_causes: List[CausalFactor],
        department: str,
        context: str = "",
    ) -> Tuple[str, str]:
        """Müdahale analizi prompt'u."""
        system_prompt = (
            "Sen bir Müdahale Analizi Uzmanısın. Belirlenen kök nedenlere karşı "
            "uygulanabilir müdahale önerileri üretiyorsun.\n\n"
            "Her müdahale için:\n"
            "1. AKSİYON: Ne yapılmalı? (spesifik ve uygulanabilir)\n"
            "2. HEDEF FAKTÖR: Hangi kök nedene yönelik?\n"
            "3. TİP: Önleyici / Düzeltici / Tespit Edici / Uyarlayıcı\n"
            "4. BEKLENEN ETKİ: Bu müdahale uygulanırsa ne değişir?\n"
            "5. MALİYET: Düşük / Orta / Yüksek\n"
            "6. SÜRE: Etkinin görülme süresi\n"
            "7. YAN ETKİLER: Olumsuz yan etkiler var mı?\n"
            "8. ÖN KOŞULLAR: Bu müdahale için neler gerekli?\n"
            "9. ÖNCELİK: 1-10 (10=en acil)\n\n"
            f"Departman: {department}\n"
            f"Maksimum {MAX_INTERVENTIONS} müdahale öner.\n"
            "Maliyet-etki dengesine dikkat et: ucuz + etkili = yüksek öncelik."
        )

        user_prompt = f"Sorun: {problem}\n\nKök nedenler:\n"
        for i, rc in enumerate(root_causes[:5], 1):
            ctrl = "kontrol edilebilir" if rc.controllability >= 0.5 else "zor kontrol edilir"
            user_prompt += f"{i}. {rc.name} (Etki: {rc.impact_score:.1f}, {ctrl})\n"
        if context:
            user_prompt += f"\nBağlam:\n{context[:800]}"

        return system_prompt, user_prompt

    @staticmethod
    def parse_response(raw_text: str) -> List[Intervention]:
        """Müdahale LLM yanıtını parse et."""
        import re
        interventions = []
        blocks = re.split(r"\n(?=(?:müdahale|aksiyon|öneri|\d+[.)]\s))", raw_text, flags=re.IGNORECASE)

        for block in blocks:
            if not block.strip():
                continue

            action = ""
            target = ""
            i_type = InterventionType.CORRECTIVE
            expected = ""
            cost = "Orta"
            time_est = ""
            side_effects = []
            prerequisites = []
            priority = 5

            lines = block.strip().split("\n")
            for line in lines:
                clean = line.strip().lstrip("-•* ")
                lower = clean.lower()

                if any(kw in lower for kw in ["aksiyon", "action", "yapılmalı", "müdahale"]):
                    action = re.sub(r"^(aksiyon|action|müdahale)\s*[:.]\s*", "", clean, flags=re.IGNORECASE)
                elif any(kw in lower for kw in ["hedef", "target", "faktör"]):
                    target = re.sub(r"^(hedef|target|faktör)\s*[:.]\s*", "", clean, flags=re.IGNORECASE)
                elif any(kw in lower for kw in ["tip", "type", "tür"]):
                    type_text = clean.lower()
                    if "önleyici" in type_text or "preventive" in type_text:
                        i_type = InterventionType.PREVENTIVE
                    elif "tespit" in type_text or "detective" in type_text:
                        i_type = InterventionType.DETECTIVE
                    elif "uyarlayıcı" in type_text or "adaptive" in type_text:
                        i_type = InterventionType.ADAPTIVE
                elif any(kw in lower for kw in ["beklenen", "expected", "etki"]):
                    expected = re.sub(r"^(beklenen|expected|etki)\s*[:.]\s*", "", clean, flags=re.IGNORECASE)
                elif any(kw in lower for kw in ["maliyet", "cost"]):
                    cost_text = clean.lower()
                    if "düşük" in cost_text or "low" in cost_text:
                        cost = "Düşük"
                    elif "yüksek" in cost_text or "high" in cost_text:
                        cost = "Yüksek"
                    else:
                        cost = "Orta"
                elif any(kw in lower for kw in ["süre", "time", "zaman"]):
                    time_est = re.sub(r"^(süre|time|zaman)\s*[:.]\s*", "", clean, flags=re.IGNORECASE)
                elif any(kw in lower for kw in ["yan etki", "side effect"]):
                    side_effects.append(re.sub(r"^(yan etki|side effect)\s*[:.]\s*", "", clean, flags=re.IGNORECASE))
                elif any(kw in lower for kw in ["ön koşul", "prerequisite", "gereksinim"]):
                    prerequisites.append(re.sub(r"^(ön koşul|prerequisite|gereksinim)\s*[:.]\s*", "", clean, flags=re.IGNORECASE))
                elif any(kw in lower for kw in ["öncelik", "priority"]):
                    pri_match = re.search(r"(\d+)", clean)
                    if pri_match:
                        priority = min(int(pri_match.group(1)), 10)

            if not action and lines:
                action = lines[0].strip()[:200]

            if action:
                # Maliyet → effect_magnitude korelasyonu
                magnitude_map = {"Düşük": 0.4, "Orta": 0.6, "Yüksek": 0.8}
                effect_mag = magnitude_map.get(cost, 0.5)

                interventions.append(Intervention(
                    action=action,
                    target_factor=target,
                    intervention_type=i_type,
                    expected_effect=expected,
                    effect_magnitude=effect_mag,
                    cost_estimate=cost,
                    time_to_effect=time_est,
                    side_effects=side_effects,
                    prerequisites=prerequisites,
                    priority=priority,
                ))

        # Önceliğe göre sırala
        interventions.sort(key=lambda x: x.priority, reverse=True)
        return interventions[:MAX_INTERVENTIONS]


# ═══════════════════════════════════════════════════════════════════
# ANALİZ TAKİPÇİSİ
# ═══════════════════════════════════════════════════════════════════

class CausalTracker:
    """Geçmiş nedensellik analizleri ve performans takibi."""

    def __init__(self):
        self._analyses: List[CausalAnalysisResult] = []
        self._category_stats: Dict[str, Dict[str, int]] = defaultdict(
            lambda: {"found_as_root": 0, "total_mentions": 0}
        )
        self._department_stats: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {"analyses": 0, "avg_root_causes": 0.0, "top_categories": []}
        )
        self._intervention_outcomes: Dict[str, Dict[str, Any]] = {}

    def record(self, result: CausalAnalysisResult):
        """Analiz sonucunu kaydet."""
        self._analyses.append(result)
        if len(self._analyses) > MAX_ANALYSIS_HISTORY:
            self._analyses = self._analyses[-MAX_ANALYSIS_HISTORY:]

        # Kategori istatistikleri
        if result.ishikawa:
            for cat, factors in result.ishikawa.categories.items():
                self._category_stats[cat]["total_mentions"] += len(factors)
                root_count = sum(1 for f in factors if f.is_root_cause)
                self._category_stats[cat]["found_as_root"] += root_count

        # Departman istatistikleri
        dept = result.department
        ds = self._department_stats[dept]
        ds["analyses"] += 1
        n = ds["analyses"]
        ds["avg_root_causes"] = round(
            ((ds["avg_root_causes"] * (n - 1)) + result.root_causes_found) / n, 1
        )

        logger.info("causal_analysis_recorded",
                     analysis_id=result.analysis_id,
                     type=result.analysis_type.value,
                     root_causes=result.root_causes_found,
                     interventions=len(result.interventions))

    def get_recent(self, n: int = 20) -> List[dict]:
        """Son N analiz."""
        return [a.to_dict() for a in self._analyses[-n:]]

    def get_statistics(self) -> dict:
        """Genel istatistikler."""
        total = len(self._analyses)
        if total == 0:
            return {"total_analyses": 0}

        avg_root_causes = sum(a.root_causes_found for a in self._analyses) / total
        avg_interventions = sum(len(a.interventions) for a in self._analyses) / total
        avg_time = sum(a.total_time_ms for a in self._analyses) / total

        # En sık kök neden kategorileri
        top_categories = sorted(
            self._category_stats.items(),
            key=lambda x: x[1]["found_as_root"],
            reverse=True,
        )[:5]

        return {
            "total_analyses": total,
            "avg_root_causes_found": round(avg_root_causes, 1),
            "avg_interventions_suggested": round(avg_interventions, 1),
            "avg_analysis_time_ms": round(avg_time, 1),
            "top_root_cause_categories": [
                {"category": cat, **stats}
                for cat, stats in top_categories
            ],
            "department_stats": dict(self._department_stats),
            "analysis_type_distribution": dict(
                defaultdict(
                    int,
                    {a.analysis_type.value: 1 for a in self._analyses}
                )
            ),
        }

    def get_category_insights(self) -> List[dict]:
        """Ishikawa kategori bazlı içgörüler — hangi kategoriden en sık kök neden çıkıyor?"""
        insights = []
        for cat, stats in sorted(
            self._category_stats.items(),
            key=lambda x: x[1]["found_as_root"],
            reverse=True,
        ):
            if stats["total_mentions"] > 0:
                root_rate = stats["found_as_root"] / stats["total_mentions"]
            else:
                root_rate = 0.0
            insights.append({
                "category": cat,
                "total_mentions": stats["total_mentions"],
                "found_as_root_cause": stats["found_as_root"],
                "root_cause_rate": round(root_rate, 2),
            })
        return insights

    def reset(self):
        """Tüm veriyi sıfırla."""
        self._analyses.clear()
        self._category_stats.clear()
        self._department_stats.clear()
        self._intervention_outcomes.clear()
        logger.info("causal_tracker_reset")


# ═══════════════════════════════════════════════════════════════════
# ANA ORKESTRATÖR — CausalInferenceEngine
# ═══════════════════════════════════════════════════════════════════

class CausalInferenceEngine:
    """Nedensellik Analiz Motoru orkestratörü.

    Kullanım (engine.py veya admin'den):
        engine = causal_engine  # singleton
        trigger, reason = engine.should_analyze(question, mode, intent)
        if trigger:
            # Prompt'ları al
            prompts = engine.build_analysis_prompts(question, dept, mode, "full")
            # Her prompt için LLM çağır (engine.py yapar)
            # Yanıtları parse et
            result = engine.process_and_finalize(...)
    """

    def __init__(self):
        self.root_cause_analyzer = RootCauseAnalyzer()
        self.chain_builder = CausalChainBuilder()
        self.counterfactual_engine = CounterfactualEngine()
        self.intervention_analyzer = InterventionAnalyzer()
        self.tracker = CausalTracker()
        self._enabled: bool = True
        self._started_at: str = _utcnow_str()

    def should_analyze(
        self,
        question: str,
        mode: str,
        intent: str,
        force: bool = False,
    ) -> Tuple[bool, str]:
        """Nedensellik analizi tetikleme kararı."""
        if not self._enabled and not force:
            return False, "causal_disabled"
        return should_trigger_causal_analysis(question, mode, intent, force)

    def build_analysis_prompts(
        self,
        question: str,
        department: str,
        mode: str,
        analysis_type: str = "full",
        context: str = "",
        known_factors: Optional[List[str]] = None,
    ) -> Dict[str, Tuple[str, str]]:
        """Analiz tiplerine göre prompt'lar oluştur.

        Returns:
            {"five_whys": (sys, usr), "ishikawa": (sys, usr), ...}
        """
        prompts: Dict[str, Tuple[str, str]] = {}

        if analysis_type in ("root_cause", "full"):
            prompts["five_whys"] = self.root_cause_analyzer.build_five_whys_prompt(
                question, department, context
            )
            prompts["ishikawa"] = self.root_cause_analyzer.build_ishikawa_prompt(
                question, department, context
            )

        if analysis_type in ("causal_chain", "full"):
            prompts["causal_chain"] = self.chain_builder.build_prompt_for_chain(
                question, department, known_factors
            )

        # Karşı-olgusal ve müdahale — kök nedenler gerekli, sonradan çağrılır
        return prompts

    def build_followup_prompts(
        self,
        question: str,
        department: str,
        root_causes: List[CausalFactor],
        context: str = "",
    ) -> Dict[str, Tuple[str, str]]:
        """Kök nedenler bulunduktan sonra followup prompt'lar."""
        prompts: Dict[str, Tuple[str, str]] = {}

        if root_causes:
            prompts["counterfactual"] = self.counterfactual_engine.build_prompt(
                question, root_causes, department, context
            )
            prompts["intervention"] = self.intervention_analyzer.build_prompt(
                question, root_causes, department, context
            )

        return prompts

    def parse_responses(
        self,
        question: str,
        raw_responses: Dict[str, str],
    ) -> Dict[str, Any]:
        """LLM yanıtlarını parse et.

        Args:
            question: Orijinal soru
            raw_responses: {"five_whys": "...", "ishikawa": "...", ...}

        Returns:
            Parsed sonuçlar dict
        """
        parsed: Dict[str, Any] = {}

        if "five_whys" in raw_responses:
            parsed["why_steps"] = self.root_cause_analyzer.parse_five_whys_response(
                raw_responses["five_whys"]
            )

        if "ishikawa" in raw_responses:
            parsed["ishikawa"] = self.root_cause_analyzer.parse_ishikawa_response(
                raw_responses["ishikawa"], question
            )

        if "causal_chain" in raw_responses:
            parsed["causal_chain"] = self.chain_builder.parse_chain_response(
                raw_responses["causal_chain"]
            )
        elif "why_steps" in parsed:
            # 5 Whys'dan zincir oluştur
            parsed["causal_chain"] = self.chain_builder.build_from_why_steps(
                parsed["why_steps"]
            )

        if "counterfactual" in raw_responses:
            parsed["counterfactuals"] = self.counterfactual_engine.parse_response(
                raw_responses["counterfactual"]
            )

        if "intervention" in raw_responses:
            parsed["interventions"] = self.intervention_analyzer.parse_response(
                raw_responses["intervention"]
            )

        return parsed

    def finalize_analysis(
        self,
        question: str,
        department: str,
        mode: str,
        analysis_type: str,
        parsed_data: Dict[str, Any],
        confidence_before: float = 0.0,
        total_time_ms: float = 0.0,
        triggered_by: str = "auto",
    ) -> CausalAnalysisResult:
        """Analizi sonlandır, kaydet ve sonuç döndür."""
        why_steps = parsed_data.get("why_steps", [])
        ishikawa = parsed_data.get("ishikawa")
        chain = parsed_data.get("causal_chain")
        counterfactuals = parsed_data.get("counterfactuals", [])
        interventions = parsed_data.get("interventions", [])

        # Kök neden sayısı
        root_causes_found = sum(1 for s in why_steps if s.is_root)
        if ishikawa:
            for factors in ishikawa.categories.values():
                root_causes_found += sum(1 for f in factors if f.is_root_cause)

        # Confidence adjustment
        conf_adj = 0.0
        if root_causes_found > 0:
            conf_adj += CONFIDENCE_BOOST_ON_ROOT_CAUSE
        if interventions:
            conf_adj += CONFIDENCE_BOOST_ON_INTERVENTION

        try:
            at = AnalysisType(analysis_type)
        except ValueError:
            at = AnalysisType.FULL

        result = CausalAnalysisResult(
            question=question,
            department=department,
            mode=mode,
            analysis_type=at,
            why_analysis=why_steps,
            ishikawa=ishikawa,
            causal_chain=chain,
            counterfactuals=counterfactuals,
            interventions=interventions,
            root_causes_found=root_causes_found,
            confidence_adjustment=conf_adj,
            total_time_ms=total_time_ms,
            triggered_by=triggered_by,
        )

        self.tracker.record(result)
        return result

    def get_dashboard(self) -> dict:
        """Dashboard verisi."""
        return {
            "available": True,
            "enabled": self._enabled,
            "started_at": self._started_at,
            "statistics": self.tracker.get_statistics(),
            "category_insights": self.tracker.get_category_insights(),
            "recent_analyses": self.tracker.get_recent(10),
            "settings": {
                "max_why_depth": MAX_WHY_DEPTH,
                "max_chain_length": MAX_CHAIN_LENGTH,
                "max_counterfactuals": MAX_COUNTERFACTUALS,
                "max_interventions": MAX_INTERVENTIONS,
                "confidence_boost_root_cause": CONFIDENCE_BOOST_ON_ROOT_CAUSE,
                "confidence_boost_intervention": CONFIDENCE_BOOST_ON_INTERVENTION,
                "ishikawa_categories": ISHIKAWA_CATEGORIES,
            },
        }

    def set_enabled(self, enabled: bool) -> dict:
        """Nedensellik analizini aç/kapat."""
        old = self._enabled
        self._enabled = enabled
        logger.info("causal_engine_toggled", old=old, new=enabled)
        return {"enabled": enabled, "previous": old}

    def reset(self):
        """Tüm veriyi sıfırla."""
        self.tracker.reset()
        self._started_at = _utcnow_str()
        logger.info("causal_engine_reset")


# ═══════════════════════════════════════════════════════════════════
# GLOBAL SINGLETON
# ═══════════════════════════════════════════════════════════════════

causal_engine: CausalInferenceEngine = CausalInferenceEngine()


# ═══════════════════════════════════════════════════════════════════
# KOLAYLIK FONKSİYONLARI — engine.py entegrasyonu
# ═══════════════════════════════════════════════════════════════════

def check_causal_trigger(
    question: str, mode: str, intent: str, force: bool = False,
) -> Tuple[bool, str]:
    """Nedensellik analizi tetikleme kontrolü."""
    return causal_engine.should_analyze(question, mode, intent, force)


def get_causal_dashboard() -> dict:
    """Dashboard verisi."""
    return causal_engine.get_dashboard()
