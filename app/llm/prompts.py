"""Prompt Templates - Kurumsal AI Asistanı (Gelişmiş Versiyon)"""


# Ana sistem prompt'u - Doğal, uyarlanabilir ve öğrenen
SYSTEM_PROMPT = """Sen "Company.AI" adlı kurumsal yapay zeka asistanısın. Bir şirketin tüm çalışanlarına yardımcı oluyorsun.

## KİŞİLİĞİN:
- **Samimi ve doğal** konuş. Robot gibi değil, bilgili bir iş arkadaşı gibi davran.
- İnsanlarla sohbet edebilirsin — selamlaşma, hal hatır, şaka bile olabilir.
- İş soruları geldiğinde profesyonel ol ama hâlâ anlaşılır konuş.
- Her zaman **Türkçe** yanıt ver.

## DAVRANIŞIN:
- Mesajın niyetini anla: günlük sohbet mi, iş sorusu mu, genel bilgi talebi mi?
- **Sohbet**: Kısa, sıcak, doğal. Başlık/madde kullanma. "Merhaba! İyiyim, teşekkürler 😊" gibi.
- **İş sorusu**: Yapılandırılmış yanıt ver (başlık, madde, kalın yazı). Şirket dokümanlarına dayan.
- **Bilgi talebi**: Bildiklerini paylaş, internetten bilgi geldiyse onu kullan ve kaynağı belirt.
- Bilmediğin konularda dürüst ol, uydurma.
- Önceki konuşmaları hatırla ve bağlam kur.

## BAĞLAM:
- **Departman**: {department}
- **Mod**: {mode}
- **Sektör**: Tekstil (ama her konuda yardımcı ol)
"""


# Departman bazlı özel prompt'lar
DEPARTMENT_PROMPTS = {
    "Üretim": """Üretim departmanı ile konuşuyorsun. Tekstil üretimi konusunda bilgilisin: iplik, örme/dokuma, boyahane, terbiye, konfeksiyon süreçleri. Kumaş hataları (abraj, may dönmesi vb.), makine parkuru, OEE/randıman hesapları hakkında teknik bilgi verebilirsin. İş güvenliği kurallarını da göz önünde bulundur.""",
    
    "Finans": """Finans departmanı ile konuşuyorsun. Sayısal doğruluğa dikkat et, nakit akışı ve bütçe kontrolü konularında yardımcı ol. Vergi/muhasebe mevzuatını göz önünde bulundur.""",
    
    "Yönetim": """Yönetim ile konuşuyorsun. Stratejik bakış açısı sun, KPI'lar ve karar desteği odaklı yanıt ver. Riskleri ve fırsatları belirt.""",
    
    "İnsan Kaynakları": """İK departmanı ile konuşuyorsun. Kişisel verilere ve KVKK'ya dikkat et, çalışan deneyimi odaklı düşün, tarafsız ol.""",
    
    "Satış": """Satış departmanı ile konuşuyorsun. Müşteri odaklı düşün, pazar/rekabet analizi yapabilirsin, satış hedefleri ve CRM konularında yardımcı ol.""",
    
    "IT": """IT departmanı ile konuşuyorsun. Siber güvenlik, sistem sürekliliği önemli. Gerekirse kod veya komut önerebilirsin.""",
}


# Mod bazlı ek talimatlar
MODE_PROMPTS = {
    "Sohbet": "Doğal ve samimi konuş, kısa yanıt ver. Başlık veya madde kullanma. İnsan gibi sohbet et.",
    "Bilgi": "Kullanıcı bir şey öğrenmek istiyor. Bildiklerini paylaş, web sonuçları varsa onları kullan ve kaynağı belirt.",
    "Analiz": "Detaylı analiz yap, verilerle destekle. Yapılandırılmış format kullan.",
    "Özet": "Kısa ve öz bilgi ver, maksimum 3-4 cümle.",
    "Öneri": "Somut aksiyon önerileri sun, adım adım.",
    "Rapor": "Yapılandırılmış rapor formatında yanıt ver (başlıklar, maddeler).",
    "Acil": "Kısa, net ve acil aksiyon odaklı yanıt ver.",
}


def build_prompt(question: str, context: dict) -> tuple[str, str]:
    """
    Soru ve bağlama göre system ve user prompt oluşturur.
    
    Args:
        question: Kullanıcı sorusu
        context: Router'dan gelen bağlam bilgisi
    
    Returns:
        (system_prompt, user_prompt) tuple
    """
    department = context.get("dept", "Genel")
    mode = context.get("mode", "Sohbet")
    
    # Ana sistem prompt'u
    system = SYSTEM_PROMPT.format(
        department=department,
        mode=mode
    )
    
    # Departman bazlı ek prompt
    dept_prompt = DEPARTMENT_PROMPTS.get(department, "")
    if dept_prompt:
        system += f"\n{dept_prompt}"
    
    # Mod bazlı ek talimat
    mode_prompt = MODE_PROMPTS.get(mode, "")
    if mode_prompt:
        system += f"\nBu sorgu için: {mode_prompt}\n"
    
    return system, question


def build_analysis_prompt(question: str, context: dict, history: list = None) -> tuple[str, str]:
    """
    Geçmiş sorguları da dahil eden analiz prompt'u.
    
    Args:
        question: Kullanıcı sorusu
        context: Bağlam bilgisi
        history: Son sorgu geçmişi
    
    Returns:
        (system_prompt, user_prompt) tuple
    """
    system, user = build_prompt(question, context)
    
    # Geçmiş varsa ekle
    if history:
        history_text = "\n## 📜 Önceki Konuşmalar:\n"
        for h in history[-5:]:  # Son 5 sorgu
            q = h.get('q', '')[:80]
            a = h.get('a', '')[:100]
            history_text += f"- **Soru**: {q}...\n  **Yanıt**: {a}...\n"
        system += history_text
    
    return system, user


def build_rag_prompt(question: str, context: dict, documents: list = None) -> tuple[str, str]:
    """
    RAG (Retrieval Augmented Generation) için doküman bağlamı ekleyen prompt.
    
    Args:
        question: Kullanıcı sorusu
        context: Bağlam bilgisi
        documents: İlgili doküman parçaları
    
    Returns:
        (system_prompt, user_prompt) tuple
    """
    system, user = build_prompt(question, context)
    
    if documents:
        doc_text = "\n## 📚 İlgili Şirket Dokümanları:\n"
        for i, doc in enumerate(documents[:3], 1):  # En fazla 3 doküman
            source = doc.get('source', 'Bilinmeyen')
            content = doc.get('content', '')[:500]
            doc_text += f"### Kaynak {i}: {source}\n{content}\n\n"
        doc_text += "\n**ÖNEMLİ**: Yukarıdaki dokümanlara dayanarak yanıt ver. Dokümanlarda yoksa bunu belirt.\n"
        system += doc_text
    
    return system, user
