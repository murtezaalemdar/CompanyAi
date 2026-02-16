"""Explainability (XAI) — Açıklanabilir Yapay Zeka Modülü v4.0

Her AI yanıtını analiz eden, gerçek verilerle faktör skoru hesaplayan,
istatistik toplayan, token attribution yapan ve kullanıcı geri bildirimiyle
kalibre olan tam kapsamlı XAI motoru.

v4.0 Yenilikler:
- Sohbet modunda sabit değerler kaldırıldı → gerçek analiz
- Kaynak güvenilirliği: LLM bilgi kalitesi + belirsizlik + referans analizi
- Yanıt kalitesi: başlık, paragraf, emoji, tekrar kontrolü
- Bağlam uyumu: TF-IDF tabanlı semantik benzerlik
- PostgreSQL'e kalıcı kayıt (sunucu restart'ta veri korunur)
- Gelişmiş heuristic'ler ile daha adil skorlama
"""

import time
import re
import math
import asyncio
from collections import deque, Counter
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import datetime

try:
    import structlog
    logger = structlog.get_logger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)

# DB kayıt desteği
try:
    from app.db.database import async_session_maker
    from app.db.models import XaiRecord
    DB_AVAILABLE = True
except Exception:
    DB_AVAILABLE = False


# ──────────────────── Sabitler ────────────────────

MAX_HISTORY = 500  # Son N açıklama kaydı

# Faktör ağırlıkları — modüle göre adapte edilir
BASE_FACTOR_WEIGHTS = {
    "yanıt_kalitesi":     0.20,
    "kaynak_güvenilirliği": 0.20,
    "bağlam_uyumu":       0.15,
    "veri_yeterliliği":   0.15,
    "risk_farkındalığı":  0.15,
    "tutarlılık":         0.15,
}

# Modül bazlı ağırlık override'ları
MODULE_WEIGHT_PROFILES = {
    "Analiz": {"veri_yeterliliği": 0.25, "yanıt_kalitesi": 0.20, "kaynak_güvenilirliği": 0.15,
               "bağlam_uyumu": 0.15, "risk_farkındalığı": 0.10, "tutarlılık": 0.15},
    "Rapor":  {"veri_yeterliliği": 0.20, "yanıt_kalitesi": 0.25, "kaynak_güvenilirliği": 0.15,
               "bağlam_uyumu": 0.10, "risk_farkındalığı": 0.15, "tutarlılık": 0.15},
    "Öneri":  {"risk_farkındalığı": 0.25, "yanıt_kalitesi": 0.20, "kaynak_güvenilirliği": 0.15,
               "bağlam_uyumu": 0.15, "veri_yeterliliği": 0.15, "tutarlılık": 0.10},
    "Acil":   {"risk_farkındalığı": 0.30, "yanıt_kalitesi": 0.20, "bağlam_uyumu": 0.15,
               "kaynak_güvenilirliği": 0.15, "veri_yeterliliği": 0.10, "tutarlılık": 0.10},
    "Sohbet": {"bağlam_uyumu": 0.25, "yanıt_kalitesi": 0.25, "tutarlılık": 0.20,
               "kaynak_güvenilirliği": 0.10, "veri_yeterliliği": 0.10, "risk_farkındalığı": 0.10},
}

# Risk anahtar kelimeleri
RISK_KW_HIGH = ["acil", "kritik", "yangın", "kaza", "tehlike", "kayıp", "zarar", "kriz", "düşüş"]
RISK_KW_MID  = ["risk", "dikkat", "kontrol", "sapma", "gecikme", "sorun", "problem"]
RISK_KW_LOW  = ["normal", "stabil", "artış", "olumlu", "iyileşme", "başarılı"]


# ──────────────────── Veri Yapıları ────────────────────

@dataclass
class ExplanationRecord:
    """Tek bir XAI analiz kaydı."""
    timestamp: float = 0.0
    query_hash: str = ""
    query_preview: str = ""
    mode: str = ""
    module_source: str = ""
    weighted_confidence: float = 0.0
    factors: list = field(default_factory=list)
    risk_level: str = "Düşük"
    risk_score: float = 0.0
    reasoning_steps: int = 0
    sources_used: int = 0
    rag_hit: bool = False
    web_searched: bool = False
    had_reflection: bool = False
    word_count: int = 0
    counterfactual: str = ""
    token_attribution: list = field(default_factory=list)  # SHAP-like token etki listesi
    user_rating: Optional[float] = None  # Kullanıcı geri bildirimi (1-5)


# ──────────────────── Geri Bildirim Yapısı ────────────────────

@dataclass
class FeedbackRecord:
    """Kullanıcı geri bildirim kaydı."""
    timestamp: float = 0.0
    query_hash: str = ""
    mode: str = ""
    xai_confidence: float = 0.0
    user_rating: float = 0.0  # 1-5 arası
    factor_overrides: Dict[str, float] = field(default_factory=dict)  # Kullanıcı düzeltmeleri


# ──────────────────── XAI Engine ────────────────────

