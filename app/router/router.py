"""Akıllı Soru Yönlendirici - LLM destekli Niyet Analizi"""

from typing import Dict, Any
import re
import structlog

logger = structlog.get_logger()

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
    # Genel sohbet / fikir
    r"\b(sence|bence|ne\s*dersin|ne\s*düşünüyorsun|fikrin\s*ne)\b",
    r"\b(bir\s*şey\s*soracağım|merak\s*ettim|acaba)\b",
    # Şaka / eğlence
    r"\b(şaka|fıkra|espri|güldür|eğlenceli)\b",
    # Bilgi sorusu (öğrenme amaçlı — iş dışı)
    r"\b(nedir|ne\s*demek|anlamı\s*ne|açıkla|tarihçesi)\b",
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
    r"\b(ne\s*zaman|kim\s*tarafından|nerede|hangi\s*ülke)\b",
    r"\b(tarih|tarihçe|geçmiş|köken|etimoloji)\b",
    r"\b(güncel|son\s*dakika|bugün|dün|bu\s*hafta)\b",
    r"\b(fiyat|döviz|kur|borsa|altın|bitcoin)\b",
    r"\b(dünya|hava\s*durumu|spor|futbol|maç)\b",
    r"\b(araştır|bul|internet|web|google)\b",
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
    
    for pattern in CHAT_PATTERNS:
        if re.search(pattern, q):
            chat_score += 2
    
    for pattern in WORK_PATTERNS:
        if re.search(pattern, q):
            work_score += 2
    
    for pattern in KNOWLEDGE_PATTERNS:
        if re.search(pattern, q):
            knowledge_score += 2
    
    # Departman keyword'ü varsa iş skoru ekle
    for dept, keywords in DEPARTMENT_KEYWORDS.items():
        if any(kw in q for kw in keywords):
            work_score += 1
    
    # Kısa tek kelime ("evet", "hayır", "tamam") → sohbet
    if len(q.split()) <= 2 and work_score == 0:
        chat_score += 3
    
    # Soru işareti + iş keyword'ü yoksa → sohbet olabilir
    if "?" in q and work_score == 0 and knowledge_score == 0:
        chat_score += 1
    
    logger.debug("intent_scores", chat=chat_score, work=work_score, knowledge=knowledge_score, q=q[:60])
    
    # En yüksek skora göre karar ver
    if work_score > chat_score and work_score > knowledge_score:
        return "iş"
    elif knowledge_score > chat_score and knowledge_score > work_score:
        return "bilgi"
    elif chat_score > 0:
        return "sohbet"
    else:
        # Hiçbir kalıba uymuyorsa — genel sohbet/bilgi
        return "sohbet"


def decide(question: str) -> Dict[str, Any]:
    """
    Soruyu analiz ederek departman, mod, risk ve niyet belirler.
    
    Args:
        question: Kullanıcı sorusu
    
    Returns:
        dict: {"dept": str, "mode": str, "risk": str, "intent": str, "needs_web": bool}
    """
    q = question.lower()
    
    # 1. Akıllı niyet tespiti
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