"""Merkezi İşlem Motoru - Tüm AI sorgu işlemleri burada koordine edilir

RAG (Retrieval Augmented Generation) entegrasyonu ile zenginleştirilmiş versiyon.
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

logger = structlog.get_logger()


async def process_question(
    question: str, 
    department_override: Optional[str] = None,
    use_rag: bool = True
) -> dict:
    """
    Ana soru işleme fonksiyonu.
    
    Akış:
    1. Router ile departman ve mod belirleme
    2. RAG ile ilgili dokümanları bulma (varsa)
    3. Geçmiş sorguları hatırlama
    4. LLM ile yanıt üretme
    5. Yanıtı hafızaya kaydetme
    
    Args:
        question: Kullanıcı sorusu
        department_override: Opsiyonel departman override
        use_rag: RAG kullanılsın mı
    
    Returns:
        İşlenmiş yanıt dict
    """
    logger.info("processing_question", question=question[:100])
    
    # 1. Departman ve mod belirleme
    context = decide(question)
    
    # Override varsa uygula
    if department_override:
        context["dept"] = department_override
    
    # 2. RAG ile ilgili dokümanları bul
    relevant_docs = []
    if use_rag and RAG_AVAILABLE:
        try:
            relevant_docs = search_documents(question, n_results=3)
            if relevant_docs:
                logger.info("rag_documents_found", count=len(relevant_docs))
        except Exception as e:
            logger.error("rag_search_error", error=str(e))
    
    # 3. Geçmiş sorguları hatırla
    history = recall()
    
    # 4. Prompt oluştur (RAG > Analysis > Basit sırasıyla)
    if relevant_docs:
        system_prompt, user_prompt = build_rag_prompt(question, context, relevant_docs)
    elif history:
        system_prompt, user_prompt = build_analysis_prompt(question, context, history)
    else:
        system_prompt, user_prompt = build_prompt(question, context)
    
    # 5. LLM'e sor
    try:
        # Ollama erişilebilir mi kontrol et
        if await ollama_client.is_available():
            # Sıcaklık ayarı (Profesyonel modlar için düşük, yaratıcı modlar için yüksek)
            temp = 0.3  # Varsayılan: Analitik ve tutarlı
            if context.get("mode") in ["Öneri", "Beyin Fırtınası"]:
                temp = 0.7
                
            llm_answer = await ollama_client.generate(
                prompt=user_prompt,
                system_prompt=system_prompt,
                temperature=temp,
            )
        else:
            # Fallback: Mock yanıt
            logger.warning("ollama_not_available", using_fallback=True)
            llm_answer = f"[Sistem Notu: LLM şu an erişilemez] Soru alındı: {question}"
    except Exception as e:
        logger.error("llm_error", error=str(e))
        llm_answer = f"[Hata] LLM yanıt üretemedi: {str(e)}"
    
    # 6. Sonucu oluştur
    result = {
        "answer": llm_answer,
        "department": context["dept"],
        "mode": context["mode"],
        "risk": context["risk"],
        "confidence": 0.85 if not relevant_docs else 0.92,  # RAG varsa daha yüksek güven
        "sources": [doc.get("source") for doc in relevant_docs] if relevant_docs else [],
    }
    
    # 7. Hafızaya kaydet
    remember(question, llm_answer, context)
    
    logger.info("question_processed", 
                department=context["dept"], 
                risk=context["risk"],
                rag_used=bool(relevant_docs))
    
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