"""Token Budget Manager (v4.4.0)

LLM context window'unu aşmamak için token bütçesi yönetimi.
Qwen2.5 72B default context: 32768 token.

Yaklaşık hesaplama: 1 token ≈ 4 karakter (Türkçe için 3.5)
Güvenli limit: %85 kullanım → ~27850 token / ~97500 karakter

v4.4.0: Akıllı prompt sıkıştırma eklendi — kırpmak yerine
bilgi yoğunluğunu artırarak sıkıştırır.
"""

import re
from typing import Optional
import structlog

logger = structlog.get_logger()

# ── Konfigürasyon ──
MAX_CONTEXT_TOKENS = 32768
SAFETY_MARGIN = 0.85  # %85 kullanım, %15 güvenlik payı
CHARS_PER_TOKEN_TR = 3.5  # Türkçe metinler için ortalama

# Bölüm bütçeleri (toplam token %'si)
BUDGET_ALLOCATION = {
    "system_prompt": 0.20,      # ~6550 token — sistem, mod, dept, CoT
    "rag_context": 0.25,        # ~8190 token — RAG dokümanları
    "memory_context": 0.08,     # ~2620 token — hafıza
    "web_results": 0.10,        # ~3270 token — web arama sonuçları
    "chat_history": 0.12,       # ~3930 token — konuşma geçmişi
    "user_prompt": 0.05,        # ~1640 token — kullanıcı sorusu
    "response_reserve": 0.20,   # ~6550 token — LLM yanıtı için boş bırak
}

# Karakter limitleri (token * chars_per_token)
CHAR_LIMITS = {
    k: int(MAX_CONTEXT_TOKENS * SAFETY_MARGIN * v * CHARS_PER_TOKEN_TR)
    for k, v in BUDGET_ALLOCATION.items()
}


def estimate_tokens(text: str) -> int:
    """Metin uzunluğundan tahmini token sayısı hesapla."""
    if not text:
        return 0
    return int(len(text) / CHARS_PER_TOKEN_TR)


def truncate_to_budget(text: str, section: str, custom_limit: int = None) -> str:
    """Metni ilgili bölüm bütçesine göre kırp.
    
    Args:
        text: Kırpılacak metin
        section: Bütçe bölümü (system_prompt, rag_context, vb.)
        custom_limit: Özel karakter limiti (opsiyonel)
    
    Returns:
        Bütçeye uygun kırpılmış metin
    """
    if not text:
        return text
    
    limit = custom_limit or CHAR_LIMITS.get(section, 5000)
    
    if len(text) <= limit:
        return text
    
    # Son cümleden kırp (anlam bütünlüğü için)
    truncated = text[:limit]
    last_period = max(
        truncated.rfind('.'),
        truncated.rfind('\n'),
        truncated.rfind('|'),  # Tablo satırı
    )
    if last_period > limit * 0.7:
        truncated = truncated[:last_period + 1]
    
    tokens_saved = estimate_tokens(text) - estimate_tokens(truncated)
    logger.debug("token_budget_truncated", 
                section=section, 
                original_chars=len(text),
                truncated_chars=len(truncated),
                tokens_saved=tokens_saved)
    
    return truncated + "\n[...kırpıldı — bütçe limiti]"


def check_total_budget(components: dict[str, str]) -> dict:
    """Tüm bileşenlerin toplam token kullanımını kontrol et.
    
    Args:
        components: {"system_prompt": "...", "rag_context": "...", ...}
    
    Returns:
        {
            "total_tokens": int,
            "budget_used_pct": float,
            "over_budget": bool,
            "section_usage": {section: {tokens, limit, pct}}
        }
    """
    total_tokens = 0
    section_usage = {}
    
    for section, text in components.items():
        tokens = estimate_tokens(text or "")
        limit_tokens = int(MAX_CONTEXT_TOKENS * SAFETY_MARGIN * BUDGET_ALLOCATION.get(section, 0.1))
        total_tokens += tokens
        section_usage[section] = {
            "tokens": tokens,
            "limit": limit_tokens,
            "pct": round(tokens / max(limit_tokens, 1) * 100, 1),
        }
    
    max_tokens = int(MAX_CONTEXT_TOKENS * SAFETY_MARGIN)
    budget_pct = round(total_tokens / max_tokens * 100, 1)
    
    return {
        "total_tokens": total_tokens,
        "max_tokens": max_tokens,
        "budget_used_pct": budget_pct,
        "over_budget": total_tokens > max_tokens,
        "section_usage": section_usage,
    }


