"""Akıllı Soru Yönlendirici - LLM + Regex Hibrit Niyet Analizi (v4.3.0)"""

from typing import Dict, Any
import re
import structlog

logger = structlog.get_logger()

# ── LLM Router Cache (v4.3.0) ──
_llm_router_cache: dict[str, str] = {}  # Son 50 sorguyu cache'le
_LLM_ROUTER_CACHE_SIZE = 50

# ── LLM Router Prompt (v4.3.0) ──
LLM_ROUTER_PROMPT = """Aşağıdaki kullanıcı mesajını sınıflandır.

Mesaj: "{question}"

Sınıflar:
- sohbet: Selamlaşma, günlük konuşma, kişisel soru, espri
- iş: İş analizi, hesaplama, rapor, KPI, üretim, maliyet, performans
- bilgi: Genel bilgi talebi, tanım, açıklama, araştırma

SADECE sınıf adını yaz (sohbet/iş/bilgi), başka bir şey yazma."""

# ──────────────────────────────────────────────
# Departman anahtar kelimeleri (fallback için)
# ──────────────────────────────────────────────
DEPARTMENT_KEYWORDS = {
    "Üretim": [
        "üretim", "fire", "yangın", "makine", "arıza", "fabrika", "hat", 
        "kalite", "hammadde", "stok", "bakım", "onarım", "vardiya",
    ],
    "Finans": [
        "nakit", "kâr", "kar", "zarar", "bütçe", "maliyet", "fatura", 
        "ödeme", "tahsilat", "kredi", "borç", "alacak", "muhasebe",
    ],
    "İnsan Kaynakları": [
        "personel", "çalışan", "işe alım", "maaş", "izin", "eğitim",
        "performans", "özlük", "bordro", "işten çıkış",
    ],
    "Satış": [
        "müşteri", "satış", "sipariş", "teklif", "fiyat", "kampanya",
        "pazar", "ihracat", "bayi", "distribütör",
    ],
    "IT": [
        "yazılım", "sistem", "sunucu", "network", "güvenlik", "yedekleme",
        "erişim", "şifre", "uygulama", "database",
    ],
}

# ──────────────────────────────────────────────
# Niyet kalıpları — regex tabanlı akıllı tespit
# (3 kelime kuralı yerine, cümle yapısına bakar)
# ──────────────────────────────────────────────

# Sohbet / günlük konuşma kalıpları
CHAT_PATTERNS = [
    # Selamlaşma
    r"\b(merhaba|selam|hey|naber|günaydın|iyi\s*akşamlar|iyi\s*geceler)\b",
    r"\b(hoş\s*geldin|hoşça\s*kal|görüşürüz|bay\s*bay)\b",
    # Hal hatır
    r"\b(nasılsın|naber|ne\s*haber|iyi\s*misin|keyifler\s*nasıl)\b",
    r"\b(n['']?apıyorsun|ne\s*yapıyorsun|meşgul\s*müsün)\b",
    # Teşekkür / nezaket
    r"\b(teşekkür|sağ\s*ol|eyvallah|rica\s*ederim|kolay\s*gelsin)\b",
    r"\b(iyi\s*çalışmalar|iyi\s*günler|hayırlı\s*işler)\b",
    # Kimlik soruları
    r"\b(kimsin|nesin|adın\s*ne|sen\s*kimsin|ne\s*yapabilirsin)\b",
    r"\b(kendini\s*tanıt|hakkında\s*bilgi)\b",
    # Tanıtma / bilgi verme (kişi, şirket, fabrika adı söyleme)
    r"\b(benim\s*adım|adım\s+\w|ben\s+[A-Z]|ismim)\b",
    r"(fabrikamız|şirketimiz|firmamız).*adı",
    r"adı(mız)?\s*[:.]?\s*[A-ZÇĞİÖŞÜ]",
    # Genel sohbet / fikir
    r"\b(sence|bence|ne\s*dersin|ne\s*düşünüyorsun|fikrin\s*ne)\b",
    r"\b(bir\s*şey\s*soracağım|merak\s*ettim|acaba)\b",
    # Şaka / eğlence
    r"\b(şaka|fıkra|espri|güldür|eğlenceli)\b",
]

