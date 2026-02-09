"""Prompt Templates - Kurumsal AI Asistanı (Sadeleştirilmiş)

GPT-OSS-20B CPU için optimize edilmiş kısa ve net prompt'lar.
Uzun prompt = kötü yanıt. Kısa prompt = iyi yanıt.
"""

import re

# ── Prompt Injection Filtreleme ──
_INJECTION_PATTERNS = [
    r"ignore\s+(previous|above|all)\s+(instructions?|prompts?|rules?)",
    r"forget\s+(everything|all|your)\s+(instructions?|rules?|training)",
    r"you\s+are\s+now\s+(a|an|the)\s+",
    r"system\s*:\s*",
    r"<\|?\s*(system|im_start|im_end)\s*\|?>",
    r"act\s+as\s+(if|a|an)\s+",
    r"pretend\s+(you|that)\s+(are|were)\s+",
    r"override\s+(your|the|all)\s+(instructions?|rules?|behavior)",
]
_injection_regex = re.compile("|".join(_INJECTION_PATTERNS), re.IGNORECASE)


def sanitize_input(text: str) -> str:
    """Kullanıcı girdisinden prompt injection denemelerini temizle"""
    # Injection pattern'larını tespit et ama metni tamamen silme — sadece etiketle
    if _injection_regex.search(text):
        return f"[Kullanıcı sorusu]: {text}"
    return text


def sanitize_document_content(text: str) -> str:
    """RAG doküman içeriğinden tehlikeli pattern'ları temizle"""
    # System prompt injection denemelerini kaldır
    cleaned = re.sub(r"<\|?\s*(system|im_start|im_end)\s*\|?>", "", text)
    cleaned = re.sub(r"\[INST\]|\[/INST\]|\[SYS\]|\[/SYS\]", "", cleaned)
    return cleaned.strip()


# ── Ana sistem prompt'u — KISA ve NET ──
SYSTEM_PROMPT = """Sen Company.AI asistanısın. Türkçe konuş. Samimi ol, kısa cevap ver. Bilmediğini uydurma."""


# ── Departman prompt'ları — KISA ──
DEPARTMENT_PROMPTS = {
    "Üretim": "Tekstil üretimi konusunda bilgilisin: iplik, dokuma, boyahane, konfeksiyon.",
    "Finans": "Mali konularda yardımcı ol. Sayısal doğruluğa dikkat et.",
    "Yönetim": "Stratejik bakış açısı sun, KPI odaklı yanıt ver.",
    "İnsan Kaynakları": "Personel konularında yardımcı ol. KVKK'ya dikkat et.",
    "Satış": "Müşteri odaklı düşün, satış ve pazar analizi yap.",
    "IT": "Teknik konularda yardımcı ol, güvenliğe dikkat et.",
}


# ── Mod talimatları — KISA ──
MODE_PROMPTS = {
    "Sohbet": "Kısa ve samimi cevap ver. Madde/başlık kullanma.",
    "Bilgi": "Bilgilendirici cevap ver. Kaynak varsa belirt.",
    "Analiz": "Detaylı analiz yap. Veri ve yapılandırılmış format kullan.",
    "Özet": "Maksimum 3-4 cümle ile özetle.",
    "Öneri": "Somut, uygulanabilir öneriler sun.",
    "Rapor": "Yapılandırılmış rapor formatında yaz.",
    "Acil": "Kısa ve net, hemen aksiyon odaklı yanıt ver.",
}


def build_prompt(question: str, context: dict) -> tuple[str, str]:
    """System ve user prompt oluşturur."""
    department = context.get("dept", "Genel")
    mode = context.get("mode", "Sohbet")
    
    # Kullanıcı girdisini sanitize et
    safe_question = sanitize_input(question)
    
    # Temel system prompt — KISA
    system = SYSTEM_PROMPT
    
    # Sadece iş/analiz modunda ek talimat ekle
    if mode not in ("Sohbet", None):
        mode_prompt = MODE_PROMPTS.get(mode, "")
        if mode_prompt:
            system += f" {mode_prompt}"
    
    # Departman bilgisi sadece iş sorularında
    if department != "Genel" and mode not in ("Sohbet", None):
        dept_prompt = DEPARTMENT_PROMPTS.get(department, "")
        if dept_prompt:
            system += f" {dept_prompt}"
    
    return system, safe_question


def build_rag_prompt(question: str, context: dict, documents: list = None) -> tuple[str, str]:
    """RAG dokümanları ile prompt oluşturur."""
    system, user = build_prompt(question, context)
    
    if documents:
        doc_text = "\n\nİlgili dokümanlar:\n"
        for i, doc in enumerate(documents[:3], 1):
            source = doc.get('source', '?')
            content = sanitize_document_content(doc.get('content', '')[:400])
            doc_text += f"[{source}]: {content}\n"
        doc_text += "\nYukarıdaki dokümanlara dayanarak yanıt ver."
        system += doc_text
    
    return system, user
