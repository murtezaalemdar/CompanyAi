"""Merkezi İşlem Motoru - Tüm AI sorgu işlemleri burada koordine edilir

RAG + Web Arama + Semantik Hafıza + Kişiselleştirme
+ Tool Calling + Multi-Step Reasoning + Structured Output
+ Forecasting + KPI Engine + Textile Knowledge + Risk Analysis
"""

from typing import Optional
import re
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

# Export modülü
try:
    from app.core.export_service import detect_export_request, generate_export, FORMAT_LABELS
    EXPORT_AVAILABLE = True
except ImportError:
    EXPORT_AVAILABLE = False
    detect_export_request = lambda q: None

# ── YENİ MODÜLLER ──

# Tool Calling
try:
    from app.core.tool_registry import tool_registry, detect_tool_calls
    TOOLS_AVAILABLE = True
except ImportError:
    TOOLS_AVAILABLE = False
    tool_registry = None

# Multi-step Reasoning
try:
    from app.core.reasoning import needs_multi_step, plan_reasoning_steps, execute_reasoning_chain, format_reasoning_result
    REASONING_AVAILABLE = True
except ImportError:
    REASONING_AVAILABLE = False

# Structured Output
try:
    from app.llm.structured_output import force_json_output, auto_structure, get_schema_for_mode
    STRUCTURED_OUTPUT_AVAILABLE = True
except ImportError:
    STRUCTURED_OUTPUT_AVAILABLE = False

# KPI Engine
try:
    from app.core.kpi_engine import interpret_kpi_value, list_kpis, kpi_scorecard
    KPI_ENGINE_AVAILABLE = True
except ImportError:
    KPI_ENGINE_AVAILABLE = False

# Textile Knowledge
try:
    from app.core.textile_knowledge import get_glossary_term, analyze_waste, get_efficiency_loss_framework
    TEXTILE_AVAILABLE = True
except ImportError:
    TEXTILE_AVAILABLE = False

# Risk Analyzer
try:
    from app.core.risk_analyzer import assess_risk, risk_heatmap, fmea_analysis, build_risk_report_prompt
    RISK_AVAILABLE = True
except ImportError:
    RISK_AVAILABLE = False

# Reflection Layer (Self-Evaluation)
try:
    from app.core.reflection import quick_evaluate, build_retry_prompt, format_reflection_footer, format_confidence_badge
    REFLECTION_AVAILABLE = True
except ImportError:
    REFLECTION_AVAILABLE = False

# Multi-Agent Pipeline
try:
    from app.core.agent_pipeline import should_use_pipeline, execute_agent_pipeline, format_pipeline_summary
    AGENT_PIPELINE_AVAILABLE = True
except ImportError:
    AGENT_PIPELINE_AVAILABLE = False

# Scenario Engine
try:
    from app.core.scenario_engine import simulate_scenarios, project_financial_impact, format_scenario_table, format_financial_impact
    SCENARIO_AVAILABLE = True
except ImportError:
    SCENARIO_AVAILABLE = False

# Monte Carlo Risk Engine
try:
    from app.core.monte_carlo import monte_carlo_simulate, format_monte_carlo_table
    MONTE_CARLO_AVAILABLE = True
except ImportError:
    MONTE_CARLO_AVAILABLE = False

# Decision Impact Ranking
try:
    from app.core.decision_ranking import rank_decisions, extract_decisions_from_llm, format_ranking_table
    DECISION_RANKING_AVAILABLE = True
except ImportError:
    DECISION_RANKING_AVAILABLE = False

# AI Governance
try:
    from app.core.governance import governance_engine, format_governance_alert
    GOVERNANCE_AVAILABLE = True
except ImportError:
    GOVERNANCE_AVAILABLE = False
    governance_engine = None

# Experiment Layer (A/B + Cross-Dept)
try:
    from app.core.experiment_layer import simulate_ab_strategy, analyze_cross_dept_impact, format_ab_result, format_cross_dept_impact
    EXPERIMENT_AVAILABLE = True
except ImportError:
    EXPERIMENT_AVAILABLE = False

# Graph Impact Mapping
try:
    from app.core.graph_impact import auto_graph_analysis, format_graph_impact
    GRAPH_IMPACT_AVAILABLE = True
except ImportError:
    GRAPH_IMPACT_AVAILABLE = False

# ARIMA / SARIMA Forecasting (v3.3.0)
try:
    from app.core.forecasting import STATSMODELS_AVAILABLE as ARIMA_AVAILABLE
