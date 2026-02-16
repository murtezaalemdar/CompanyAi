"""
╔══════════════════════════════════════════════════════════════════════╗
║  CompanyAI — Bilgi Çıkarma ve Otomatik Öğrenme Motoru              ║
║  knowledge_extractor.py  (v1.0.0)                                  ║
╠══════════════════════════════════════════════════════════════════════╣
║                                                                      ║
║  AMAÇ:                                                               ║
║  Sistemdeki HER bilgi kaynağından (sohbet, doküman, video, ses,     ║
║  URL, düzeltme, AI yanıtı) otomatik bilgi çıkarıp ChromaDB'ye      ║
║  kaydetmek. Kullanıcının "öğren" demesine GEREK YOK.               ║
║                                                                      ║
║  MİMARİ:                                                             ║
║  ┌───────────────┐     ┌──────────────────┐    ┌──────────────┐     ║
║  │ Kullanıcı     │────>│ Bilgi Çıkarıcı   │───>│ ChromaDB     │     ║
║  │ (chat/ses/    │     │ (knowledge_      │    │ (RAG store)  │     ║
║  │  doküman/url) │     │  extractor)      │    │              │     ║
║  └───────────────┘     └──────────────────┘    └──────────────┘     ║
║         │                      │                       │             ║
║         │              ┌───────┴────────┐              │             ║
║         │              │ Sınıflandırma: │              │             ║
║         │              │ • fact         │              │             ║
║         │              │ • process      │              │             ║
║         │              │ • preference   │              │             ║
║         │              │ • correction   │              │             ║
║         │              │ • definition   │              │             ║
║         │              │ • conversation │              │             ║
║         │              └────────────────┘              │             ║
║         │                                              │             ║
║         └──────── Soru sorulduğunda ◄──────────────────┘             ║
║                   RAG search ile                                     ║
║                   bilgi geri döner                                   ║
║                                                                      ║
║  ÖĞRENME KAYNAKLARI:                                                 ║
║  1. Chat mesajları (kullanıcı → AI)                                  ║
║  2. AI yanıtları (değerli/faydalı olanlar)                          ║
║  3. Soru-Cevap çiftleri (tüm Q&A)                                  ║
║  4. Doküman yüklemeleri (PDF/DOCX/XLSX)                             ║
║  5. Video transkriptleri (YouTube)                                   ║
║  6. URL web içerikleri                                               ║
║  7. Sesli konuşma transkriptleri                                     ║
║  8. Düzeltme/güncelleme mesajları                                    ║
║                                                                      ║
║  FİLTRELEME (kaydetMEMESİ gerekenler):                             ║
║  ✗ Selamlaşma ("merhaba", "nasılsın")                               ║
║  ✗ Tek kelimelik tepkiler ("ok", "tamam", "evet")                   ║
║  ✗ Saf sorular (bilgi İÇERMEYEN sorular)                           ║
║  ✗ Hata mesajları, sistem notları                                    ║
║  ✗ Çok kısa/anlamsız mesajlar (<20 karakter)                        ║
║                                                                      ║
╚══════════════════════════════════════════════════════════════════════╝
"""

import re
import structlog
from typing import Optional

logger = structlog.get_logger()

# ── RAG modülü ──
try:
    from app.rag.vector_store import add_document as rag_add_document
    RAG_AVAILABLE = True
except ImportError:
    RAG_AVAILABLE = False
    rag_add_document = lambda *a, **k: False


# ═══════════════════════════════════════════════════════════════
# 1. AKILLI FİLTRELEME — Kaydetmeye DEĞMEYECEK mesajları ayıkla
# ═══════════════════════════════════════════════════════════════

# Selamlaşma ve anlamsız kısa mesajlar
SKIP_PATTERNS = re.compile(
    r'^(?:merhaba|selam|hey|hi|hello|günaydın|iyi\s*(?:akşam|gece)lar?|'
    r'hoşça\s*kal|bye|bb|görüşürüz|iyi\s*günler|'
    r'ok|tamam|evet|hayır|olur|anladım|teşekkür|sağol|eyw|'
    r'peki|hm+|hmm+|aha|heh|şey|ya|yani|ee+|aa+|'
    r'güzel|harika|süper|mükemmel|iyi|kötü|fena|idare\s*eder|'
    r'nasılsın|ne\s*haber|naber|n[aı]b[eə]r|ne\s*var\s*ne\s*yok|'
    r'sen\s*nasılsın|iyi\s*misin|'
    r'\?+|!+|\.+|\.\.\.)$',
    re.IGNORECASE
)