def smart_truncate_all(
    system_prompt: str,
    user_prompt: str,
    rag_context: str = "",
    memory_context: str = "",
    web_results: str = "",
    chat_history_text: str = "",
) -> dict[str, str]:
    """Tüm bileşenleri bütçeye sığacak şekilde akıllıca kırp.
    
    Öncelik sırası (en son kırpılan = en önemli):
    1. web_results (ilk kırpılan)
    2. memory_context
    3. chat_history
    4. rag_context
    5. system_prompt (son kırpılan)
    """
    result = {
        "system_prompt": truncate_to_budget(system_prompt, "system_prompt"),
        "user_prompt": truncate_to_budget(user_prompt, "user_prompt"),
        "rag_context": compress_and_truncate(rag_context, "rag_context"),
        "memory_context": compress_and_truncate(memory_context, "memory_context"),
        "web_results": compress_and_truncate(web_results, "web_results"),
        "chat_history": compress_and_truncate(chat_history_text, "chat_history"),
    }
    
    # Toplam bütçe kontrolü
    budget = check_total_budget(result)
    if budget["over_budget"]:
        logger.warning("token_budget_exceeded", 
                      total=budget["total_tokens"],
                      max=budget["max_tokens"],
                      pct=budget["budget_used_pct"])
        
        # Öncelik sırasına göre agresif kırp
        for section in ["web_results", "memory_context", "chat_history", "rag_context"]:
            current_limit = CHAR_LIMITS.get(section, 5000)
            result[section] = truncate_to_budget(
                result[section], section, 
                custom_limit=int(current_limit * 0.6)
            )
    
    return result


# ═══════════════════════════════════════════════════════════════
# AKILLI PROMPT SIKIŞTIRMA (v4.4.0)
# ═══════════════════════════════════════════════════════════════

# Türkçe dolgu ifadeler — bilgi taşımayan cümlelerden çıkart
_FILLER_PATTERNS = [
    r'(?i)\bbu\s+bağlamda\b',
    r'(?i)\bsonuç\s+olarak\b',
    r'(?i)\bözetle\s*(belirtmek\s+gerekir(se)?|söylemek\s+gerekir(se)?)\b',
    r'(?i)\byukarıda\s+(belirtildiği|ifade\s+edildiği)\b',
    r'(?i)\bgenel\s+anlamda\b',
    r'(?i)\bayrıca\s+belirtmek\s+gerekir\s+ki\b',
    r'(?i)\bbunun\s+yanı\s+sıra\b',
    r'(?i)\bbuna\s+ek\s+olarak\b',
    r'(?i)\bdaha\s+önce\s+de\s+belirtildiği\s+gibi\b',
    r'(?i)\bbilindiği\s+üzere\b',
]

# Bilgi yoğunluğu göstergeleri — bunları içeren cümleler korunur
_HIGH_INFO_PATTERNS = [
    r'\d+[\.,]?\d*\s*(%|TL|USD|EUR|kg|ton|mt|adet|metre)',
    r'\d{1,2}[./]\d{1,2}[./]\d{2,4}',  # Tarih
    r'[A-Z]{2,}\d+',  # Lot/sipariş no
    r'(?i)(sonuç|karar|öner|aksiyon|uyarı|dikkat|önemli)',
    r'(?i)(artı[şs]|düşüş|azal|iyileş|kötüleş)',
    r'(?i)(rakam|veri|ölçüm|test|analiz|rapor)',
]


