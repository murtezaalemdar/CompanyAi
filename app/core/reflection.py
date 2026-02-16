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
MAX_RETRY_COUNT = 2  # En fazla 2 kez retry (toplam 3 deneme — self-correction loop)


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
# 2.5 SAYISAL DOĞRULAMA MOTORU (v4.4.0) — RAG Kaynak Kontrolü
# ══════════════════════════════════════════════════════════════

def _extract_numbers(text: str) -> list[dict]:
    """Metinden sayısal değerleri ve bağlamlarını çıkar.
    
    Returns:
        [{"value": float, "unit": str, "context": str}, ...]
    """
    patterns = [
        # Para: ₺1.234.567 veya 1.234 TL veya $500
        (r'[₺$€]\s*([\d.,]+)\s*(?:milyon|milyar)?', 'para'),
        (r'([\d.,]+)\s*(?:TL|USD|EUR|₺|\$|€)', 'para'),
        (r'([\d.,]+)\s*(?:milyon|milyar)\s*(?:TL|USD|₺)?', 'para'),
        # Yüzde: %15.3 veya 15.3%
        (r'%\s*([\d.,]+)', 'yüzde'),
        (r'([\d.,]+)\s*%', 'yüzde'),
        # Ağırlık/miktar: 500 kg, 3.2 ton
        (r'([\d.,]+)\s*(?:kg|ton|gr|gram|lt|litre|m²|m³|metre|adet|kişi)', 'miktar'),
        # Zaman: 15 gün, 3 ay
        (r'([\d.,]+)\s*(?:gün|hafta|ay|yıl|saat|dakika)', 'zaman'),
        # Genel sayı (bağlam ile)
        (r'(?:toplam|ortalama|minimum|maksimum|yaklaşık|tahmini)\s*:?\s*([\d.,]+)', 'hesaplama'),
    ]
    
    results = []
    for pattern, unit_type in patterns:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            try:
                raw = match.group(1).replace('.', '').replace(',', '.')
                value = float(raw)
                # Bağlam: eşleşmeden 40 karakter öncesi ve sonrası
                start = max(0, match.start() - 40)
                end = min(len(text), match.end() + 40)
                context = text[start:end].strip()
                results.append({
                    "value": value,
                    "unit": unit_type,
                    "context": context,
                    "raw": match.group(0),
                })
            except (ValueError, IndexError):
                continue
    
    return results


def validate_numbers_against_source(answer: str, rag_context: str) -> dict:
    """LLM yanıtındaki sayıları RAG kaynak verileriyle karşılaştır.
    
    Args:
        answer: LLM'in ürettiği yanıt
        rag_context: RAG'dan gelen kaynak dokümanlar (birleştirilmiş metin)
    
    Returns:
        {
            "validated": bool,       # Sayısal tutarlılık var mı
            "match_count": int,      # Eşleşen sayı adedi
            "mismatch_count": int,   # Uyuşmayan sayı adedi
            "fabricated_count": int,  # Kaynakta hiç olmayan sayılar
            "issues": [str],         # Sorun açıklamaları
            "details": [dict],       # Detay
            "score": float,          # 0-100 doğruluk skoru
        }
    """
    if not rag_context or not answer:
        return {"validated": True, "match_count": 0, "mismatch_count": 0,
                "fabricated_count": 0, "issues": [], "details": [], "score": 100}
    
    answer_numbers = _extract_numbers(answer)
    source_numbers = _extract_numbers(rag_context)
    
    if not answer_numbers:
        return {"validated": True, "match_count": 0, "mismatch_count": 0,
                "fabricated_count": 0, "issues": [], "details": [], "score": 100}
    
    # Kaynak sayıları set'e çevir (hızlı arama için)
    source_values = {n["value"] for n in source_numbers}
    # Toleranslı eşleme için kaynak listesi
    source_list = [n["value"] for n in source_numbers]
    
    matched = 0
    mismatched = 0
    fabricated = 0
    issues = []
    details = []
    
    for ans_num in answer_numbers:
        val = ans_num["value"]
        
        # Tam eşleşme kontrolü
        if val in source_values:
            matched += 1
            details.append({"value": val, "status": "eşleşti", "raw": ans_num["raw"]})
            continue
        
        # Toleranslı eşleşme (%5 sapma)
        found_close = False
        for src_val in source_list:
            if src_val == 0:
                continue
            diff_pct = abs(val - src_val) / abs(src_val) * 100
            if diff_pct <= 5:
                matched += 1
                found_close = True
                details.append({"value": val, "status": "yakın_eşleşme",
                              "source_value": src_val, "diff_pct": round(diff_pct, 1),
                              "raw": ans_num["raw"]})
                break
            elif diff_pct <= 20:
                mismatched += 1
                found_close = True
                issues.append(
                    f"Sayısal sapma: yanıtta {ans_num['raw']}, kaynakta {src_val} "
                    f"(fark: %{diff_pct:.0f})"
                )
                details.append({"value": val, "status": "sapma",
                              "source_value": src_val, "diff_pct": round(diff_pct, 1),
                              "raw": ans_num["raw"]})
                break
        
        if not found_close:
            # Hesaplama sonucu olabilir (toplam, ortalama vb.) — tolerans ver
            if ans_num["unit"] == "hesaplama":
                details.append({"value": val, "status": "hesaplama", "raw": ans_num["raw"]})
            else:
                fabricated += 1
                details.append({"value": val, "status": "kaynakta_yok", "raw": ans_num["raw"]})
    
    # Çok fazla uydurma varsa uyar
    total = matched + mismatched + fabricated
    if total == 0:
        score = 100
    else:
        score = max(0, (matched / total) * 100 - fabricated * 5 - mismatched * 10)
    
    if fabricated > 2:
        issues.append(f"⚠️ {fabricated} sayısal değer kaynakta bulunamadı — uydurma riski")
    if mismatched > 1:
        issues.append(f"⚠️ {mismatched} sayısal değerde önemli sapma tespit edildi")
    
    return {
        "validated": len(issues) == 0,
        "match_count": matched,
        "mismatch_count": mismatched,
        "fabricated_count": fabricated,
        "issues": issues,
        "details": details,
        "score": round(score, 1),
    }


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