# Saf soru kalıpları — bilgi İÇERMEYEN sorular (bunları kaydetme)
PURE_QUESTION_PATTERNS = re.compile(
    r'^(?:ne(?:dir|ler|rede|den|ye|yin)?|'
    r'kim(?:dir)?|nasıl|neden|niçin|niye|hangi|kaç|'
    r'ne\s+zaman|nere(?:de|ye|den|si)|'
    r'(?:ne|kim|nasıl|neden|kaç).*\?$)',
    re.IGNORECASE
)

# Sistem hata mesajları
SYSTEM_NOISE = re.compile(
    r'(?:\[Hata\]|\[Sistem\s*Notu\]|LLM\s*(?:şu\s*an|erişilemez)|'
    r'traceback|exception|error\s*code|status\s*\d{3})',
    re.IGNORECASE
)


# ═══════════════════════════════════════════════════════════════
# 2. BİLGİ SINIFLANDIRMA — Mesajdaki bilgi türünü belirle
# ═══════════════════════════════════════════════════════════════

# Fakt / Gerçek bilgiler (sayısal, somut veriler)
FACT_PATTERNS = re.compile(
    r'(?:'
    # Sayısal veriler
    r'\d+(?:\.\d+)?(?:\s*(?:ton|kg|metre|m²|adet|kişi|TL|USD|EUR|₺|\$|€|%|yıl|ay|gün|saat))'
    r'|(?:toplam|yıllık|aylık|günlük|haftalık)\s+\d+'
    # Tarih/yıl bilgileri
    r'|(?:19|20)\d{2}\s*(?:yılında|senesinde|\'(?:de|da|ten|dan))?'
    # İletişim bilgileri
    r'|\d{3}[\s-]?\d{3}[\s-]?\d{2}[\s-]?\d{2}'  # Telefon
    r'|[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'  # E-posta
    # Konum/adres
    r'|(?:adres|konum|merkez|fabrika|şube)[\s:]+[A-ZÇĞİÖŞÜ]'
    r')',
    re.IGNORECASE
)

# Süreç / Prosedür bilgileri
PROCESS_PATTERNS = re.compile(
    r'(?:'
    r'(?:önce|sonra|ardından|sırasıyla|adım\s*\d|aşama\s*\d)'
    r'|(?:süreç|prosedür|iş\s*akış|workflow|pipeline|yöntem|metod|usul)'
    r'|(?:yapılır|yapılmalı|yapılması\s*gerek|uygulanır|uygulanmalı)'
    r'|(?:birinci|ikinci|üçüncü|dördüncü|beşinci)\s+(?:olarak|adım|aşama)'
    r'|(?:\d+[\.\)]\s+[A-ZÇĞİÖŞÜa-zçğıöşü])'  # Numaralı listeler
    r')',
    re.IGNORECASE
)

# Tanım / Açıklama bilgileri
DEFINITION_PATTERNS = re.compile(
    r'(?:'
    r'(?:demek(?:tir)?|anlamına\s*gelir|(?:ne\s*)?demek\s*(?:ki|oluyor))'
    r'|(?:tanım[ıi]|açıklama[sı]|kısaca|özetle|yani|başka\s*bir\s*deyişle)'
    r'|(?:olarak\s+(?:tanımlan|bilin|adlandırıl))'
    r'|(?:[A-ZÇĞİÖŞÜ][a-zçğıöşü]+(?:\s+[A-ZÇĞİÖŞÜ][a-zçğıöşü]+)*\s*[,:;]\s+)'  # Terim: açıklama
    r')',
    re.IGNORECASE
)

# Düzeltme / Güncelleme bilgileri
CORRECTION_PATTERNS = re.compile(
    r'(?:'
    r'hayır\s*[,.]?\s*(?:aslında|doğrusu|gerçekte|tam\s*olarak)'
    r'|yanlış\s*[,.]?\s*(?:doğrusu|aslında|öyle\s*değil)'
    r'|düzeltme\s*:|güncelleme\s*:|revize\s*:'
    r'|(?:bu|o|şu)\s*(?:yanlış|hatalı|eksik|güncel\s*değil)'
    r'|(?:artık|bundan\s*sonra|değişti|güncellendi)\s'
    r')',
    re.IGNORECASE
)