class DecisionExplainer:
    """AI kararlarını açıklayan, token attribution yapan ve kullanıcı geri bildirimiyle
    kalibre olan tam kapsamlı XAI modülü v3.0."""

    def __init__(self):
        self._history: deque[ExplanationRecord] = deque(maxlen=MAX_HISTORY)
        self._total_evaluations: int = 0
        self._confidence_sum: float = 0.0
        self._risk_distribution: Dict[str, int] = {"Düşük": 0, "Orta": 0, "Yüksek": 0}
        self._mode_stats: Dict[str, Dict] = {}  # mode -> {count, conf_sum}
        self._low_confidence_count: int = 0
        self._high_confidence_count: int = 0
        # v3.0: Geri bildirim ve kalibrasyon
        self._feedback_history: deque[FeedbackRecord] = deque(maxlen=MAX_HISTORY)
        self._calibration_weights: Dict[str, float] = {}  # Kalibrasyon delta'ları
        self._total_feedback: int = 0
        self._feedback_sum: float = 0.0
        self._calibration_log: List[Dict] = []  # Kalibrasyon geçmişi

    # ══════════════════════════════════════════════════════
    # ANA ANALİZ FONKSİYONU — engine.py'den çağrılır
    # ══════════════════════════════════════════════════════

    def explain(
        self,
        query: str,
        response: str,
        mode: str = "Sohbet",
        confidence: float = 0.0,
        sources: Optional[List[str]] = None,
        rag_docs: Optional[List[dict]] = None,
        web_searched: bool = False,
        reflection_data: Optional[dict] = None,
        module_source: str = "engine",
        context_data: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        Bir AI yanıtının tam XAI analizini üret.
        
        Gerçek verilerle çalışır — statik varsayılanlar yok.
        """
        ctx = context_data or {}
        src_list = sources or []

        # 1. Modül bazlı ağırlıklar
        weights = MODULE_WEIGHT_PROFILES.get(mode, BASE_FACTOR_WEIGHTS)

        # 2. Gerçek faktör analizi
        factors = self._analyze_factors(
            query=query,
            response=response,
            mode=mode,
            confidence=confidence,
            sources=src_list,
            rag_docs=rag_docs,
            web_searched=web_searched,
            reflection_data=reflection_data,
            weights=weights,
        )

        # 3. Ağırlıklı güven skoru (kalibrasyon uygulanır)
        weights_calibrated = self._apply_calibration(weights)
        weighted_conf = sum(f["score"] * weights_calibrated.get(f["key"], f["weight"]) for f in factors)
        weighted_conf = max(0.0, min(1.0, weighted_conf))

        # 4. Risk değerlendirmesi
        risk = self._assess_risk(query, response)

        # 5. Modül bazlı reasoning chain
        chain = self._build_reasoning_chain(
            query=query,
            response=response,
            mode=mode,
            module_source=module_source,
            sources=src_list,
            rag_docs=rag_docs,
            web_searched=web_searched,
            reflection_data=reflection_data,
        )

        # 6. Karşı-olgusal analiz
        counterfactual = self._generate_counterfactual(factors, risk, mode)

        # 7. Geçmiş karşılaştırma
        historical = self._compare_with_history(query, weighted_conf, mode)

        # 8. Öneriler
        recommendations = self._generate_recommendations(factors, risk, weighted_conf, mode)

        # 9. Özet
        summary = self._build_summary(mode, module_source, weighted_conf, risk)

        # 10. SHAP-Like Token Attribution
        token_attr = self._compute_token_attribution(query, response, mode, src_list, rag_docs, web_searched, reflection_data)

        # 11. Attention Heatmap — query vs response kelime etkileşimi
        attention_map = self._compute_attention_heatmap(query, response)

        # 12. Kaydı istatistiklere ekle
        record = ExplanationRecord(
            timestamp=time.time(),
            query_hash=self._hash_query(query),
            query_preview=query[:80],
            mode=mode,
            module_source=module_source,
            weighted_confidence=weighted_conf,
            factors=factors,
            risk_level=risk["level"],
            risk_score=risk["score"],
            reasoning_steps=len(chain),
            sources_used=len(src_list),
            rag_hit=bool(rag_docs),
            web_searched=web_searched,
            had_reflection=bool(reflection_data),
            word_count=len(response.split()),
            counterfactual=counterfactual,
            token_attribution=token_attr,
        )
        self._record_stats(record)

        return {
            "summary": summary,
            "confidence": round(weighted_conf, 3),
            "confidence_pct": round(weighted_conf * 100, 1),
            "confidence_label": self._confidence_label(weighted_conf),
            "factors": factors,
            "reasoning_chain": chain,
            "risk_assessment": risk,
            "counterfactual": counterfactual,
            "historical_comparison": historical,
            "recommendations": recommendations,
            "token_attribution": token_attr,
            "attention_heatmap": attention_map,
            "calibration_active": bool(self._calibration_weights),
            "module_source": module_source,
            "mode": mode,
            "meta": {
                "word_count": len(response.split()),
                "sources_used": len(src_list),
                "rag_hit": bool(rag_docs),
                "web_searched": web_searched,
                "had_reflection": bool(reflection_data),
                "calibration_adjustments": len(self._calibration_weights),
                "total_feedback_received": self._total_feedback,
            },
            "timestamp": datetime.now().isoformat(),
        }

    # ══════════════════════════════════════════════════════
    # FAKTÖR ANALİZİ — Gerçek Verilerle
    # ══════════════════════════════════════════════════════

    def _analyze_factors(
        self, query: str, response: str, mode: str, confidence: float,
        sources: list, rag_docs: Optional[list], web_searched: bool,
        reflection_data: Optional[dict], weights: dict,
    ) -> List[Dict]:
        factors = []

        # ── 1. Yanıt Kalitesi ──
        quality_score = self._score_response_quality(response, mode)
        factors.append({
            "name": "Yanıt Kalitesi",
            "key": "yanıt_kalitesi",
            "score": quality_score,
            "weight": weights.get("yanıt_kalitesi", 0.20),
            "explanation": self._quality_explanation(quality_score, response, mode),
        })

        # ── 2. Kaynak Güvenilirliği ──
        source_score = self._score_source_reliability(sources, rag_docs, web_searched, response)
        factors.append({
            "name": "Kaynak Güvenilirliği",
            "key": "kaynak_güvenilirliği",
            "score": source_score,
            "weight": weights.get("kaynak_güvenilirliği", 0.20),
            "explanation": self._source_explanation(source_score, sources, rag_docs, web_searched),
        })

        # ── 3. Bağlam Uyumu ──
        context_score = self._score_context_match(query, response)
        factors.append({
            "name": "Bağlam Uyumu",
            "key": "bağlam_uyumu",
            "score": context_score,
            "weight": weights.get("bağlam_uyumu", 0.15),
            "explanation": self._context_explanation(context_score, query, response),
        })

        # ── 4. Veri Yeterliliği ──
        data_score = self._score_data_sufficiency(response, mode)
        factors.append({
            "name": "Veri Yeterliliği",
            "key": "veri_yeterliliği",
            "score": data_score,
            "weight": weights.get("veri_yeterliliği", 0.15),
            "explanation": self._data_explanation(data_score, response, mode),
        })

        # ── 5. Risk Farkındalığı ──
        risk_awareness = self._score_risk_awareness(response, mode)
        factors.append({
            "name": "Risk Farkındalığı",
            "key": "risk_farkındalığı",
            "score": risk_awareness,
            "weight": weights.get("risk_farkındalığı", 0.15),
            "explanation": self._risk_awareness_explanation(risk_awareness, mode),
        })

        # ── 6. Tutarlılık ──
        consistency_score = self._score_consistency(response, reflection_data, confidence)
        factors.append({
            "name": "Tutarlılık",
            "key": "tutarlılık",
            "score": consistency_score,
            "weight": weights.get("tutarlılık", 0.15),
            "explanation": self._consistency_explanation(consistency_score, reflection_data),
        })

        return factors

    # ── Yanıt Kalitesi Skorlama (v4.0 — Gelişmiş) ──

    def _score_response_quality(self, response: str, mode: str) -> float:
        score = 0.45  # v4: taban biraz düşürüldü, bonuslar artırıldı
        words = response.split()
        word_count = len(words)

        # ── Uzunluk — moda göre ──
        if mode in ("Analiz", "Rapor", "Öneri"):
            if word_count >= 200: score += 0.15
            elif word_count >= 100: score += 0.10
            elif word_count >= 50: score += 0.05
            elif word_count < 30: score -= 0.10
        elif mode == "Sohbet":
            if 10 <= word_count <= 150: score += 0.12
            elif 150 < word_count <= 300: score += 0.08
            elif word_count > 300: score -= 0.03
            elif word_count < 5: score -= 0.10

        # ── Yapısal elementler ──
        if re.search(r'^\s*[-•\d.)\]✅✔⭐🔹▹►]', response, re.M):
            score += 0.08  # Madde işareti / liste
        if '|' in response and '-' in response:
            score += 0.08  # Tablo

        # ── Başlık / bold yapı (v4 yeni) ──
        if re.search(r'(\*\*[^*]+\*\*|##\s+\S|#{1,3}\s)', response):
            score += 0.07  # Başlık veya bold bölüm

        # ── Paragraf yapısı (v4 yeni) ──
        paragraphs = [p.strip() for p in response.split('\n\n') if p.strip()]
        if len(paragraphs) >= 3:
            score += 0.06  # Düzenli paragraf yapısı
        elif len(paragraphs) >= 2:
            score += 0.03

        # ── Sonuç / Sonuç bölümü ──
        if re.search(r'(sonuç|özet|tavsiye|öneri|değerlendirme|özetle)', response, re.I):
            score += 0.05

        # ── Sebep-sonuç / açıklama ──
        if re.search(r'(çünkü|nedeniyle|dolayı|bu\s*nedenle|sebebiyle|zira)', response, re.I):
            score += 0.05

        # ── Tekrar kontrolü (v4 yeni — ceza) ──
        if word_count > 20:
            unique_ratio = len(set(w.lower() for w in words)) / word_count
            if unique_ratio < 0.3:  # %70+ tekrar
                score -= 0.15
            elif unique_ratio < 0.45:
                score -= 0.05

        # ── Hata belirteçleri ──
        if response.startswith("[Hata]") or "hata" in response.lower()[:50]:
            score -= 0.30

        return max(0.0, min(1.0, score))

    def _quality_explanation(self, score: float, response: str, mode: str) -> str:
        words = response.split()
        word_count = len(words)
        parts = [f"{word_count} kelime"]
        if score >= 0.8: parts.append("yapısal olarak güçlü")
        elif score >= 0.65: parts.append("iyi yapılandırılmış")
        elif score >= 0.5: parts.append("kabul edilebilir yapı")
        else: parts.append("yapısal iyileştirme gerekebilir")
        # v4: Tekrar oranı bilgisi
        if word_count > 20:
            unique_ratio = len(set(w.lower() for w in words)) / word_count
            if unique_ratio < 0.3:
                parts.append("⚠️ yüksek tekrar")
        return f"Yanıt kalitesi: {' — '.join(parts)}"

    # ── Kaynak Güvenilirliği (v4.0 — Zenginleştirilmiş) ──

    def _score_source_reliability(self, sources: list, rag_docs: Optional[list],
                                   web: bool, response: str = "") -> float:
        score = 0.25  # v4: taban biraz düşürüldü, gerçek analizle yükselsin

        # ── Harici kaynaklar ──
        if rag_docs:
            score += 0.25  # RAG doküman eşleşmesi
            if len(rag_docs) >= 3:
                score += 0.10  # Çoklu kaynak
            elif len(rag_docs) >= 2:
                score += 0.05
        if sources:
            score += min(0.15, len(sources) * 0.04)  # Her kaynak +4%, max %15
        if web:
            score += 0.10  # Web doğrulaması

        # ── v4: LLM bilgi kalitesi analizi (kaynak olmasa bile) ──
        if response:
            resp_lower = response.lower()

            # Belirsizlik dürüstlüğü → pozitif sinyal (hallüsinasyon riski düşük)
            honesty_markers = re.findall(
                r'(kesin\s*bilgim\s*yok|tahmin|yaklaşık|net\s*değil|emin\s*değilim|'
                r'bilmiyorum|doğrulanmalı|kontrol\s*edilmeli|genel\s*olarak)',
                resp_lower
            )
            if honesty_markers:
                score += min(0.08, len(honesty_markers) * 0.03)

            # Somut referanslar (tarih, sayı, isim) → bilgi somutluğu
            has_dates = bool(re.search(r'\d{4}|\d{1,2}[./]\d{1,2}[./]\d{2,4}', response))
            has_specifics = bool(re.search(r'(örneğin|mesela|spesifik|özellikle)', resp_lower))
            has_numbers = len(re.findall(r'\b\d+[.,]?\d*\s*(%|₺|\$|€|kg|ton|adet|metre)', response))

            if has_dates: score += 0.04
            if has_specifics: score += 0.03
            if has_numbers >= 2: score += 0.05
            elif has_numbers >= 1: score += 0.03

            # Teknik terimler yoğunluğu → alan bilgisi
            technical = re.findall(
                r'(algoritma|optimizasyon|veritabanı|API|sistem|süreç|analiz|'
                r'metrik|parametre|konfigürasyon|entegrasyon|modül|fonksiyon|'
                r'performans|rapor|strateji|planlama|üretim|kalite|maliyet)',
                resp_lower
            )
            if len(technical) >= 5: score += 0.06
            elif len(technical) >= 3: score += 0.04
            elif len(technical) >= 1: score += 0.02

        return max(0.0, min(1.0, score))

    def _source_explanation(self, score: float, sources: list, rag_docs: Optional[list], web: bool) -> str:
        parts = []
        if rag_docs:
            parts.append(f"RAG: {len(rag_docs)} doküman eşleşti")
        if sources:
            parts.append(f"{len(sources)} kaynak kullanıldı")
        if web:
            parts.append("Web araması yapıldı")
        if not parts:
            if score >= 0.45:
                parts.append("Model bilgisi + içerik analizi ile değerlendirildi")
            else:
                parts.append("Sadece model bilgisi kullanıldı — kaynak eklenmesi önerilir")
        return " | ".join(parts)

    # ── Bağlam Uyumu (v4.0 — TF-IDF Tabanlı) ──

    _STOP_WORDS = frozenset({
        "bir", "bu", "ve", "ile", "için", "olarak", "daha", "olan",
        "gibi", "çok", "var", "den", "dan", "ise", "ama", "hem", "her",
        "kadar", "sonra", "önce", "nasıl", "neden", "nedir", "midir",
        "mıdır", "hangi", "bana", "benim", "onun", "şey", "the", "and",
        "is", "are", "was", "were", "that", "this", "from", "with",
    })

    def _score_context_match(self, query: str, response: str) -> float:
        # Soru ve yanıt kelimelerini ayıkla (stop words hariç)
        q_tokens = [w for w in re.findall(r'\b\w{3,}\b', query.lower())
                     if w not in self._STOP_WORDS]
        r_tokens = [w for w in re.findall(r'\b\w{3,}\b', response.lower())
                     if w not in self._STOP_WORDS]

        if not q_tokens:
            return 0.5

        q_set = set(q_tokens)
        r_set = set(r_tokens)

        # ── 1. Basit kelime eşleşmesi ──
        overlap = len(q_set & r_set)
        overlap_ratio = overlap / len(q_set)

        # ── 2. TF-IDF tabanlı ağırlıklı benzerlik (v4 yeni) ──
        r_freq = Counter(r_tokens)
        r_total = max(len(r_tokens), 1)

        # IDF-benzeri: Sık geçen yanıt kelimeleri daha az bilgi taşır
        tfidf_score = 0.0
        matched_importance = 0.0
        for qw in q_set:
            if qw in r_freq:
                tf = r_freq[qw] / r_total  # Term Frequency in response
                # Nadiren geçen eşleşmeler daha değerli (inverse popularity)
                idf_weight = 1.0 / (1.0 + math.log1p(r_freq[qw]))  # Sık geçen = düşük IDF
                tfidf_score += tf * idf_weight * 10  # Normalize edilmiş katkı
                matched_importance += 1

        tfidf_normalized = min(0.3, tfidf_score / max(len(q_set), 1))

        # ── 3. Skor birleştirme ──
        score = 0.25 + overlap_ratio * 0.35 + tfidf_normalized

        # ── 4. Uzunluk oranı ──
        len_ratio = len(response) / max(len(query), 1)
        if len_ratio >= 3:
            score += 0.08
        elif len_ratio >= 1.5:
            score += 0.05
        elif len_ratio < 0.5:
            score -= 0.08

        # ── 5. Tam soru ibaresi yanıtta var mı (v4 yeni) ──
        # Sorunun önemli kısmı aynen yanıtta geçiyorsa bağlam tam oturmuş
        q_important = " ".join(q_tokens[:5])  # İlk 5 anlamlı kelime
        if len(q_important) > 8 and q_important in response.lower():
            score += 0.07

        return max(0.0, min(1.0, score))

    def _context_explanation(self, score: float, query: str, response: str) -> str:
        q_tokens = [w for w in re.findall(r'\b\w{3,}\b', query.lower())
                     if w not in self._STOP_WORDS]
        r_tokens_set = set(re.findall(r'\b\w{3,}\b', response.lower()))
        overlap = len(set(q_tokens) & r_tokens_set)
        method = "TF-IDF + kelime eşleşmesi"
        return f"Soru-yanıt uyumu ({method}): {overlap}/{len(q_tokens)} anahtar kelime eşleşti"

    # ── Veri Yeterliliği (v4.0 — Sohbette de gerçek analiz) ──

    def _score_data_sufficiency(self, response: str, mode: str) -> float:
        # v4: Sohbet modunda da gerçek analiz — sabit değer döndürülmüyor
        is_chat = mode == "Sohbet"
        score = 0.50 if is_chat else 0.40  # Sohbette beklenti biraz düşük

        resp_lower = response.lower()

        # ── Sayısal veri ──
        numbers = re.findall(r'\d+[.,]?\d*', response)
        if numbers:
            if is_chat:
                score += min(0.15, len(numbers) * 0.04)  # Sohbette sayı önemli ama gerekli değil
            else:
                score += min(0.20, len(numbers) * 0.03)

        # ── Birimler / ölçüler ──
        units = re.findall(r'[₺$€%]|(?:kg|ton|metre|adet|gün|saat|ay|yıl|dk|dakika|saniye)', response, re.I)
        if units:
            score += 0.08 if is_chat else 0.10

        # ── Tablo ──
        if '|' in response:
            score += 0.08

        # ── Bilgi zenginliği (v4 yeni) ──
        # Farklı bilgi parçacıkları (cümle sayısı)
        sentences = [s.strip() for s in re.split(r'[.!?\n]', response) if len(s.strip()) > 10]
        if len(sentences) >= 5:
            score += 0.08
        elif len(sentences) >= 3:
            score += 0.04

        # ── Somut açıklama / adım ──
        if re.search(r'(adım|öncelikle|ardından|sonrasında|ilk olarak)', resp_lower):
            score += 0.05

        # ── "Bilmiyorum" dürüstlüğü → pozitif ──
        if re.search(r'(kesin\s*bilgim\s*yok|tahmin|yaklaşık|net\s*değil)', resp_lower):
            score += 0.04

        # ── Çok kısa yanıt cezası ──
        word_count = len(response.split())
        if word_count < 5:
            score -= 0.15
        elif word_count < 15 and not is_chat:
            score -= 0.10

        return max(0.0, min(1.0, score))

    def _data_explanation(self, score: float, response: str, mode: str) -> str:
        nums = len(re.findall(r'\d+[.,]?\d*', response))
        sentences = len([s for s in re.split(r'[.!?\n]', response) if len(s.strip()) > 10])
        label = "Sohbet" if mode == "Sohbet" else mode
        return f"[{label}] Yanıtta {nums} sayısal veri, {sentences} cümle, {'tablo var' if '|' in response else 'tablo yok'}"

    # ── Risk Farkındalığı (v4.0 — Sohbette de gerçek analiz) ──

    def _score_risk_awareness(self, response: str, mode: str) -> float:
        # v4: Sohbet modunda da gerçek analiz
        is_chat = mode == "Sohbet"
        resp_lower = response.lower()

        # Sohbette baz skor daha yüksek (risk beklentisi düşük)
        score = 0.60 if is_chat else 0.50

        has_risk_mention = bool(re.search(r'(risk|tehlike|tehdit|uyarı|dikkat|sorun|problem)', resp_lower))
        has_level = bool(re.search(r'(düşük|orta|yüksek|kritik|🔴|🟡|🟢|önemli|ciddi)', resp_lower))
        has_mitigation = bool(re.search(r'(önlem|azalt|tedbir|engellemek|koruma|çözüm|öneri|tavsiye)', resp_lower))
        has_limitation = bool(re.search(r'(ancak|dikkat|unutmayın|not:|uyarı:|önemli:)', resp_lower))

        if has_risk_mention:
            score += 0.12 if is_chat else 0.15
        if has_level:
            score += 0.10 if is_chat else 0.15
        if has_mitigation:
            score += 0.10 if is_chat else 0.15
        if has_limitation:
            score += 0.06  # v4: Sınırlamaları belirtmek pozitif

        return max(0.0, min(1.0, score))

    def _risk_awareness_explanation(self, score: float, mode: str) -> str:
        if mode == "Sohbet" and score >= 0.7:
            return "Sohbet yanıtında uygun düzeyde risk/sınırlama bilinci var"
        if score >= 0.8: return "Risk tanımlanmış, seviyesi belirtilmiş, azaltma önerisi var"
        if score >= 0.6: return "Risk kısmen belirtilmiş ancak detay eksik"
        return "Risk değerlendirmesi yetersiz"

    # ── Tutarlılık ──

    def _score_consistency(self, response: str, reflection_data: Optional[dict], confidence: float) -> float:
        score = 0.6

        # Reflection varsa onun puanını kullan
        if reflection_data:
            ref_conf = reflection_data.get("confidence", 70)
            if ref_conf >= 80: score += 0.20
            elif ref_conf >= 60: score += 0.10
            else: score -= 0.10

            if reflection_data.get("pass"):
                score += 0.10

            issues = reflection_data.get("issues", [])
            if not issues:
                score += 0.05
            elif len(issues) >= 3:
                score -= 0.10

        # Confidence-based
        if confidence >= 0.85: score += 0.05
        elif confidence < 0.5: score -= 0.10

        # Çelişki kontrolü
        contradictions = len(re.findall(
            r'(ancak|fakat|öte yandan|aksine|tam tersine)', response, re.I
        ))
        if contradictions > 4:
            score -= 0.10

        return max(0.0, min(1.0, score))

    def _consistency_explanation(self, score: float, reflection_data: Optional[dict]) -> str:
        if reflection_data:
            ref_conf = reflection_data.get("confidence", 0)
            return f"Reflection puanı: %{ref_conf:.0f}, {'geçti' if reflection_data.get('pass') else 'kaldı'}"
        return "Reflection verisi yok — temel tutarlılık kontrolü yapıldı"

    # ══════════════════════════════════════════════════════
    # REASONING CHAIN — Modül Bazlı Adaptasyon
    # ══════════════════════════════════════════════════════

    def _build_reasoning_chain(
        self, query: str, response: str, mode: str, module_source: str,
        sources: list, rag_docs: Optional[list], web_searched: bool,
        reflection_data: Optional[dict],
    ) -> List[Dict]:
        chain = []
        step = 0

        # 1. Sorgu analizi (her zaman)
        step += 1
        chain.append({
            "step": step,
            "action": "Sorgu Analizi",
            "detail": f"Sorgu alındı ({len(query)} kar.). Mod: {mode}, Modül: {module_source}",
            "status": "done",
        })

        # 2. Router kararı
        step += 1
        chain.append({
            "step": step,
            "action": "Akıllı Yönlendirme",
            "detail": f"Router soruyu '{mode}' moduna yönlendirdi",
            "status": "done",
        })

        # 3. RAG (varsa)
        if rag_docs:
            step += 1
            chain.append({
                "step": step,
                "action": "RAG Bilgi Tabanı",
                "detail": f"{len(rag_docs)} ilgili doküman bulundu ve bağlama eklendi",
                "status": "done",
            })

        # 4. Web araması (varsa)
        if web_searched:
            step += 1
            chain.append({
                "step": step,
                "action": "Web Araması",
                "detail": "İnternet araması yapıldı ve sonuçlar bağlama eklendi",
                "status": "done",
            })

        # 5. Hafıza
        step += 1
        chain.append({
            "step": step,
            "action": "Hafıza Kontrolü",
            "detail": "Semantik hafızadan benzer geçmiş konuşmalar sorgulandı",
            "status": "done",
        })

        # 6. LLM yanıt üretimi
        step += 1
        word_count = len(response.split())
        chain.append({
            "step": step,
            "action": "LLM Yanıt Üretimi",
            "detail": f"{word_count} kelimelik yanıt üretildi ({module_source})",
            "status": "done",
        })

        # 7. Reflection (varsa)
        if reflection_data:
            step += 1
            ref_conf = reflection_data.get("confidence", 0)
            retried = reflection_data.get("should_retry", False)
            chain.append({
                "step": step,
                "action": "Kalite Kontrolü (Reflection)",
                "detail": f"Yanıt değerlendirildi: %{ref_conf:.0f} güven"
                         + (" — retry yapıldı" if retried else ""),
                "status": "done" if ref_conf >= 60 else "warning",
            })

        # 8. Risk kontrolü
        risk = self._assess_risk(query, response)
        step += 1
        chain.append({
            "step": step,
            "action": "Risk Değerlendirmesi",
            "detail": f"Risk: {risk['level']} ({risk['score']:.0%})"
                     + (" — onay gerekebilir" if risk["needs_approval"] else ""),
            "status": "warning" if risk["needs_approval"] else "done",
        })

        return chain

    # ══════════════════════════════════════════════════════
    # RİSK DEĞERLENDİRMESİ
    # ══════════════════════════════════════════════════════

    def _assess_risk(self, query: str, response: str) -> Dict:
        score = self._risk_score(query, response)
        if score < 0.3:
            level, color = "Düşük", "green"
        elif score < 0.6:
            level, color = "Orta", "yellow"
        else:
            level, color = "Yüksek", "red"
        return {
            "score": round(score, 2),
            "level": level,
            "color": color,
            "needs_approval": score >= 0.6,
        }

    def _risk_score(self, query: str, response: str) -> float:
        text = (query + " " + response).lower()
        high = sum(1 for k in RISK_KW_HIGH if k in text)
        mid = sum(1 for k in RISK_KW_MID if k in text)
        low = sum(1 for k in RISK_KW_LOW if k in text)
        score = (high * 0.25 + mid * 0.10 - low * 0.05)
        return max(0.0, min(1.0, score))

    # ══════════════════════════════════════════════════════
    # KARŞI-OLGUSAL ANALİZ
    # ══════════════════════════════════════════════════════

    def _generate_counterfactual(self, factors: list, risk: dict, mode: str) -> str:
        weakest = min(factors, key=lambda f: f["score"])
        strongest = max(factors, key=lambda f: f["score"])

        parts = []
        if weakest["score"] < 0.5:
            diff_pct = (0.8 - weakest["score"]) * weakest["weight"] * 100
            parts.append(
                f"'{weakest['name']}' faktörü %{weakest['score'] * 100:.0f}'den %80'e çıkarılsaydı, "
                f"toplam güven ~{diff_pct:.0f} puan artardı."
            )

        if not factors[1]["score"] >= 0.6:  # sources
            parts.append("RAG bilgi tabanına ilgili dokümanlar eklenirse kaynak güvenilirliği artacaktır.")

        if risk["needs_approval"]:
            parts.append("Sorgu daha az riskli içerik barındırsaydı, otomatik onay verilebilirdi.")

        if not parts:
            parts.append(
                f"En güçlü faktör '{strongest['name']}' (%{strongest['score'] * 100:.0f}). "
                f"Genel performans yeterli seviyede."
            )
        return " ".join(parts)

    # ══════════════════════════════════════════════════════
    # GEÇMİŞ KARŞILAŞTIRMA
    # ══════════════════════════════════════════════════════

    def _compare_with_history(self, query: str, current_conf: float, mode: str) -> Dict:
        """Mevcut sorguyu geçmiş sorgularla karşılaştır."""
        if not self._history:
            return {
                "has_history": False,
                "message": "İlk analiz — karşılaştırma verisi henüz yok",
            }

        # Aynı mod'daki geçmiş
        mode_history = [r for r in self._history if r.mode == mode]
        all_confs = [r.weighted_confidence for r in self._history]
        mode_confs = [r.weighted_confidence for r in mode_history] if mode_history else all_confs

        avg_all = sum(all_confs) / len(all_confs) if all_confs else 0
        avg_mode = sum(mode_confs) / len(mode_confs) if mode_confs else 0

        diff = current_conf - avg_mode
        if diff > 0.05:
            trend = "Ortalamanın üzerinde"
        elif diff < -0.05:
            trend = "Ortalamanın altında"
        else:
            trend = "Ortalama seviyede"

        return {
            "has_history": True,
            "total_past": len(all_confs),
            "mode_past": len(mode_confs),
            "avg_confidence_all": round(avg_all, 3),
            "avg_confidence_mode": round(avg_mode, 3),
            "current_vs_avg": round(diff, 3),
            "trend": trend,
        }

    # ══════════════════════════════════════════════════════
    # ÖNERİLER
    # ══════════════════════════════════════════════════════

    def _generate_recommendations(self, factors: list, risk: dict, conf: float, mode: str) -> List[str]:
        recs = []
        for f in factors:
            if f["score"] < 0.4:
                recs.append(f"⚠️ {f['name']} çok düşük (%{f['score'] * 100:.0f}) — acil iyileştirme gerekli")
            elif f["score"] < 0.6:
                recs.append(f"💡 {f['name']} orta seviye (%{f['score'] * 100:.0f}) — geliştirilebilir")

        if risk["needs_approval"]:
            recs.append("🔒 Yüksek riskli karar — insan onayı önerilir")

        if conf < 0.5:
            recs.append("📊 Genel güven düşük — ek veri veya kaynak gerekebilir")

        # Kaynak eksikliği
        source_factor = next((f for f in factors if f["key"] == "kaynak_güvenilirliği"), None)
        if source_factor and source_factor["score"] < 0.5:
            recs.append("📚 Bilgi tabanına (RAG) ilgili konuda doküman eklenmesi önerilir")

        if not recs:
            recs.append("✅ Tüm faktörler kabul edilebilir seviyede")

        return recs

    # ══════════════════════════════════════════════════════
    # İSTATİSTİK TOPLAMA
    # ══════════════════════════════════════════════════════

    def _record_stats(self, record: ExplanationRecord):
        """İstatistikleri güncelle ve DB'ye kaydet."""
        self._history.append(record)
        self._total_evaluations += 1
        self._confidence_sum += record.weighted_confidence
        self._risk_distribution[record.risk_level] = (
            self._risk_distribution.get(record.risk_level, 0) + 1
        )

        # Mod istatistikleri
        if record.mode not in self._mode_stats:
            self._mode_stats[record.mode] = {"count": 0, "conf_sum": 0.0}
        self._mode_stats[record.mode]["count"] += 1
        self._mode_stats[record.mode]["conf_sum"] += record.weighted_confidence

        if record.weighted_confidence >= 0.8:
            self._high_confidence_count += 1
        elif record.weighted_confidence < 0.5:
            self._low_confidence_count += 1

        # v4: Async DB kayıt — fire-and-forget
        if DB_AVAILABLE:
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(self._save_to_db(record))
                else:
                    asyncio.run(self._save_to_db(record))
            except RuntimeError:
                # No event loop — skip DB save silently
                pass
            except Exception as e:
                logger.debug("xai_db_save_skipped", error=str(e))

    async def _save_to_db(self, record: ExplanationRecord):
        """XAI kaydını PostgreSQL'e kaydet."""
        try:
            async with async_session_maker() as session:
                factors_data = []
                for f in record.factors:
                    factors_data.append({
                        "name": f.get("name", ""),
                        "key": f.get("key", ""),
                        "score": round(f.get("score", 0), 4),
                        "weight": round(f.get("weight", 0), 4),
                    })

                db_record = XaiRecord(
                    query_hash=record.query_hash,
                    query_preview=record.query_preview[:200],
                    mode=record.mode,
                    module_source=record.module_source,
                    weighted_confidence=round(record.weighted_confidence, 4),
                    risk_level=record.risk_level,
                    risk_score=round(record.risk_score, 4),
                    reasoning_steps=record.reasoning_steps,
                    sources_used=record.sources_used,
                    rag_hit=record.rag_hit,
                    web_searched=record.web_searched,
                    had_reflection=record.had_reflection,
                    word_count=record.word_count,
                    factors=factors_data,
                    counterfactual=record.counterfactual[:500] if record.counterfactual else None,
                )
                session.add(db_record)
                await session.commit()
                logger.debug("xai_saved_to_db", query_hash=record.query_hash)
        except Exception as e:
            logger.debug("xai_db_save_failed", error=str(e))

    # ══════════════════════════════════════════════════════
    # TOKEN ATTRIBUTION — SHAP-Like Perturbation Analizi
    # ══════════════════════════════════════════════════════

    def _compute_token_attribution(
        self, query: str, response: str, mode: str,
        sources: list, rag_docs: Optional[list],
        web_searched: bool, reflection_data: Optional[dict],
    ) -> List[Dict]:
        """
        Perturbation-based token attribution:
        Her query kelimesini sırayla çıkararak faktör skorlarındaki
        değişimi ölçer. SHAP benzeri local explanation sağlar.
        """
        query_words = re.findall(r'\b\w{3,}\b', query)
        if not query_words or len(query_words) > 30:
            # Çok uzun sorgularda top 15 unique kelimeyi al
            seen = set()
            unique = []
            for w in query_words:
                wl = w.lower()
                if wl not in seen:
                    seen.add(wl)
                    unique.append(w)
                if len(unique) >= 15:
                    break
            query_words = unique if unique else query_words[:15]

        if not query_words:
            return []

        # Temel skor — tüm kelimelerle
        weights = MODULE_WEIGHT_PROFILES.get(mode, BASE_FACTOR_WEIGHTS)
        base_factors = self._analyze_factors(
            query=query, response=response, mode=mode, confidence=0.5,
            sources=sources, rag_docs=rag_docs, web_searched=web_searched,
            reflection_data=reflection_data, weights=weights,
        )
        base_score = sum(f["score"] * f["weight"] for f in base_factors)

        # Her kelimeyi çıkararak perturbation
        attributions = []
        for word in query_words:
            # Kelimeyi çıkar
            perturbed_query = re.sub(r'\b' + re.escape(word) + r'\b', '', query, count=1).strip()
            if not perturbed_query:
                continue

            # Pertürbe skor
            perturbed_factors = self._analyze_factors(
                query=perturbed_query, response=response, mode=mode, confidence=0.5,
                sources=sources, rag_docs=rag_docs, web_searched=web_searched,
                reflection_data=reflection_data, weights=weights,
            )
            perturbed_score = sum(f["score"] * f["weight"] for f in perturbed_factors)

            # Etki = çıkarıldığında ne kadar değişti
            impact = base_score - perturbed_score  # Pozitif = kelime katkı yapıyor
            attributions.append({
                "token": word,
                "impact": round(impact, 4),
                "direction": "pozitif" if impact > 0 else ("negatif" if impact < 0 else "nötr"),
                "importance": round(abs(impact) * 100, 1),  # %importance
            })

        # Etki büyüklüğüne göre sırala
        attributions.sort(key=lambda x: abs(x["impact"]), reverse=True)
        return attributions[:15]  # Top 15

    # ══════════════════════════════════════════════════════
    # ATTENTION HEATMAP — Query-Response Kelime Etkileşimi
    # ══════════════════════════════════════════════════════

    def _compute_attention_heatmap(self, query: str, response: str) -> Dict:
        """
        Query ve response kelimeleri arasında çapraz dikkat matrisi oluşturur.
        Co-occurrence + TF-IDF benzeri ağırlıklandırma ile pseudo-attention.
        """
        q_words = list(dict.fromkeys(re.findall(r'\b\w{3,}\b', query.lower())))[:12]
        r_words_raw = re.findall(r'\b\w{3,}\b', response.lower())

        if not q_words:
            return {"query_tokens": [], "response_tokens": [], "matrix": []}

        # Response'da en sık geçen top kelimeler (stop words hariç)
        stop = {"bir", "bu", "ve", "ile", "için", "olarak", "daha", "olan",
                "gibi", "çok", "var", "den", "dan", "ise", "ama", "hem", "her",
                "kadar", "sonra", "önce"}
        r_freq: Dict[str, int] = {}
        for w in r_words_raw:
            if w not in stop and len(w) >= 3:
                r_freq[w] = r_freq.get(w, 0) + 1

        # Top 10 response kelimesi
        top_r = sorted(r_freq.items(), key=lambda x: -x[1])[:10]
        r_tokens = [w for w, _ in top_r]

        if not r_tokens:
            return {"query_tokens": q_words, "response_tokens": [], "matrix": []}

        # Attention matrisi: co-occurrence tabanlı
        total_r_words = max(len(r_words_raw), 1)
        matrix = []
        for qw in q_words:
            row = []
            for rw in r_tokens:
                # Proximity-based co-occurrence: Her bir response kelimesi ile
                # query kelimesinin aynı cümlede geçme oranı
                co_count = 0
                sentences = re.split(r'[.!?;\n]', response.lower())
                for sent in sentences:
                    if qw in sent and rw in sent:
                        co_count += 1
                # Normalize (0-1)
                attention = min(1.0, co_count * 0.3 + (0.5 if qw == rw else 0))
                # TF boost
                tf_boost = min(0.3, r_freq.get(rw, 0) / total_r_words * 5)
                attention = min(1.0, attention + tf_boost)
                row.append(round(attention, 2))
            matrix.append(row)

        return {
            "query_tokens": q_words,
            "response_tokens": r_tokens,
            "matrix": matrix,
        }

    # ══════════════════════════════════════════════════════
    # KULLANICI GERİ BİLDİRİM & KALİBRASYON
    # ══════════════════════════════════════════════════════

    def submit_feedback(
        self,
        query_hash: str,
        user_rating: float,
        factor_overrides: Optional[Dict[str, float]] = None,
        comment: str = "",
    ) -> Dict:
        """
        Kullanıcı geri bildirimi alır ve kalibrasyon ağırlıklarını günceller.
        
        user_rating: 1-5 arası (1=çok kötü, 5=mükemmel)
        factor_overrides: {"yanıt_kalitesi": 0.9, ...} — kullanıcının düzeltmeleri
        """
        user_rating = max(1.0, min(5.0, float(user_rating)))

        # İlgili kaydı bul
        target_record = None
        for r in reversed(list(self._history)):
            if r.query_hash == query_hash:
                target_record = r
                break

        fb = FeedbackRecord(
            timestamp=time.time(),
            query_hash=query_hash,
            mode=target_record.mode if target_record else "",
            xai_confidence=target_record.weighted_confidence if target_record else 0,
            user_rating=user_rating,
            factor_overrides=factor_overrides or {},
        )
        self._feedback_history.append(fb)
        self._total_feedback += 1
        self._feedback_sum += user_rating

        # Kalibrasyon: XAI skoru ile kullanıcı puanı arasındaki farkı hesapla
        if target_record:
            target_record.user_rating = user_rating
            xai_norm = target_record.weighted_confidence  # 0-1
            user_norm = (user_rating - 1) / 4.0  # 1-5 → 0-1
            gap = user_norm - xai_norm  # Pozitif = XAI çok düşük vermiş

            # Faktör bazlı kalibrasyon
            if factor_overrides:
                for factor_key, user_score in factor_overrides.items():
                    if factor_key in BASE_FACTOR_WEIGHTS:
                        # Mevcut delta'ya ekle (exponential moving average)
                        current_delta = self._calibration_weights.get(factor_key, 0)
                        user_s_norm = max(0, min(1, user_score))
                        # Orijinal skoru bul
                        orig_score = 0.5
                        for f in target_record.factors:
                            if f.get("key") == factor_key:
                                orig_score = f["score"]
                                break
                        factor_gap = user_s_norm - orig_score
                        # EMA ile güncelle (alpha=0.3)
                        new_delta = current_delta * 0.7 + factor_gap * 0.3
                        self._calibration_weights[factor_key] = round(new_delta, 4)
            else:
                # Genel kalibrasyon — gap'i tüm faktörlere dağıt
                per_factor = gap * 0.1  # Yavaş güncelleme
                for factor_key in BASE_FACTOR_WEIGHTS:
                    current = self._calibration_weights.get(factor_key, 0)
                    self._calibration_weights[factor_key] = round(
                        current * 0.7 + per_factor * 0.3, 4
                    )

            self._calibration_log.append({
                "timestamp": time.time(),
                "query_hash": query_hash,
                "gap": round(gap, 4),
                "user_rating": user_rating,
                "xai_confidence": round(xai_norm, 3),
                "adjustments": dict(self._calibration_weights),
            })

        avg_rating = self._feedback_sum / self._total_feedback if self._total_feedback > 0 else 0
        return {
            "accepted": True,
            "feedback_id": f"fb_{int(time.time())}",
            "total_feedback": self._total_feedback,
            "avg_user_rating": round(avg_rating, 2),
            "calibration_active": bool(self._calibration_weights),
            "calibration_adjustments": dict(self._calibration_weights),
            "message": f"Geri bildirim kaydedildi. Kalibrasyon {'güncellendi' if self._calibration_weights else 'henüz aktif değil'}.",
        }

    def _apply_calibration(self, weights: Dict[str, float]) -> Dict[str, float]:
        """Kalibrasyon delta'larını faktör ağırlıklarına uygula."""
        if not self._calibration_weights:
            return weights

        calibrated = dict(weights)
        for key, delta in self._calibration_weights.items():
            if key in calibrated:
                # Score'a eklenir, weight'e değil — ama weight'i bias olarak shift edebiliriz
                calibrated[key] = max(0.05, min(0.40, calibrated[key] + delta * 0.5))

        # Normalize — toplamı 1.0 olsun
        total = sum(calibrated.values())
        if total > 0:
            calibrated = {k: round(v / total, 4) for k, v in calibrated.items()}

        return calibrated

    def get_calibration_status(self) -> Dict:
        """Kalibrasyon durumu ve geçmişi."""
        avg_rating = self._feedback_sum / self._total_feedback if self._total_feedback > 0 else 0

        # Kalibrasyon etkinliği
        alignment_scores = []
        for fb in self._feedback_history:
            if fb.xai_confidence > 0:
                user_norm = (fb.user_rating - 1) / 4.0
                alignment = 1.0 - abs(user_norm - fb.xai_confidence)
                alignment_scores.append(alignment)

        avg_alignment = sum(alignment_scores) / len(alignment_scores) if alignment_scores else 0

        return {
            "total_feedback": self._total_feedback,
            "avg_user_rating": round(avg_rating, 2),
            "avg_alignment": round(avg_alignment, 3),
            "alignment_pct": round(avg_alignment * 100, 1),
            "calibration_active": bool(self._calibration_weights),
            "weight_adjustments": dict(self._calibration_weights),
            "recent_calibrations": self._calibration_log[-5:],
        }

    # ══════════════════════════════════════════════════════
    # DASHBOARD — Gerçek İstatistikler v3.0
    # ══════════════════════════════════════════════════════

    def get_dashboard(self) -> Dict:
        """XAI modül durumu + gerçek istatistikler + kalibrasyon."""
        avg_conf = (self._confidence_sum / self._total_evaluations) if self._total_evaluations > 0 else 0

        # Son 20 trend
        recent = list(self._history)[-20:]
        recent_confs = [r.weighted_confidence for r in recent]
        if len(recent_confs) >= 10:
            first_half = sum(recent_confs[:len(recent_confs)//2]) / (len(recent_confs)//2)
            second_half = sum(recent_confs[len(recent_confs)//2:]) / (len(recent_confs) - len(recent_confs)//2)
            if second_half - first_half > 0.03:
                trend = "yükseliyor"
            elif first_half - second_half > 0.03:
                trend = "düşüyor"
            else:
                trend = "stabil"
        else:
            trend = "yeterli_veri_yok"

        # Mod bazlı istatistikler
        mode_breakdown = {}
        for mode, stats in self._mode_stats.items():
            mode_breakdown[mode] = {
                "count": stats["count"],
                "avg_confidence": round(stats["conf_sum"] / stats["count"], 3) if stats["count"] > 0 else 0,
            }

        # Faktörler
        factors = list(BASE_FACTOR_WEIGHTS.keys())

        # Son uyarılar
        recent_warnings = []
        for r in reversed(list(self._history)[-10:]):
            if r.weighted_confidence < 0.5:
                recent_warnings.append({
                    "query": r.query_preview,
                    "confidence": round(r.weighted_confidence, 3),
                    "mode": r.mode,
                    "risk": r.risk_level,
                })

        # Güven skoru dağılımı (histogram)
        conf_distribution = {"0-20": 0, "20-40": 0, "40-60": 0, "60-80": 0, "80-100": 0}
        for r in self._history:
            pct = r.weighted_confidence * 100
            if pct < 20: conf_distribution["0-20"] += 1
            elif pct < 40: conf_distribution["20-40"] += 1
            elif pct < 60: conf_distribution["40-60"] += 1
            elif pct < 80: conf_distribution["60-80"] += 1
            else: conf_distribution["80-100"] += 1

        # Güven trend verisi (grafik için)
        confidence_trend_data = []
        for r in list(self._history)[-30:]:
            confidence_trend_data.append({
                "timestamp": r.timestamp,
                "confidence": round(r.weighted_confidence * 100, 1),
                "mode": r.mode,
                "risk": r.risk_level,
            })

        # Ortalama faktör skorları
        avg_factor_scores = {}
        if self._history:
            factor_sums: Dict[str, float] = {}
            factor_counts: Dict[str, int] = {}
            for r in self._history:
                for f in r.factors:
                    key = f.get("key", f.get("name", "?"))
                    factor_sums[key] = factor_sums.get(key, 0) + f["score"]
                    factor_counts[key] = factor_counts.get(key, 0) + 1
            for key in factor_sums:
                avg_factor_scores[key] = round(
                    factor_sums[key] / factor_counts[key] * 100, 1
                )

        # Kalibrasyon durumu
        calib = self.get_calibration_status()

        return {
            "module": "Explainability (XAI)",
            "version": "4.0.0",
            "factors": factors,
            "factor_count": len(factors),
            "capabilities": [
                "Faktör ağırlıklandırma",
                "Akıl yürütme zinciri",
                "Risk değerlendirmesi",
                "Karşı-olgusal analiz",
                "Toplu açıklama",
                "Güven skoru hesaplama",
                "Geçmiş karşılaştırma",
                "Modül bazlı adaptasyon",
                "İstatistik toplama",
                "SHAP-Like Token Attribution",
                "Attention Heatmap",
                "Kullanıcı Geri Bildirim Kalibrasyon",
                "TF-IDF Bağlam Benzerliği",
                "LLM Bilgi Kalitesi Analizi",
                "PostgreSQL Kalıcı Kayıt",
                "Sohbet Modu Gerçek Analiz",
            ],
            "stats": {
                "total_evaluations": self._total_evaluations,
                "avg_confidence": round(avg_conf, 3),
                "avg_confidence_pct": round(avg_conf * 100, 1),
                "confidence_trend": trend,
                "high_confidence_count": self._high_confidence_count,
                "low_confidence_count": self._low_confidence_count,
                "risk_distribution": dict(self._risk_distribution),
                "mode_breakdown": mode_breakdown,
                "recent_warnings": recent_warnings[:5],
                "conf_distribution": conf_distribution,
                "confidence_trend_data": confidence_trend_data,
                "avg_factor_scores": avg_factor_scores,
            },
            "calibration": calib,
        }

    # ── Toplu Açıklama ──

    def explain_batch(self, decisions: List[Dict]) -> Dict:
        """Birden fazla kararı toplu olarak açıkla."""
        results = []
        for d in decisions:
            exp = self.explain(
                query=d.get("query", ""),
                response=d.get("response", ""),
                mode=d.get("mode", "Sohbet"),
                confidence=d.get("confidence", 0.0),
                sources=d.get("sources"),
                rag_docs=d.get("rag_docs"),
                web_searched=d.get("web_searched", False),
                reflection_data=d.get("reflection_data"),
                module_source=d.get("module_source", "unknown"),
            )
            results.append(exp)

        avg_conf = sum(r["confidence"] for r in results) / len(results) if results else 0
        risk_dist = {"Düşük": 0, "Orta": 0, "Yüksek": 0}
        for r in results:
            level = r["risk_assessment"]["level"]
            risk_dist[level] += 1

        return {
            "total": len(results),
            "average_confidence": round(avg_conf, 3),
            "risk_distribution": risk_dist,
            "explanations": results,
        }

    # ── Yardımcılar ──

    def _confidence_label(self, conf: float) -> str:
        if conf >= 0.8: return "Yüksek"
        if conf >= 0.6: return "Orta"
        if conf >= 0.4: return "Düşük"
        return "Çok Düşük"

    def _build_summary(self, mode: str, module: str, conf: float, risk: dict) -> str:
        return (
            f"Bu yanıt {module} modülü tarafından {mode} modunda üretilmiştir. "
            f"Toplam güven: %{conf * 100:.0f} ({self._confidence_label(conf)}). "
            f"Risk: {risk['level']}."
        )

    @staticmethod
    def _hash_query(query: str) -> str:
        """Basit hash — gizlilik için tam query saklanmaz."""
        h = 0
        for c in query.lower():
            h = (h * 31 + ord(c)) & 0xFFFFFFFF
        return f"q_{h:08x}"


# ── Singleton ───────────────────────────────────────────────────
decision_explainer = DecisionExplainer()
