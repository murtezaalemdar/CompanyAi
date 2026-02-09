"""Prompt Templates - Kurumsal AI Asistanı (Sadeleştirilmiş)

Mistral 7B CPU için optimize edilmiş kısa ve net prompt'lar.
Uzun prompt = kötü yanıt. Kısa prompt = iyi yanıt.
"""


# ── Ana sistem prompt'u — KISA ve NET ──
SYSTEM_PROMPT = """Sen Company.AI adlı bir kurumsal asistansın. Türkçe konuş.

Kurallar:
- Samimi ve doğal konuş, robot gibi değil.
- Sohbette kısa ve sıcak cevap ver.
- İş sorusunda yapılandırılmış, detaylı cevap ver.
- Bilmediğini uydurma, bilmiyorum de.
- Departman: {department} | Mod: {mode}"""


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
    
    system = SYSTEM_PROMPT.format(department=department, mode=mode)
    
    dept_prompt = DEPARTMENT_PROMPTS.get(department, "")
    if dept_prompt:
        system += f"\n{dept_prompt}"
    
    mode_prompt = MODE_PROMPTS.get(mode, "")
    if mode_prompt:
        system += f"\n{mode_prompt}"
    
    return system, question


def build_rag_prompt(question: str, context: dict, documents: list = None) -> tuple[str, str]:
    """RAG dokümanları ile prompt oluşturur."""
    system, user = build_prompt(question, context)
    
    if documents:
        doc_text = "\n\nİlgili dokümanlar:\n"
        for i, doc in enumerate(documents[:3], 1):
            source = doc.get('source', '?')
            content = doc.get('content', '')[:400]
            doc_text += f"[{source}]: {content}\n"
        doc_text += "\nYukarıdaki dokümanlara dayanarak yanıt ver."
        system += doc_text
    
    return system, user
