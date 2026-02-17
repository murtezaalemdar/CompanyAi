"""Merkezi İşlem Motoru - Tüm AI sorgu işlemleri burada koordine edilir

RAG + Web Arama + Semantik Hafıza + Kişiselleştirme
+ Tool Calling + Multi-Step Reasoning + Structured Output
+ Forecasting + KPI Engine + Textile Knowledge + Risk Analysis
+ Module Synapse Network — Modüller Arası Öz-Öğrenen Zeka Ağı
+ Enterprise Platform: Event Bus, Orchestrator, Policy Engine,
  Observability 2.0, Security Layer

v5.9.0 DEĞİŞİKLİKLER (ÖNEMLİ — İŞE YARADI):
- Sıcaklık: Bilgi/Öneri 0.7 → 0.4 (halüsinasyon azalması)
- max_tokens: Analiz/Rapor 1024 → 2048 (kesilme sorunu çözüldü)
- Kullanıcı kimliği: 3x tekrar → 1 satır (token tasarrufu)
- Multi-perspective LLM çağrısı: Devre dışı (10-30 sn tasarruf)
- Post-processing: 12 bölüm cevaptan kaldırıldı → JSON metadata'da
  Korunan: confidence badge, sayısal doğrulama, OOD, politika, governance alert

TODO GELİŞTİRİLMELİ:
- [ ] Self-correction loop token maliyeti yüksek → sadece Analiz/Rapor'da aktif tut
- [ ] Kaldırılan 12 post-processing bölümü için frontend UI bileşenleri yok
- [ ] "Detaylı/Kısa cevap" kullanıcı tercihi ekle (post-processing gösterimi için)
- [ ] router.py regex pattern'leri çok geniş → false positive azalt
- [ ] Context window: 8K→12K test et (TPS etkisini ölç)
- [ ] Reflection LLM çağrısı (60-75% güven): token bütçesinin %20'sini aşmasın

═══════════════════════════════════════════════════════════════
  CompanyAI v5.5.0 — 49 AI Modül + 5 Enterprise Platform Katmanı
═══════════════════════════════════════════════════════════════

  #  Modül                        Puan   Satır   Sınıf  Not
  ── ─────────────────────────     ────   ─────   ─────  ──────────────────────────────────
  1  Tool Registry                 88     858      2     ReAct pattern, 8+ araç, Ollama function calling
  2  Reasoning                     86     650+     3     CoT zincir, varsayım çıkarma, argüman gücü, çelişki tespiti
  3  Structured Output             86     550+     2     JSON Schema Draft-7, oto-düzeltme, MD/CSV/YAML, şema önbellek
  4  KPI Engine                    85     442      0     50+ KPI, Balanced Scorecard, sektörel benchmark
  5  Textile Knowledge             80     373      0     200+ terim, fire analizi, kalite kontrol, kapasite
  6  Risk Analyzer                 82     339      1     FMEA, 5×5 matris, what-if, maliyet kırılım
  7  Reflection                    90     673      0     5 kriter kalite, hallucination algılama, auto-retry, sayısal doğrulama
  8  Agent Pipeline                78     554      2     6 uzman ajan, sequential + parallel pipeline
  9  Scenario Engine               86     600+     1     Tornado/hassasiyet, başabaş, Monte Carlo, stres testi, çok değişkenli
  10 Monte Carlo                   80     264      0     N-iterasyon simülasyon, VaR, CI, volatilite
  11 Decision Ranking              76     261      2     ROI×Risk×Strateji puanlama, priority bands
  12 Governance                    92     643      8     Bias algılama, drift izleme, 12 politika, hash chain audit
  13 Experiment Layer              86     700+     5     Welch t-test, ki-kare, Bayesian A/B, çok değişkenli, power analysis
  14 Graph Impact                  86     650+     6     PageRank, kaskad yayılım, what-if, döngü tespiti, hassasiyet
  15 ARIMA Forecasting             89     844      0     ARIMA/SARIMA, Holt-Winters, SES, anomaly detection
  16 SQL Generator                 77     409      0     Doğal dil→SQL, şema algılama, feature engineering
  17 Export Service                83     683      1     Excel/PDF/PPTX/Word/CSV, auto-cleanup, format algılama
  18 Web Search                    79     515      0     SerpAPI+Google+DuckDuckGo fallback, HTML scraping
  19 Model Registry                86     500+     3     Yaşam döngüsü, A/B karşılaştırma, regresyon tespiti, bağımlılık grafı
  20 Data Versioning               86     550+     3     Diff motoru, branching, rollback, çakışma tespiti
  21 Human-in-the-Loop             81     287      2     Yüksek riskli onay kuyruğu, feedback öğrenme
  22 Monitoring                    84     586      5     GPU/API/error izleme, z-score anomaly, SLA monitoring
  23 Textile Vision                86     600+     2     Batch analiz, renk tutarlılık (Delta-E), desen tekrar, trend takip
  24 Explainability                91     1209     3     XAI v4, faktör skoru, TF-IDF, PostgreSQL kayıt, kalibrasyon
  25 Bottleneck Engine             77     421      2     Süreç darboğaz, kaynak haritası, kuyruk analizi, iyileştirme
  26 Executive Health              82     688      2     Şirket sağlık skoru 0-100, 4 boyut, A+→F grade
  27 OCR Engine                    76     450      0     EasyOCR (TR+EN), etiket/fatura/tablo parse, PDF OCR
  28 Numerical Validation          86     480+     1     Birim farkındalıklı eşleştirme, yüzde tutarlılık, trend doğrulama
  29 Meta Learning                 93     824      7     Strategy profiling, knowledge gap, quality trend, failure mining
  30 Self Improvement              94     1042     12    ThresholdOptimizer, RAGTuner, PromptEvolver, auto-rollback
  31 Multi-Agent Debate            92     1098     11    6 perspektif ajan, round-robin, consensus, sentez
  32 Causal Inference              91     1208     18    5 Whys, Ishikawa, DAG, counterfactual, intervention analizi
  33 Strategic Planner             90     1171     19    PESTEL, Porter 5F, SMART, OKR, strateji formülasyonu
  34 Executive Intelligence        89     1008     19    CEO brifing, KPI korelasyon, RAPID/RACI, board raporu
  35 Knowledge Graph               88     944      13    Entity/relation extraction, BFS, kümeleme, bağlam zenginleştirme
  36 Decision Gatekeeper           87     635      12    PASS/WARN/BLOCK/ESCALATE, eskalasyon, risk sinyal toplama
  37 Uncertainty Quantification    85     404      9     Epistemik/Aleatoric, ensemble güven skoru, hata payı hesaplama
  38 Chart Engine                  78     350+     0     Matplotlib grafik üretimi, bar/line/pie, trend çizimi
  39 Decision Quality Score        88     500+     3     8-sinyal birleşik kalite skoru, güven bandı, yönetim özeti
  40 KPI Impact Mapping            87     550+     2     28 anahtar kelime→KPI eşleme, domino etki, finansal tahmin
  41 Decision Memory               86     500+     3     Karar hafızası, benzer karar arama, sonuç takibi, doğruluk raporu
  42 Executive Digest              85     400+     2     5 madde + Risk + Fırsat + Net Öneri format, öncelik sınıflandırma
  43 OOD Detector                  86     480+     2     Semantik yenilik, alan uyumu, yapısal normallik, OOD skor
  44 Module Synapse Network         90     700+     3     Nöral sinaps iletişim, Hebbian öğrenme, kaskad tetikleme, 40+ sinaps

  ─── GENEL ORTALAMA: 85.3 / 100 ───

  Toplam: ~27.700+ satır AI kodu, ~195+ sınıf, ~835+ fonksiyon/metot
  En güçlü: Self Improvement (94), Meta Learning (93), Governance (92),
            Multi-Agent Debate (92), Causal Inference (91), Explainability (91)
  Gelişime açık: Decision Ranking (76), OCR Engine (76)

  Son güncelleme: v5.4.0
═══════════════════════════════════════════════════════════════
"""

from typing import Optional
import re
import time
import structlog

from app.router.router import decide, async_decide
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
    from app.rag.vector_store import search_documents, agentic_search, get_stats as get_rag_stats, add_document as rag_add_document
    RAG_AVAILABLE = True
except ImportError:
    RAG_AVAILABLE = False
    search_documents = lambda q, n=3: []
    agentic_search = lambda q, n=5, d=None: []
    get_rag_stats = lambda: {"available": False}
    rag_add_document = lambda *a, **k: False

# Bilgi Çıkarma ve Otomatik Öğrenme Motoru
try:
    from app.core.knowledge_extractor import learn_from_conversation, learn_from_user_message
    KNOWLEDGE_EXTRACTOR_AVAILABLE = True
except ImportError:
    KNOWLEDGE_EXTRACTOR_AVAILABLE = False
    learn_from_conversation = lambda **k: {"user_learned": False, "ai_learned": False}
    learn_from_user_message = lambda *a, **k: False

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
    from app.core.tool_registry import tool_registry, detect_tool_calls, detect_tool_chain
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
    from app.core.reflection import quick_evaluate, build_retry_prompt, format_reflection_footer, format_confidence_badge, self_correction_loop
    REFLECTION_AVAILABLE = True
except ImportError:
    REFLECTION_AVAILABLE = False

# Sayısal Doğrulama Motoru (v4.4.0 → v5.2.0 standalone)
try:
    from app.core.numerical_validation import validate_numbers_against_source
    NUMERICAL_VALIDATION_AVAILABLE = True
except ImportError:
    try:
        from app.core.reflection import validate_numbers_against_source
        NUMERICAL_VALIDATION_AVAILABLE = True
    except ImportError:
        NUMERICAL_VALIDATION_AVAILABLE = False
        validate_numbers_against_source = None

# OCR Motor (v4.4.0)
try:
    from app.core.ocr_engine import extract_text_from_image, extract_text_from_image_bytes, EASYOCR_AVAILABLE
    OCR_AVAILABLE = EASYOCR_AVAILABLE
except ImportError:
    OCR_AVAILABLE = False

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

# Bottleneck Engine (v3.8.0)
try:
    from app.core.bottleneck_engine import analyze_from_data as bottleneck_analyze, format_bottleneck_report
    BOTTLENECK_AVAILABLE = True
except ImportError:
    BOTTLENECK_AVAILABLE = False

# Executive Health Index (v3.8.0)
try:
    from app.core.executive_health import calculate_health_index, format_health_dashboard
    EXECUTIVE_HEALTH_AVAILABLE = True
except ImportError:
    EXECUTIVE_HEALTH_AVAILABLE = False

# Insight Engine — Otomatik İçgörü (v3.9.0)
try:
    from app.core.insight_engine import extract_insights, format_insight_report, insights_to_dict
    INSIGHT_ENGINE_AVAILABLE = True
except ImportError:
    INSIGHT_ENGINE_AVAILABLE = False

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

# Token Budget Manager (v4.3.0)
try:
    from app.core.token_budget import truncate_to_budget, smart_truncate_all, estimate_tokens
    TOKEN_BUDGET_AVAILABLE = True
except ImportError:
    TOKEN_BUDGET_AVAILABLE = False
    truncate_to_budget = lambda text, section, **kw: text
    smart_truncate_all = None

# Meta Learning Engine (v4.6.0)
try:
    from app.core.meta_learning import meta_learning_engine, record_query_outcome
    META_LEARNING_AVAILABLE = True