# Şirket / Kurum bilgileri (ÇOOOK GENİŞ — her şeyi yakala)
COMPANY_PATTERNS = re.compile(
    r'(?:'
    # Sahiplik/kurumsallık
    r'(?:şirket|firma|işletme|fabrika|kurum|kuruluş|marka|holding)(?:imiz|mız|nız)?'
    r'|(?:biz(?:im)?|bizde(?:ki)?|bizler)'
    r'|(?:(?:ürün|hizmet|müşteri|tedarikçi|personel|çalışan|departman|birim|bölüm)(?:lerimiz|imiz|ımız|umuz|ümüz)?)'
    r'|(?:müdür|direktör|genel\s*müdür|patron|sahip|ortak)(?:ümüz|imiz)?'
    # Operasyonel
    r'|(?:üret(?:im|iyoruz|tik)|sat(?:ış|ıyoruz)|ihracat|ithalat|dağıt|sevk|depo|stok)'
    r'|(?:ciro|gelir|kâr|zarar|bütçe|maliyet|fiyat)(?:ımız|imiz)?'
    r'|(?:kalite|standart|sertifika|ISO|CE|OEKO|GOTS|GRS)'
    r'|(?:makine|tezgah|hat|loom|ring|open-end|rapier|jacquard)'
    # Sektör terminolojisi
    r'|(?:iplik|kumaş|boya|boyahane|terbiye|apre|konfeksiyon|dokuma|örme|triko)'
    r'|(?:pamuk|polyester|viskon|modal|tencel|lycra|elastan|akrilik|yün|keten|ipek)'
    r'|(?:sipariş|order|müşteri(?:\s*talebi)?|teklif|numune|metraj|gramaj|en|desen)'
    r')',
    re.IGNORECASE
)

# Tercih / Karar bilgileri
PREFERENCE_PATTERNS = re.compile(
    r'(?:'
    r'(?:tercih|seç|karar|belirledi|onayladı|kabul\s*(?:etti|edildi))'
    r'|(?:kullanıyoruz|kullanıyorum|geçtik|geçiyoruz|aldık|alıyoruz)'
    r'|(?:benimsedik|uygulamaya\s*(?:koyduk|geçtik))'
    r'|(?:(?:yeni|eski|mevcut)\s+(?:sistem|yazılım|yöntem|süreç))'
    r')',
    re.IGNORECASE
)

# Kişi / Organizasyon bilgileri
PERSON_ORG_PATTERNS = re.compile(
    r'(?:'
    r'(?:[A-ZÇĞİÖŞÜ][a-zçğıöşü]+\s+(?:Bey|Hanım|müdür|şef|mühendis|uzman|sorumlu))'
    r'|(?:(?:satın\s*alma|İK|HR|muhasebe|pazarlama|üretim|kalite|lojistik|IT|ar-ge)\s+(?:birimi|departmanı|ekibi|müdürlüğü))'
    r')',
    re.IGNORECASE
)


def classify_knowledge(text: str) -> Optional[str]:
    """
    Metnin bilgi türünü sınıflandır.
    
    Returns:
        Bilgi türü string'i veya None (kaydetmeye değmiyorsa)
        
    Sınıflar:
        'fact'        — Sayısal, somut, ölçülebilir bilgi
        'process'     — Süreç, prosedür, iş akışı
        'definition'  — Tanım, açıklama, terim
        'correction'  — Düzeltme, güncelleme
        'company'     — Şirket/kurum bilgisi
        'preference'  — Tercih, karar
        'person_org'  — Kişi/organizasyon bilgisi
        'general'     — Genel bilgi (yukarıdakilere uymayan ama yeterli uzunlukta)
    """
    if not text or len(text.strip()) < 20:
        return None
    
    t = text.strip()
    
    # Filtrele — kaydetmeye değmeyen mesajlar
    if SKIP_PATTERNS.match(t):
        return None
    if SYSTEM_NOISE.search(t):
        return None
    
    # Saf soru kontrolü — BİLGİ İÇERMEYEN soru ise kaydetme
    # Ama: bilgi de içeren sorular (cevaplı) kaydedilmeli
    if t.endswith('?') and len(t) < 80 and PURE_QUESTION_PATTERNS.match(t):
        return None
    
    # Bilgi türünü belirle (öncelik sırası)
    if CORRECTION_PATTERNS.search(t):
        return 'correction'
    if FACT_PATTERNS.search(t):
        return 'fact'
    if PROCESS_PATTERNS.search(t):
        return 'process'
    if DEFINITION_PATTERNS.search(t):
        return 'definition'
    if COMPANY_PATTERNS.search(t):
        return 'company'
    if PERSON_ORG_PATTERNS.search(t):
        return 'person_org'
    if PREFERENCE_PATTERNS.search(t):
        return 'preference'
    
    # Yeterince uzun mesajlar (50+ karakter) genel bilgi olarak kaydet
    # Kısa mesajları (20-50 karakter) kaydetme (genellikle tepki/onay)
    if len(t) >= 50:
        return 'general'
    
    return None