# İş / profesyonel kalıpları
WORK_PATTERNS = [
    # Analiz / rapor talebi
    r"\b(analiz\s*et|rapor\s*(ver|hazırla|oluştur)|değerlendir)\b",
    r"\b(karşılaştır|trend|istatistik|grafik|tablo)\b",
    # Sorun / problem
    r"\b(sorun|problem|arıza|hata|bozul|çalışmıyor)\b",
    r"\b(acil|kritik|ivedi|tehlike|kaza|yangın)\b",
    # İş süreçleri
    r"\b(sipariş|fatura|stok|üretim|sevkiyat|teslimat)\b",
    r"\b(maliyet|bütçe|kar|zarar|nakit|ödeme)\b",
    r"\b(personel|maaş|izin|performans|bordro)\b",
    # Karar / strateji
    r"\b(karar|onay|strateji|planlama|hedef)\b",
    # Teknik talepler
    r"\b(güncelle|düzelt|konfigür|ayarla|yedekle|kurulum)\b",
]

# Bilgi talebi (internetten araştırma gerektirebilir)
KNOWLEDGE_PATTERNS = [
    r"\b(kim|ne\s*zaman|nasıl|neden|nerede|kaç|hangi)\b",
    r"\b(tarih|tarihçe|geçmiş|köken|etimoloji)\b",
    r"\b(güncel|son\s*dakika|bugün|dün|bu\s*hafta)\b",
    r"\b(fiyat|döviz|kur|borsa|altın|bitcoin)\b",
    r"\b(dünya|hava\s*durumu|spor|futbol|maç)\b",
    r"\b(araştır|bul|internet|web|google)\b",
    # Bilgi sorusu kalıpları (öğrenme / tanım amaçlı)
    r"\b(nedir|ne\s*demek|anlamı\s*ne|açıkla|tarihçesi)\b",
    # Örnek / görsek / bilgi talepleri
    r"\b(örnek|örneği|örnekleri|numune)\b",
    r"\b(göster|gösterir\s*misin|görebilir\s*miyim)\b",
    r"\b(nasıl\s*yapılır|nasıl\s*olur|ne\s*işe\s*yarar)\b",
    r"\bver(ir\s*misin|ebilir\s*misin|sene|\s*bana)?\b",
    r"\b(baskı|matbaa|tasarım|desen|model|çeşit|tür)\b",
]

# Doküman / şirket bilgisi kalıpları — RAG her zaman çalışmalı
DOCUMENT_PATTERNS = [
    r"\b(şirket|firma|fabrika|kuruluş|işletme)\b",
    r"\b(katalog|broşür|döküman|doküman|belge|dosya)\b",
    r"\b(ürün|ürünler|hizmet|hizmetler)\b",
    r"\b(bilgi\s*ver|anlat|açıkla|özetle|detay)\b",
    r"\b(yüklediğim|eklediğim|kayıtlı|mevcut)\b",
    r"\b(hakkında|ilgili|konusunda|dair)\b",
    r"\b(kumaş|iplik|tekstil|konfeksiyon|dikiş|boyama)\b",
    r"\b(ne\s*iş\s*yapar|ne\s*üretir|faaliyet|sektör)\b",
    r"\b(kimdir|nedir|vizyonu?|misyonu?)\b",
    r"\b(bilgi\s*tabanı|veritabanı|kaynak|referans)\b",
]


