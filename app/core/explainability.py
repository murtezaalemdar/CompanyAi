"""Explainability (XAI) — Açıklanabilir Yapay Zeka Modülü

Mevcut reflection.py + risk_analyzer.py'ı güçlendirir:
- Karar açıklama zinciri (reasoning chain)
- Faktör ağırlıklandırma
- Karşı-olgusal analiz (counterfactual)
- Güven skoru dağılımı
- Kullanıcı dostu özet oluşturma
"""

import json
import re
from typing import Optional, List, Dict, Any
from pathlib import Path
from datetime import datetime
import structlog

logger = structlog.get_logger()


class DecisionExplainer:
    """AI kararlarını açıklayan modül."""

    # ── Faktör ağırlıkları ──────────────────────────────────────
    FACTOR_WEIGHTS = {
        "veri_kalitesi":    0.20,
        "model_güveni":     0.25,
        "geçmiş_doğruluk": 0.15,
        "risk_seviyesi":    0.20,
        "bağlam_uyumu":     0.10,
        "zaman_tutarlılığı": 0.10,
    }

    RISK_KEYWORDS = {
        "yüksek": ["fire", "zarar", "kayıp", "tehlike", "kriz", "acil", "düşüş"],
        "orta":   ["risk", "dikkat", "kontrol", "izleme", "sapma"],
        "düşük":  ["normal", "stabil", "artış", "olumlu", "iyileşme"],
    }

    def explain_decision(
        self,
        query: str,
        response: str,
        confidence: float = 0.0,
        context_data: Optional[Dict] = None,
        module_source: str = "unknown",
    ) -> Dict:
        """Bir AI kararının tam açıklamasını üret.

        Returns:
            {
                "summary": "...",
                "confidence": 0.82,
                "factors": [...],
                "reasoning_chain": [...],
                "risk_assessment": {...},
                "counterfactual": "...",
                "recommendations": [...],
            }
        """
        ctx = context_data or {}

        # 1. Faktör analizi
        factors = self._analyze_factors(query, response, confidence, ctx)

        # 2. Akıl yürütme zinciri
        chain = self._build_reasoning_chain(query, response, module_source, ctx)

        # 3. Risk değerlendirmesi
        risk = self._assess_risk(query, response)

        # 4. Karşı-olgusal
        counterfactual = self._generate_counterfactual(query, factors, risk)

        # 5. Öneriler
        recommendations = self._generate_recommendations(factors, risk, confidence)

        # 6. Toplam güven
        weighted_conf = self._calculate_weighted_confidence(factors)

        # 7. Özet
        summary = self._build_summary(query, module_source, weighted_conf, risk)

        return {
            "summary": summary,
            "confidence": round(weighted_conf, 3),
            "confidence_label": self._confidence_label(weighted_conf),
            "factors": factors,
            "reasoning_chain": chain,
            "risk_assessment": risk,
            "counterfactual": counterfactual,
            "recommendations": recommendations,
            "module_source": module_source,
            "timestamp": datetime.now().isoformat(),
        }

    # ── Faktör Analizi ──────────────────────────────────────────

    def _analyze_factors(
        self, query: str, response: str, confidence: float, ctx: Dict
    ) -> List[Dict]:
        """Her karar faktörünü ayrı ayrı değerlendir."""
        factors = []

        # 1. Veri kalitesi
        data_quality = ctx.get("data_quality", 0.7)
        factors.append({
            "name": "Veri Kalitesi",
            "score": round(data_quality, 2),
            "weight": self.FACTOR_WEIGHTS["veri_kalitesi"],
            "explanation": self._data_quality_text(data_quality),
        })

        # 2. Model güveni
        model_conf = confidence if confidence > 0 else 0.5
        factors.append({
            "name": "Model Güveni",
            "score": round(model_conf, 2),
            "weight": self.FACTOR_WEIGHTS["model_güveni"],
            "explanation": f"LLM yanıt güveni: {model_conf:.0%}",
        })

        # 3. Geçmiş doğruluk
        hist_accuracy = ctx.get("historical_accuracy", 0.75)
        factors.append({
            "name": "Geçmiş Doğruluk",
            "score": round(hist_accuracy, 2),
            "weight": self.FACTOR_WEIGHTS["geçmiş_doğruluk"],
            "explanation": f"Benzer sorulardaki geçmiş doğruluk oranı: {hist_accuracy:.0%}",
        })

        # 4. Risk seviyesi
        risk_score = self._risk_score(query, response)
        factors.append({
            "name": "Risk Değerlendirmesi",
            "score": round(1.0 - risk_score, 2),  # düşük risk = yüksek skor
            "weight": self.FACTOR_WEIGHTS["risk_seviyesi"],
            "explanation": f"Risk seviyesi: {risk_score:.0%} — "
                          + ("Düşük" if risk_score < 0.3 else "Orta" if risk_score < 0.6 else "Yüksek"),
        })

        # 5. Bağlam uyumu
        context_match = ctx.get("context_relevance", 0.7)
        factors.append({
            "name": "Bağlam Uyumu",
            "score": round(context_match, 2),
            "weight": self.FACTOR_WEIGHTS["bağlam_uyumu"],
            "explanation": f"Soru-yanıt bağlam uyumu: {context_match:.0%}",
        })

        # 6. Zaman tutarlılığı
        time_cons = ctx.get("time_consistency", 0.8)
        factors.append({
            "name": "Zaman Tutarlılığı",
            "score": round(time_cons, 2),
            "weight": self.FACTOR_WEIGHTS["zaman_tutarlılığı"],
            "explanation": f"Önceki yanıtlarla tutarlılık: {time_cons:.0%}",
        })

        return factors

    def _data_quality_text(self, score: float) -> str:
        if score >= 0.8:
            return "Yüksek kaliteli, güncel veriler kullanıldı"
        if score >= 0.5:
            return "Orta kaliteli veriler — bazı eksiklikler olabilir"
        return "Düşük kaliteli/eksik veriler — sonuçlar dikkatle değerlendirilmeli"

    # ── Akıl Yürütme Zinciri ────────────────────────────────────

    def _build_reasoning_chain(
        self, query: str, response: str, module: str, ctx: Dict
    ) -> List[Dict]:
        """Kararın adım adım açıklaması."""
        chain = []

        # Adım 1: Sorgu analizi
        chain.append({
            "step": 1,
            "action": "Sorgu Analizi",
            "detail": f"Kullanıcı sorusu alındı ({len(query)} karakter). "
                     f"Modül: {module}",
        })

        # Adım 2: Veri toplama
        sources = ctx.get("sources", [])
        chain.append({
            "step": 2,
            "action": "Veri Toplama",
            "detail": f"{len(sources)} veri kaynağından bilgi toplandı"
                     if sources else "İç bilgi tabanı ve genel model bilgisi kullanıldı",
        })

        # Adım 3: Analiz
        chain.append({
            "step": 3,
            "action": "Analiz & İşleme",
            "detail": f"Sorgu {module} modülü ile işlendi. "
                     f"Yanıt uzunluğu: {len(response)} karakter.",
        })

        # Adım 4: Risk kontrolü
        risk = self._risk_score(query, response)
        chain.append({
            "step": 4,
            "action": "Risk Kontrolü",
            "detail": f"Risk seviyesi hesaplandı: {risk:.0%}. "
                     + ("Onay gerekmedi." if risk < 0.5 else "İnsan onayı gerekebilir."),
        })

        # Adım 5: Yanıt oluşturma
        chain.append({
            "step": 5,
            "action": "Yanıt Oluşturma",
            "detail": "Tüm faktörler değerlendirilerek nihai yanıt oluşturuldu.",
        })

        return chain

    # ── Risk Skoru ──────────────────────────────────────────────

    def _risk_score(self, query: str, response: str) -> float:
        """Basit kural bazlı risk skoru (0-1)."""
        text = (query + " " + response).lower()
        high_count = sum(1 for k in self.RISK_KEYWORDS["yüksek"] if k in text)
        mid_count  = sum(1 for k in self.RISK_KEYWORDS["orta"]   if k in text)
        low_count  = sum(1 for k in self.RISK_KEYWORDS["düşük"]  if k in text)

        score = (high_count * 0.3 + mid_count * 0.1 - low_count * 0.05)
        return max(0.0, min(1.0, score))

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

    # ── Karşı-Olgusal ──────────────────────────────────────────

    def _generate_counterfactual(
        self, query: str, factors: List[Dict], risk: Dict
    ) -> str:
        """Farklı koşullarda sonucun nasıl değişeceğini açıkla."""
        weakest = min(factors, key=lambda f: f["score"])
        strongest = max(factors, key=lambda f: f["score"])

        parts = []
        if weakest["score"] < 0.5:
            parts.append(
                f"Eğer '{weakest['name']}' faktörü daha yüksek olsaydı "
                f"(mevcut: {weakest['score']:.0%}), güven skoru önemli ölçüde artardı."
            )
        if risk["score"] > 0.5:
            parts.append(
                "Sorgu daha az riskli içerik barındırsaydı, "
                "otomatik onay verilebilirdi."
            )
        if not parts:
            parts.append(
                f"En güçlü faktör '{strongest['name']}' ({strongest['score']:.0%}). "
                f"Tüm faktörler yeterli seviyede."
            )

        return " ".join(parts)

    # ── Öneriler ────────────────────────────────────────────────

    def _generate_recommendations(
        self, factors: List[Dict], risk: Dict, confidence: float
    ) -> List[str]:
        recs = []
        for f in factors:
            if f["score"] < 0.5:
                recs.append(f"⚠️ {f['name']} düşük ({f['score']:.0%}) — iyileştirme önerilir")

        if risk["needs_approval"]:
            recs.append("🔒 Yüksek riskli karar — insan onayı gerekli")

        if confidence < 0.5:
            recs.append("📊 Model güveni düşük — ek veri veya alternatif model deneyin")

        if not recs:
            recs.append("✅ Tüm faktörler kabul edilebilir seviyede")

        return recs

    # ── Güven Hesaplama ─────────────────────────────────────────

    def _calculate_weighted_confidence(self, factors: List[Dict]) -> float:
        total = sum(f["score"] * f["weight"] for f in factors)
        return max(0.0, min(1.0, total))

    def _confidence_label(self, conf: float) -> str:
        if conf >= 0.8:
            return "Yüksek"
        if conf >= 0.6:
            return "Orta"
        if conf >= 0.4:
            return "Düşük"
        return "Çok Düşük"

    def _build_summary(
        self, query: str, module: str, confidence: float, risk: Dict
    ) -> str:
        return (
            f"Bu yanıt {module} modülü tarafından üretilmiştir. "
            f"Toplam güven skoru: {confidence:.0%} ({self._confidence_label(confidence)}). "
            f"Risk seviyesi: {risk['level']}."
        )

    # ── Toplu Açıklama ──────────────────────────────────────────

    def explain_batch(self, decisions: List[Dict]) -> Dict:
        """Birden fazla kararı toplu olarak açıkla."""
        results = []
        for d in decisions:
            exp = self.explain_decision(
                query=d.get("query", ""),
                response=d.get("response", ""),
                confidence=d.get("confidence", 0.0),
                context_data=d.get("context_data"),
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

    def get_dashboard(self) -> Dict:
        """XAI modül durumu."""
        return {
            "module": "Explainability (XAI)",
            "version": "1.0.0",
            "factors": list(self.FACTOR_WEIGHTS.keys()),
            "factor_count": len(self.FACTOR_WEIGHTS),
            "capabilities": [
                "Faktör ağırlıklandırma",
                "Akıl yürütme zinciri",
                "Risk değerlendirmesi",
                "Karşı-olgusal analiz",
                "Toplu açıklama",
                "Güven skoru hesaplama",
            ],
        }


# ── Singleton ───────────────────────────────────────────────────
decision_explainer = DecisionExplainer()
