"""Multi-Agent Orchestration Pipeline — Sequential Agent Zinciri

Enterprise Tier-0 Seviye Multi-Agent Sistemi:
- 6 uzman ajan — her biri kendi rolünde
- Sequential pipeline — her ajan öncekinin çıktısını alır
- Ajan arası context paylaşımı
- Son adımda Reflection Agent ile kalite kontrolü

Ajan Zinciri:
1. DataValidatorAgent   → Veri bütünlüğü + kalite skoru
2. StatisticalAgent     → İstatistik, trend, anomali tespiti
3. RiskScoringAgent     → Risk skoru 0-100, risk seviyesi
4. FinancialImpactAgent → Gelir/maliyet projeksiyon
5. StrategyAgent        → Kısa/Orta/Uzun vade öneriler
6. ReflectionAgent      → Kalite kontrol + confidence
"""

import json
import structlog
from typing import Optional, Any
from dataclasses import dataclass, field
import asyncio

logger = structlog.get_logger()


# ══════════════════════════════════════════════════════════════
# 1. AGENT TANIMLARI
# ══════════════════════════════════════════════════════════════

@dataclass
class AgentResult:
    """Tek bir ajanın çıktısı."""
    agent_name: str
    role: str
    output: str
    structured_data: dict = field(default_factory=dict)
    confidence: float = 0.0
    skip_reason: str = ""
    
    def to_dict(self) -> dict:
        return {
            "agent": self.agent_name,
            "role": self.role,
            "output": self.output[:500],
            "structured_data": self.structured_data,
            "confidence": self.confidence,
            "skipped": bool(self.skip_reason),
        }


@dataclass
class PipelineResult:
    """Tüm pipeline çıktısı."""
    question: str
    agent_results: list = field(default_factory=list)
    final_answer: str = ""
    executive_summary: str = ""
    overall_confidence: float = 0.0
    data_integrity_score: float = 0.0
    risk_score: float = 0.0
    scenario_simulation: dict = field(default_factory=dict)
    strategic_recommendations: dict = field(default_factory=dict)
    financial_impact: dict = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        return {
            "question": self.question,
            "agents_executed": len(self.agent_results),
            "agent_results": [a.to_dict() for a in self.agent_results],
            "overall_confidence": self.overall_confidence,
            "data_integrity_score": self.data_integrity_score,
            "risk_score": self.risk_score,
        }


# ══════════════════════════════════════════════════════════════
# 2. AGENT PROMPT ŞABLONLARI
# ══════════════════════════════════════════════════════════════