# ═══════════════════════════════════════════════════════════════
# 3. ANA ÖĞRENME FONKSİYONLARI
# ═══════════════════════════════════════════════════════════════

def learn_from_user_message(
    message: str,
    user_name: str = None,
    department: str = None,
) -> bool:
    """
    Kullanıcının HER mesajından bilgi çıkar ve kaydet.
    "Öğren" demesine gerek yok — otomatik algıla.
    
    Args:
        message: Kullanıcının yazdığı mesaj
        user_name: Kullanıcı adı  
        department: Kullanıcının departmanı
        
    Returns:
        True eğer bilgi kaydedildiyse
    """
    if not RAG_AVAILABLE:
        return False
    
    knowledge_type = classify_knowledge(message)
    if not knowledge_type:
        return False
    
    # v4.4.0: Kalite filtresi
    if not _should_save(message, knowledge_type):
        return False
    
    author = user_name or "Anonim"
    
    success = rag_add_document(
        content=message.strip(),
        source=f"chat_user_{knowledge_type}_{author}",
        doc_type="chat_learned",
        metadata={
            "type": "chat_learned",
            "knowledge_type": knowledge_type,
            "learn_source": "user_message",
            "author": author,
            "department": department or "Genel",
        }
    )
    
    if success:
        logger.info("learned_from_user",
                    knowledge_type=knowledge_type,
                    author=author,
                    content_len=len(message))
    return success


def learn_from_ai_response(
    question: str,
    answer: str,
    user_name: str = None,
    department: str = None,
    had_rag_docs: bool = False,
) -> bool:
    """
    AI'ın VERDİĞİ yanıttan bilgi çıkar ve kaydet.
    Böylece AI kendi ürettiği bilgiyi de hatırlar.
    
    Sadece FAYDALI yanıtları kaydeder:
    - RAG dokümanlarından alıntı yapan yanıtlar (zaten var, kaydetme)
    - Genel/kısa yanıtlar (kaydetme)
    - Somut bilgi, analiz, öneri içeren yanıtlar (kaydet)
    
    Soru + Cevap birlikte kaydedilir = gelecekte benzer sorularda hatırlar.
    """
    if not RAG_AVAILABLE:
        return False
    
    # RAG'dan gelen yanıtları tekrar kaydetme (döngü olur)
    if had_rag_docs:
        return False
    
    # Hata mesajlarını kaydetme
    if not answer or answer.startswith(("[Hata]", "[Sistem")):
        return False
    
    # Çok kısa yanıtları kaydetme
    if len(answer) < 80:
        return False
    
    # Kalıp yanıtlarını kaydetme
    if '💡' in answer and 'hafızama kaydedildi' in answer:
        return False
    
    # Yanıtın bilgi değeri var mı?
    answer_type = classify_knowledge(answer)
    if not answer_type:
        return False
    
    # v4.4.0: Kalite filtresi
    if not _should_save(answer, answer_type):
        return False
    
    # Soru + Cevap çiftini birlikte kaydet
    combined = f"Soru: {question}\n\nCevap: {answer}"
    author = user_name or "Sistem"
    
    success = rag_add_document(
        content=combined,
        source=f"chat_qa_{answer_type}_{author}",
        doc_type="qa_learned",
        metadata={
            "type": "qa_learned",
            "knowledge_type": answer_type,
            "learn_source": "ai_response",
            "question": question[:200],
            "author": author,
            "department": department or "Genel",
        }
    )
    
    if success:
        logger.info("learned_from_ai_response",
                    knowledge_type=answer_type,
                    question_len=len(question),
                    answer_len=len(answer))
    return success