def _sentence_importance(sentence: str) -> float:
    """Bir cümlenin bilgi yoğunluğunu 0-1 arası skorla."""
    if not sentence.strip():
        return 0.0
    
    score = 0.3  # Taban skor
    
    # Dolgu ifade varsa skor düşür
    for pat in _FILLER_PATTERNS:
        if re.search(pat, sentence):
            score -= 0.15
    
    # Bilgi yoğunluğu göstergeleri varsa skor artır
    for pat in _HIGH_INFO_PATTERNS:
        if re.search(pat, sentence):
            score += 0.15
    
    # Sayısal veri varsa bonus
    numbers = re.findall(r'\d+[\.,]?\d*', sentence)
    if numbers:
        score += min(len(numbers) * 0.05, 0.20)
    
    # Çok kısa veya çok uzun cümle cezası
    words = sentence.split()
    if len(words) < 3:
        score -= 0.10
    elif len(words) > 50:
        score -= 0.10
    
    return max(0.0, min(1.0, score))


def _remove_duplicate_sentences(text: str) -> str:
    """Tekrar eden veya çok benzer cümleleri kaldır."""
    sentences = re.split(r'(?<=[.!?])\s+', text)
    seen_normalized = set()
    unique = []
    
    for sent in sentences:
        # Normalize: küçük harf, fazla boşluk temizle
        norm = re.sub(r'\s+', ' ', sent.lower().strip())
        # İlk 60 karakter benzerlik kontrolü (paraphrase tespiti)
        key = norm[:60]
        if key not in seen_normalized and len(norm) > 5:
            seen_normalized.add(key)
            unique.append(sent)
    
    return ' '.join(unique)


def _compress_whitespace(text: str) -> str:
    """Fazla boşluk ve boş satırları sıkıştır."""
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r'[ \t]{2,}', ' ', text)
    text = re.sub(r' +\n', '\n', text)
    return text.strip()


def compress_text(text: str, target_ratio: float = 0.7) -> str:
    """Metni akıllıca sıkıştır — bilgi kaybını minimize ederek.
    
    Args:
        text: Sıkıştırılacak metin
        target_ratio: Hedef sıkıştırma oranı (0.7 = %70'ine düşür)
    
    Returns:
        Sıkıştırılmış metin
    """
    if not text or len(text) < 200:
        return text
    
    original_len = len(text)
    target_len = int(original_len * target_ratio)
    
    # Adım 1: Boşluk sıkıştırma
    text = _compress_whitespace(text)
    
    # Adım 2: Tekrar eden cümleleri kaldır
    text = _remove_duplicate_sentences(text)
    
    if len(text) <= target_len:
        return text
    
    # Adım 3: Düşük önemli cümleleri çıkar
    sentences = re.split(r'(?<=[.!?\n])\s*', text)
    scored = [(s, _sentence_importance(s)) for s in sentences if s.strip()]
    scored.sort(key=lambda x: x[1])
    
    # En düşük skorlu cümleleri çıkarmaya başla
    current_len = len(text)
    removed = set()
    
    for i, (sent, score) in enumerate(scored):
        if current_len <= target_len:
            break
        if score < 0.25:  # Sadece düşük skorluları çıkar
            removed.add(sent)
            current_len -= len(sent)
    
    if removed:
        result_sentences = [s for s in sentences if s.strip() and s not in removed]
        text = ' '.join(result_sentences)
    
    # Adım 4: Son boşluk temizliği
    text = _compress_whitespace(text)
    
    compression_pct = round((1 - len(text) / original_len) * 100, 1)
    if compression_pct > 5:
        logger.debug("prompt_compressed",
                     original_chars=original_len,
                     compressed_chars=len(text),
                     compression_pct=compression_pct)
    
    return text


def compress_and_truncate(text: str, section: str, custom_limit: int = None) -> str:
    """Önce sıkıştır, sonra gerekirse kırp.
    
    truncate_to_budget'ın gelişmiş versiyonu — 
    kırpmadan önce akıllı sıkıştırma uygular.
    """
    if not text:
        return text
    
    limit = custom_limit or CHAR_LIMITS.get(section, 5000)
    
    if len(text) <= limit:
        return text
    
    # Bütçenin %120'sinin altındaysa hafif sıkıştırma yeter
    if len(text) <= limit * 1.2:
        compressed = compress_text(text, target_ratio=0.85)
    elif len(text) <= limit * 1.5:
        compressed = compress_text(text, target_ratio=0.70)
    else:
        compressed = compress_text(text, target_ratio=0.55)
    
    # Sıkıştırma yetmediyse kırp
    if len(compressed) > limit:
        compressed = truncate_to_budget(compressed, section, custom_limit=limit)
    
    return compressed