except ImportError:
    ARIMA_AVAILABLE = False

# SQL Generator
try:
    from app.core.sql_generator import generate_sql, build_sql_prompt
    SQL_AVAILABLE = True
except ImportError:
    SQL_AVAILABLE = False

# Model Registry (v3.4.0)
try:
    from app.core.model_registry import model_registry
    MODEL_REGISTRY_AVAILABLE = True
except ImportError:
    MODEL_REGISTRY_AVAILABLE = False
    model_registry = None

# Data Versioning (v3.4.0)
try:
    from app.core.data_versioning import data_version_manager
    DATA_VERSIONING_AVAILABLE = True
except ImportError:
    DATA_VERSIONING_AVAILABLE = False
    data_version_manager = None

# Human-in-the-Loop (v3.4.0)
try:
    from app.core.hitl import hitl_manager
    HITL_AVAILABLE = True
except ImportError:
    HITL_AVAILABLE = False
    hitl_manager = None

# Enhanced Monitoring (v3.4.0)
try:
    from app.core.monitoring import metrics_collector, alert_manager, get_full_telemetry, calculate_health_score
    MONITORING_AVAILABLE = True
except ImportError:
    MONITORING_AVAILABLE = False
    metrics_collector = None

# Textile Vision (v3.4.0)
try:
    from app.core.textile_vision import analyze_colors, analyze_pattern, compare_images, generate_quality_report, get_textile_vision_capabilities
    TEXTILE_VISION_AVAILABLE = True
except ImportError:
    TEXTILE_VISION_AVAILABLE = False

# Explainability / XAI (v3.4.0)
try:
    from app.core.explainability import decision_explainer
    XAI_AVAILABLE = True
except ImportError:
    XAI_AVAILABLE = False
    decision_explainer = None

logger = structlog.get_logger()