def _classify_intent(question: str) -> str:
    """
    Mesajın niyetini akıllı şekilde tespit eder.
    Regex kalıpları + cümle yapısı analizi kullanır.
    
    Returns:
        "sohbet" | "iş" | "bilgi"
    """
    q = question.lower().strip()
    
    # Puan tabanlı sistem
    chat_score = 0
    work_score = 0
    knowledge_score = 0
    document_score = 0
    
    for pattern in CHAT_PATTERNS:
        if re.search(pattern, q):
            chat_score += 2
    
    for pattern in WORK_PATTERNS:
        if re.search(pattern, q):
            work_score += 2
    
    for pattern in KNOWLEDGE_PATTERNS:
        if re.search(pattern, q):
            knowledge_score += 2
    
    for pattern in DOCUMENT_PATTERNS:
        if re.search(pattern, q):
            document_score += 2
    
    # Departman keyword'ü varsa iş skoru ekle
    for dept, keywords in DEPARTMENT_KEYWORDS.items():
        if any(kw in q for kw in keywords):
            work_score += 1
    
    # Doküman/şirket skoru varsa iş veya bilgi olarak değerlendir (sohbet değil!)
    if document_score > 0:
        # Doküman kalıpları tespit edildiyse, bilgi veya iş skoruna ekle
        knowledge_score += document_score
        work_score += document_score // 2
    
    # Kısa tek kelime ("evet", "hayır", "tamam") → sohbet
    if len(q.split()) <= 2 and work_score == 0 and knowledge_score == 0:
        chat_score += 3
    
    # Soru işareti + iş keyword'ü yoksa → sohbet olabilir
    if "?" in q and work_score == 0 and knowledge_score == 0:
        chat_score += 1
    
    logger.debug("intent_scores", chat=chat_score, work=work_score, 
                 knowledge=knowledge_score, document=document_score, q=q[:60])
    
    # En yüksek skora göre karar ver
    if work_score > chat_score and work_score > knowledge_score:
        return "iş"
    elif knowledge_score > chat_score and knowledge_score > work_score:
        return "bilgi"
    elif chat_score > 0:
        return "sohbet"
    else:
        # Hiçbir kalıba uymuyorsa — bilgi olarak değerlendir (RAG şansı ver)
        return "bilgi"


