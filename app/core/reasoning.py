"""Çok Adımlı Reasoning Engine — ReAct Pattern

Karmaşık soruları adım adım çözer:
1. Thought (Düşün) — Soruyu analiz et
2. Action (Eylem) — Araç kullan veya bilgi topla
3. Observation (Gözlem) — Sonucu değerlendir
4. ... (tekrarla)
5. Final Answer — Son yanıt

Max 5 adım ile döngüsel reasoning.
"""

import re
import structlog
from typing import Optional

logger = structlog.get_logger()

MAX_REASONING_STEPS = 5


class ReasoningStep:
    """Tek bir reasoning adımı."""
    def __init__(self, step_num: int, thought: str = "", action: str = "",
                 action_input: dict = None, observation: str = ""):
        self.step_num = step_num
        self.thought = thought
        self.action = action
        self.action_input = action_input or {}
        self.observation = observation
    
    def to_dict(self) -> dict:
        return {
            "step": self.step_num,
            "thought": self.thought,
            "action": self.action,
            "action_input": self.action_input,
            "observation": self.observation,
        }


class ReasoningChain:
    """Tüm reasoning zinciri."""
    def __init__(self, question: str):
        self.question = question
        self.steps: list[ReasoningStep] = []
        self.final_answer: str = ""
        self.confidence: float = 0.0
        self.tools_used: list[str] = []
    
    def add_step(self, step: ReasoningStep):
        self.steps.append(step)
    
    def to_dict(self) -> dict:
        return {
            "question": self.question,
            "steps": [s.to_dict() for s in self.steps],
            "final_answer": self.final_answer,
            "confidence": self.confidence,
            "tools_used": self.tools_used,
            "total_steps": len(self.steps),
        }
    
    def get_context_for_llm(self) -> str:
        """LLM'e gönderilecek reasoning context."""
        text = f"## Reasoning Zinciri\nSoru: {self.question}\n\n"
        for step in self.steps:
            text += f"### Adım {step.step_num}\n"
            if step.thought:
                text += f"**Düşünce**: {step.thought}\n"
            if step.action:
                text += f"**Eylem**: {step.action}({step.action_input})\n"
            if step.observation:
                text += f"**Gözlem**: {step.observation}\n"
            text += "\n"
        return text


def needs_multi_step(question: str, context: dict) -> bool:
    """Bu soru çok adımlı reasoning gerektiriyor mu?"""
    q = question.lower()
    
    # Karmaşıklık göstergeleri
    complexity_signals = [
        # Birden fazla hesaplama/karşılaştırma
        bool(re.search(r'(karşılaştır|kıyasla|versus|vs|fark)', q)),
        # Çok parçalı soru
        bool(re.search(r'(ve|ayrıca|bunun\s+yanında|hem.*hem)', q)),
        # Koşullu analiz
        bool(re.search(r'(eğer|durumunda|olursa|varsayalım)', q)),
        # Çok adımlı hesaplama
        bool(re.search(r'(hesapla.*ve.*yorumla|analiz.*et.*öner)', q)),
        # Neden-sonuç
        bool(re.search(r'(neden.*ve.*ne\s*yapılmalı|sebep.*çözüm)', q)),
        # Tahmin + analiz
        bool(re.search(r'(tahmin|öngör|projeksiyon|gelecek)', q)),
        # Risk + aksiyon
        bool(re.search(r'risk.*aksiyon|tehlike.*önlem', q)),
        # Soru uzunluğu (30+ kelime genelde karmaşık)
        len(q.split()) > 30,
    ]
    
    complexity_score = sum(complexity_signals)
    
    # Intent iş/analiz ise ve 2+ sinyal varsa multi-step
    intent = context.get("intent", "sohbet")
    if intent in ("iş", "bilgi") and complexity_score >= 2:
        return True
    if complexity_score >= 3:
        return True
    
    return False


def plan_reasoning_steps(question: str, context: dict) -> list[dict]:
    """Soru için reasoning planı oluştur."""
    q = question.lower()
    steps = []
    
    # Adım 1: Her zaman — soruyu analiz et
    steps.append({
        "thought": "Soruyu analiz ediyorum: Ne soruluyor, hangi veriler gerekli?",
        "action": "analyze_question",
    })
    
    # Adım 2: Veri toplama — duruma göre
    if re.search(r'(veri|dosya|tablo|rapor|excel)', q):
        steps.append({"thought": "Veri analizi gerekiyor", "action": "analyze_data"})
    
    if re.search(r'(bilgi\s*taban|doküman|kaynak)', q):
        steps.append({"thought": "Bilgi tabanında aranmalı", "action": "search_documents"})
    
    if context.get("needs_web"):
        steps.append({"thought": "Güncel bilgi gerekiyor", "action": "web_search"})
    
    # Adım 3: Hesaplama varsa
    if re.search(r'(hesapla|oran|yüzde|toplam|ortalama|fire|oee|maliyet)', q):
        steps.append({"thought": "Hesaplama yapılmalı", "action": "calculate"})
    
    # Adım 4: Yorumlama
    if re.search(r'(yorumla|değerlendir|analiz|kıyasla)', q):
        steps.append({"thought": "Sonuçları yorumla ve karşılaştır", "action": "interpret"})
    
    # Adım 5: Her zaman — sonuç ve tavsiye
    steps.append({
        "thought": "Tüm bulguları birleştir, tavsiye oluştur",
        "action": "synthesize",
    })
    
    return steps[:MAX_REASONING_STEPS]


