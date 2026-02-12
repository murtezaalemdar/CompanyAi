"""Reflection Layer — LLM Yanıt Kalite Kontrol ve Self-Evaluation

Enterprise Tier-0 seviye reflection:
- 5 kriterli kalite değerlendirmesi
- Dinamik confidence score (0-100)
- Düşük güvenli yanıtlarda otomatik retry
- Hallucination detection (sayısal tutarsızlık)
"""

import re
import json
import structlog
from typing import Optional

logger = structlog.get_logger()

# ══════════════════════════════════════════════════════════════
# 1. DEĞERLENDİRME KRİTERLERİ
# ══════════════════════════════════════════════════════════════

EVALUATION_CRITERIA = {
    "data_accuracy": {
        "name": "Veri Doğruluğu",
        "weight": 0.25,
        "checks": [
            "Sayısal değerler tutarlı mı?",
            "Birimler doğru mu (₺, %, kg)?",
            "Toplam/ortalama hesapları doğru mu?",
        ],
    },
    "logical_consistency": {
        "name": "Mantıksal Tutarlılık",
        "weight": 0.20,
        "checks": [
            "Sonuçlar öncülleri ile tutarlı mı?",
            "Çelişkili ifadeler var mı?",
            "Neden-sonuç ilişkisi doğru mu?",
        ],
    },
    "financial_reasoning": {
        "name": "Finansal Akıl Yürütme",
        "weight": 0.20,
        "checks": [
            "Finansal etkiler somut hesaplanmış mı?",
            "Maliyet/gelir projeksiyonları mantıklı mı?",
            "Risk-getiri dengesi değerlendirilmiş mi?",
        ],
    },
    "risk_clarity": {
        "name": "Risk Netliği",
        "weight": 0.15,
        "checks": [
            "Riskler belirlenmiş mi?",
            "Risk seviyesi (Düşük/Orta/Yüksek/Kritik) ifade edilmiş mi?",
            "Risk azaltma önerileri var mı?",
        ],
    },
    "strategic_depth": {
        "name": "Stratejik Derinlik",
        "weight": 0.20,
        "checks": [
            "Kısa/orta/uzun vadeli perspektif var mı?",
            "Somut aksiyon önerileri var mı?",
            "Alternatif senaryolar düşünülmüş mü?",
        ],
    },
}

# Otomatik yeniden analiz eşiği
AUTO_REANALYZE_THRESHOLD = 60
MAX_RETRY_COUNT = 1  # En fazla 1 kez retry (toplam 2 deneme)


# ══════════════════════════════════════════════════════════════
# 2. HIZLI DEĞERLENDİRME — LLM KULLANMADAN
# ══════════════════════════════════════════════════════════════