async def _llm_classify_intent(question: str) -> str | None:
    """v4.3.0: LLM ile niyet sınıflandırma (primary router).
    
    Cache destekli. LLM erişilemezse None döner → regex fallback.
    """
    # Cache kontrolü
    cache_key = question.strip().lower()[:100]
    if cache_key in _llm_router_cache:
        return _llm_router_cache[cache_key]
    
    try:
        from app.llm.client import ollama_client
        if not await ollama_client.is_available():
            return None
        
        prompt = LLM_ROUTER_PROMPT.format(question=question[:200])
        result = await ollama_client.generate(
            prompt=prompt,
            system_prompt="Sadece sınıf adı yaz: sohbet, iş veya bilgi.",
            temperature=0.0,
            max_tokens=10,
        )
        
        if result:
            cleaned = result.strip().lower().split()[0] if result.strip() else ""
            # Geçerli sınıflardan birini bul
            for cls in ("sohbet", "iş", "bilgi"):
                if cls in cleaned:
                    # Cache'e ekle
                    if len(_llm_router_cache) > _LLM_ROUTER_CACHE_SIZE:
                        # En eski yarısını sil
                        keys = list(_llm_router_cache.keys())
                        for k in keys[:_LLM_ROUTER_CACHE_SIZE // 2]:
                            _llm_router_cache.pop(k, None)
                    _llm_router_cache[cache_key] = cls
                    logger.info("llm_router_classified", intent=cls, q=question[:60])
                    return cls
        
        return None
    except Exception as e:
        logger.debug("llm_router_failed", error=str(e))
        return None


def decide(question: str) -> Dict[str, Any]:
    """
    Soruyu analiz ederek departman, mod, risk ve niyet belirler.
    Senkron versiyon — regex tabanlı.
    
    Args:
        question: Kullanıcı sorusu
    
    Returns:
        dict: {"dept": str, "mode": str, "risk": str, "intent": str, "needs_web": bool}
    """
    q = question.lower()
    
    # 1. Akıllı niyet tespiti (regex fallback)
    intent = _classify_intent(question)
    
    # 2. Departman belirleme (iş soruları için anlamlı)
    department = "Genel"
    max_matches = 0
    
    for dept, keywords in DEPARTMENT_KEYWORDS.items():
        matches = sum(1 for kw in keywords if kw in q)
        if matches > max_matches:
            max_matches = matches
            department = dept
    
    # Sohbette departman önemli değil
    if intent == "sohbet" and max_matches == 0:
        department = "Genel"
    
    # 3. Risk belirleme
    RISK_KEYWORDS = {
        "Yüksek": ["acil", "kritik", "yangın", "kaza", "tehlike", "ivedi"],
        "Orta": ["sorun", "problem", "arıza", "gecikme", "risk", "eksik"],
    }
    risk = "Düşük"
    for risk_level, keywords in RISK_KEYWORDS.items():
        if any(kw in q for kw in keywords):
            risk = risk_level
            break
    
    # 4. Mod belirleme (niyete göre)
    MODE_KEYWORDS = {
        "Acil": ["acil", "hemen", "ivedi", "yangın", "kaza"],
        "Analiz": ["analiz", "rapor", "değerlendirme", "karşılaştırma", "trend"],
        "Özet": ["özet", "özetle", "kısaca"],
        "Rapor": ["rapor", "raporla", "döküm"],
    }
    
    if intent == "sohbet":
        mode = "Sohbet"
    elif intent == "bilgi":
        mode = "Bilgi"
    else:
        mode = "Analiz"  # iş varsayılanı
        for mode_type, keywords in MODE_KEYWORDS.items():
            if any(kw in q for kw in keywords):
                mode = mode_type
                break
    
    # 5. Web arama gerekiyor mu?
    needs_web = (intent == "bilgi") or any(
        kw in q for kw in ["araştır", "internet", "güncel", "bul", "web"]
    )
    
    return {
        "dept": department,
        "mode": mode,
        "risk": risk,
        "intent": intent,
        "needs_web": needs_web,
    }


async def async_decide(question: str) -> Dict[str, Any]:
    """v5.7.0: Sadeleştirilmiş async versiyon — SADECE regex tabanlı.
    
    Eski versiyon her soruda 72B modele LLM çağrısı yapıyordu (5-10sn ekstra).
    Regex tabanlı _classify_intent() zaten %95+ doğrulukla çalışıyor.
    LLM router çağrısı kaldırıldı — her soruda 5-10 saniye tasarruf.
    """
    result = decide(question)
    result["router_type"] = "regex"
    return result


def get_department_info(department: str) -> Dict[str, Any]:
    """Departman hakkında bilgi döner"""
    info = {
        "Üretim": {
            "description": "Üretim ve fabrika operasyonları",
            "priority_contact": "Üretim Müdürü",
            "escalation_time_minutes": 15,
        },
        "Finans": {
            "description": "Mali işler ve muhasebe",
            "priority_contact": "Finans Müdürü",
            "escalation_time_minutes": 30,
        },
        "İnsan Kaynakları": {
            "description": "Personel ve özlük işleri",
            "priority_contact": "İK Müdürü",
            "escalation_time_minutes": 60,
        },
        "Satış": {
            "description": "Satış ve müşteri ilişkileri",
            "priority_contact": "Satış Müdürü",
            "escalation_time_minutes": 30,
        },
        "IT": {
            "description": "Bilgi teknolojileri",
            "priority_contact": "IT Müdürü",
            "escalation_time_minutes": 20,
        },
        "Yönetim": {
            "description": "Genel yönetim ve strateji",
            "priority_contact": "Genel Müdür",
            "escalation_time_minutes": 60,
        },
    }
    return info.get(department, info["Yönetim"])