def build_reasoning_prompt(question: str, chain: ReasoningChain, step_plan: dict) -> str:
    """Reasoning adımı için LLM prompt'u oluştur."""
    prompt = f"""## Çok Adımlı Analiz — Adım {len(chain.steps) + 1}/{MAX_REASONING_STEPS}

### Soru: {question}

### Şimdiye Kadar:
{chain.get_context_for_llm()}

### Bu Adımda:
**Düşünce**: {step_plan.get('thought', '')}
**Eylem**: {step_plan.get('action', '')}

Lütfen bu adımı tamamla ve bulgularını yaz. Kısa ve somut ol."""
    
    return prompt


def format_reasoning_result(chain: ReasoningChain) -> str:
    """Reasoning zincirini kullanıcıya gösterilecek formata çevir."""
    output = ""
    
    # Adımları göster (kısa)
    if len(chain.steps) > 1:
        output += "### 🧠 Analiz Süreci\n"
        for step in chain.steps:
            if step.thought:
                output += f"**{step.step_num}.** {step.thought}\n"
            if step.observation:
                output += f"   → {step.observation[:200]}\n"
        output += "\n---\n\n"
    
    # Son yanıt
    output += chain.final_answer
    
    return output


async def execute_reasoning_chain(
    question: str,
    context: dict,
    llm_generate,
    tool_execute=None,
    rag_search=None,
    web_search=None,
) -> dict:
    """
    Tam reasoning zincirini çalıştır.
    
    Args:
        question: Kullanıcı sorusu
        context: Router context
        llm_generate: LLM generate fonksiyonu (async)
        tool_execute: Tool registry execute fonksiyonu (async, optional)
        rag_search: RAG arama fonksiyonu (optional)
        web_search: Web arama fonksiyonu (optional)
    
    Returns:
        {"answer": str, "reasoning": ReasoningChain, "tools_used": list}
    """
    chain = ReasoningChain(question)
    step_plans = plan_reasoning_steps(question, context)
    
    logger.info("reasoning_chain_started", question=question[:80], planned_steps=len(step_plans))
    
    for i, step_plan in enumerate(step_plans):
        step = ReasoningStep(step_num=i + 1, thought=step_plan.get("thought", ""))
        action = step_plan.get("action", "")
        step.action = action
        
        try:
            # Aksiyona göre işlem yap
            if action == "search_documents" and rag_search:
                docs = rag_search(question, n_results=5)
                if docs:
                    step.observation = f"{len(docs)} ilgili doküman bulundu"
                    # Doküman içeriklerini context'e ekle
                    for doc in docs[:3]:
                        step.observation += f"\n- {doc.get('source', '?')}: {doc.get('content', '')[:200]}"
                else:
                    step.observation = "Bilgi tabanında ilgili doküman bulunamadı"
            
            elif action == "web_search" and web_search:
                web_result, _ = await web_search(question)
                step.observation = web_result[:500] if web_result else "Web araması sonuç vermedi"
            
            elif action == "calculate" and tool_execute:
                # Hesaplama gereken metrikleri algıla
                from app.core.tool_registry import detect_tool_calls
                calls = detect_tool_calls(question)
                for call in calls:
                    result = await tool_execute(call["tool"], call["params"])
                    if result.get("success"):
                        step.observation += f"\n{call['tool']}: {result['result']}"
                        chain.tools_used.append(call["tool"])
                if not step.observation:
                    step.observation = "Otomatik hesaplama yapılamadı, LLM ile devam ediliyor"
            
            elif action == "analyze_data":
                step.observation = "Veri analizi modu aktif — yüklenen veriler incelenecek"
            
            elif action in ("interpret", "synthesize", "analyze_question"):
                # Bu adımlar LLM tarafından yanıtlanır
                reasoning_prompt = build_reasoning_prompt(question, chain, step_plan)
                step.observation = "LLM tarafından işlenecek"
            
            else:
                step.observation = f"Adım tamamlandı: {action}"
        
        except Exception as e:
            step.observation = f"Hata: {str(e)}"
            logger.warning("reasoning_step_error", step=i+1, error=str(e))
        
        chain.add_step(step)
    
    # Confidence hesapla
    chain.confidence = min(0.95, 0.6 + (len(chain.tools_used) * 0.05) + (len(chain.steps) * 0.05))
    
    logger.info("reasoning_chain_completed", 
                steps=len(chain.steps), 
                tools_used=chain.tools_used,
                confidence=chain.confidence)
    
    return {
        "reasoning_chain": chain,
        "reasoning_context": chain.get_context_for_llm(),
        "tools_used": chain.tools_used,
        "confidence": chain.confidence,
    }
