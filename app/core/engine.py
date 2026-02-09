"""Merkezi İşlem Motoru - Tüm AI sorgu işlemleri burada koordine edilir

RAG + Web Arama + Semantik Hafıza + Kişiselleştirme
"""

from typing import Optional
import structlog

from app.router.router import decide
from app.llm.client import ollama_client
from app.llm.prompts import build_prompt, build_rag_prompt, build_analysis_prompt
from app.memory.vector_memory import remember, recall, search_memory

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
    use_rag: bool = True,
    user_name: Optional[str] = None,
    user_department: Optional[str] = None,
    session_history: Optional[list] = None,
) -> dict:
    """
    Ana soru işleme fonksiyonu — Akıllı Pipeline.
    
    Akış:
    1. Router ile niyet analizi
    2. Semantik hafıza — benzer geçmiş konuşmalar
    3. Niyete göre bilgi kaynakları (RAG / Web / Hafıza)
    4. Kişiselleştirilmiş prompt oluşturma
    5. LLM yanıt üretme
    6. Otomatik öğrenme (hafıza + web → RAG)
    """
    logger.info("processing_question", question=question[:100])
    
    # 1. Akıllı yönlendirme
    context = decide(question)
    intent = context.get("intent", "sohbet")
    needs_web = context.get("needs_web", False)
    
    if department_override:
        context["dept"] = department_override
    
    # Kullanıcı bilgisi
    if user_name:
        context["user_name"] = user_name
    if user_department:
        context["user_dept"] = user_department
    
    logger.info("intent_detected", intent=intent, mode=context["mode"], 
                dept=context["dept"], needs_web=needs_web)
    
    # 2. Semantik hafıza — soruya EN BENZER geçmiş konuşmalar
    similar_memories = []
    try:
        similar_memories = search_memory(question, limit=3)
        if similar_memories:
            logger.info("similar_memories_found", count=len(similar_memories))
    except Exception as e:
        logger.warning("memory_search_error", error=str(e))
    
    # 3. Bilgi kaynaklarını topla
    relevant_docs = []
    web_results = None
    
    # RAG araması (sohbet dışında)
    if use_rag and RAG_AVAILABLE and intent != "sohbet":
        try:
            relevant_docs = search_documents(question, n_results=3)
            if relevant_docs:
                logger.info("rag_documents_found", count=len(relevant_docs))
        except Exception as e:
            logger.error("rag_search_error", error=str(e))
    
    # Web araması
    if WEB_SEARCH_AVAILABLE and search_and_summarize:
        should_search_web = (
            needs_web or 
            (intent == "bilgi") or
            (intent == "iş" and not relevant_docs)
        )
        if should_search_web:
            try:
                web_results = await search_and_summarize(question)
                if web_results:
                    logger.info("web_search_results_found")
            except Exception as e:
                logger.warning("web_search_error", error=str(e))
    
    # 4. Prompt oluştur
    # Konuşma oturumu veya semantik hafızayı history olarak kullan
    effective_history = session_history or []
    
    # Semantik hafızadan ilgili konuşmaları ekle
    if similar_memories:
        for mem in similar_memories:
            score = mem.get("similarity_score", 0)
            if score > 0.3:  # Benzerlik eşiği
                effective_history.append({
                    "q": mem.get("q", ""),
                    "a": mem.get("a", ""),
                })
    
    if relevant_docs:
        system_prompt, user_prompt = build_rag_prompt(question, context, relevant_docs)
    elif effective_history:
        system_prompt, user_prompt = build_analysis_prompt(question, context, effective_history)
    else:
        system_prompt, user_prompt = build_prompt(question, context)
    
    # Kişiselleştirme ekle
    if user_name:
        system_prompt += f"\nKullanıcının adı: {user_name}. Gerekirse adıyla hitap et.\n"
    
    # Web sonuçlarını prompt'a ekle
    if web_results:
        system_prompt += web_results
    
    # 5. LLM'e sor
    try:
        if await ollama_client.is_available():
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
    
    # 6. Sonuç
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
    
    # 7. Hafızaya kaydet (öğrenme)
    remember(question, llm_answer, context)
    
    # 8. Otomatik öğrenme: Web sonuçlarını RAG'a kaydet
    if web_results and RAG_AVAILABLE:
        try:
            _auto_learn_from_web(question, web_results)
        except Exception as e:
            logger.warning("auto_learn_failed", error=str(e))
    
    logger.info("question_processed", 
                intent=intent,
                department=context["dept"], 
                rag_used=bool(relevant_docs),
                web_used=web_results is not None,
                memories_used=len(similar_memories))
    
    return result


def _auto_learn_from_web(question: str, web_text: str):
    """Web'den bulunan bilgiyi RAG'a kaydet — bir sonraki sefere daha hızlı"""
    try:
        from app.rag.vector_store import add_document
        
        # Web sonuçlarını temizle ve kaydet
        clean_text = web_text.replace("## 🌐 İnternet Araması Sonuçları:\n", "").strip()
        if len(clean_text) > 50:  # Çok kısa ise kaydetme
            add_document(
                content=clean_text,
                source=f"web_search: {question[:80]}",
                metadata={
                    "type": "web_learned",
                    "original_query": question,
                    "auto_learned": True,
                }
            )
            logger.info("auto_learned_from_web", query=question[:60])
    except (ImportError, Exception) as e:
        logger.debug("auto_learn_skipped", reason=str(e))


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