def quick_evaluate(answer: str, question: str, mode: str = "Sohbet") -> dict:
    """LLM kullanmadan hızlı kalite değerlendirmesi yap.
    
    Args:
        answer: LLM'in ürettiği yanıt
        question: Kullanıcının sorusu
        mode: Yanıt modu (Sohbet, Analiz, Rapor vb.)
    
    Returns:
        {
            "confidence": 0-100,
            "criteria_scores": {...},
            "issues": [...],
            "pass": True/False,
            "suggestions": [...]
        }
    """
    scores = {}
    issues = []
    suggestions = []
    
    # ── Veri Doğruluğu ──
    data_score = _check_data_accuracy(answer, question)
    scores["data_accuracy"] = data_score
    if data_score < 50:
        issues.append("Sayısal veri yetersiz veya tutarsız")
        suggestions.append("Yanıtta somut sayısal veriler kullan")
    
    # ── Mantıksal Tutarlılık ──
    logic_score = _check_logical_consistency(answer)
    scores["logical_consistency"] = logic_score
    if logic_score < 50:
        issues.append("Yanıtta çelişkili ifadeler olabilir")
        suggestions.append("Neden-sonuç ilişkisini güçlendir")
    
    # ── Finansal Akıl Yürütme ──
    financial_score = _check_financial_reasoning(answer, mode)
    scores["financial_reasoning"] = financial_score
    if financial_score < 50 and mode in ("Analiz", "Rapor", "Öneri"):
        issues.append("Finansal etki hesabı eksik")
        suggestions.append("₺ cinsinden maliyet/gelir etkisi ekle")
    
    # ── Risk Netliği ──
    risk_score = _check_risk_clarity(answer, mode)
    scores["risk_clarity"] = risk_score
    if risk_score < 50 and mode in ("Analiz", "Rapor", "Acil"):
        issues.append("Risk değerlendirmesi yetersiz")
        suggestions.append("Risk seviye ve azaltma öneri ekle")
    
    # ── Stratejik Derinlik ──
    strategic_score = _check_strategic_depth(answer, mode)
    scores["strategic_depth"] = strategic_score
    if strategic_score < 50 and mode in ("Analiz", "Rapor", "Öneri"):
        issues.append("Stratejik derinlik eksik")
        suggestions.append("Kısa/orta/uzun vade önerileri ekle")
    
    # ── Hallucination Check ──
    hallucination_issues = _check_hallucination(answer, question)
    if hallucination_issues:
        issues.extend(hallucination_issues)
        for key in scores:
            scores[key] = max(20, scores[key] - 20)
    
    # ── Final Confidence Hesaplama ──
    weighted_score = sum(
        scores[key] * EVALUATION_CRITERIA[key]["weight"]
        for key in scores
    )
    
    # Mod bazlı ayarlama — Sohbet modunda criteria daha yumuşak
    if mode == "Sohbet":
        weighted_score = min(95, weighted_score + 25)
    elif mode == "Bilgi":
        weighted_score = min(95, weighted_score + 15)
    
    # Yanıt uzunluğu bonusu/cezası
    word_count = len(answer.split())
    if mode in ("Analiz", "Rapor") and word_count < 50:
        weighted_score = max(30, weighted_score - 15)
        issues.append("Yanıt çok kısa, analiz derinliği yetersiz")
    elif word_count > 30:
        weighted_score = min(100, weighted_score + 5)
    
    confidence = round(weighted_score, 1)
    passed = confidence >= AUTO_REANALYZE_THRESHOLD
    
    return {
        "confidence": confidence,
        "criteria_scores": {
            EVALUATION_CRITERIA[k]["name"]: round(v, 1)
            for k, v in scores.items()
        },
        "issues": issues,
        "pass": passed,
        "suggestions": suggestions,
        "should_retry": not passed and mode in ("Analiz", "Rapor", "Öneri", "Acil"),
    }


def _check_data_accuracy(answer: str, question: str) -> float:
    """Sayısal veri doğruluğu kontrolü."""
    score = 60.0  # Başlangıç
    
    # Sayı var mı?
    numbers = re.findall(r'\d+[.,]?\d*', answer)
    if numbers:
        score += 15
    
    # Birim var mı? (₺, %, kg, m, adet, gün, saat)
    units = re.findall(r'[₺$€%]|(?:kg|ton|metre|m²|adet|gün|saat|hafta|ay|yıl)', answer)
    if units:
        score += 10
    
    # Tablo var mı?
    if '|' in answer and '-' in answer:
        score += 10
    
    # "Bilmiyorum" / "kesin değil" dürüstlüğü
    if re.search(r'(kesin\s*bilgim\s*yok|tahmin|yaklaşık|net\s*değil)', answer, re.I):
        score += 5  # Dürüstlük ödülü
    
    return min(100, score)


def _check_logical_consistency(answer: str) -> float:
    """Mantıksal tutarlılık kontrolü."""
    score = 70.0
    
    # Çelişki belirteçleri
    contradictions = re.findall(
        r'(ancak|fakat|bununla birlikte|öte yandan|aksine|tam tersine)',
        answer, re.I
    )
    # Çelişki normal olabilir ama çok fazlası sorun
    if len(contradictions) > 3:
        score -= 10
    
    # Sonuç / tavsiye var mı?
    if re.search(r'(sonuç|özet|tavsiye|öneri|sonuç\s*olarak|özetle)', answer, re.I):
        score += 15
    
    # Neden-sonuç bağlantısı var mı?
    if re.search(r'(çünkü|nedeniyle|dolayı|sonucunda|bu\s*nedenle|bu\s*yüzden)', answer, re.I):
        score += 10
    
    return min(100, score)