AGENT_PROMPTS = {
    "DataValidatorAgent": {
        "role": "Veri bütünlüğü ve kalite değerlendirmesi",
        "prompt": """Sen bir Veri Doğrulama Uzmanısın. Kullanıcının sorusundaki verileri değerlendir.

GÖREV:
1. Soruda/bağlamda sayısal veri var mı? Varsa listele.
2. Veri kaynağı belirtilmiş mi?
3. Eksik veri var mı? (karşılaştırma için geçmiş dönem, hedef, benchmark gerekli mi?)
4. Veri kalite skoru ver (0-100):
   - 90-100: Tam, güvenilir veri 
   - 70-89: Yeterli ama bazı eksikler
   - 50-69: Kısmi veri, varsayım gerekli
   - 0-49: Yetersiz veri, dikkatli yaklaş

ÖNEMLİ: Kısa ve yapısal yanıt ver. Sadece veri kalitesini değerlendir, analiz yapma.

Soru: {question}
Bağlam: {context}""",
    },
    
    "StatisticalAgent": {
        "role": "İstatistiksel analiz, trend ve anomali tespiti",
        "prompt": """Sen bir İstatistik ve Trend Analizi Uzmanısın.

ÖNCEKİ AJAN ÇIKTISI (Veri Doğrulama):
{prev_output}

GÖREV:
1. Mevcut verileri analiz et — ortalama, değişim oranı, trend yönü
2. Anomali tespiti — normal aralık dışında değer var mı?
3. Dönemsel karşılaştırma — geçmiş döneme göre değişim
4. Korelasyon — birbirine etki eden faktörler
5. Tahmin — mevcut trend devam ederse sonraki dönem tahmini

Mümkünse tablo formatı kullan. Somut sayılarla yanıt ver.

Soru: {question}""",
    },
    
    "RiskScoringAgent": {
        "role": "Risk skoru hesaplama (0-100)",
        "prompt": """Sen bir Risk Değerlendirme Uzmanısın.

ÖNCEKİ ÇIKTILAR:
- Veri Kalitesi: {data_quality}
- İstatistiksel Analiz: {stat_output}

GÖREV:
1. Tespit edilen riskleri listele (Operasyonel, Finansal, Pazar, Tedarik Zinciri, Regülasyon)
2. Her risk için:
   - Olasılık (1-5)
   - Etki (1-5)  
   - Risk Skoru = Olasılık × Etki
   - Seviye: Düşük (1-6) / Orta (7-12) / Yüksek (13-19) / Kritik (20-25)
3. Genel risk skoru hesapla (0-100): En yüksek risk × 4
4. Risk azaltma önerileri

Yanıtını yapısal ver. Risk tablosu kullan.

Soru: {question}""",
    },
    
    "FinancialImpactAgent": {
        "role": "Finansal etki projeksiyonu",
        "prompt": """Sen bir Finansal Etki Modelleme Uzmanısın.

ÖNCEKİ ÇIKTILAR:
- Risk Skoru: {risk_output}
- İstatistik: {stat_output}

GÖREV:
1. **Tahmini Gelir Değişimi**: Mevcut durum devam ederse gelire etkisi (₺ veya %)
2. **Tahmini Maliyet Değişimi**: Operasyonel maliyet etkisi (₺ veya %)
3. **Net Etki**: Gelir değişimi - Maliyet değişimi
4. **Senaryo Analizi**:
   - 🟢 **Best Case**: İyimser senaryo — her şey yolunda giderse
   - 🟡 **Expected Case**: Beklenen senaryo — mevcut trend devam ederse
   - 🔴 **Worst Case**: Kötümser senaryo — riskler gerçekleşirse
5. **Yatırım Getirisi**: Önerilen iyileştirmenin tahmini ROI'si

Tüm değerleri somut sayılarla ifade et. Varsayımlarını belirt.

Soru: {question}""",
    },
    
    "StrategyAgent": {
        "role": "Stratejik öneriler — kısa/orta/uzun vade",
        "prompt": """Sen bir Kurumsal Strateji Danışmanısın. CEO/CFO seviyesinde tavsiyelerde bulun.

ÖNCEKİ ÇIKTILAR:
- Finansal Etki: {financial_output}
- Risk Değerlendirmesi: {risk_output}
- İstatistiksel Analiz: {stat_output}

GÖREV — Stratejik öneriler sun:

### Kısa Vade (1-4 hafta):
- Hemen yapılması gereken 2-3 aksiyon
- Sorumlu departman/kişi
- Beklenen etki

### Orta Vade (1-3 ay):
- Süreç iyileştirme ve yapısal değişiklikler
- Yatırım gerektiren aksiyonlar
- KPI hedefleri

### Uzun Vade (3-12 ay):
- Stratejik dönüşüm önerileri
- Teknoloji/altyapı yatırımları
- Rekabet avantajı oluşturacak adımlar

Her öneride: Ne → Neden → Nasıl → Kim → Ne zaman → Beklenen etki (₺/%)

Soru: {question}""",
    },
}


# ══════════════════════════════════════════════════════════════
# 3. PİPELİNE YÖNETİCİSİ
# ══════════════════════════════════════════════════════════════