async def process_question(
    question: str, 
    department_override: Optional[str] = None,
    use_rag: bool = True,
    user_name: Optional[str] = None,
    user_department: Optional[str] = None,
    session_history: Optional[list] = None,
    memory_context: Optional[str] = None,
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
    # ÖNEMLİ: Kimlik/hafıza soruları ("beni tanıyor musun", "ismimi biliyor musun")
    # pattern matcher'a girmeden LLM'e yönlendirilir. Çünkü pattern matcher kullanıcı
    # ismi hafızasına erişemez, sadece LLM context'inde user_name bilgisi var.
    _is_identity_question = bool(re.search(
        r"(beni\s*tanı|ismimi|adımı|hatırlıyor|biliyor\s*mu|kim\s*olduğ|tanıyor\s*mu)",
        question.lower()
    ))
    
    if intent == "sohbet" and CHAT_EXAMPLES_AVAILABLE and not _is_identity_question:
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
    web_results = None
    web_rich_data = None
    if WEB_SEARCH_AVAILABLE and search_and_summarize:
        should_search_web = (
            needs_web or 
            (intent == "bilgi") or
            (intent == "iş" and not relevant_docs)
        )
        if should_search_web:
            try:
                web_results, web_rich_data = await search_and_summarize(question)
                if web_results:
                    logger.info("web_search_results_found", has_rich_data=web_rich_data is not None)
            except Exception as e:
                logger.warning("web_search_error", error=str(e))
    
    # 4. Prompt oluştur (KISA tut — Mistral 7B CPU)
    if relevant_docs:
        system_prompt, user_prompt = build_rag_prompt(question, context, relevant_docs)
    else:
        system_prompt, user_prompt = build_prompt(question, context)
    
    # Kişiselleştirme — kullanıcı kimliği (LLM bunun üzerinden hitap eder)
    if user_name:
        system_prompt += (f"\n\nÖNEMLİ: Şu an seninle konuşan kullanıcının adı '{user_name}'.\n"
                         f"Kullanıcı sana adını veya kim olduğunu sorarsa kesinlikle '{user_name}' olarak cevap ver.\n"
                         f"Her zaman kullanıcıya '{user_name.split()[0]}' diye hitap edebilirsin.")    
    # Kalıcı hafıza bağlamı — PostgreSQL'den gelen kullanıcı bilgileri + geçmiş
    if memory_context:
        system_prompt += f"\n\nKullanıcı Hafızası (geçmiş konusmalardan öğrenilen bilgiler):\n{memory_context}"    
    
    # Kullanıcı kimliği tekrar (LLM recency bias — son gelen bilgi güçlü)
    if user_name:
        system_prompt += f"\n\nHATIRLATMA: Kullanıcının adı kesinlikle '{user_name}'. Geçmiş konuşmalardaki farklı isimler BAŞKA kişilere aittir."
    
    # Web sonuçlarını prompt'a ekle
    if web_results:
        system_prompt += f"\n\nAşağıda internetten bulunan güncel bilgiler var. Bu bilgileri kullanarak yanıt ver:\n{web_results[:1500]}"
    
    # Chat history — system prompt'a DEĞİL, client'a ayrı gönder
    # Her intent'te (sohbet dahil) geçmişi gönder — "biraz daha basit anlat" gibi takip soruları için
    chat_history = []
    if session_history:
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
                max_tokens=512,
                history=chat_history if chat_history else None,
            )
        else:
            logger.warning("ollama_not_available", using_fallback=True)
            llm_answer = f"[Sistem Notu: LLM şu an erişilemez] Soru alındı: {question}"
    except Exception as e:
        logger.error("llm_error", error=str(e))
        llm_answer = f"[Hata] LLM yanıt üretemedi: {str(e)}"
    
    # ── 5b. TOOL CALLING — LLM çıktısında tool çağrısı var mı? ──
    tool_results = []
    if TOOLS_AVAILABLE and llm_answer and not llm_answer.startswith("[Hata]"):
        try:
            detected_tools = detect_tool_calls(llm_answer)
            if detected_tools:
                for tool_call in detected_tools[:3]:  # Max 3 tool
                    tool_name = tool_call.get("tool", "")
                    tool_params = tool_call.get("params", {})
                    result = tool_registry.execute(tool_name, tool_params)
                    if result and not result.get("error"):
                        tool_results.append({
                            "tool": tool_name,
                            "result": result,
                        })
                if tool_results:
                    # Tool sonuçlarını cevaba ekle
                    tool_text = "\n\n---\n📊 **Hesaplama Sonuçları:**\n"
                    for tr in tool_results:
                        tool_text += f"\n**{tr['tool']}**: {_format_tool_result(tr['result'])}"
                    llm_answer += tool_text
                    logger.info("tools_executed", count=len(tool_results))
        except Exception as e:
            logger.warning("tool_execution_error", error=str(e))
    
    # ── 5c. STRUCTURED OUTPUT — Analiz/Rapor modunda JSON yapılandırma ──
    structured_data = None
    if STRUCTURED_OUTPUT_AVAILABLE and context.get("mode") in ["Analiz", "Rapor", "Acil"]:
        try:
            structured_data = auto_structure(llm_answer)
            if structured_data and structured_data.get("sections"):
                logger.info("output_structured", sections=len(structured_data.get("sections", [])))
        except Exception as e:
            logger.debug("structured_output_skipped", error=str(e))
    
    # ── 5d. REFLECTION LAYER — Yanıt Kalite Kontrolü ──
    reflection_data = None
    dynamic_confidence = 0.85  # Default
    if REFLECTION_AVAILABLE and llm_answer and not llm_answer.startswith("[Hata]"):
        try:
            evaluation = quick_evaluate(llm_answer, question, context.get("mode", "Sohbet"))
            reflection_data = evaluation
            dynamic_confidence = evaluation["confidence"] / 100.0  # 0-1 arası
            
            # Düşük güvenli yanıtlarda retry (Analiz/Rapor/Öneri modunda)
            if evaluation.get("should_retry") and not llm_answer.startswith("[Hata]"):
                logger.info("reflection_retry_triggered", 
                           confidence=evaluation["confidence"],
                           issues=evaluation.get("issues", []))
                try:
                    retry_prompt = build_retry_prompt(question, evaluation)
                    retry_answer = await ollama_client.generate(
                        prompt=retry_prompt,
                        system_prompt=system_prompt,
                        temperature=0.2,
                        max_tokens=600,
                        history=chat_history if chat_history else None,
                    )
                    if retry_answer and len(retry_answer) > len(llm_answer) * 0.5:
                        llm_answer = retry_answer
                        # Retry sonrası tekrar değerlendir
                        evaluation = quick_evaluate(llm_answer, question, context.get("mode", "Sohbet"))
                        reflection_data = evaluation
                        dynamic_confidence = evaluation["confidence"] / 100.0
                        logger.info("reflection_retry_success", new_confidence=evaluation["confidence"])
                except Exception as retry_err:
                    logger.warning("reflection_retry_failed", error=str(retry_err))
            
            # Confidence badge — sadece Analiz/Rapor modlarında göster
            if context.get("mode") in ["Analiz", "Rapor", "Öneri", "Acil"]:
                badge = format_confidence_badge(evaluation["confidence"])
                llm_answer += f"\n\n---\n{badge}"
            
            logger.info("reflection_evaluated", 
                        confidence=evaluation["confidence"],
                        passed=evaluation["pass"])
        except Exception as e:
            logger.debug("reflection_skipped", error=str(e))
    
    # ── 5e. MULTI-AGENT PIPELINE — Karmaşık Analiz Sorularında ──
    pipeline_data = None
    if AGENT_PIPELINE_AVAILABLE and should_use_pipeline(question, context.get("mode", ""), intent):
        try:
            # Bağlam oluştur
            pipeline_context = ""
            if relevant_docs:
                pipeline_context = "\n".join(
                    doc.get("content", "")[:200] for doc in relevant_docs[:3]
                )
            if web_results:
                pipeline_context += f"\n{web_results[:500]}"
            
            pipeline_result = await execute_agent_pipeline(
                question=question,
                context=pipeline_context,
                llm_generate=ollama_client.generate,
                mode=context.get("mode", "Analiz"),
            )
            
            if pipeline_result and pipeline_result.final_answer:
                # Pipeline çıktısını ana yanıta ekle
                llm_answer += f"\n\n{pipeline_result.final_answer}"
                llm_answer += format_pipeline_summary(pipeline_result)
                pipeline_data = pipeline_result.to_dict()
                # Pipeline confidence ile override
                if pipeline_result.overall_confidence > dynamic_confidence * 100:
                    dynamic_confidence = pipeline_result.overall_confidence / 100.0
                logger.info("agent_pipeline_completed", 
                           agents=len(pipeline_result.agent_results))
        except Exception as e:
            logger.warning("agent_pipeline_error", error=str(e))
    
    # ── 5f. AI GOVERNANCE — Bias / Drift / Confidence Monitoring ──
    governance_data = None
    if GOVERNANCE_AVAILABLE and governance_engine and llm_answer and not llm_answer.startswith("[Hata]"):
        try:
            gov_record = governance_engine.evaluate(
                question=question,
                answer=llm_answer,
                mode=context.get("mode", "Sohbet"),
                confidence=dynamic_confidence * 100 if dynamic_confidence <= 1 else dynamic_confidence,
            )
            if gov_record.alert_triggered:
                alert_text = format_governance_alert(gov_record)
                if alert_text and context.get("mode") in ["Analiz", "Rapor", "Öneri", "Acil"]:
                    llm_answer += f"\n\n{alert_text}"
            governance_data = {
                "confidence": gov_record.confidence,
                "bias_score": gov_record.bias_score,
                "drift_detected": gov_record.drift_detected,
                "alert": gov_record.alert_reason if gov_record.alert_triggered else None,
            }
            logger.info("governance_evaluated", bias=gov_record.bias_score, drift=gov_record.drift_detected)
        except Exception as e:
            logger.debug("governance_skipped", error=str(e))
    
    # ── 5g. DECISION IMPACT RANKING — Analiz modunda kararları sırala ──
    ranking_data = None
    if DECISION_RANKING_AVAILABLE and llm_answer and context.get("mode") in ["Analiz", "Rapor", "Öneri"]:
        try:
            decisions = extract_decisions_from_llm(llm_answer, question)
            if decisions and len(decisions) >= 2:
                ranking_result = rank_decisions(decisions)
                ranking_table = format_ranking_table(ranking_result)
                llm_answer += f"\n{ranking_table}"
                ranking_data = {
                    "total": ranking_result.total_evaluated,
                    "top_action": ranking_result.top_action,
                }
                logger.info("decision_ranking_applied", count=len(decisions))
        except Exception as e:
            logger.debug("decision_ranking_skipped", error=str(e))
    
    # ── 5h. GRAPH IMPACT MAPPING — KPI/Risk/Departman ilişki grafiği ──
    graph_data = None
    if GRAPH_IMPACT_AVAILABLE and llm_answer and context.get("mode") in ["Analiz", "Rapor", "Öneri"]:
        try:
            graph_result = auto_graph_analysis(question, llm_answer)
            if graph_result and graph_result.total_nodes_affected > 0:
                graph_table = format_graph_impact(graph_result)
                llm_answer += f"\n{graph_table}"
                graph_data = {
                    "focus": graph_result.focus_node,
                    "affected": graph_result.total_nodes_affected,
                    "critical_chain": graph_result.critical_chain,
                }
                logger.info("graph_impact_applied", focus=graph_result.focus_node,
                           affected=graph_result.total_nodes_affected)
        except Exception as e:
            logger.debug("graph_impact_skipped", error=str(e))
    
    # 6. Sonuç
    sources = []
    if relevant_docs:
        sources.extend([doc.get("source") for doc in relevant_docs])
    if web_results:
        sources.append("İnternet Araması")
    
    # Rich data listesi
    rich_data = web_rich_data if web_rich_data else []
    if not isinstance(rich_data, list):
        rich_data = [rich_data]
    
    # 6b. Export talebi varsa dosya üret
    export_format = None
    if EXPORT_AVAILABLE:
        export_format = detect_export_request(question)
    
    if export_format and llm_answer and not llm_answer.startswith("[Hata]"):
        try:
            # Başlığı sorudan çıkar
            export_title = question.strip()[:60].rstrip("?.!")
            export_result = generate_export(llm_answer, export_format, export_title)
            if export_result:
                fmt_info = FORMAT_LABELS.get(export_format, {})
                rich_data.append({
                    "type": "export",
                    "file_id": export_result["file_id"],
                    "filename": export_result["filename"],
                    "format": export_format,
                    "format_label": fmt_info.get("label", export_format),
                    "format_icon": fmt_info.get("icon", "📄"),
                    "download_url": f"/api/export/download/{export_result['file_id']}",
                })
                logger.info("export_auto_generated", format=export_format, file_id=export_result["file_id"])
        except Exception as e:
            logger.warning("export_auto_failed", error=str(e))
    
    result = {
        "answer": llm_answer,
        "department": context["dept"],
        "mode": context["mode"],
        "risk": context["risk"],
        "intent": intent,
        "confidence": dynamic_confidence if REFLECTION_AVAILABLE else (0.85 if not relevant_docs else 0.92),
        "sources": sources,
        "web_searched": web_results is not None,
        "rich_data": rich_data if rich_data else None,
        "tool_results": tool_results if tool_results else None,
        "structured_data": structured_data,
        "reflection": reflection_data,
        "pipeline": pipeline_data,
        "governance": governance_data,
        "ranking": ranking_data,
        "graph_impact": graph_data,
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
        "modules": {
            "tools": TOOLS_AVAILABLE,
            "reasoning": REASONING_AVAILABLE,
            "structured_output": STRUCTURED_OUTPUT_AVAILABLE,
            "kpi_engine": KPI_ENGINE_AVAILABLE,
            "textile_knowledge": TEXTILE_AVAILABLE,
            "risk_analyzer": RISK_AVAILABLE,
            "reflection": REFLECTION_AVAILABLE,
            "agent_pipeline": AGENT_PIPELINE_AVAILABLE,
            "scenario_engine": SCENARIO_AVAILABLE,
            "monte_carlo": MONTE_CARLO_AVAILABLE,
            "decision_ranking": DECISION_RANKING_AVAILABLE,
            "governance": GOVERNANCE_AVAILABLE,
            "experiment_layer": EXPERIMENT_AVAILABLE,
            "graph_impact": GRAPH_IMPACT_AVAILABLE,
            "arima_forecasting": ARIMA_AVAILABLE,
            "sql_generator": SQL_AVAILABLE,
            "export": EXPORT_AVAILABLE,
            "web_search": WEB_SEARCH_AVAILABLE,
            "model_registry": MODEL_REGISTRY_AVAILABLE,
            "data_versioning": DATA_VERSIONING_AVAILABLE,
            "human_in_the_loop": HITL_AVAILABLE,
            "monitoring": MONITORING_AVAILABLE,
            "textile_vision": TEXTILE_VISION_AVAILABLE,
            "explainability": XAI_AVAILABLE,
        },
    }


def _format_tool_result(result: dict) -> str:
    """Tool sonucunu kullanıcı dostu formata çevir."""
    if not result:
        return ""
    
    parts = []
    for key, value in result.items():
        if key in ("error", "tool"):
            continue
        if isinstance(value, float):
            parts.append(f"{key}: {value:.2f}")
        elif isinstance(value, dict):
            inner = ", ".join(f"{k}: {v}" for k, v in value.items())
            parts.append(f"{key}: {{{inner}}}")
        elif isinstance(value, list):
            parts.append(f"{key}: {', '.join(str(v) for v in value[:5])}")
        else:
            parts.append(f"{key}: {value}")
    
    return " | ".join(parts) if parts else str(result)