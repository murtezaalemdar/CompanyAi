"""Merkezi İşlem Motoru - Tüm AI sorgu işlemleri burada koordine edilir

RAG + Web Arama + Semantik Hafıza + Kişiselleştirme
"""

from typing import Optional
import structlog

from app.router.router import decide
from app.llm.client import ollama_client
from app.llm.prompts import build_prompt, build_rag_prompt
from app.memory.vector_memory import remember, recall, search_memory

# Few-shot sohbet örnekleri
try:
    from app.llm.chat_examples import get_pattern_response, get_few_shot_examples
    CHAT_EXAMPLES_AVAILABLE = True
except ImportError:
    CHAT_EXAMPLES_AVAILABLE = False
    get_pattern_response = lambda q: None
    get_few_shot_examples = lambda q, c=2: ""

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
    
    # ── HIZLI SOHBET YOLU ── Kalıp eşleşmesi varsa LLM'e gitmeden cevapla
    if intent == "sohbet" and CHAT_EXAMPLES_AVAILABLE:
        pattern_answer = get_pattern_response(question)
        if pattern_answer:
            # Kişiselleştirme ekle
            if user_name and "{name}" not in pattern_answer:
                # İsimle hitap et (rastgele, her seferinde değil)
                import random
                if random.random() < 0.4:
                    first_name = user_name.split()[0] if user_name else ""
                    if first_name:
                        pattern_answer = f"{first_name}, {pattern_answer[0].lower()}{pattern_answer[1:]}"
            
            logger.info("fast_pattern_response", pattern=True)
            remember(question, pattern_answer, context)
            return {
                "answer": pattern_answer,
                "department": context["dept"],
                "mode": "Sohbet",
                "risk": context["risk"],
                "intent": "sohbet",
                "confidence": 0.95,
                "sources": ["Kalıp Eşleşmesi"],
                "web_searched": False,
            }
    
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
    
    # RAG araması (sohbet dışında + sadece SORU varsa)
    # "fabrikamızın adı X" gibi bilgi verme cümlelerinde RAG çalıştırma
    is_statement = not any(c in question for c in "??") and len(question.split()) < 10
    if use_rag and RAG_AVAILABLE and intent != "sohbet" and not is_statement:
        try:
            raw_docs = search_documents(question, n_results=3)
            # Alakasız dokümanları filtrele (distance skoru yüksekse = alakasız)
            if raw_docs:
                for doc in raw_docs:
                    score = doc.get('distance', doc.get('score', 999))
                    # ChromaDB distance: düşük = benzer. 1.0'dan büyükse alakasız.
                    if score < 1.0:
                        relevant_docs.append(doc)
                if relevant_docs:
                    logger.info("rag_documents_found", count=len(relevant_docs))
                else:
                    logger.info("rag_documents_filtered_out", raw=len(raw_docs))
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
    
    # 4. Prompt oluştur (KISA tut — Mistral 7B CPU)
    if relevant_docs:
        system_prompt, user_prompt = build_rag_prompt(question, context, relevant_docs)
    else:
        system_prompt, user_prompt = build_prompt(question, context)
    
    # Kişiselleştirme — tek satır
    if user_name:
        system_prompt += f"\nKullanıcı: {user_name}"
    
    # Web sonuçlarını KISA ekle
    if web_results:
        system_prompt += f"\nWeb bilgisi: {web_results[:300]}"
    
    # Chat history — system prompt'a DEĞİL, client'a ayrı gönder
    chat_history = []
    if intent != "sohbet" and session_history:
        chat_history = session_history[-5:]
    
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
                history=chat_history if chat_history else None,
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