def should_use_pipeline(question: str, mode: str, intent: str) -> bool:
    """Bu soru multi-agent pipeline gerektiriyor mu?
    
    Pipeline sadece karmaşık analiz/rapor sorularında aktif olur.
    Sohbet, basit bilgi soruları için gereksiz overhead.
    """
    # Sadece analiz ağırlıklı modlar
    if mode not in ("Analiz", "Rapor", "Öneri", "Acil"):
        return False
    
    # Intent kontrolü — iş veya bilgi sorusu olmalı
    if intent not in ("iş", "bilgi"):
        return False
    
    # Soru yeterince karmaşık mı? (15+ kelime)
    if len(question.split()) < 15:
        return False
    
    return True


def build_agent_prompt(agent_name: str, question: str, context: str = "", 
                       prev_outputs: dict = None) -> str:
    """Ajana özel prompt oluştur."""
    agent_config = AGENT_PROMPTS.get(agent_name, {})
    template = agent_config.get("prompt", "")
    
    if not template:
        return f"Analiz et: {question}"
    
    prev = prev_outputs or {}
    
    return template.format(
        question=question,
        context=context,
        prev_output=prev.get("DataValidatorAgent", "Henüz yok"),
        data_quality=prev.get("DataValidatorAgent", "Bilinmiyor"),
        stat_output=prev.get("StatisticalAgent", "Henüz yok"),
        risk_output=prev.get("RiskScoringAgent", "Henüz yok"),
        financial_output=prev.get("FinancialImpactAgent", "Henüz yok"),
    )


PIPELINE_ORDER = [
    "DataValidatorAgent",
    "StatisticalAgent",
    "RiskScoringAgent",
    "FinancialImpactAgent",
    "StrategyAgent",
]


# ══════════════════════════════════════════════════════════════
# 4. DYNAMIC AGENT ROUTING — Context-Aware Branching
# ══════════════════════════════════════════════════════════════

ROUTING_RULES = {
    "high_volatility": {
        "condition": "Trend veya oynaklık yüksek",
        "action": "Monte Carlo ajanı eklenir",
        "extra_agents": ["MonteCarloAgent"],
    },
    "critical_kpi": {
        "condition": "KPI kritik seviyede",
        "action": "Risk ajanı öncelikli çalışır",
        "reorder": ["DataValidatorAgent", "RiskScoringAgent", "StatisticalAgent", 
                     "FinancialImpactAgent", "StrategyAgent"],
    },
    "low_data_quality": {
        "condition": "Veri kalitesi düşük",
        "action": "Veri onarlama modu aktif",
        "skip_agents": ["FinancialImpactAgent"],  # Güvenilmez veri ile finansal projeksiyon yapma
    },
    "financial_focus": {
        "condition": "Finansal analiz ağırlıklı",
        "action": "Finansal ajan genişletilir",
        "extra_agents": ["MonteCarloAgent"],
    },
}

# Monte Carlo ajan prompt'u
AGENT_PROMPTS["MonteCarloAgent"] = {
    "role": "Olasılıksal risk simülasyonu ve belirsizlik analizi",
    "prompt": """Sen bir Monte Carlo Simülasyon Uzmanısın.

ÖNCEKİ ÇIKTILAR:
- İstatistik: {stat_output}
- Risk: {risk_output}

GÖREV:
1. Mevcut verilerdeki belirsizlik/volatilite seviyesini değerlendir
2. Hedef başarısızlık olasılığını tahmin et (%olasılık)
3. En kötü durum kaybını tahmin et
4. Volatilite indeksi belirt (Düşük/Orta/Yüksek/Çok Yüksek)
5. VaR (Value at Risk) — %95 güvenle maksimum kayıp

Mümkünse tablo kullan. Somut sayılar ver.

Soru: {question}""",
}