def _check_financial_reasoning(answer: str, mode: str) -> float:
    """Finansal akıl yürütme kalitesi."""
    if mode == "Sohbet":
        return 80.0  # Sohbette finansal reasoning beklenmez
    
    score = 50.0
    
    # Para birimi var mı?
    if re.search(r'[₺$€]|\d+\s*TL|milyon|milyar', answer, re.I):
        score += 20
    
    # Yüzde hesabı var mı?
    if re.search(r'%\s*\d+|\d+\s*%', answer):
        score += 10
    
    # Maliyet/gelir/kâr kelimesi
    if re.search(r'(maliyet|gelir|kâr|zarar|tasarruf|yatırım|getiri|bütçe)', answer, re.I):
        score += 10
    
    # Karşılaştırma var mı?
    if re.search(r'(hedef|benchmark|geçen\s*(yıl|ay|dönem)|artış|azalış|değişim)', answer, re.I):
        score += 10
    
    return min(100, score)


def _check_risk_clarity(answer: str, mode: str) -> float:
    """Risk değerlendirmesi kalitesi."""
    if mode == "Sohbet":
        return 80.0
    
    score = 50.0
    
    # Risk kelimesi var mı?
    if re.search(r'(risk|tehlike|tehdit|uyarı|dikkat|sorun)', answer, re.I):
        score += 15
    
    # Risk seviyesi belirtilmiş mi?
    if re.search(r'(düşük|orta|yüksek|kritik|🔴|🟡|🟢|🟠)', answer, re.I):
        score += 15
    
    # Azaltma önerisi var mı?
    if re.search(r'(önlem|azalt|hafiflet|engellemek|önce|tedbir)', answer, re.I):
        score += 10
    
    return min(100, score)


def _check_strategic_depth(answer: str, mode: str) -> float:
    """Stratejik derinlik kontrolü."""
    if mode in ("Sohbet", "Bilgi"):
        return 80.0
    
    score = 50.0
    
    # Zaman perspektifi var mı?
    if re.search(r'(kısa\s*vade|orta\s*vade|uzun\s*vade|hemen|hafta|ay|yıl)', answer, re.I):
        score += 15
    
    # Aksiyon maddesi var mı?
    action_items = re.findall(r'^\s*[-•✅\d.)\]]\s*.+', answer, re.M)
    if len(action_items) >= 3:
        score += 15
    elif len(action_items) >= 1:
        score += 8
    
    # Sorumlu / timeline var mı?
    if re.search(r'(sorumlu|departman|müdür|ekip|tarih|deadline)', answer, re.I):
        score += 10
    
    # Alternatif / senaryo var mı?
    if re.search(r'(alternatif|senaryo|seçenek|plan\s*b|ihtimal)', answer, re.I):
        score += 10
    
    return min(100, score)


def _check_hallucination(answer: str, question: str) -> list[str]:
    """Olası hallucination (uydurma) tespiti."""
    issues = []
    
    # Aşırı kesin ifadeler (genelde uydurma riski)
    overconfident = re.findall(
        r'(kesinlikle|%100|şüphesiz|tartışmasız|mutlaka.*olacak)',
        answer, re.I
    )
    if len(overconfident) > 2:
        issues.append("Aşırı kesin ifadeler — uydurma riski")
    
    # Tutarsız sayılar — aynı metriğin farklı değerleri
    percentages = re.findall(r'(%\s*[\d.,]+|[\d.,]+\s*%)', answer)
    if len(percentages) > 8:
        # Çok fazla yüzde değeri varsa kontrol et
        values = []
        for p in percentages:
            try:
                val = float(re.search(r'[\d.,]+', p).group().replace(',', '.'))
                values.append(val)
            except:
                pass
        # 100'den büyük yüzde — hata olabilir
        for v in values:
            if v > 100 and '%' in answer:
                issues.append(f"Yüzde değer %{v} > 100 — kontrol gerekli")
                break
    
    return issues