SELF_CORRECTION_PROMPT = """Aşağıdaki yanıtını gözden geçir ve iyileştir.

## Orijinal Soru:
{question}

## Mevcut Yanıtın:
{current_answer}

## Kalite Değerlendirmesi (Güven: %{confidence}):
{evaluation_summary}

## Görev:
1. Yanıtındaki eksikleri ve hataları tespit et
2. Somut veriler, sayılar ve örneklerle zenginleştir
3. Mantıksal tutarlılığı kontrol et
4. Yapısal netliği artır (başlıklar, listeler, tablolar)

Düzeltilmiş ve iyileştirilmiş yanıtı yaz:"""


def build_self_correction_prompt(question: str, current_answer: str, evaluation: dict) -> str:
    """Self-correction döngüsü için prompt oluştur.
    
    Normal retry'dan farkı: Mevcut yanıtı da gösterir ve üzerine düzeltme ister.
    """
    eval_summary = []
    for criterion, score in evaluation.get("criteria_scores", {}).items():
        eval_summary.append(f"- {criterion}: {score}/100")
    if evaluation.get("issues"):
        eval_summary.extend(f"- ⚠️ {i}" for i in evaluation["issues"])
    if evaluation.get("suggestions"):
        eval_summary.extend(f"- 💡 {s}" for s in evaluation["suggestions"])
    
    return SELF_CORRECTION_PROMPT.format(
        question=question,
        current_answer=current_answer[:2000],  # Token limiti için kısalt
        confidence=evaluation.get("confidence", 0),
        evaluation_summary="\n".join(eval_summary),
    )


async def self_correction_loop(
    question: str,
    initial_answer: str,
    mode: str,
    llm_generate,
    system_prompt: str = "",
    chat_history: list = None,
    max_rounds: int = None,
) -> dict:
    """İteratif self-correction döngüsü.
    
    LLM çıktısını değerlendirir, düşükse düzeltme ister, en iyi versiyonu döndürür.
    
    Args:
        question: Kullanıcı sorusu
        initial_answer: İlk LLM yanıtı
        mode: Yanıt modu (Sohbet, Analiz, Rapor)
        llm_generate: LLM generate fonksiyonu (async)
        system_prompt: Sistem prompt'u
        chat_history: Chat geçmişi
        max_rounds: Maksimum düzeltme turu
    
    Returns:
        {
            "answer": str,           # En iyi yanıt
            "confidence": float,     # 0-100
            "rounds": int,           # Kaç tur çalıştı
            "improved": bool,        # İyileştirme oldu mu
            "evaluation": dict,      # Son değerlendirme
        }
    """
    if max_rounds is None:
        max_rounds = MAX_RETRY_COUNT
    
    best_answer = initial_answer
    best_confidence = 0
    best_evaluation = {}
    rounds = 0
    
    current_answer = initial_answer
    
    for i in range(max_rounds + 1):  # +1 çünkü ilk değerlendirme de dahil
        # Değerlendir
        evaluation = quick_evaluate(current_answer, question, mode)
        confidence = evaluation.get("confidence", 0)
        rounds = i
        
        # En iyi sonucu takip et
        if confidence > best_confidence:
            best_confidence = confidence
            best_answer = current_answer
            best_evaluation = evaluation
        
        # Yeterli kalite → döngüyü kır
        if confidence >= AUTO_REANALYZE_THRESHOLD or not evaluation.get("should_retry"):
            break
        
        # Son tur → retry yapma
        if i >= max_rounds:
            break
        
        # Self-correction prompt oluştur
        try:
            if i == 0:
                # İlk retry — standart retry prompt
                correction_prompt = build_retry_prompt(question, evaluation)
            else:
                # Sonraki turlar — self-correction (mevcut yanıtı göstererek)
                correction_prompt = build_self_correction_prompt(
                    question, current_answer, evaluation
                )
            
            corrected = await llm_generate(
                prompt=correction_prompt,
                system_prompt=system_prompt,
                temperature=max(0.1, 0.3 - i * 0.1),  # Her turda daha deterministik
                max_tokens=800,
                history=chat_history,
            )
            
            if corrected and len(corrected) > len(current_answer) * 0.3:
                current_answer = corrected
                logger.info("self_correction_round", round=i+1, 
                           prev_confidence=confidence)
        except Exception as e:
            logger.warning("self_correction_error", round=i+1, error=str(e))
            break
    
    improved = best_confidence > quick_evaluate(initial_answer, question, mode).get("confidence", 0)
    
    logger.info("self_correction_done", rounds=rounds, 
                final_confidence=best_confidence, improved=improved)
    
    return {
        "answer": best_answer,
        "confidence": best_confidence,
        "rounds": rounds,
        "improved": improved,
        "evaluation": best_evaluation,
    }


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