def learn_from_conversation(
    question: str,
    answer: str,
    user_name: str = None,
    department: str = None,
    had_rag_docs: bool = False,
) -> dict:
    """
    Tek bir konuşma turunu (soru + cevap) analiz et ve öğren.
    
    Bu fonksiyon HER konuşma turunda çağrılmalıdır:
    1. Kullanıcı mesajından bilgi çıkar
    2. AI yanıtından bilgi çıkar  
    3. Sonuç özetini döndür
    
    Returns:
        {"user_learned": bool, "ai_learned": bool, "knowledge_type": str|None}
    """
    result = {
        "user_learned": False,
        "ai_learned": False,
        "knowledge_type": None,
    }
    
    if not RAG_AVAILABLE:
        return result
    
    # Kullanıcı mesajından öğren
    user_type = classify_knowledge(question)
    if user_type:
        result["knowledge_type"] = user_type
        result["user_learned"] = learn_from_user_message(
            question, user_name, department
        )
    
    # AI yanıtından öğren (sadece RAG'sız yanıtlarda — döngüyü engelle)
    if not had_rag_docs:
        result["ai_learned"] = learn_from_ai_response(
            question, answer, user_name, department, had_rag_docs
        )
    
    return result


def learn_from_voice_transcript(
    transcript: str,
    user_name: str = None,
    department: str = None,
) -> bool:
    """
    Sesli konuşma transkriptinden bilgi çıkar ve kaydet.
    
    Sesli mesajlar genelde daha doğal ve bilgi yoğun olur.
    Minimum uzunluk eşiğini düşür (sesli mesajlar daha kısa olabilir).
    """
    if not RAG_AVAILABLE or not transcript:
        return False
    
    t = transcript.strip()
    if len(t) < 15:
        return False
    
    # Sesli mesajlarda selamlaşmayı filtrele ama bilgi eşiğini düşür
    if SKIP_PATTERNS.match(t):
        return False
    
    knowledge_type = classify_knowledge(t)
    if not knowledge_type:
        # Sesli mesajlarda eşik daha düşük — 30+ karakter bile kaydet
        if len(t) >= 30:
            knowledge_type = "voice_general"
        else:
            return False
    
    author = user_name or "Anonim"
    
    success = rag_add_document(
        content=t,
        source=f"voice_{knowledge_type}_{author}",
        doc_type="voice_learned",
        metadata={
            "type": "voice_learned",
            "knowledge_type": knowledge_type,
            "learn_source": "voice_transcript",
            "author": author,
            "department": department or "Genel",
        }
    )
    
    if success:
        logger.info("learned_from_voice",
                    knowledge_type=knowledge_type,
                    author=author,
                    content_len=len(t))
    return success


def learn_from_file_context(
    filename: str,
    question: str,
    extracted_text: str,
    user_name: str = None,
    department: str = None,
) -> bool:
    """
    Multimodal endpoint'te dosya ile birlikte gelen soru bağlamını kaydet.
    
    Dosya içeriği zaten upload sırasında kaydedilir, ama kullanıcının
    dosya hakkında sorduğu sorular ve bağlam da değerli bilgi.
    """
    if not RAG_AVAILABLE:
        return False
    
    if not question or len(question.strip()) < 15:
        return False
    
    # Dosya + soru bağlamını birlikte kaydet
    context = f"Dosya: {filename}\nKullanıcı sorusu/bağlamı: {question}"
    if extracted_text and len(extracted_text) > 50:
        # Çıkarılan metnin özeti (ilk 500 karakter)
        context += f"\nDosya içeriği özeti: {extracted_text[:500]}"
    
    author = user_name or "Anonim"
    
    success = rag_add_document(
        content=context,
        source=f"file_context_{filename}_{author}",
        doc_type="file_context",
        metadata={
            "type": "file_context",
            "knowledge_type": "file_interaction",
            "learn_source": "multimodal",
            "filename": filename,
            "author": author,
            "department": department or "Genel",
        }
    )
    
    if success:
        logger.info("learned_from_file_context",
                    filename=filename,
                    author=author)
    return success


# ═══════════════════════════════════════════════════════════════
# 4. YARDIMCI FONKSİYONLAR
# ═══════════════════════════════════════════════════════════════

# v4.4.0: Öğrenme Kalite Filtresi — düşük kaliteli bilgiyi kaydetme
MIN_QUALITY_SCORE = 0.35  # Minimum kalite skoru (0-1)