# ══════════════════════════════════════════════════════════════
# 3. LLM İLE DERİN DEĞERLENDİRME (opsiyonel, ağır analiz)
# ══════════════════════════════════════════════════════════════

REFLECTION_PROMPT = """Sen bir kalite kontrol uzmanısın. Aşağıdaki AI yanıtını değerlendir.

## Kullanıcı Sorusu:
{question}

## AI Yanıtı:
{answer}

## Değerlendirme Kriterleri (her birini 0-100 puanla):
1. **Veri Doğruluğu**: Sayılar tutarlı mı, birimler doğru mu?
2. **Mantıksal Tutarlılık**: Çelişki var mı, neden-sonuç doğru mu?
3. **Finansal Akıl Yürütme**: Mali etki hesaplanmış mı?
4. **Risk Netliği**: Riskler belirlenmiş ve seviyelendirilmiş mi?
5. **Stratejik Derinlik**: Kısa/orta/uzun vade öneriler var mı?

## Yanıtını SADECE bu JSON formatında ver:
```json
{{
  "data_accuracy": <0-100>,
  "logical_consistency": <0-100>,
  "financial_reasoning": <0-100>,
  "risk_clarity": <0-100>,
  "strategic_depth": <0-100>,
  "overall_confidence": <0-100>,
  "issues": ["sorun1", "sorun2"],
  "improvement_suggestions": ["öneri1", "öneri2"]
}}
```"""


RETRY_ENHANCEMENT_PROMPT = """Önceki yanıtın kalite değerlendirmesinde düşük puan aldı.

## Sorunlar:
{issues}

## İyileştirme Önerileri:
{suggestions}

Lütfen yanıtını şu kriterlere göre iyileştir:
- Somut sayısal veriler ekle (₺, %, birim)
- Finansal etki hesabı yap
- Risk seviyelerini belirt (Düşük/Orta/Yüksek/Kritik)
- Kısa/Orta/Uzun vade öneriler sun
- Best Case / Expected Case / Worst Case senaryolarını değerlendir

## Orijinal Soru:
{question}

Yanıtını iyileştirilmiş haliyle yeniden yaz:"""


def build_retry_prompt(question: str, evaluation: dict) -> str:
    """Düşük kaliteli yanıt için iyileştirme prompt'u oluştur."""
    issues_text = "\n".join(f"- {i}" for i in evaluation.get("issues", []))
    suggestions_text = "\n".join(f"- {s}" for s in evaluation.get("suggestions", []))
    
    return RETRY_ENHANCEMENT_PROMPT.format(
        issues=issues_text or "- Genel kalite yetersiz",
        suggestions=suggestions_text or "- Daha detaylı ve yapılandırılmış yanıt ver",
        question=question,
    )


def format_confidence_badge(confidence: float) -> str:
    """Confidence değerini görsel badge'e çevir."""
    if confidence >= 90:
        return f"🟢 Güven: %{confidence:.0f}"
    elif confidence >= 75:
        return f"🔵 Güven: %{confidence:.0f}"
    elif confidence >= 60:
        return f"🟡 Güven: %{confidence:.0f}"
    else:
        return f"🔴 Güven: %{confidence:.0f}"


# ══════════════════════════════════════════════════════════════
# 4. REFLECTION SONUCU FORMAT
# ══════════════════════════════════════════════════════════════

def format_reflection_footer(evaluation: dict, show_details: bool = False) -> str:
    """Yanıt altına reflection bilgisi ekle."""
    confidence = evaluation.get("confidence", 0)
    badge = format_confidence_badge(confidence)
    
    footer = f"\n\n---\n{badge}"
    
    if show_details and evaluation.get("criteria_scores"):
        footer += "\n<details><summary>📊 Kalite Detayı</summary>\n\n"
        for criterion, score in evaluation["criteria_scores"].items():
            bar = "█" * int(score / 10) + "░" * (10 - int(score / 10))
            footer += f"- {criterion}: {bar} {score:.0f}/100\n"
        footer += "\n</details>"
    
    if evaluation.get("issues"):
        footer += f"\n⚠️ {len(evaluation['issues'])} iyileştirme notu"
    
    return footer