def determine_dynamic_route(question: str, context: str, mode: str,
                            prev_outputs: dict = None) -> list[str]:
    """Soruya ve bağlama göre dinamik ajan sırasını belirle.
    
    Context-aware dynamic branching:
    - Volatilite yüksekse → MC ajan eklenir
    - Kritik KPI varsa → Risk önce
    - Veri düşükse → Finansal projeksiyon atlanır
    - Finansal odak → MC ajan eklenir
    """
    q = question.lower()
    route = list(PIPELINE_ORDER)  # Kopyasını al
    
    data_quality_output = (prev_outputs or {}).get("DataValidatorAgent", "")
    
    # ── Kural 1: Finansal odaklı sorular → Monte Carlo ekle
    import re
    if re.search(r'(gelir|maliyet|kâr|zarar|bütçe|yatırım|finansal|mali|₺|ciro)', q):
        if "MonteCarloAgent" not in route:
            # FinancialImpact'tan sonra ekle
            idx = route.index("FinancialImpactAgent") + 1 if "FinancialImpactAgent" in route else -1
            route.insert(idx, "MonteCarloAgent")
            logger.info("dynamic_routing", rule="financial_focus", added="MonteCarloAgent")
    
    # ── Kural 2: Risk/tehlike ağırlıklı → Risk ajanı önce
    if re.search(r'(risk|tehlike|tehdit|kriz|acil|kritik|düşüş|kayıp|zarar)', q):
        if "RiskScoringAgent" in route:
            route.remove("RiskScoringAgent")
            route.insert(1, "RiskScoringAgent")  # DataValidator'dan hemen sonra
            logger.info("dynamic_routing", rule="critical_kpi", reordered=True)
    
    # ── Kural 3: Volatilite / belirsizlik soruları → Monte Carlo ekle
    if re.search(r'(belirsizlik|volatilite|dalgalanma|öngörüleme|tahmin.*risk|olasılık)', q):
        if "MonteCarloAgent" not in route:
            route.insert(-1, "MonteCarloAgent")  # Strategy'den önce
            logger.info("dynamic_routing", rule="high_volatility", added="MonteCarloAgent")
    
    # ── Kural 4: Düşük veri kalitesi tespit edilmişse → Finansal projeksiyon atla
    if data_quality_output and re.search(r'(yetersiz|eksik|düşük.*kalite|0-49|güvenilmez)', 
                                          data_quality_output, re.I):
        if "FinancialImpactAgent" in route:
            route.remove("FinancialImpactAgent")
            logger.info("dynamic_routing", rule="low_data_quality", 
                       removed="FinancialImpactAgent")
    
    # ── Kural 5: Acil mod → Kısa zincir (veri → risk → strateji)
    if mode == "Acil":
        route = ["DataValidatorAgent", "RiskScoringAgent", "StrategyAgent"]
        logger.info("dynamic_routing", rule="urgent_mode", agents=route)
    
    return route