except ImportError:
    META_LEARNING_AVAILABLE = False
    meta_learning_engine = None
    record_query_outcome = lambda **k: {}

# Self-Improvement Loop (v4.6.0)
try:
    from app.core.self_improvement import self_improvement_loop, on_query_completed as si_on_query_completed, get_threshold_override
    SELF_IMPROVEMENT_AVAILABLE = True
except ImportError:
    SELF_IMPROVEMENT_AVAILABLE = False
    self_improvement_loop = None
    si_on_query_completed = lambda **k: None
    get_threshold_override = lambda d, m: None

# Multi-Agent Debate (v4.7.0)
try:
    from app.core.multi_agent_debate import debate_engine, check_debate_trigger, get_debate_dashboard
    MULTI_AGENT_DEBATE_AVAILABLE = True
except ImportError:
    MULTI_AGENT_DEBATE_AVAILABLE = False
    debate_engine = None
    check_debate_trigger = lambda **k: (False, "unavailable")
    get_debate_dashboard = lambda: {"available": False}

# Causal Inference Engine (v4.7.0)
try:
    from app.core.causal_inference import causal_engine, check_causal_trigger, get_causal_dashboard
    CAUSAL_INFERENCE_AVAILABLE = True
except ImportError:
    CAUSAL_INFERENCE_AVAILABLE = False
    causal_engine = None
    check_causal_trigger = lambda **k: (False, "unavailable")
    get_causal_dashboard = lambda: {"available": False}

# Strategic Planner (v5.0.0)
try:
    from app.core.strategic_planner import strategic_planner, check_strategic_trigger, get_strategic_dashboard
    STRATEGIC_PLANNER_AVAILABLE = True
except ImportError:
    STRATEGIC_PLANNER_AVAILABLE = False
    strategic_planner = None
    check_strategic_trigger = lambda **k: (False, "unavailable")
    get_strategic_dashboard = lambda: {"available": False}

# Executive Intelligence (v5.0.0)
try:
    from app.core.executive_intelligence import executive_intelligence, check_executive_trigger, get_executive_dashboard
    EXECUTIVE_INTELLIGENCE_AVAILABLE = True
except ImportError:
    EXECUTIVE_INTELLIGENCE_AVAILABLE = False
    executive_intelligence = None
    check_executive_trigger = lambda **k: (False, "unavailable")
    get_executive_dashboard = lambda: {"available": False}

# Knowledge Graph (v5.0.0)
try:
    from app.core.knowledge_graph import knowledge_graph, check_kg_trigger, get_kg_dashboard
    KNOWLEDGE_GRAPH_AVAILABLE = True
except ImportError:
    KNOWLEDGE_GRAPH_AVAILABLE = False
    knowledge_graph = None
    check_kg_trigger = lambda **k: (False, "unavailable")
    get_kg_dashboard = lambda: {"available": False}

# Decision Risk Gatekeeper (v5.1.0)
try:
    from app.core.decision_gatekeeper import decision_gatekeeper, check_gate_trigger, get_gate_dashboard
    DECISION_GATEKEEPER_AVAILABLE = True
except ImportError:
    DECISION_GATEKEEPER_AVAILABLE = False
    decision_gatekeeper = None
    check_gate_trigger = lambda **k: (False, "unavailable")
    get_gate_dashboard = lambda: {"available": False}

# Uncertainty Quantification (v5.1.0)
try:
    from app.core.uncertainty_quantification import uncertainty_quantifier, check_uncertainty_trigger, get_uncertainty_dashboard
    UNCERTAINTY_AVAILABLE = True
except ImportError:
    UNCERTAINTY_AVAILABLE = False
    uncertainty_quantifier = None
    check_uncertainty_trigger = lambda **k: (False, "unavailable")
    get_uncertainty_dashboard = lambda: {"available": False}

# Decision Quality Score (v5.3.0)
try:
    from app.core.decision_quality import evaluate_decision_quality, format_quality_score, format_quality_badge
    DECISION_QUALITY_AVAILABLE = True
except ImportError:
    DECISION_QUALITY_AVAILABLE = False
    evaluate_decision_quality = None

# KPI Impact Mapping (v5.3.0)
try:
    from app.core.kpi_impact import analyze_kpi_impact, format_kpi_impact, format_kpi_impact_brief
    KPI_IMPACT_AVAILABLE = True
except ImportError:
    KPI_IMPACT_AVAILABLE = False
    analyze_kpi_impact = None

# Decision Memory (v5.3.0)
try:
    from app.core.decision_memory import store_decision, find_similar_decisions, format_similar_decisions
    DECISION_MEMORY_AVAILABLE = True
except ImportError:
    DECISION_MEMORY_AVAILABLE = False
    store_decision = None
    find_similar_decisions = None

# Executive Digest (v5.3.0)
try:
    from app.core.executive_digest import generate_executive_digest, format_executive_digest, format_digest_micro
    EXECUTIVE_DIGEST_AVAILABLE = True
except ImportError:
    EXECUTIVE_DIGEST_AVAILABLE = False
    generate_executive_digest = None

# OOD Detector (v5.3.0)
try:
    from app.core.ood_detector import check_ood, format_ood_warning, format_ood_badge
    OOD_DETECTOR_AVAILABLE = True
except ImportError:
    OOD_DETECTOR_AVAILABLE = False
    check_ood = None

# Module Synapse Network — Modüller Arası Öz-Öğrenen Zeka Ağı (v5.4.0)
try:
    from app.core.module_synapse import (
        create_pipeline_context, emit_signal, gather_module_inputs,
        check_cascades, finalize_context, format_signal_trace,
        format_network_summary, learn_from_outcome as synapse_learn
    )
    SYNAPSE_AVAILABLE = True
except ImportError:
    SYNAPSE_AVAILABLE = False
    create_pipeline_context = None

# ── v5.5.0 Enterprise Platform Katmanları ──

# Event Bus — Event-Driven Architecture + Event Sourcing
try:
    from app.core.event_bus import event_bus
    EVENT_BUS_AVAILABLE = True
except ImportError:
    EVENT_BUS_AVAILABLE = False
    event_bus = None

# Workflow Orchestrator — DAG-based durable workflows
try:
    from app.core.orchestrator import workflow_engine
    ORCHESTRATOR_AVAILABLE = True
except ImportError:
    ORCHESTRATOR_AVAILABLE = False
    workflow_engine = None

# Policy Engine — OPA-style JSON rule engine
try:
    from app.core.policy_engine import policy_engine as enterprise_policy_engine
    POLICY_ENGINE_AVAILABLE = True
except ImportError:
    POLICY_ENGINE_AVAILABLE = False
    enterprise_policy_engine = None

# Observability 2.0 — Decision drift, concept drift, latency profiling
try:
    from app.core.observability import observability
    OBSERVABILITY_AVAILABLE = True
except ImportError:
    OBSERVABILITY_AVAILABLE = False
    observability = None

# Security Layer — Zero-trust, prompt injection firewall, rate limiting
try:
    from app.core.security import security_layer
    SECURITY_AVAILABLE = True
except ImportError:
    SECURITY_AVAILABLE = False
    security_layer = None

# Decision Quality v5.5.0 — Outcome prediction recording
try:
    from app.core.decision_quality import record_prediction as dq_record_prediction
    DQ_OUTCOME_AVAILABLE = True
except ImportError:
    DQ_OUTCOME_AVAILABLE = False
    dq_record_prediction = None

# v6.02.00: PDF Görsel Desteği
try:
    from app.rag.pdf_images import (
        get_pdf_images_for_pages, get_all_pdf_images, PDF_IMAGES_DIR, _safe_dirname
    )
    PDF_IMAGES_AVAILABLE = True
except ImportError:
    PDF_IMAGES_AVAILABLE = False
    get_pdf_images_for_pages = lambda s, p: []
    get_all_pdf_images = lambda s: []

# v6.02.00: Görsel istemi algılama anahtar kelimeleri
_IMAGE_INTENT_KEYWORDS = {
    "resim", "resmini", "resimler", "resimlerini", "resminden",
    "görsel", "görseli", "görseller", "görsellerini",
    "fotoğraf", "fotoğrafı", "fotoğraflar", "fotoğrafını", "foto",
    "image", "picture", "photo",
    "göster", "gösterir",
}

def _detect_image_intent(question: str) -> bool:
    """Kullanıcının görsel isteyip istemediğini algıla (v6.02.00)"""
    q_lower = question.lower()
    words = set(re.findall(r'\w+', q_lower))
    return bool(words & _IMAGE_INTENT_KEYWORDS)


def _extract_page_numbers_from_chunk(content: str) -> list:
    """Chunk içeriğinden sayfa numaralarını çıkar (v6.02.00)
    
    '--- Sayfa N ---' marker'larını arar. OCR ile işlenmiş PDF'lerde
    her sayfa bu şekilde işaretlenmiştir.
    """
    pages = re.findall(r'---\s*Sayfa\s+(\d+)\s*---', content)
    return [int(p) for p in pages]