def score_knowledge_quality(text: str, knowledge_type: str = None) -> float:
    """Bilginin kalitesini 0-1 arası skorla (v4.4.0).
    
    Kriterler:
    - Uzunluk (uzun = daha değerli, genellikle)
    - Spesifiklik (sayısal veri, isim, terim = daha spesifik)
    - Yapı (cümle yapısı, listeler = daha yapılandırılmış)
    - Bilgi yoğunluğu (farklı bilgi tipi sayısı)
    
    Returns:
        0.0 - 1.0 arası kalite skoru
    """
    if not text or len(text.strip()) < 15:
        return 0.0
    
    t = text.strip()
    score = 0.0
    
    # 1. Uzunluk skoru (0-0.25) — logaritmik
    import math
    length_score = min(0.25, math.log(len(t) + 1) / 30)
    score += length_score
    
    # 2. Spesifiklik (0-0.30) — sayısal veri, özel isimler, teknik terimler
    specificity = 0.0
    # Sayısal veri
    numbers = re.findall(r'\d+(?:[.,]\d+)?', t)
    specificity += min(0.10, len(numbers) * 0.02)
    # Büyük harfle başlayan kelimeler (özel isim, terim)
    proper_nouns = re.findall(r'\b[A-ZÇĞİÖŞÜ][a-zçğıöşü]{2,}', t)
    specificity += min(0.10, len(proper_nouns) * 0.015)
    # Teknik terimler / birimler
    tech_terms = re.findall(
        r'(?:ton|kg|metre|m²|adet|TL|USD|EUR|%|RPM|bar|°C|pH|dtex|Ne|Nm|denier)',
        t, re.IGNORECASE
    )
    specificity += min(0.10, len(tech_terms) * 0.03)
    score += specificity
    
    # 3. Yapı skoru (0-0.25) — cümle, liste, tablo yapısı
    structure = 0.0
    sentences = re.split(r'[.!?]\s+', t)
    structure += min(0.10, len(sentences) * 0.02)
    # Listeler (numaralı veya madde işaretli)
    list_items = re.findall(r'(?:^|\n)\s*(?:\d+[\.\)]\s|[-•*]\s)', t)
    structure += min(0.10, len(list_items) * 0.025)
    # Anahtar-değer çiftleri
    kv_pairs = re.findall(r'\w+\s*[:=]\s*\S+', t)
    structure += min(0.05, len(kv_pairs) * 0.015)
    score += structure
    
    # 4. Bilgi yoğunluğu (0-0.20) — farklı bilgi türleri
    density = 0.0
    type_checks = [
        (FACT_PATTERNS, 0.05),
        (PROCESS_PATTERNS, 0.04),
        (DEFINITION_PATTERNS, 0.04),
        (COMPANY_PATTERNS, 0.04),
        (CORRECTION_PATTERNS, 0.03),
    ]
    for pattern, bonus in type_checks:
        if pattern.search(t):
            density += bonus
    score += min(0.20, density)
    
    # Bilgi tipi bonusu
    type_bonus = {
        'correction': 0.10,  # Düzeltmeler çok değerli
        'fact': 0.08,
        'process': 0.07,
        'company': 0.06,
        'definition': 0.05,
        'preference': 0.04,
        'person_org': 0.04,
        'general': 0.0,
    }
    if knowledge_type:
        score += type_bonus.get(knowledge_type, 0)
    
    return round(min(1.0, score), 3)


def _should_save(text: str, knowledge_type: str) -> bool:
    """Kalite filtresi geçen bilgiyi kaydet mi? (v4.4.0)"""
    quality = score_knowledge_quality(text, knowledge_type)
    if quality < MIN_QUALITY_SCORE:
        logger.debug("knowledge_quality_too_low",
                     quality=quality, threshold=MIN_QUALITY_SCORE,
                     knowledge_type=knowledge_type, 
                     text_preview=text[:60])
        return False
    return True


def get_learning_stats() -> dict:
    """Öğrenme istatistiklerini döndür"""
    try:
        from app.rag.vector_store import get_stats
        stats = get_stats()
        return {
            "total_documents": stats.get("total_documents", 0),
            "available": stats.get("available", False),
            "learning_active": RAG_AVAILABLE,
        }
    except Exception:
        return {"total_documents": 0, "available": False, "learning_active": False}