async def execute_agent_pipeline(
    question: str,
    context: str,
    llm_generate,
    mode: str = "Analiz",
) -> PipelineResult:
    """Multi-agent pipeline'ı dinamik routing ile çalıştır.
    
    Args:
        question: Kullanıcı sorusu
        context: RAG/web/hafıza bağlamı
        llm_generate: LLM generate fonksiyonu (async)
        mode: Yanıt modu
    
    Returns:
        PipelineResult — tüm ajanların çıktısı ve birleştirilmiş sonuç
    """
    pipeline = PipelineResult(question=question)
    prev_outputs = {}
    
    # Dinamik rota belirle
    agent_route = determine_dynamic_route(question, context, mode)
    
    logger.info("agent_pipeline_started", 
                question=question[:80], 
                agents=len(agent_route),
                route=agent_route)
    
    for agent_name in agent_route:
        agent_config = AGENT_PROMPTS.get(agent_name, {})
        role = agent_config.get("role", "")
        
        try:
            # Ajan prompt'u oluştur
            agent_prompt = build_agent_prompt(
                agent_name, question, context, prev_outputs
            )
            
            # LLM'e sor — düşük temperature (deterministik)
            agent_answer = await llm_generate(
                prompt=agent_prompt,
                system_prompt=f"Sen bir {role} uzmanısın. Kısa, yapısal ve somut yanıt ver. Türkçe konuş.",
                temperature=0.2,
                max_tokens=400,
            )
            
            result = AgentResult(
                agent_name=agent_name,
                role=role,
                output=agent_answer,
                confidence=0.8,
            )
            
            # Önceki çıktılara ekle (sonraki ajanlar görsün)
            prev_outputs[agent_name] = agent_answer
            
            # ── DYNAMIC RE-ROUTE: DataValidator sonrası rotayı güncelle ──
            if agent_name == "DataValidatorAgent":
                agent_route = determine_dynamic_route(
                    question, context, mode, prev_outputs
                )
                logger.info("dynamic_reroute_after_validation", new_route=agent_route)
            
            logger.info("agent_completed", 
                        agent=agent_name, 
                        output_length=len(agent_answer))
            
        except Exception as e:
            logger.warning("agent_failed", agent=agent_name, error=str(e))
            result = AgentResult(
                agent_name=agent_name,
                role=role,
                output="",
                skip_reason=str(e),
            )
            prev_outputs[agent_name] = f"[Hata: {str(e)[:100]}]"
        
        pipeline.agent_results.append(result)
    
    # ── TÜM AJANLARIN ÇIKTISINI BİRLEŞTİR ──
    pipeline.final_answer = _synthesize_pipeline(pipeline, prev_outputs)
    
    # Confidence hesapla
    successful = [a for a in pipeline.agent_results if not a.skip_reason]
    pipeline.overall_confidence = (len(successful) / len(PIPELINE_ORDER)) * 90
    
    logger.info("agent_pipeline_completed", 
                agents_success=len(successful),
                confidence=pipeline.overall_confidence)
    
    return pipeline


def _synthesize_pipeline(pipeline: PipelineResult, outputs: dict) -> str:
    """Tüm ajan çıktılarını tek bir executive rapor formatında birleştir."""
    sections = []
    
    # 1. Executive Summary
    sections.append("## 📋 Yönetici Özeti (Multi-Agent Analiz)\n")
    
    # Data Validator çıktısı
    if outputs.get("DataValidatorAgent"):
        sections.append(f"### 📊 Veri Kalitesi\n{outputs['DataValidatorAgent'][:300]}\n")
    
    # Statistical çıktısı
    if outputs.get("StatisticalAgent"):
        sections.append(f"### 📈 İstatistiksel Analiz\n{outputs['StatisticalAgent'][:400]}\n")
    
    # Risk çıktısı
    if outputs.get("RiskScoringAgent"):
        sections.append(f"### ⚠️ Risk Değerlendirmesi\n{outputs['RiskScoringAgent'][:400]}\n")
    
    # Financial Impact çıktısı
    if outputs.get("FinancialImpactAgent"):
        sections.append(f"### 💰 Finansal Etki Projeksiyonu\n{outputs['FinancialImpactAgent'][:400]}\n")
    
    # Strategy çıktısı
    if outputs.get("StrategyAgent"):
        sections.append(f"### 🎯 Stratejik Öneriler\n{outputs['StrategyAgent'][:500]}\n")
    
    return "\n".join(sections)


def format_pipeline_summary(pipeline: PipelineResult) -> str:
    """Pipeline sonucu için kısa özet — yanıt sonuna eklenir."""
    agents_ok = sum(1 for a in pipeline.agent_results if not a.skip_reason)
    total = len(pipeline.agent_results)
    
    summary = f"\n\n---\n🤖 **Multi-Agent Analiz** | "
    summary += f"{agents_ok}/{total} uzman ajan | "
    summary += f"Güven: %{pipeline.overall_confidence:.0f}"
    
    agent_icons = {
        "DataValidatorAgent": "📊",
        "StatisticalAgent": "📈",
        "RiskScoringAgent": "⚠️",
        "FinancialImpactAgent": "💰",
        "StrategyAgent": "🎯",
    }
    
    agents_text = " → ".join(
        f"{agent_icons.get(a.agent_name, '🔹')}"
        for a in pipeline.agent_results
        if not a.skip_reason
    )
    summary += f"\n{agents_text}"
    
    return summary