def _build_pdf_image_rich_data(question: str, relevant_docs: list) -> dict | None:
    """
    RAG sonuçlarından PDF görsellerini rich_data formatında döndür (v6.02.00).
    
    Akış:
    1. relevant_docs'tan PDF kaynaklarını bul
    2. Chunk'lardan sayfa numaralarını çıkar
    3. İlgili sayfalardaki görselleri al
    4. ImageResultsCard formatında rich_data döndür
    """
    if not PDF_IMAGES_AVAILABLE or not relevant_docs:
        return None
    
    all_images = []
    seen_sources = set()
    
    for doc in relevant_docs:
        source = doc.get("source", "")
        doc_type = doc.get("type", "")
        
        # Sadece PDF kaynaklarını işle
        if not source.lower().endswith(".pdf"):
            continue
        
        # Sayfa numaralarını chunk içeriğinden çıkar
        content = doc.get("content", "")
        page_numbers = _extract_page_numbers_from_chunk(content)
        
        if page_numbers:
            # Belirli sayfalardaki görselleri al
            images = get_pdf_images_for_pages(source, page_numbers)
        elif source not in seen_sources:
            # Sayfa bilgisi yoksa tüm görselleri al (max 6)
            images = get_all_pdf_images(source)[:6]
        else:
            continue
        
        seen_sources.add(source)
        all_images.extend(images)
    
    if not all_images:
        return None
    
    # Tekrarlayan görselleri kaldır
    unique_images = []
    seen_srcs = set()
    for img in all_images:
        if img["src"] not in seen_srcs:
            seen_srcs.add(img["src"])
            unique_images.append(img)
    
    # Maksimum 12 görsel
    unique_images = unique_images[:12]
    
    return {
        "type": "images",
        "query": question,
        "images": unique_images,
        "source": "PDF Doküman Görselleri",
    }

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
    6. OTOMATİK ÖĞRENME — Her konuşmadan bilgi çıkar ve RAG'a kaydet
       (kullanıcı mesajı + AI yanıtı → knowledge_extractor → ChromaDB)
    """
    logger.info("processing_question", question=question[:100])
    _t0 = time.time()  # Governance elapsed_ms için zamanlama
    
    # ── Synapse Network — Pipeline Context oluştur ──
    synapse_ctx = None
    if SYNAPSE_AVAILABLE and create_pipeline_context:
        synapse_ctx = create_pipeline_context(
            question=question,
            department=department_override or user_department or "",
        )

    # ═══ v5.5.0: Security Layer — Zero-trust giriş kontrolü ═══
    security_result = None
    if SECURITY_AVAILABLE and security_layer:
        try:
            security_result = security_layer.check_request(
                user_input=question,
                user_id=user_name or "anonymous",
                endpoint="query",
                model_name=getattr(ollama_client, 'model', 'unknown'),
                user_role="analyst",  # Default role — HITL'den gelecek
            )
            if security_result.get("blocked"):
                logger.warning("security_blocked",
                              reason=security_result.get("block_reason", "unknown"))
                return {
                    "answer": f"⛔ Güvenlik kontrolü başarısız: {security_result.get('block_reason', 'İstek engellendi')}",
                    "department": department_override or user_department or "genel",
                    "mode": "Güvenlik",
                    "risk": "yüksek",
                    "intent": "blocked",
                    "confidence": 0,
                    "sources": [],
                    "web_searched": False,
                    "security": security_result,
                }
            logger.debug("security_passed", threat_score=security_result.get("threat_score", 0))
        except Exception as sec_err:
            logger.debug("security_check_skipped", error=str(sec_err))

    # ═══ v5.5.0: Event Bus — Sorgu başlangıç olayı ═══
    _query_event_id = None
    if EVENT_BUS_AVAILABLE and event_bus:
        try:
            import uuid as _uuid
            _query_event_id = str(_uuid.uuid4())[:12]
            event_bus.emit("query.received", {
                "query_id": _query_event_id,
                "question": question[:200],
                "user": user_name or "anonymous",
                "department": department_override or user_department or "",
            })
        except Exception:
            pass
    
    # 1. Akıllı yönlendirme — v4.3.0: LLM-based router (primary) + regex (fallback)
    try:
        context = await async_decide(question)
    except Exception:
        context = decide(question)  # Fallback to sync regex
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
    
    # ══════════════════════════════════════════════════════════════
    # v5.7.0: SOHBET FAST-PATH — Enterprise modüller ATLANIR
    # Sohbet intent'inde pattern tutmayanlar için:
    #   Router → LLM çağrısı → hafızaya kaydet → dön
    # 30+ enterprise modül (governance, XAI, gatekeeper vb.) ÇALIŞMAZ.
    # Tahmini kazanç: 10-30x hız artışı (sohbet sorularında)
    # ══════════════════════════════════════════════════════════════
    if intent == "sohbet":
        logger.info("sohbet_fast_path", question=question[:80])
        
        # Hafıza bağlamı — sohbette de kullanıcıyı hatırlasın
        chat_system_prompt = (
            "Sen CompanyAI kurumsal yapay zeka asistanısın. "
            "Kullanıcıyla doğal, sıcak ve yardımcı bir şekilde sohbet et. "
            "Türkçe yanıt ver. Yanıtların 1-2 cümle olsun. "
            "Liste, başlık, madde KULLANMA. Kısa ve doğal konuş."
        )
        if user_name:
            chat_system_prompt += (
                f"\n\nKullanıcının adı: '{user_name}'. "
                f"Kullanıcıya '{user_name.split()[0]}' diye hitap edebilirsin."
            )
        if memory_context:
            chat_system_prompt += f"\n\nKullanıcı Hafızası:\n{memory_context}"
        
        # Session history — takip soruları için gerekli
        chat_history = []
        if session_history:
            chat_history = session_history[-5:]
        
        try:
            if await ollama_client.is_available():
                chat_answer = await ollama_client.generate(
                    prompt=question,
                    system_prompt=chat_system_prompt,
                    temperature=0.7,
                    max_tokens=512,
                    history=chat_history if chat_history else None,
                )
            else:
                chat_answer = "Şu an yanıt veremiyorum, biraz sonra tekrar dener misin?"
        except Exception as e:
            logger.error("sohbet_fast_path_llm_error", error=str(e))
            chat_answer = "Bir hata oluştu, tekrar dener misin?"
        
        # Hafızaya kaydet
        remember(question, chat_answer, context)
        
        # Arka planda öğrenme (event loop'u bloklamaz)
        if KNOWLEDGE_EXTRACTOR_AVAILABLE:
            import asyncio
            loop = asyncio.get_event_loop()
            loop.run_in_executor(None, _background_learn,
                question, chat_answer, user_name, context.get("dept"), False)
        
        logger.info("sohbet_fast_path_done", 
                    elapsed_ms=round((time.time() - _t0) * 1000, 1))
        
        return {
            "answer": chat_answer,
            "department": context["dept"],
            "mode": "Sohbet",
            "risk": context["risk"],
            "intent": "sohbet",
            "confidence": 0.90,
            "sources": [],
            "web_searched": False,
        }
    
    # ═════════════════════════════════════════════════════════════
    # İŞ / BİLGİ MODU — RAG + Web + LLM Pipeline
    # Sohbet atlandı (yukarıda fast-path ile döndü).
    # Bilgi modunda: RAG + Web + LLM → sonra enterprise modüller ATLANIR.
    # İş/Analiz/Rapor modunda: RAG + Web + LLM → enterprise modüller ÇALIŞIR.
    # ═════════════════════════════════════════════════════════════
    
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
    
    # RAG araması — Agentic RAG: karmaşık sorular alt parçalara ayrılır
    # Her alt parça bağımsız aranır, sonuçlar birleştirilip re-rank edilir
    if use_rag and RAG_AVAILABLE:
        try:
            raw_docs = agentic_search(question, n_results=5, department=department_override)
            # Hybrid skor filtreleme — vector_store zaten semantic + keyword
            # hybrid scoring yapıyor. Burada sadece tamamen alakasız olanları ele.
            if raw_docs:
                for doc in raw_docs:
                    hybrid = doc.get('relevance', 0)
                    dist = doc.get('distance', 999)
                    # Hybrid skor > 0.12 VEYA distance < 1.4 ise dahil et
                    # Eski eşikler (0.03/1.8) neredeyse hiçbir şeyi reddetmiyordu
                    if hybrid > 0.12 or dist < 1.4:
                        relevant_docs.append(doc)
                if relevant_docs:
                    logger.info("rag_documents_found", count=len(relevant_docs),
                                scores=[f"h={d.get('relevance',0):.3f}/d={d.get('distance',0):.2f}" for d in relevant_docs])
                else:
                    logger.info("rag_documents_filtered_out", raw=len(raw_docs),
                                scores=[f"h={d.get('relevance',0):.3f}/d={d.get('distance',0):.2f}" for d in raw_docs])
        except Exception as e:
            logger.error("rag_search_error", error=str(e))
    
    # Web araması — RAG'da iyi sonuç varsa web aramayı atla (öğretilen içerik öncelikli)
    web_results = None
    web_rich_data = None
    _rag_has_good = any(d.get('relevance', 0) > 0.12 or d.get('distance', 999) < 1.4 for d in relevant_docs) if relevant_docs else False
    if WEB_SEARCH_AVAILABLE and search_and_summarize and not _rag_has_good:
        should_search_web = (
            needs_web or 
            (intent == "bilgi" and not relevant_docs) or
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
    
    # v6.02.00: Görsel intent + varlık kontrolü — LLM'e KOŞULLU bilgi ver
    _has_pdf_images = False
    if _detect_image_intent(question) and relevant_docs and PDF_IMAGES_AVAILABLE:
        # Görsellerin disk üzerinde gerçekten mevcut olup olmadığını kontrol et
        _pre_image_card = _build_pdf_image_rich_data(question, relevant_docs)
        if _pre_image_card and _pre_image_card.get("images"):
            _has_pdf_images = True
            system_prompt += """

