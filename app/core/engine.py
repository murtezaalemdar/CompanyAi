"""Merkezi İşlem Motoru - Tüm AI sorgu işlemleri burada koordine edilir

RAG + Web Arama + Akıllı Hafıza entegrasyonu.
"""

from typing import Optional
import structlog

from app.router.router import decide
from app.llm.client import ollama_client
from app.llm.prompts import build_prompt, build_rag_prompt, build_analysis_prompt
from app.memory.vector_memory import remember, recall

# RAG modülünü güvenli şekilde import et
try:
    from app.rag.vector_store import search_documents, get_stats as get_rag_stats
    RAG_AVAILABLE = True
except ImportError:
    RAG_AVAILABLE = False
    search_documents = lambda q, n=3: []
    get_rag_stats = lambda: {"available": False}

# Web arama modülü
try:
    from app.llm.web_search import search_and_summarize
    WEB_SEARCH_AVAILABLE = True
except ImportError:
    WEB_SEARCH_AVAILABLE = False
    search_and_summarize = None

logger = structlog.get_logger()


async def process_question(
    question: str, 
    department_override: Optional[str] = None,
    use_rag: bool = True
) -> dict:
    """
    Ana soru işleme fonksiyonu — Akıllı Pipeline.
    
    Akış:
    1. Router ile niyet, departman, mod belirleme
    2. Niyete göre bilgi kaynaklarını seç:
       - Sohbet → direkt LLM (hafıza ile)
       - İş → RAG dokümanları + hafıza
       - Bilgi → Web arama + RAG + hafıza 
    3. LLM ile yanıt üretme
    4. Hafızaya kaydetme (öğrenme)
    
    Args:
        question: Kullanıcı sorusu
        department_override: Opsiyonel departman override
        use_rag: RAG kullanılsın mı
    
    Returns:
        İşlenmiş yanıt dict
    """
    logger.info("processing_question", question=question[:100])
    
    # 1. Akıllı yönlendirme
    context = decide(question)
    intent = context.get("intent", "sohbet")
    needs_web = context.get("needs_web", False)
    
    if department_override:
        context["dept"] = department_override
    
    logger.info("intent_detected", intent=intent, mode=context["mode"], 
                dept=context["dept"], needs_web=needs_web)
    
    # 2. Bilgi kaynaklarını topla
    relevant_docs = []
    web_results = None
    history = recall()
    
    # RAG araması (sohbet dışı sorularda)
    if use_rag and RAG_AVAILABLE and intent != "sohbet":
        try:
            relevant_docs = search_documents(question, n_results=3)
            if relevant_docs:
                logger.info("rag_documents_found", count=len(relevant_docs))
        except Exception as e:
            logger.error("rag_search_error", error=str(e))
    
    # Web araması (bilgi sorularında veya RAG sonuç bulamadığında)
    if WEB_SEARCH_AVAILABLE and search_and_summarize:
        should_search_web = (
            needs_web or 
            (intent == "bilgi") or
            (intent == "iş" and not relevant_docs)  # RAG boşsa web'e bak
        )
        if should_search_web:
            try:
                web_results = await search_and_summarize(question)
                if web_results:
                    logger.info("web_search_results_found")
            except Exception as e:
                logger.warning("web_search_error", error=str(e))
    
    # 3. Prompt oluştur
    if relevant_docs:
        system_prompt, user_prompt = build_rag_prompt(question, context, relevant_docs)
    elif history:
        system_prompt, user_prompt = build_analysis_prompt(question, context, history)
    else:
        system_prompt, user_prompt = build_prompt(question, context)
    
    # Web sonuçlarını prompt'a ekle
    if web_results:
        system_prompt += web_results
    
    # 4. LLM'e sor
    try:
        if await ollama_client.is_available():
            # Sıcaklık: Sohbet/bilgi → doğal, İş → tutarlı
            temp = 0.3
            if context.get("mode") in ["Sohbet", "Bilgi", "Öneri", "Beyin Fırtınası"]:
                temp = 0.7
                
            llm_answer = await ollama_client.generate(
                prompt=user_prompt,
                system_prompt=system_prompt,
                temperature=temp,
            )
        else:
            logger.warning("ollama_not_available", using_fallback=True)
            llm_answer = f"[Sistem Notu: LLM şu an erişilemez] Soru alındı: {question}"
    except Exception as e:
        logger.error("llm_error", error=str(e))
        llm_answer = f"[Hata] LLM yanıt üretemedi: {str(e)}"
    
    # 5. Sonucu oluştur
    sources = []
    if relevant_docs:
        sources.extend([doc.get("source") for doc in relevant_docs])
    if web_results:
        sources.append("İnternet Araması")
    
    result = {
        "answer": llm_answer,
        "department": context["dept"],
        "mode": context["mode"],
        "risk": context["risk"],
        "intent": intent,
        "confidence": 0.85 if not relevant_docs else 0.92,
        "sources": sources,
        "web_searched": web_results is not None,
    }
    
    # 6. Hafızaya kaydet (öğrenme!)
    remember(question, llm_answer, context)
    
    logger.info("question_processed", 
                intent=intent,
                department=context["dept"], 
                rag_used=bool(relevant_docs),
                web_used=web_results is not None)
    
    return result


async def get_system_status() -> dict:
    """Sistem durumu özeti"""
    llm_available = await ollama_client.is_available()
    models = await ollama_client.get_models() if llm_available else []
    memory_size = len(recall())
    
    # RAG durumu
    rag_stats = get_rag_stats() if RAG_AVAILABLE else {"available": False}
    
    return {
        "llm_available": llm_available,
        "llm_model": ollama_client.model,
        "available_models": models,
        "memory_entries": memory_size,
        "rag": rag_stats,
    }