# ══════════════════════════════════════════════════════════════
# 5. PARALEL AGENT PIPELINE (v3.9.0)
# ══════════════════════════════════════════════════════════════

# Bağımsız çalışabilecek ajan grupları tanımı
PARALLEL_GROUPS = [
    # Grup 1: Sadece DataValidator (temel, ilk çalışmalı)
    ["DataValidatorAgent"],
    # Grup 2: Statistical + Risk paralel (birbirinden bağımsız çalışabilir)
    ["StatisticalAgent", "RiskScoringAgent"],
    # Grup 3: Financial + Monte Carlo (önceki sonuçlara bağımlı)
    ["FinancialImpactAgent"],
    # Grup 4: Strateji (hepsinin sonucuna bağımlı)
    ["StrategyAgent"],
]


async def _run_single_agent(
    agent_name: str,
    question: str,
    context: str,
    prev_outputs: dict,
    llm_generate,
) -> AgentResult:
    """Tek bir ajanı çalıştır."""
    agent_config = AGENT_PROMPTS.get(agent_name, {})
    role = agent_config.get("role", "")
    
    try:
        agent_prompt = build_agent_prompt(agent_name, question, context, prev_outputs)
        agent_answer = await llm_generate(
            prompt=agent_prompt,
            system_prompt=f"Sen bir {role} uzmanısın. Kısa, yapısal ve somut yanıt ver. Türkçe konuş.",
            temperature=0.2,
            max_tokens=400,
        )
        return AgentResult(
            agent_name=agent_name,
            role=role,
            output=agent_answer,
            confidence=0.8,
        )
    except Exception as e:
        logger.warning("agent_failed", agent=agent_name, error=str(e))
        return AgentResult(
            agent_name=agent_name,
            role=role,
            output="",
            skip_reason=str(e),
        )


async def execute_parallel_pipeline(
    question: str,
    context: str,
    llm_generate,
    mode: str = "Analiz",
) -> PipelineResult:
    """Multi-agent pipeline'ı paralel gruplarla çalıştır (v3.9.0).
    
    Bağımsız ajanlar aynı anda çalışarak toplam süreyi kısaltır.
    DataValidator → [Statistical ∥ Risk] → Financial → Strategy
    """
    pipeline = PipelineResult(question=question)
    prev_outputs = {}
    
    logger.info("parallel_pipeline_started", question=question[:80])
    
    for group in PARALLEL_GROUPS:
        # Filtreleme: sadece route'ta olanları çalıştır
        route = determine_dynamic_route(question, context, mode, prev_outputs)
        agents_in_group = [a for a in group if a in route]
        
        if not agents_in_group:
            continue
        
        if len(agents_in_group) == 1:
            # Tekli — sequential
            result = await _run_single_agent(
                agents_in_group[0], question, context, prev_outputs, llm_generate
            )
            pipeline.agent_results.append(result)
            prev_outputs[result.agent_name] = result.output or f"[Atlandı: {result.skip_reason}]"
        else:
            # Paralel çalıştır
            tasks = [
                _run_single_agent(agent, question, context, prev_outputs, llm_generate)
                for agent in agents_in_group
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for r in results:
                if isinstance(r, Exception):
                    logger.warning("parallel_agent_exception", error=str(r))
                    continue
                pipeline.agent_results.append(r)
                prev_outputs[r.agent_name] = r.output or f"[Atlandı: {r.skip_reason}]"
            
            logger.info("parallel_group_completed", agents=agents_in_group)
    
    # Birleştir
    pipeline.final_answer = _synthesize_pipeline(pipeline, prev_outputs)
    successful = [a for a in pipeline.agent_results if not a.skip_reason]
    pipeline.overall_confidence = (len(successful) / max(len(PIPELINE_ORDER), 1)) * 90
    
    logger.info("parallel_pipeline_completed",
                agents_success=len(successful),
                confidence=pipeline.overall_confidence)
    
    return pipeline
