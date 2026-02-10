"""
Türkçe Sohbet Örnekleri Yükleyici (Few-Shot Learning)

Bu modül:
1. Yerel kalıpları (chat_patterns.json) yükler → selamlaşma, teşekkür vs.
2. HuggingFace dataseti'nden benzer örnekleri bulur (ChromaDB ile)
3. Sohbet modunda prompt'a 2-3 örnek ekleyerek AI'ın doğal konuşmasını sağlar

Fine-tune gerektirmez! Tamamen prompt-tabanlı (in-context learning).
"""

import json
import os
import random
import re
from pathlib import Path
from typing import Optional

import structlog

logger = structlog.get_logger()

# ── Dosya yolları ──
_BASE_DIR = Path(__file__).parent
_PATTERNS_FILE = _BASE_DIR / "chat_patterns.json"
_DATASET_DIR = Path(__file__).parent.parent.parent / "data"
_DATASET_FILE = _DATASET_DIR / "turkish_chat_dataset.json"

# ── Cache ──
_patterns_cache: Optional[dict] = None
_dataset_cache: Optional[list] = None
_dataset_loaded = False

# ── ChromaDB chat collection ──
_chat_collection = None


def _load_patterns() -> dict:
    """chat_patterns.json'dan kalıpları yükle (cache'li)"""
    global _patterns_cache
    if _patterns_cache is not None:
        return _patterns_cache
    
    try:
        if _PATTERNS_FILE.exists():
            with open(_PATTERNS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            _patterns_cache = data
            logger.info("chat_patterns_loaded", categories=len([k for k in data if k[0] != "_"]))
            return data
    except Exception as e:
        logger.warning("chat_patterns_load_error", error=str(e))
    
    _patterns_cache = {}
    return _patterns_cache


def _load_dataset() -> list:
    """HuggingFace dataset'ini yükle (cache'li)"""
    global _dataset_cache, _dataset_loaded
    if _dataset_loaded:
        return _dataset_cache or []
    
    _dataset_loaded = True
    try:
        if _DATASET_FILE.exists():
            with open(_DATASET_FILE, "r", encoding="utf-8") as f:
                _dataset_cache = json.load(f)
            logger.info("chat_dataset_loaded", entries=len(_dataset_cache))
            return _dataset_cache
    except Exception as e:
        logger.warning("chat_dataset_load_error", error=str(e))
    
    _dataset_cache = []
    return _dataset_cache


def _is_question(text: str) -> bool:
    """Metin bir soru mu? (Soru kalıplarını LLM'e yönlendirmek için)"""
    q = text.lower().strip()
    # Soru ekleri veya soru işareti
    if "?" in q:
        return True
    # Türkçe soru kalıpları (ayrık ve bitişik yazım)
    if re.search(r"\b(ne|nedir|nerede|nasıl|niçin|neden|niye|kaç|kim|hangi)\b", q):
        return True
    # Soru ekleri — ayrık ve bitişik (biliyormusun, tanıyormusun, hatırlıyormusun)
    if re.search(r"(m[iıuü]s[iıuü]n|m[iıuü]y[iıuü][mz]|\bm[iıuü]\b)", q):
        return True
    return False


def _match_pattern_category(question: str) -> Optional[str]:
    """Soruyu kalıp kategorisi ile eşle"""
    q = question.lower().strip()
    
    # Selamlaşma
    if re.search(r"(merhaba|selam|günaydın|iyi\s*(akşam|gece)|hey\b|selamün)", q):
        return "greetings"
    
    # İsim tanıtma — SORU DEĞİLSE ("benim ismim ne" gibi sorular LLM'e gitsin)
    if not _is_question(q) and re.search(r"(benim\s*adım|adım\s+\w|ben\s+[A-ZÇĞİÖŞÜa-zçğıöşü]{2,}$|ismim)", q):
        return "introduction"
    
    # Şirket/fabrika adı tanıtma — SORU DEĞİLSE
    if not _is_question(q):
        if re.search(r"(fabrikamız|şirketimiz|firmamız).*adı", q, re.IGNORECASE):
            return "company_introduction"
        if re.search(r"(adımız|biz\s+\w+.*olarak\s+(çalış|faaliyet))", q, re.IGNORECASE):
            return "company_introduction"
    
    # Nasılsın
    if re.search(r"(nasılsın|naber|ne\s*haber|iyi\s*misin|keyfin|keyifler)", q):
        return "how_are_you"
    
    # Kimlik — "sen kimsin" gibi AI hakkında sorular (kullanıcı İSMİ soruları HERİÇ)
    if re.search(r"(sen\s*kim|adın\s*ne|ne\s*yapabilir|robot\s*mu|yapay\s*zeka)", q):
        # "beni tanıyor musun", "ismimi biliyor musun" gibi sorular PATTERNSIZ — LLM'e gitsin
        if re.search(r"(beni|ismimi|adımı|hatırl|tanı|biliy)", q):
            return None
        return "identity"
    
    # Teşekkür
    if re.search(r"(teşekkür|sağ\s*ol|eyvallah|süpersin|çok\s*iyi\s*yaptın|yardımcı\s*old)", q):
        return "thanks"
    
    # Veda
    if re.search(r"(hoşça\s*kal|görüşürüz|iyi\s*geceler|bay\s*bay|güle\s*güle|kolay\s*gelsin)", q):
        return "farewell"
    
    # Moral/cesaretlendirme
    if re.search(r"(yapamayac|moralim|zor\s*bir\s*gün|çok\s*zor|umutsuz)", q):
        return "encouragement"
    
    # Günlük sohbet
    if re.search(r"(canım\s*sık|yoğun|yoruldum|sıcak|soğuk|bir\s*şey\s*sor|fıkra|bilmiyorsun|seviyorum)", q):
        return "small_talk"
    
    # İş-sohbet
    if re.search(r"(toplantı.*var|patron|öğle\s*yemeğ|kantın|ne\s*yesem)", q):
        return "work_casual"
    
    return None


def get_pattern_response(question: str) -> Optional[str]:
    """
    Kalıp eşleşmesi varsa doğrudan yanıt döndür (en hızlı yol).
    Eşleşme yoksa None döner.
    """
    patterns = _load_patterns()
    if not patterns:
        return None
    
    category = _match_pattern_category(question)
    if not category or category not in patterns:
        return None
    
    examples = patterns[category]
    if not examples:
        return None
    
    # Rastgele bir yanıt seç (çeşitlilik için)
    example = random.choice(examples)
    response = example.get("ai")
    
    # İsim tanıtma: yanıttaki örnek ismi gerçek isimle değiştir
    if category == "introduction" and response:
        q = question.strip()
        name_match = re.search(
            r"(?:benim\s*adım|adım|ben|ismim)\s+([A-ZÇĞİÖŞÜa-zçğıöşü]+)",
            q, re.IGNORECASE
        )
        if name_match:
            real_name = name_match.group(1).capitalize()
            for placeholder in ["Ali", "Ayşe", "Mehmet", "Murteza"]:
                response = response.replace(placeholder, real_name)
    
    # Şirket/fabrika adı tanıtma: ismi çıkar ve yerleştir
    if category == "company_introduction" and response:
        q = question.strip()
        # "adı X" veya "adı: X" formatı
        name_match = re.search(
            r"adı\s*[:.]?\s*(.+?)$",
            q, re.IGNORECASE
        )
        if not name_match:
            # "biz X olarak" formatı
            name_match = re.search(r"biz\s+(.+?)\s+olarak", q, re.IGNORECASE)
        if name_match:
            company_name = name_match.group(1).strip()
            # Placeholder isimleri değiştir
            for placeholder in ["ORHAN KARAKOÇ TEKSTİL", "ABC Tekstil", "XYZ", "KARAKOÇ TEKSTİL"]:
                response = response.replace(placeholder, company_name)
    
    return response


def get_few_shot_examples(question: str, count: int = 2) -> str:
    """
    Soru için uygun few-shot örnekler döndür.
    Kalıp eşleşmesi varsa kalıplardan, yoksa dataset'ten rastgele seçer.
    
    Returns:
        Few-shot prompt metni (boş string olabilir)
    """
    examples = []
    
    # 1. Kalıp eşleşmesi
    patterns = _load_patterns()
    category = _match_pattern_category(question)
    
    if category and category in patterns:
        cat_examples = patterns[category]
        selected = random.sample(cat_examples, min(count, len(cat_examples)))
        for ex in selected:
            examples.append({"user": ex["user"], "ai": ex["ai"]})
    
    # 2. Eksik kalan örnekleri dataset'ten doldur
    if len(examples) < count:
        dataset = _load_dataset()
        if dataset:
            remaining = count - len(examples)
            # Basit keyword eşleşmesi ile ilgili örnekleri bul
            keywords = _extract_keywords(question)
            matched = _find_relevant_from_dataset(keywords, dataset, limit=remaining)
            
            if not matched:
                # Keyword eşleşmesi yoksa rastgele seç
                matched = random.sample(dataset, min(remaining, len(dataset)))
            
            for m in matched:
                examples.append({
                    "user": m["input"][:200],
                    "ai": m["output"][:300]
                })
    
    if not examples:
        return ""
    
    # Prompt formatla
    text = "\n## Konuşma Tarzı Referansı (BUNLARI YANITINDA TEKRARLAMA):\n"
    text += "Aşağıdaki örneklerdeki TARZ ve TONLA konuş ama bu örnekleri yanıtına KOPYALAMA:\n\n"
    for i, ex in enumerate(examples, 1):
        text += f"Örnek soru: {ex['user']}\nÖrnek cevap: {ex['ai']}\n\n"
    text += "ÖNEMLİ: Bu örnekleri yanıtına ASLA dahil etme. Sadece tarzını benimse ve doğrudan kullanıcının sorusuna cevap ver.\n"
    
    return text


def _extract_keywords(question: str) -> list[str]:
    """Sorudan önemli kelimeleri çıkar"""
    # Türkçe stopwords
    stopwords = {
        "bir", "bu", "şu", "o", "ne", "nasıl", "mı", "mi", "mu", "mü",
        "ve", "ile", "için", "da", "de", "den", "dan", "ben", "sen", "biz",
        "siz", "var", "yok", "çok", "az", "daha", "en", "her", "ama",
        "ancak", "gibi", "kadar", "bana", "sana", "olan", "olur", "olarak",
    }
    words = re.findall(r"\b\w+\b", question.lower())
    return [w for w in words if w not in stopwords and len(w) > 2]


def _find_relevant_from_dataset(keywords: list[str], dataset: list, limit: int = 2) -> list:
    """Keyword eşleşmesi ile dataset'ten ilgili örnekleri bul"""
    if not keywords:
        return []
    
    scored = []
    for item in dataset:
        text = (item.get("input", "") + " " + item.get("output", "")).lower()
        score = sum(1 for kw in keywords if kw in text)
        if score > 0:
            scored.append((score, item))
    
    # En yüksek skorlu olanlardan seç
    scored.sort(key=lambda x: x[0], reverse=True)
    
    # Biraz çeşitlilik ekle — en iyi 10 arasından rastgele seç
    top = [s[1] for s in scored[:10]]
    if len(top) <= limit:
        return top
    return random.sample(top, limit)


def get_dataset_stats() -> dict:
    """Dataset istatistikleri"""
    patterns = _load_patterns()
    dataset = _load_dataset()
    
    pattern_count = sum(
        len(v) for k, v in patterns.items() 
        if isinstance(v, list) and k[0] != "_"
    )
    
    return {
        "pattern_categories": len([k for k in patterns if k[0] != "_"]),
        "pattern_examples": pattern_count,
        "dataset_entries": len(dataset),
        "patterns_file": str(_PATTERNS_FILE),
        "dataset_file": str(_DATASET_FILE),
    }


# ── RAG'a yükleme fonksiyonu ──

def load_dataset_to_rag(max_entries: int = 500) -> dict:
    """
    Dataset'teki en kaliteli örnekleri RAG'a yükle.
    Bu sayede semantic search ile en uygun örnekler bulunabilir.
    
    max_entries: En fazla kaç örnek yüklenecek (RAM/performans için sınırla)
    """
    try:
        from app.rag.vector_store import add_document
    except ImportError:
        return {"success": False, "error": "RAG modülü bulunamadı"}
    
    dataset = _load_dataset()
    if not dataset:
        return {"success": False, "error": "Dataset yüklenemedi"}
    
    # Kaliteli örnekleri seç (çok kısa cevapları atla)
    quality = [
        d for d in dataset 
        if len(d.get("output", "")) > 50 and len(d.get("input", "")) > 10
    ]
    
    # Rastgele seç (çeşitlilik için)
    selected = random.sample(quality, min(max_entries, len(quality)))
    
    loaded = 0
    errors = 0
    for item in selected:
        try:
            content = f"Soru: {item['input']}\nCevap: {item['output']}"
            add_document(
                content=content,
                source="turkish_chat_dataset",
                metadata={
                    "type": "chat_example",
                    "dataset": "sixfinger-2b",
                    "auto_loaded": True,
                }
            )
            loaded += 1
        except Exception:
            errors += 1
    
    result = {
        "success": True,
        "total_dataset": len(dataset),
        "quality_filtered": len(quality),
        "loaded_to_rag": loaded,
        "errors": errors,
    }
    logger.info("dataset_loaded_to_rag", **result)
    return result