📸 GÖRSEL BİLGİSİ: Bu konuyla ilgili PDF dokümanlarından çıkarılmış görseller MEVCUT.
- "Metin tabanlı asistanım, görsel gösteremem" gibi şeyler SÖYLEME.
- Görsellerin yanıtla birlikte otomatik olarak aşağıda gösterildiğini belirt.
- Konu hakkında bildiklerini kısaca açıkla, "ilgili görselleri aşağıda bulabilirsiniz" de."""
    
    # Kişiselleştirme — kullanıcı kimliği (tek seferde, v5.9.0)
    if user_name:
        system_prompt += f"\n\nKullanıcının adı: '{user_name}'. Ona '{user_name.split()[0]}' diye hitap edebilirsin. Geçmiş konuşmalardaki farklı isimler başka kişilere aittir."
    
    # Kalıcı hafıza bağlamı — PostgreSQL'den gelen kullanıcı bilgileri + geçmiş
    if memory_context:
        system_prompt += f"\n\nKullanıcı Hafızası (geçmiş konusmalardan öğrenilen bilgiler):\n{memory_context}"    
    
    # Web sonuçlarını prompt'a ekle (RAG yoksa ana kaynak, RAG varsa ek referans)
    if web_results:
        _web_text = web_results[:1500]
        if TOKEN_BUDGET_AVAILABLE:
            _web_text = truncate_to_budget(_web_text, "web_results")
        if relevant_docs:
            system_prompt += f"\n\nEk referans (internetten): Aşağıdaki bilgiler tamamlayıcıdır. Önceliği yukarıdaki doküman bilgilerine ver:\n{_web_text}"
        else:
            system_prompt += f"\n\nAşağıda internetten bulunan güncel bilgiler var. Bu bilgileri kullanarak yanıt ver:\n{_web_text}"
    
    # v4.3.0: Token Bütçe Kontrolü — tüm bileşenleri bütçeye sığdır
    if TOKEN_BUDGET_AVAILABLE and smart_truncate_all:
        _memory_text = memory_context or ""
        _history_text = ""
        if session_history:
            _history_text = "\n".join(
                f"{m.get('role','?')}: {m.get('content','')[:200]}" 
                for m in session_history[-5:]
            )
        budget_result = smart_truncate_all(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            rag_context="",  # Zaten system_prompt içinde
            memory_context=_memory_text,
            web_results="",  # Zaten system_prompt içinde
            chat_history_text=_history_text,
        )
        system_prompt = budget_result["system_prompt"]
        user_prompt = budget_result["user_prompt"]
    
    # Chat history — system prompt'a DEĞİL, client'a ayrı gönder
    # Her intent'te (sohbet dahil) geçmişi gönder — "biraz daha basit anlat" gibi takip soruları için
    chat_history = []
    if session_history:
        chat_history = session_history[-5:]
    
    # 5. LLM'e sor
    try:
        if await ollama_client.is_available():
            # v5.9.1: Mod bazlı sıcaklık ve token limiti + detay algılama
            _mode = context.get("mode", "Sohbet")
            if _mode in ("Sohbet", "Beyin Fırtınası"):
                temp = 0.7
            elif _mode in ("Bilgi", "Öneri"):
                temp = 0.4
            else:  # Analiz, Rapor, Acil, Özet
                temp = 0.3
            
            # Kullanıcı detaylı yanıt mı istiyor?
            import re as _re
            _wants_detail = bool(_re.search(
                r'(detayl[ıi]|kapsaml[ıi]|ayr[ıi]nt[ıi]l[ıi]|madde\s*madde|listele|'
                r's[ıi]rala|a[çc][ıi]kla|t[üu]m|hepsini|tam\s*liste|uzun\s*anlat)',
                question.lower()
            ))
            
            if _mode in ("Analiz", "Rapor"):
                _max_tokens = 2048
            elif _wants_detail:
                _max_tokens = 1024  # Detay isteniyorsa biraz daha uzun
            elif _mode in ("Bilgi", "Öneri"):
                _max_tokens = 384   # Varsayılan kısa
            else:
                _max_tokens = 256   # Sohbet, Özet, Acil
                
            llm_answer = await ollama_client.generate(
                prompt=user_prompt,
                system_prompt=system_prompt,
                temperature=temp,
                max_tokens=_max_tokens,
                history=chat_history if chat_history else None,
            )
        else:
            logger.warning("ollama_not_available", using_fallback=True)
            llm_answer = f"[Sistem Notu: LLM şu an erişilemez] Soru alındı: {question}"
    except Exception as e:
        logger.error("llm_error", error=str(e))
        llm_answer = f"[Hata] LLM yanıt üretemedi: {str(e)}"
    
    # ══════════════════════════════════════════════════════════════
    # v5.7.0: BİLGİ MODU FAST-PATH — LLM cevabından sonra
    # Enterprise post-processing (governance, XAI, gatekeeper, debate,
    # causal, strategic, executive, KG, uncertainty, OOD, quality,
    # KPI impact, decision memory, executive digest, observability,
    # policy engine, meta learning) ATLANIR.
    # Sadece: RAG kaynakları + export + hafıza kaydı yapılır.
    # ══════════════════════════════════════════════════════════════
    _is_enterprise_mode = context.get("mode") in ("Analiz", "Rapor", "Öneri", "Acil")
    
    if not _is_enterprise_mode and intent != "sohbet":
        logger.info("bilgi_fast_path_return", 
                    mode=context.get("mode"), intent=intent,
                    elapsed_ms=round((time.time() - _t0) * 1000, 1))
        
        sources = []
        if relevant_docs:
            sources.extend([doc.get("source") for doc in relevant_docs])
        if web_results:
            sources.append("İnternet Araması")
        
        rich_data = web_rich_data if web_rich_data else []
        if not isinstance(rich_data, list):
            rich_data = [rich_data]
        
        # v6.02.00: PDF görsel desteği — önceden hesaplanan _pre_image_card'ı kullan
        if _has_pdf_images and _pre_image_card:
            rich_data.append(_pre_image_card)
            logger.info("pdf_images_injected_bilgi",
                       image_count=len(_pre_image_card["images"]))
        
        # Export talebi varsa dosya üret (bu hızlı)
        if EXPORT_AVAILABLE:
            export_format = detect_export_request(question)
            if export_format and llm_answer and not llm_answer.startswith("[Hata]"):
                try:
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
                except Exception:
                    pass
        
        # Hafızaya kaydet
        remember(question, llm_answer, context)
        
        # Arka planda öğrenme
        if KNOWLEDGE_EXTRACTOR_AVAILABLE:
            import asyncio
            loop = asyncio.get_event_loop()
            loop.run_in_executor(None, _background_learn,
                question, llm_answer, user_name, context.get("dept"), bool(relevant_docs))
        
        return {
            "answer": llm_answer,
            "department": context["dept"],
            "mode": context["mode"],
            "risk": context["risk"],
            "intent": intent,
            "confidence": 0.88 if relevant_docs else 0.82,
            "sources": sources,
            "web_searched": web_results is not None,
            "rich_data": rich_data if rich_data else None,
        }
    
    # ══════════════════════════════════════════════════════════════
    # ENTERPRISE PIPELINE — Sadece Analiz/Rapor/Öneri/Acil modlarında
    # Aşağıdaki tüm modüller sadece iş analizi modlarında çalışır.
    # ══════════════════════════════════════════════════════════════
    
    # ── 5b. TOOL CALLING + DYNAMIC CHAIN — Tool çağrısı + zincirleme ──
    tool_results = []
    if TOOLS_AVAILABLE and llm_answer and not llm_answer.startswith("[Hata]"):
        try:
            # Önce zincirleme tool call var mı kontrol et
            chain_calls = detect_tool_chain(question)
            
            if chain_calls and len(chain_calls) >= 2:
                # Dynamic Tool Chaining — araçları sıralı çalıştır
                chain_result = await tool_registry.chain_execute(chain_calls)
                if chain_result.get("success"):
                    for cr in chain_result.get("chain_results", []):
                        if cr["result"].get("success"):
                            tool_results.append({
                                "tool": cr["tool"],
                                "result": cr["result"],
                                "chain_step": cr["step"],
                            })
                    logger.info("tool_chain_executed", steps=chain_result["tools_executed"])
            
            if not tool_results:
                # Tekil tool detection (fallback)
                detected_tools = detect_tool_calls(llm_answer)
                if detected_tools:
                    for tool_call in detected_tools[:3]:  # Max 3 tool
                        tool_name = tool_call.get("tool", "")
                        tool_params = tool_call.get("params", {})
                        result = await tool_registry.execute(tool_name, tool_params)
                        if result and not result.get("error"):
                            tool_results.append({
                                "tool": tool_name,
                                "result": result,
                            })
            
            if tool_results:
                # Tool sonuçlarını cevaba ekle
                tool_text = "\n\n---\n📊 **Hesaplama Sonuçları:**\n"
                for tr in tool_results:
                    chain_info = f" (Adım {tr['chain_step']})" if tr.get("chain_step") else ""
                    tool_text += f"\n**{tr['tool']}{chain_info}**: {_format_tool_result(tr['result'])}"
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
    
    # ── 5d. REFLECTION LAYER + SELF-CORRECTION LOOP ──
    reflection_data = None
    dynamic_confidence = 0.85  # Default
    if REFLECTION_AVAILABLE and llm_answer and not llm_answer.startswith("[Hata]"):
        try:
            evaluation = quick_evaluate(llm_answer, question, context.get("mode", "Sohbet"))
            reflection_data = evaluation
            dynamic_confidence = evaluation["confidence"] / 100.0  # 0-1 arası
            
            # v4.3.0: LLM-Based Deep Reflection — Analiz/Rapor/Öneri modunda
            # Orta güvenli yanıtlarda (60-75%) REFLECTION_PROMPT ile LLM self-eval yap
            _mode = context.get("mode", "Sohbet")
            if (_mode in ("Analiz", "Rapor", "Öneri") and 
                60 <= evaluation["confidence"] <= 75 and
                not llm_answer.startswith("[Hata]")):
                try:
                    from app.core.reflection import REFLECTION_PROMPT
                    _refl_prompt = REFLECTION_PROMPT.format(
                        question=question[:500],
                        answer=llm_answer[:2000]
                    )
                    _refl_result = await ollama_client.generate(
                        prompt=_refl_prompt,
                        system_prompt="Sen bir kalite kontrol uzmanısın. JSON formatında yanıt ver.",
                        temperature=0.1,
                        max_tokens=500,
                    )
                    if _refl_result:
                        import json as _json
                        try:
                            _refl_json = _json.loads(
                                _refl_result.strip().strip("```json").strip("```").strip()
                            )
                            # LLM reflection sonuçlarını evaluation'a merge et
                            if isinstance(_refl_json, dict) and "overall_confidence" in _refl_json:
                                evaluation["llm_reflection"] = _refl_json
                                # LLM reflection güveni ile heuristic'in ortalamasını al
                                llm_conf = _refl_json.get("overall_confidence", evaluation["confidence"])
                                evaluation["confidence"] = (evaluation["confidence"] + llm_conf) / 2
                                dynamic_confidence = evaluation["confidence"] / 100.0
                                reflection_data = evaluation
                                logger.info("llm_reflection_applied",
                                           heuristic_conf=evaluation["confidence"],
                                           llm_conf=llm_conf)
                        except (ValueError, _json.JSONDecodeError):
                            logger.debug("llm_reflection_parse_failed")
                except Exception as refl_err:
                    logger.debug("llm_reflection_skipped", error=str(refl_err))
            
            # Self-correction loop — Analiz/Rapor/Öneri modunda düşük güvenli yanıtları
            # iteratif olarak iyileştir (max 2 tur)
            if evaluation.get("should_retry") and not llm_answer.startswith("[Hata]"):
                logger.info("self_correction_triggered", 
                           confidence=evaluation["confidence"],
                           issues=evaluation.get("issues", []))
                try:
                    correction_result = await self_correction_loop(
                        question=question,
                        initial_answer=llm_answer,
                        mode=context.get("mode", "Sohbet"),
                        llm_generate=ollama_client.generate,
                        system_prompt=system_prompt,
                        chat_history=chat_history if chat_history else None,
                        max_rounds=2,
                    )
                    if correction_result["improved"]:
                        llm_answer = correction_result["answer"]
                        reflection_data = correction_result["evaluation"]
                        dynamic_confidence = correction_result["confidence"] / 100.0
                        logger.info("self_correction_success",
                                   rounds=correction_result["rounds"],
                                   new_confidence=correction_result["confidence"])
                except Exception as retry_err:
                    logger.warning("self_correction_failed", error=str(retry_err))
            
            # Confidence badge — sadece Analiz/Rapor modlarında göster
            if context.get("mode") in ["Analiz", "Rapor", "Öneri", "Acil"]:
                badge = format_confidence_badge(evaluation["confidence"])
                llm_answer += f"\n\n---\n{badge}"
            
            logger.info("reflection_evaluated", 
                        confidence=evaluation["confidence"],
                        passed=evaluation["pass"])
            
            # ── Sinaps: Reflection sinyalleri ──
            if SYNAPSE_AVAILABLE and synapse_ctx and reflection_data:
                emit_signal(synapse_ctx, "reflection", "reflection_score",
                           reflection_data.get("confidence", 0), 0.85)
                emit_signal(synapse_ctx, "reflection", "confidence",
                           dynamic_confidence, 0.80)
        except Exception as e:
            logger.debug("reflection_skipped", error=str(e))
    
    # ── 5d-1.5. SAYISAL DOĞRULAMA + KAYNAK ATIF (v4.4.0) ──
    numerical_validation = None
    source_citation_valid = True
    if (NUMERICAL_VALIDATION_AVAILABLE and validate_numbers_against_source
        and relevant_docs and llm_answer and not llm_answer.startswith("[Hata]")
        and context.get("mode") in ("Analiz", "Rapor", "Öneri", "Acil")):
        try:
            # RAG bağlamını birleştir
            _rag_context = "\n".join(
                doc.get("content", "")[:500] for doc in relevant_docs[:5]
            )
            numerical_validation = validate_numbers_against_source(llm_answer, _rag_context)
            
            if numerical_validation:
                _num_score = numerical_validation.get("score", 100)
                _mismatches = numerical_validation.get("mismatch_count", 0)
                _fabricated = numerical_validation.get("fabricated_count", 0)
                
                if _fabricated > 0 or _mismatches > 1:
                    # Uyumsuz sayılar bulundu — uyarı ekle
                    _issues = numerical_validation.get("issues", [])
                    _issue_text = "\n".join(f"  - {i}" for i in _issues[:3])
                    llm_answer += (
                        f"\n\n---\n⚠️ **Sayısal Doğrulama Uyarısı** (skor: {_num_score}/100)\n"
                        f"{_issue_text}\n"
                        f"Lütfen kaynak verileri kontrol ediniz."
                    )
                    # Confidence düşür
                    dynamic_confidence = max(0.3, dynamic_confidence - 0.15)
                    source_citation_valid = False
                    logger.warning("numerical_validation_issues",
                                  score=_num_score, mismatches=_mismatches,
                                  fabricated=_fabricated)
                elif _num_score >= 80:
                    logger.info("numerical_validation_passed", score=_num_score)
                
                # Kaynak atıf doğrulama — yanıtta bahsedilen kaynaklar RAG'da var mı?
                _mentioned_sources = re.findall(
                    r'(?:kaynağ?a?|dosya|rapor|belge|doküman)[:\s]+["\']?([^"\',\n]{5,50})["\']?',
                    llm_answer, re.IGNORECASE
                )
                if _mentioned_sources and relevant_docs:
                    _actual_sources = set()
                    for doc in relevant_docs:
                        _src = doc.get("source", "").lower()
                        if _src:
                            _actual_sources.add(_src)
                            # Dosya adını da ekle
                            from pathlib import Path as _Path
                            _actual_sources.add(_Path(_src).stem.lower())
                    
                    _unverified = []
                    for ms in _mentioned_sources:
                        ms_lower = ms.strip().lower()
                        if not any(ms_lower in src or src in ms_lower for src in _actual_sources):
                            _unverified.append(ms.strip())
                    
                    if _unverified:
                        llm_answer += (
                            f"\n⚠️ Doğrulanamayan kaynak atıfları: {', '.join(_unverified[:3])}"
                        )
                        source_citation_valid = False
                        logger.warning("unverified_source_citations", sources=_unverified)
        except Exception as num_err:
            logger.debug("numerical_validation_skipped", error=str(num_err))
    
    # ── Sinaps: Numerical Validation sinyalleri ──
    if SYNAPSE_AVAILABLE and synapse_ctx and numerical_validation:
        _nv_score = numerical_validation.get("score", 100)
        emit_signal(synapse_ctx, "numerical_validation", "numerical_valid",
                   _nv_score >= 80, 0.75)
        emit_signal(synapse_ctx, "numerical_validation", "numerical_score",
                   _nv_score, 0.70)
    
    # ── 5d-2. ACTIVE LEARNING (v4.3.0) — Düşük güvenli yanıtlarda kullanıcıdan doğrulama iste ──
    if (REFLECTION_AVAILABLE and reflection_data and 
        40 <= reflection_data.get("confidence", 100) <= 60 and
        context.get("mode") not in ("Sohbet",) and
        not llm_answer.startswith("[Hata]")):
        # v5.9.0: Active learning notu cevaba eklenmez (gürültü azaltma)
        logger.info("active_learning_triggered", confidence=reflection_data["confidence"])
    
    # ── 5d-3. MULTI-PERSPECTIVE DECISIONS (v4.3.0 → v5.9.0 devre dışı) ──
    # v5.9.0: Ekstra LLM çağrısı kaldırıldı — CoT şablonu zaten çoklu perspektif sağlıyor
    # Bu 10-30 saniyelik ek gecikmeyi ve token israfını önler
    _is_strategic = False  # Devre dışı
    
    # ── 5d-4. ROI RECOMMENDATIONS (v4.3.0) ──
    # Yatırım/maliyet sorularında Monte Carlo simülasyonu tetikle
    _is_investment = bool(re.search(
        r'(yatırım|maliyet|bütçe|roi\b|getiri|tasarruf|amorti|geri.?ödeme)',
        question.lower()
    ))
    if (_is_investment and MONTE_CARLO_AVAILABLE 
        and context.get("mode") in ("Analiz", "Rapor", "Öneri")
        and not llm_answer.startswith("[Hata]")):
        try:
            # Monte Carlo simülasyonu — yatırım senaryosu
            mc_result = monte_carlo_simulate(
                base_value=100.0,  # Normalize edilmiş baz değer
                volatility=0.25,
                simulations=1000,
                periods=12,
            )
            if mc_result:
                # v5.9.0: Monte Carlo tablosu JSON'a taşındı, cevaba eklenmez
                logger.info("roi_monte_carlo_applied")
        except Exception as roi_err:
            logger.debug("roi_monte_carlo_skipped", error=str(roi_err))
    
    # ── 5e. MULTI-AGENT PIPELINE — Karmaşık Analiz Sorularında ──
    # v4.3.0: Cross-Module Orchestrator — geniş sorularda paralel modül çalıştır
    _is_broad_query = bool(re.search(
        r'(genel\s*durum|özet|dashboard|sağlık|health|tüm\s*departman|panorama|büyük\s*resim)',
        question.lower()
    ))
    if _is_broad_query and context.get("mode") in ("Analiz", "Rapor", "Öneri"):
        import asyncio
        _parallel_tasks = []
        _parallel_labels = []
        
        if EXECUTIVE_HEALTH_AVAILABLE:
            _parallel_tasks.append(asyncio.to_thread(calculate_health_index))
            _parallel_labels.append("health")
        if BOTTLENECK_AVAILABLE:
            _parallel_tasks.append(asyncio.to_thread(bottleneck_analyze, question))
            _parallel_labels.append("bottleneck")
        if GRAPH_IMPACT_AVAILABLE:
            _parallel_tasks.append(asyncio.to_thread(auto_graph_analysis, question, llm_answer))
            _parallel_labels.append("graph")
        
        if _parallel_tasks:
            try:
                _parallel_results = await asyncio.gather(*_parallel_tasks, return_exceptions=True)
                _orchestrator_text = "\n\n---\n🎯 **Cross-Module Panorama**\n"
                for label, res in zip(_parallel_labels, _parallel_results):
                    if isinstance(res, Exception):
                        continue
                    if label == "health" and res:
                        _orchestrator_text += f"\n{format_health_dashboard(res)}"
                    elif label == "bottleneck" and res:
                        _orchestrator_text += f"\n{format_bottleneck_report(res)}"
                    elif label == "graph" and res and res.total_nodes_affected > 0:
                        _orchestrator_text += f"\n{format_graph_impact(res)}"
                if len(_orchestrator_text) > 50:
                    # v5.9.0: Cross-module panorama JSON'a taşındı
                    logger.info("cross_module_orchestrator_done", modules=len(_parallel_tasks))
            except Exception as orch_err:
                logger.debug("cross_module_orchestrator_failed", error=str(orch_err))
    
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
                # v5.9.0: Pipeline çıktısı JSON'da, cevaba eklenmez
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
            _elapsed_ms = (time.time() - _t0) * 1000
            
            # Kullanılan modülleri topla
            _modules_invoked = []
            if relevant_docs:
                _modules_invoked.append("rag")
            if web_results:
                _modules_invoked.append("web_search")
            if tool_results:
                _modules_invoked.append("tool_calling")
            if structured_data:
                _modules_invoked.append("structured_output")
            if reflection_data:
                _modules_invoked.append("reflection")
            if pipeline_data:
                _modules_invoked.append("agent_pipeline")
            
            # Reasoning adımlarını topla
            _reasoning_steps = []
            if reflection_data and isinstance(reflection_data, dict):
                _reasoning_steps = reflection_data.get("issues", [])
            
            # Model adını al
            _model_name = getattr(ollama_client, 'model', 'unknown')
            
            gov_record = governance_engine.evaluate(
                question=question,
                answer=llm_answer,
                mode=context.get("mode", "Sohbet"),
                confidence=dynamic_confidence * 100 if dynamic_confidence <= 1 else dynamic_confidence,
                elapsed_ms=_elapsed_ms,
                model_name=_model_name,
                modules_invoked=_modules_invoked,
                reasoning_steps=_reasoning_steps,
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
                "compliance_score": getattr(gov_record, 'compliance_score', None),
                "trace_id": getattr(gov_record, 'trace_id', None),
                "drift_types": getattr(gov_record, 'drift_types', []),
                "policy_violations": getattr(gov_record, 'policy_violations', []),
                "risk_level": getattr(gov_record, 'risk_level', None) if hasattr(gov_record, 'risk_level') else None,
            }
            logger.info("governance_evaluated", 
                       bias=gov_record.bias_score, 
                       drift=gov_record.drift_detected,
                       compliance=getattr(gov_record, 'compliance_score', None),
                       trace_id=getattr(gov_record, 'trace_id', None))
            
            # ── Sinaps: Governance sinyalleri ──
            if SYNAPSE_AVAILABLE and synapse_ctx and governance_data:
                emit_signal(synapse_ctx, "governance", "bias_flags",
                           governance_data.get("policy_violations", []), 0.85)
                emit_signal(synapse_ctx, "governance", "drift_status",
                           governance_data.get("drift_detected", False), 0.70)
                emit_signal(synapse_ctx, "governance", "compliance_score",
                           governance_data.get("compliance_score", 1.0), 0.80)
                _gov_risk = governance_data.get("risk_level")
                if _gov_risk:
                    emit_signal(synapse_ctx, "governance", "risk_level",
                               _gov_risk, 0.85)
                # Kaskad kontrol — bias tetikleme
                _cascaded = check_cascades(synapse_ctx, "governance")
                if _cascaded:
                    logger.info("synapse_cascade_from_governance", targets=_cascaded)
        except Exception as e:
            logger.debug("governance_skipped", error=str(e))
    
    # ── 5g. XAI — Açıklanabilir Yapay Zeka Analizi ──
    xai_data = None
    if XAI_AVAILABLE and decision_explainer and llm_answer and not llm_answer.startswith("[Hata]"):
        try:
            xai_result = decision_explainer.explain(
                query=question,
                response=llm_answer,
                mode=context.get("mode", "Sohbet"),
                confidence=dynamic_confidence,
                sources=[doc.get("source", "") for doc in relevant_docs] if relevant_docs else [],
                rag_docs=relevant_docs if relevant_docs else None,
                web_searched=web_results is not None,
                reflection_data=reflection_data,
                module_source="engine",
            )
            if xai_result:
                xai_data = xai_result
                logger.info("xai_evaluated",
                           weighted_confidence=xai_result.get("weighted_confidence", 0),
                           risk_level=xai_result.get("risk", {}).get("level", "?"))
                
                # ── Sinaps: XAI sinyalleri ──
                if SYNAPSE_AVAILABLE and synapse_ctx:
                    emit_signal(synapse_ctx, "explainability", "xai_factors",
                               xai_result.get("factors", []), 0.65)
                    emit_signal(synapse_ctx, "explainability", "weighted_confidence",
                               xai_result.get("weighted_confidence", 0), 0.60)
        except Exception as e:
            logger.debug("xai_skipped", error=str(e))
    
    # ── 5i. DECISION IMPACT RANKING — Analiz modunda kararları sırala ──
    # v4.3.0: Trend Detection — Aynı KPI/konu tekrar soruluyorsa trend raporla
    if (session_history and len(session_history) >= 3 
        and context.get("mode") in ("Analiz", "Rapor", "Öneri")
        and not llm_answer.startswith("[Hata]")):
        try:
            # Geçmiş sorularda benzer KPI/konu arayışı
            _kpi_pattern = re.compile(
                r'(verimlilik|fire\s*oranı|maliyet|ciro|üretim|stok|kalite|karlılık|'
                r'sipariş|teslimat|devamsızlık|enerji|hurda|duruş)',
                re.IGNORECASE
            )
            _current_kpis = set(_kpi_pattern.findall(question.lower()))
            
            if _current_kpis:
                _past_mentions = []
                for msg in session_history[-10:]:
                    _q = msg.get("q", msg.get("content", ""))
                    _past_kpis = set(_kpi_pattern.findall(_q.lower()))
                    overlap = _current_kpis & _past_kpis
                    if overlap:
                        _past_mentions.append({"q": _q[:100], "kpis": overlap})
                
                if len(_past_mentions) >= 2:
                    _trend_kpis = ", ".join(_current_kpis)
                    # v5.9.0: Trend notu JSON metadata'da
                    logger.info("trend_detected", kpis=list(_current_kpis), 
                               mentions=len(_past_mentions))
        except Exception as trend_err:
            logger.debug("trend_detection_skipped", error=str(trend_err))
    
    ranking_data = None
    if DECISION_RANKING_AVAILABLE and llm_answer and context.get("mode") in ["Analiz", "Rapor", "Öneri"]:
        try:
            decisions = extract_decisions_from_llm(llm_answer, question)
            if decisions and len(decisions) >= 2:
                ranking_result = rank_decisions(decisions)
                # v5.9.0: Ranking tablosu JSON'da
                ranking_data = {
                    "total": ranking_result.total_evaluated,
                    "top_action": ranking_result.top_action,
                }
                logger.info("decision_ranking_applied", count=len(decisions))
        except Exception as e:
            logger.debug("decision_ranking_skipped", error=str(e))
    
    # ── 5j. GRAPH IMPACT MAPPING — KPI/Risk/Departman ilişki grafiği ──
    graph_data = None
    if GRAPH_IMPACT_AVAILABLE and llm_answer and context.get("mode") in ["Analiz", "Rapor", "Öneri"]:
        try:
            graph_result = auto_graph_analysis(question, llm_answer)
            if graph_result and graph_result.total_nodes_affected > 0:
                # v5.9.0: Graph impact JSON'da
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
    
    # v6.02.00: PDF görsel desteği — Enterprise modunda da çalışır (önceden hesaplandı)
    if _has_pdf_images and _pre_image_card:
        rich_data.append(_pre_image_card)
        logger.info("pdf_images_injected_enterprise",
                   image_count=len(_pre_image_card["images"]))
    
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
    
    # ══════════════════════════════════════════════════════════════
    # 6c. MULTI-AGENT DEBATE — Çok perspektifli tartışma (v4.7.0)
    #     Karmaşık / stratejik sorularda birden fazla perspektif ajanı
    #     tartışır ve konsensüs sentezi üretir.
    # ══════════════════════════════════════════════════════════════
    debate_data = None
    if MULTI_AGENT_DEBATE_AVAILABLE:
        try:
            should_debate, debate_reason = check_debate_trigger(
                question=question,
                mode=context.get("mode", ""),
                intent=intent,
                confidence=dynamic_confidence if REFLECTION_AVAILABLE else 85,
            )
            if should_debate:
                logger.info("multi_agent_debate_triggered", reason=debate_reason)
                debate_data = {"triggered": True, "reason": debate_reason}
        except Exception as e:
            logger.debug("multi_agent_debate_check_error", error=str(e))

    # ══════════════════════════════════════════════════════════════
    # 6d. CAUSAL INFERENCE — Nedensellik analizi tetikleme (v4.7.0)
    #     "Neden", "kök neden", "sebep" gibi sorularda otomatik tetiklenir.
    # ══════════════════════════════════════════════════════════════
    causal_data = None
    if CAUSAL_INFERENCE_AVAILABLE:
        try:
            should_causal, causal_reason = check_causal_trigger(
                question=question,
                mode=context.get("mode", ""),
                intent=intent,
            )
            if should_causal:
                logger.info("causal_inference_triggered", reason=causal_reason)
                causal_data = {"triggered": True, "reason": causal_reason}
        except Exception as e:
            logger.debug("causal_inference_check_error", error=str(e))

    # ══════════════════════════════════════════════════════════════
    # 6e. STRATEGIC PLANNER — Stratejik planlama motoru (v5.0.0)
    #     Strateji, hedef, vizyon, roadmap sorularında tetiklenir.
    # ══════════════════════════════════════════════════════════════
    strategic_data = None
    if STRATEGIC_PLANNER_AVAILABLE:
        try:
            should_strategic, strategic_reason = check_strategic_trigger(
                question=question,
                mode=context.get("mode", ""),
                intent=intent,
            )
            if should_strategic:
                logger.info("strategic_planner_triggered", reason=strategic_reason)
                strategic_data = {"triggered": True, "reason": strategic_reason}
        except Exception as e:
            logger.debug("strategic_planner_check_error", error=str(e))

    # ══════════════════════════════════════════════════════════════
    # 6f. EXECUTIVE INTELLIGENCE — Yönetici zekası (v5.0.0)
    #     CEO/CFO/CTO brifingleri, KPI korelasyon, board raporu.
    # ══════════════════════════════════════════════════════════════
    exec_intel_data = None
    if EXECUTIVE_INTELLIGENCE_AVAILABLE:
        try:
            should_exec, exec_reason = check_executive_trigger(
                question=question,
                mode=context.get("mode", ""),
                intent=intent,
            )
            if should_exec:
                logger.info("executive_intelligence_triggered", reason=exec_reason)
                exec_intel_data = {"triggered": True, "reason": exec_reason}
        except Exception as e:
            logger.debug("executive_intelligence_check_error", error=str(e))

    # ══════════════════════════════════════════════════════════════
    # 6g. KNOWLEDGE GRAPH — Bilgi grafiği zenginleştirme (v5.0.0)
    #     Varlık/ilişki çıkarma ve bağlam zenginleştirme.
    # ══════════════════════════════════════════════════════════════
    kg_data = None
    if KNOWLEDGE_GRAPH_AVAILABLE:
        try:
            should_kg, kg_reason = check_kg_trigger(
                question=question,
                mode=context.get("mode", ""),
                intent=intent,
            )
            if should_kg:
                logger.info("knowledge_graph_triggered", reason=kg_reason)
                kg_data = {"triggered": True, "reason": kg_reason}
        except Exception as e:
            logger.debug("knowledge_graph_check_error", error=str(e))

    # ══════════════════════════════════════════════════════════════
    # 6h. UNCERTAINTY QUANTIFICATION — Belirsizlik ölçümleme (v5.1.0)
    #     Tüm güven kaynaklarını birleştirip ensemble skor üretir.
    # ══════════════════════════════════════════════════════════════
    uncertainty_data = None
    if UNCERTAINTY_AVAILABLE:
        try:
            uq_result = uncertainty_quantifier.quantify(
                question=question,
                reflection_data=reflection_data,
                engine_confidence=dynamic_confidence if REFLECTION_AVAILABLE else 0.85,
                governance_data=governance_data,
            )
            uncertainty_data = uq_result.to_dict()
            logger.debug("uncertainty_quantified",
                         confidence=uq_result.ensemble_confidence,
                         margin=uq_result.margin_of_error)
            
            # ── Sinaps: Uncertainty sinyalleri ──
            if SYNAPSE_AVAILABLE and synapse_ctx:
                emit_signal(synapse_ctx, "uncertainty_quantification", "uncertainty",
                           uncertainty_data.get("uncertainty_pct", 50), 0.80)
                emit_signal(synapse_ctx, "uncertainty_quantification", "ensemble_confidence",
                           uq_result.ensemble_confidence, 0.75)
                emit_signal(synapse_ctx, "uncertainty_quantification", "confidence_adjustment",
                           uncertainty_data.get("confidence_adjustment", 0), 0.70)
        except Exception as e:
            logger.debug("uncertainty_quantification_error", error=str(e))

    # ══════════════════════════════════════════════════════════════
    # 6i. DECISION RISK GATEKEEPER — Karar risk kapısı (v5.1.0)
    #     Tüm risk sinyallerini birleştirip kararı geçir/engeller.
    # ══════════════════════════════════════════════════════════════
    gate_data = None
    if DECISION_GATEKEEPER_AVAILABLE:
        try:
            should_gate, gate_reason = check_gate_trigger(
                question=question,
                mode=context.get("mode", ""),
                intent=intent,
            )
            if should_gate:
                # ── Sinaps: risk_data artık None değil — sinaps ağından topla ──
                _synapse_risk = None
                if SYNAPSE_AVAILABLE and synapse_ctx:
                    _synapse_risk = gather_module_inputs(synapse_ctx, "decision_gatekeeper")
                    # risk_analyzer sinyallerini risk_data olarak kullan
                    if _synapse_risk.get("risk_level") or _synapse_risk.get("risk_factors"):
                        _synapse_risk = {
                            "risk_level": _synapse_risk.get("risk_level", "LOW"),
                            "risk_factors": _synapse_risk.get("risk_factors", []),
                            "risk_score": _synapse_risk.get("risk_score", 0),
                        }
                    else:
                        _synapse_risk = None

                gate_result = decision_gatekeeper.evaluate(
                    question=question,
                    answer=llm_answer,
                    governance_data=governance_data,
                    reflection_data=reflection_data,
                    confidence=dynamic_confidence if REFLECTION_AVAILABLE else 0.85,
                    risk_data=_synapse_risk,
                    ranking_data=ranking_data,
                )
                gate_data = gate_result.to_dict()
                logger.info("decision_gate_evaluated",
                            verdict=gate_result.verdict.value,
                            risk_score=gate_result.composite_risk_score)
                
                # ── Sinaps: Gatekeeper sinyalleri + kaskad ──
                if SYNAPSE_AVAILABLE and synapse_ctx:
                    emit_signal(synapse_ctx, "decision_gatekeeper", "gate_verdict",
                               gate_result.verdict.value, 0.90)
                    emit_signal(synapse_ctx, "decision_gatekeeper", "composite_risk_score",
                               gate_result.composite_risk_score, 0.80)
                    emit_signal(synapse_ctx, "decision_gatekeeper", "escalation_required",
                               gate_data.get("escalation_required", False), 0.75)
                    emit_signal(synapse_ctx, "decision_gatekeeper", "risk_signals",
                               gate_data.get("risk_signals", []), 0.70)
                    _cascaded = check_cascades(synapse_ctx, "decision_gatekeeper")
                    if _cascaded:
                        logger.info("synapse_cascade_from_gate", targets=_cascaded)
        except Exception as e:
            logger.debug("decision_gatekeeper_error", error=str(e))

    # ══════════════════════════════════════════════════════════════
    # 6j. OOD DETECTOR — Dağılım dışı girdi algılama (v5.3.0)
    #     Sorunun bilinen alan içinde olup olmadığını kontrol eder.
    # ══════════════════════════════════════════════════════════════
    ood_data = None
    if OOD_DETECTOR_AVAILABLE and check_ood:
        try:
            ood_result = check_ood(question=question, department=context.get("dept", ""))
            ood_data = ood_result.to_dict()

            # OOD ise uyarı ekle
            if ood_result.is_ood and context.get("mode") in ["Analiz", "Rapor", "Öneri", "Acil"]:
                ood_warning_text = format_ood_warning(ood_result)
                if ood_warning_text:
                    llm_answer += f"\n{ood_warning_text}"

            # Confidence/uncertainty ayarla
            if ood_result.confidence_adjustment != 0:
                dynamic_confidence = max(0.1, dynamic_confidence + ood_result.confidence_adjustment / 100)

            logger.debug("ood_checked", severity=ood_result.severity.value, score=ood_result.ood_score)
            
            # ── Sinaps: OOD sinyalleri + kaskad ──
            if SYNAPSE_AVAILABLE and synapse_ctx:
                emit_signal(synapse_ctx, "ood_detector", "ood_score",
                           ood_result.ood_score, 0.80)
                emit_signal(synapse_ctx, "ood_detector", "ood_severity",
                           ood_result.severity.value, 0.85)
                if ood_result.confidence_adjustment != 0:
                    emit_signal(synapse_ctx, "ood_detector", "confidence_adjustment",
                               ood_result.confidence_adjustment, 0.75)
                _cascaded = check_cascades(synapse_ctx, "ood_detector")
                if _cascaded:
                    logger.info("synapse_cascade_from_ood", targets=_cascaded)
        except Exception as e:
            logger.debug("ood_detector_error", error=str(e))

    # ══════════════════════════════════════════════════════════════
    # 6k. DECISION QUALITY SCORE — Birleşik karar kalitesi (v5.3.0)
    #     Tüm modül çıktılarını toplayarak tek bir kalite skoru üretir.
    # ══════════════════════════════════════════════════════════════
    quality_data = None
    if DECISION_QUALITY_AVAILABLE and evaluate_decision_quality:
        try:
            # ── Sinaps: meta_data artık None değil — sinaps ağından topla ──
            _synapse_meta = None
            if SYNAPSE_AVAILABLE and synapse_ctx:
                _meta_inputs = gather_module_inputs(synapse_ctx, "decision_quality")
                if _meta_inputs.get("meta_strategy") or _meta_inputs.get("quality_trend"):
                    _synapse_meta = _meta_inputs

            quality_result = evaluate_decision_quality(
                reflection_data=reflection_data,
                uncertainty_data=uncertainty_data,
                gate_data=gate_data,
                meta_data=_synapse_meta,
                governance_data=governance_data,
                debate_data=debate_data,
                causal_data=causal_data,
                rag_used=bool(relevant_docs),
                web_searched=web_results is not None,
                sources=sources,
                source_citation_valid=source_citation_valid,
                question=question,
                department=context.get("dept", ""),
            )
            quality_data = {
                "overall_score": quality_result.overall_score,
                "band": quality_result.band.value,
                "confidence_interval": quality_result.confidence_interval,
                "executive_line": quality_result.executive_line,
            }

            # Analiz/Rapor modlarında badge ekle
            # v5.9.0: Quality badge JSON'da (confidence badge yeterli)

            logger.info("decision_quality_scored",
                        score=quality_result.overall_score,
                        band=quality_result.band.value)
            
            # ── Sinaps: Decision Quality sinyalleri + kaskad ──
            if SYNAPSE_AVAILABLE and synapse_ctx and quality_data:
                emit_signal(synapse_ctx, "decision_quality", "quality_score",
                           quality_result.overall_score, 0.90)
                emit_signal(synapse_ctx, "decision_quality", "quality_band",
                           quality_result.band.value, 0.80)
                _cascaded = check_cascades(synapse_ctx, "decision_quality")
                if _cascaded:
                    logger.info("synapse_cascade_from_quality", targets=_cascaded)
        except Exception as e:
            logger.debug("decision_quality_error", error=str(e))

    # ══════════════════════════════════════════════════════════════
    # 6l. KPI IMPACT MAPPING — KPI etki analizi (v5.3.0)
    #     Kararın KPI'lara etkisini tahmin eder, domino etkilerini hesaplar.
    # ══════════════════════════════════════════════════════════════
    kpi_impact_data = None
    if KPI_IMPACT_AVAILABLE and analyze_kpi_impact:
        try:
            _decision_text = f"{question} {llm_answer[:500]}"
            kpi_result = analyze_kpi_impact(decision_text=_decision_text)
            if kpi_result and kpi_result.primary_impacts:
                kpi_impact_data = {
                    "primary_count": len(kpi_result.primary_impacts),
                    "domino_count": len(kpi_result.domino_effects),
                    "impact_score": kpi_result.impact_score,
                    "net_financial": kpi_result.net_financial_direction,
                    "executive_summary": kpi_result.executive_summary,
                    "impacts": [
                        {"kpi_id": i.kpi_id, "kpi_name": i.kpi_name, "direction": i.direction.value,
                         "magnitude": i.magnitude.value, "estimated_change_pct": i.estimated_change_pct}
                        for i in kpi_result.primary_impacts[:5]
                    ],
                }

                # Analiz modlarında etki özeti ekle
                # v5.9.0: KPI impact brief JSON'da

                logger.info("kpi_impact_analyzed",
                            impacts=len(kpi_result.primary_impacts),
                            score=kpi_result.impact_score)
                
                # ── Sinaps: KPI Impact sinyalleri + kaskad ──
                if SYNAPSE_AVAILABLE and synapse_ctx:
                    emit_signal(synapse_ctx, "kpi_impact", "kpi_impacts",
                               kpi_impact_data.get("impacts", []), 0.80)
                    emit_signal(synapse_ctx, "kpi_impact", "impact_score",
                               kpi_result.impact_score, 0.75)
                    emit_signal(synapse_ctx, "kpi_impact", "financial_estimate",
                               kpi_result.net_financial_direction, 0.70)
                    _cascaded = check_cascades(synapse_ctx, "kpi_impact")
                    if _cascaded:
                        logger.info("synapse_cascade_from_kpi", targets=_cascaded)
        except Exception as e:
            logger.debug("kpi_impact_error", error=str(e))

    # ══════════════════════════════════════════════════════════════
    # 6m. DECISION MEMORY — Benzer geçmiş kararları bul (v5.3.0)
    #     Soruyu geçmiş kararlarla karşılaştırır ve benzer olanları gösterir.
    # ══════════════════════════════════════════════════════════════
    memory_data = None
    similar_decisions = None
    if DECISION_MEMORY_AVAILABLE and find_similar_decisions:
        try:
            similar = find_similar_decisions(
                question=question,
                department=context.get("dept", ""),
                top_n=3,
            )
            if similar:
                memory_data = {
                    "similar_count": len(similar),
                    "top_similarity": similar[0].similarity_score,
                    "similar_decisions": [
                        {"question": s.record.question[:100], "outcome": s.record.outcome.value,
                         "similarity": round(s.similarity_score, 2), "quality": s.record.quality_score}
                        for s in similar
                    ],
                }
                similar_decisions = similar

                # Analiz modlarında benzer kararları göster
                # v5.9.0: Similar decisions JSON'da

                logger.info("similar_decisions_found", count=len(similar),
                            top_sim=similar[0].similarity_score)
                
                # ── Sinaps: Decision Memory sinyalleri ──
                if SYNAPSE_AVAILABLE and synapse_ctx:
                    emit_signal(synapse_ctx, "decision_memory", "similar_decisions",
                               memory_data.get("similar_decisions", []), 0.70)
                    emit_signal(synapse_ctx, "decision_memory", "accuracy_data",
                               memory_data.get("top_similarity", 0), 0.60)
        except Exception as e:
            logger.debug("decision_memory_search_error", error=str(e))

    # ══════════════════════════════════════════════════════════════
    # 6n. EXECUTIVE DIGEST — Yönetim özeti (v5.3.0)
    #     5 madde + Risk + Fırsat + Net Öneri formatında sade özet üretir.
    # ══════════════════════════════════════════════════════════════
    digest_data = None
    if EXECUTIVE_DIGEST_AVAILABLE and generate_executive_digest:
        try:
            if context.get("mode") in ["Analiz", "Rapor", "Öneri", "Acil"]:
                _gate_verdict = gate_data.get("verdict", "") if gate_data else ""
                _gate_risks = gate_data.get("risk_signals", []) if gate_data else []
                _unc_val = uncertainty_data.get("uncertainty_pct", 50) if uncertainty_data else 50
                _conf_val = uncertainty_data.get("ensemble_confidence", 50) if uncertainty_data else dynamic_confidence * 100
                _moe = uncertainty_data.get("margin_of_error", 0) if uncertainty_data else 0
                _refl_score = reflection_data.get("confidence", 0) if reflection_data else 0
                _q_score = quality_data.get("overall_score", 0) if quality_data else 0
                _q_band = quality_data.get("band", "") if quality_data else ""
                _kpi_impacts_list = kpi_impact_data.get("impacts", []) if kpi_impact_data else []
                _kpi_iscore = kpi_impact_data.get("impact_score", 0) if kpi_impact_data else 0
                _kpi_summary = kpi_impact_data.get("executive_summary", "") if kpi_impact_data else ""
                _ood_flag = ood_data.get("is_ood", False) if ood_data else False
                _ood_note = ood_data.get("warning_message", "") if ood_data else ""

                digest = generate_executive_digest(
                    question=question,
                    ai_answer=llm_answer[:2000],
                    department=context.get("dept", ""),
                    quality_score=_q_score,
                    quality_band=_q_band,
                    kpi_impacts=_kpi_impacts_list,
                    impact_score=_kpi_iscore,
                    kpi_executive_summary=_kpi_summary,
                    gate_verdict=_gate_verdict,
                    gate_risks=_gate_risks,
                    uncertainty=_unc_val,
                    confidence=_conf_val,
                    margin_of_error=_moe,
                    reflection_score=_refl_score,
                    ood_detected=_ood_flag,
                    ood_note=_ood_note,
                )
                digest_data = digest.to_dict()

                # v5.9.0: Executive digest JSON'da, cevaba eklenmez

                logger.info("executive_digest_generated",
                            priority=digest.priority.value,
                            impact=digest.impact_level)
                
                # ── Sinaps: Executive Digest sinyalleri ──
                if SYNAPSE_AVAILABLE and synapse_ctx:
                    emit_signal(synapse_ctx, "executive_digest", "executive_digest",
                               digest_data, 0.85)
                    emit_signal(synapse_ctx, "executive_digest", "digest_priority",
                               digest.priority.value, 0.70)
        except Exception as e:
            logger.debug("executive_digest_error", error=str(e))

    # ══════════════════════════════════════════════════════════════
    # 6p. OBSERVABILITY 2.0 — Karar drift + kalite trend izleme (v5.5.0)
    # ══════════════════════════════════════════════════════════════
    observability_data = None
    if OBSERVABILITY_AVAILABLE and observability:
        try:
            _elapsed_ms = (time.time() - _t0) * 1000
            _obs_confidence = dynamic_confidence * 100 if dynamic_confidence <= 1 else dynamic_confidence
            _obs_quality = quality_data.get("overall_score", 70) if quality_data else 70

            observability.record_decision(
                confidence=_obs_confidence,
                quality_score=_obs_quality,
                latency_ms=_elapsed_ms,
                intent=intent,
                department=context.get("dept", "genel"),
            )

            # Drift kontrolü
            drift_report = observability.check_all_drifts()
            if drift_report:
                _any_drift = any(
                    d.get("severity", "none") not in ("none", "NONE")
                    for d in drift_report.values()
                    if isinstance(d, dict)
                )
                if _any_drift:
                    observability_data = drift_report
                    logger.info("observability_drift_detected",
                               drifts={k: v.get("severity") for k, v in drift_report.items() if isinstance(v, dict)})

            logger.debug("observability_recorded", latency_ms=round(_elapsed_ms, 1))
        except Exception as obs_err:
            logger.debug("observability_error", error=str(obs_err))

    # ══════════════════════════════════════════════════════════════
    # 6q. POLICY ENGINE — Enterprise kural motoru (v5.5.0)
    #     Sonuç döndürülmeden önce tüm politika kurallarını kontrol eder.
    # ══════════════════════════════════════════════════════════════
    policy_data = None
    if POLICY_ENGINE_AVAILABLE and enterprise_policy_engine:
        try:
            _elapsed_ms = (time.time() - _t0) * 1000
            _policy_context = {
                "risk_score": gate_data.get("composite_risk_score", 0) if gate_data else 0,
                "confidence": dynamic_confidence * 100 if dynamic_confidence <= 1 else dynamic_confidence,
                "quality_score": quality_data.get("overall_score", 70) if quality_data else 70,
                "response_time_ms": _elapsed_ms,
                "department": context.get("dept", "genel"),
                "mode": context.get("mode", "Sohbet"),
                "data_source_count": len(sources) if sources else 0,
                "model_name": getattr(ollama_client, 'model', 'unknown'),
            }
            policy_result = enterprise_policy_engine.evaluate(_policy_context)
            if policy_result and not policy_result.allowed:
                policy_data = {
                    "allowed": policy_result.allowed,
                    "action": policy_result.action.value,
                    "violations": [
                        {"rule": v.rule_id, "message": v.message, "severity": v.severity.value}
                        for v in policy_result.violations
                    ],
                }
                # Block ise uyarı ekle
                if policy_result.action.value == "block":
                    _violations_text = "; ".join(v.message for v in policy_result.violations[:3])
                    llm_answer += f"\n\n---\n⚠️ **Politika Uyarısı**: {_violations_text}"
                logger.info("policy_violations",
                            action=policy_result.action.value,
                            violation_count=len(policy_result.violations))
            elif policy_result:
                policy_data = {"allowed": True, "action": "allow", "violations": []}
        except Exception as pol_err:
            logger.debug("policy_engine_error", error=str(pol_err))

    # ══════════════════════════════════════════════════════════════
    # 6r. OUTCOME PREDICTION — Decision Quality v5.5.0 tahmin kaydı
    # ══════════════════════════════════════════════════════════════
    if DQ_OUTCOME_AVAILABLE and dq_record_prediction and _query_event_id:
        try:
            _q_score = quality_data.get("overall_score", 0) if quality_data else 0
            dq_record_prediction(
                decision_id=_query_event_id,
                predicted_outcome=llm_answer[:200],
                confidence=dynamic_confidence * 100 if dynamic_confidence <= 1 else dynamic_confidence,
                quality_score=_q_score,
            )
        except Exception:
            pass

    # ═══ v5.5.0: Event Bus — Sorgu tamamlanma olayı ═══
    if EVENT_BUS_AVAILABLE and event_bus and _query_event_id:
        try:
            _elapsed_ms = (time.time() - _t0) * 1000
            event_bus.emit("query.completed", {
                "query_id": _query_event_id,
                "intent": intent,
                "department": context.get("dept", ""),
                "confidence": dynamic_confidence,
                "quality_score": quality_data.get("overall_score", 0) if quality_data else 0,
                "latency_ms": round(_elapsed_ms, 1),
                "modules_used": len([v for v in (relevant_docs, web_results, tool_results, pipeline_data, governance_data) if v]),
            })
        except Exception:
            pass

    # ── Sinaps: Pipeline sonlandır ve sonucu zenginleştir ──
    synapse_summary = None
    synapse_trace_text = ""
    if SYNAPSE_AVAILABLE and synapse_ctx:
        try:
            finalize_context(synapse_ctx)
            synapse_summary = synapse_ctx.summary()
            synapse_trace_text = format_network_summary(synapse_ctx)
            
            # Analiz modlarında sinyal akış izini cevaba ekle
            # v5.9.0: Signal trace JSON'da
            pass
        except Exception as syn_err:
            logger.debug("synapse_finalize_error", error=str(syn_err))

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
        "xai": xai_data,
        "numerical_validation": numerical_validation,
        "source_citation_valid": source_citation_valid,
        "debate": debate_data,
        "causal": causal_data,
        "strategic": strategic_data,
        "executive_intel": exec_intel_data,
        "knowledge_graph": kg_data,
        "uncertainty": uncertainty_data,
        "gate": gate_data,
        "ood": ood_data,
        "decision_quality": quality_data,
        "kpi_impact": kpi_impact_data,
        "decision_memory": memory_data,
        "executive_digest": digest_data,
        "synapse_network": synapse_summary,
        # v5.5.0 Enterprise Platform
        "security": security_result,
        "observability": observability_data,
        "policy": policy_data,
    }
    
    # 7. Hafızaya kaydet (semantik hafıza)
    remember(question, llm_answer, context)

    # 7b. Decision Memory'ye kaydet (v5.3.0)
    if DECISION_MEMORY_AVAILABLE and store_decision:
        try:
            _q_score = quality_data.get("overall_score", 0) if quality_data else 0
            _q_band = quality_data.get("band", "") if quality_data else ""
            _kpi_list = kpi_impact_data.get("impacts", []) if kpi_impact_data else []
            _risk_lvl = governance_data.get("risk_level", "unknown") if governance_data else "unknown"
            _gate_v = gate_data.get("verdict", "unknown") if gate_data else "unknown"
            _unc_pct = uncertainty_data.get("uncertainty_pct", 50) if uncertainty_data else 50
            _conf_pct = dynamic_confidence * 100 if dynamic_confidence <= 1 else dynamic_confidence

            store_decision(
                question=question,
                ai_recommendation=llm_answer[:1000],
                department=context.get("dept", ""),
                quality_score=_q_score,
                quality_band=_q_band,
                kpi_impacts=_kpi_list,
                risk_level=_risk_lvl,
                gate_verdict=_gate_v,
                uncertainty=_unc_pct,
                confidence=_conf_pct,
                user_id=user_name,
            )
        except Exception as e:
            logger.debug("decision_memory_store_error", error=str(e))
    
    # ══════════════════════════════════════════════════════════════
    # 8. OTOMATİK ÖĞRENME — HER konuşmadan bilgi çıkar ve RAG'a kaydet
    #    Kullanıcının "öğren" demesine GEREK YOK.
    #    Öğrenme ARKA PLANDA çalışır — yanıt süresini etkilemez.
    # ══════════════════════════════════════════════════════════════
    if KNOWLEDGE_EXTRACTOR_AVAILABLE:
        import asyncio
        loop = asyncio.get_event_loop()
        loop.run_in_executor(None, _background_learn,
            question, llm_answer, user_name, context.get("dept"), bool(relevant_docs))
    
    # ══════════════════════════════════════════════════════════════
    # 9. META LEARNING — Performans kaydı ve self-improvement hook
    #    Her sorgu sonucunu meta_learning_engine'e kaydet.
    #    Self-improvement loop'a bildirim gönder.
    # ══════════════════════════════════════════════════════════════
    if META_LEARNING_AVAILABLE:
        try:
            _reflection_conf = reflection_data.get("confidence", 0) if reflection_data else 0
            _gov_compliance = governance_data.get("compliance_score", 1.0) if governance_data else 1.0
            _criteria = reflection_data.get("criteria_scores", {}) if reflection_data else {}
            _issues = reflection_data.get("issues", []) if reflection_data else []
            _retry_count = reflection_data.get("rounds", 0) if reflection_data else 0

            meta_result = record_query_outcome(
                question=question,
                department=context.get("dept", "genel"),
                mode=context.get("mode", "Sohbet"),
                intent=intent,
                confidence=dynamic_confidence if REFLECTION_AVAILABLE else 85,
                had_rag=bool(relevant_docs),
                had_web=web_results is not None,
                had_tools=bool(tool_results),
                reflection_pass=reflection_data.get("pass", True) if reflection_data else True,
                reflection_confidence=_reflection_conf,
                governance_compliance=_gov_compliance,
                response_time_ms=(time.time() - start_time) * 1000 if 'start_time' in dir() else 0,
                knowledge_learned=False,  # background'da belirlenecek
                knowledge_type=None,
                criteria_scores=_criteria,
                issues=_issues,
                retry_count=_retry_count,
                numerical_valid=numerical_validation.get("validated", True) if numerical_validation else True,
                source_citation_valid=source_citation_valid,
            )
            result["meta_learning"] = meta_result

            # Self-Improvement Loop hook
            if SELF_IMPROVEMENT_AVAILABLE:
                domain_key = f"{context.get('dept', 'genel')}:{context.get('mode', 'Sohbet')}"
                si_on_query_completed(
                    meta_result=meta_result,
                    domain_key=domain_key,
                    current_confidence=dynamic_confidence if REFLECTION_AVAILABLE else 85,
                )
        except Exception as e:
            logger.debug("meta_learning_error", error=str(e))

    logger.info("question_processed", 
                intent=intent,
                department=context["dept"], 
                rag_used=bool(relevant_docs),
                web_used=web_results is not None,
                memories_used=len(similar_memories))
    
    return result


def _auto_learn_from_web(question: str, web_text: str):
    """Web'den bulunan bilgiyi RAG'a kaydet — DEVRE DIŞI
    Web aramaları ChromaDB'yi kirletip gerçek dokümanları bastırıyordu.
    Bu fonksiyon artık kullanılmıyor, referans olarak duruyor.
    """
    pass


def _background_learn(question: str, answer: str, user_name: str, department: str, had_rag: bool):
    """Arka planda öğrenme — run_in_executor ile çağrılır, event loop'u bloklamaz."""
    try:
        result = learn_from_conversation(
            question=question,
            answer=answer,
            user_name=user_name,
            department=department,
            had_rag_docs=had_rag,
        )
        if result.get("user_learned"):
            logger.info("bg_learned", knowledge_type=result.get("knowledge_type"), user=user_name)
    except Exception as e:
        logger.debug("bg_learn_error", error=str(e))


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
            "ocr_engine": OCR_AVAILABLE,
            "numerical_validation": NUMERICAL_VALIDATION_AVAILABLE,
            "explainability": XAI_AVAILABLE,
            "bottleneck_engine": BOTTLENECK_AVAILABLE,
            "executive_health": EXECUTIVE_HEALTH_AVAILABLE,
            "meta_learning": META_LEARNING_AVAILABLE,
            "self_improvement": SELF_IMPROVEMENT_AVAILABLE,
            "multi_agent_debate": MULTI_AGENT_DEBATE_AVAILABLE,
            "causal_inference": CAUSAL_INFERENCE_AVAILABLE,
            "strategic_planner": STRATEGIC_PLANNER_AVAILABLE,
            "executive_intelligence": EXECUTIVE_INTELLIGENCE_AVAILABLE,
            "knowledge_graph": KNOWLEDGE_GRAPH_AVAILABLE,
            "decision_gatekeeper": DECISION_GATEKEEPER_AVAILABLE,
            "uncertainty_quantification": UNCERTAINTY_AVAILABLE,
            "decision_quality": DECISION_QUALITY_AVAILABLE,
            "kpi_impact": KPI_IMPACT_AVAILABLE,
            "decision_memory": DECISION_MEMORY_AVAILABLE,
            "executive_digest": EXECUTIVE_DIGEST_AVAILABLE,
            "ood_detector": OOD_DETECTOR_AVAILABLE,
            "module_synapse": SYNAPSE_AVAILABLE,
            # v5.5.0 Enterprise Platform
            "event_bus": EVENT_BUS_AVAILABLE,
            "orchestrator": ORCHESTRATOR_AVAILABLE,
            "policy_engine": POLICY_ENGINE_AVAILABLE,
            "observability": OBSERVABILITY_AVAILABLE,
            "security_layer": SECURITY_AVAILABLE,
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