"""Çok Adımlı Reasoning Engine — ReAct Pattern (v2)

Karmaşık soruları adım adım çözer:
1. Thought (Düşün) — Soruyu analiz et
2. Action (Eylem) — Araç kullan veya bilgi topla
3. Observation (Gözlem) — Sonucu değerlendir
4. ... (tekrarla)
5. Final Answer — Son yanıt

Özellikler:
- Dinamik derinlik (5-10 adım arası, soru karmaşıklığına göre)
- Backtracking: başarısız adımlarda alternatif eylem dene
- Güven bazlı dallanma: yüksek güvende erken dur, düşükte devam et
- ReasoningTree: dallanmalı akıl yürütme, en iyi dalı seç
- Adım meta verileri: süre, token, güven
- ReasoningEngine singleton: merkezi yönetim, dashboard, istatistik
"""

import re
import time
import structlog
from dataclasses import dataclass, field
from typing import Optional

logger = structlog.get_logger()

MAX_REASONING_STEPS = 5

# ---------------------------------------------------------------------------
# Yardımcı veri yapıları
# ---------------------------------------------------------------------------

@dataclass
class StepMetadata:
    """Her reasoning adımına ait meta veri."""
    duration_ms: float = 0.0
    tokens_used: int = 0
    confidence: float = 0.0
    backtracked: bool = False
    alternative_action: Optional[str] = None


class ReasoningStep:
    """Tek bir reasoning adımı."""
    def __init__(self, step_num: int, thought: str = "", action: str = "",
                 action_input: dict = None, observation: str = ""):
        self.step_num = step_num
        self.thought = thought
        self.action = action
        self.action_input = action_input or {}
        self.observation = observation
        # v2: meta veri alanları
        self.metadata = StepMetadata()

    def to_dict(self) -> dict:
        return {
            "step": self.step_num,
            "thought": self.thought,
            "action": self.action,
            "action_input": self.action_input,
            "observation": self.observation,
            "metadata": {
                "duration_ms": self.metadata.duration_ms,
                "tokens_used": self.metadata.tokens_used,
                "confidence": self.metadata.confidence,
                "backtracked": self.metadata.backtracked,
            },
        }


class ReasoningChain:
    """Tüm reasoning zinciri."""
    def __init__(self, question: str, conversation_context: str = ""):
        self.question = question
        self.conversation_context = conversation_context  # Önceki konuşma bağlamı
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
            "conversation_aware": bool(self.conversation_context),
        }

    def get_context_for_llm(self) -> str:
        """LLM'e gönderilecek reasoning context."""
        text = ""
        # Konuşma bağlamı varsa ekle
        if self.conversation_context:
            text += f"## Konuşma Geçmişi (Önceki Bağlam)\n{self.conversation_context}\n\n"

        text += f"## Reasoning Zinciri\nSoru: {self.question}\n\n"
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

    # v2 yardımcı metotlar --------------------------------------------------
    def get_avg_step_confidence(self) -> float:
        """Adım güvenlerinin ortalaması."""
        confs = [s.metadata.confidence for s in self.steps if s.metadata.confidence > 0]
        return sum(confs) / len(confs) if confs else 0.0

    def total_duration_ms(self) -> float:
        """Toplam zincir süresi (ms)."""
        return sum(s.metadata.duration_ms for s in self.steps)

    def backtrack_count(self) -> int:
        """Kaç adımda backtracking yapıldı."""
        return sum(1 for s in self.steps if s.metadata.backtracked)


# ---------------------------------------------------------------------------
# ReasoningTree — dallanmalı akıl yürütme
# ---------------------------------------------------------------------------

class ReasoningBranch:
    """Bir reasoning dalı — kendi adım listesi ve skoru var."""
    def __init__(self, branch_id: int, description: str = ""):
        self.branch_id = branch_id
        self.description = description
        self.steps: list[ReasoningStep] = []
        self.score: float = 0.0
        self.final_answer: str = ""

    def add_step(self, step: ReasoningStep):
        self.steps.append(step)

    def compute_score(self) -> float:
        """Dal skorunu hesapla: güven + adım çeşitliliği + gözlem kalitesi."""
        if not self.steps:
            return 0.0
        conf_avg = sum(s.metadata.confidence for s in self.steps) / len(self.steps)
        obs_quality = sum(1 for s in self.steps if s.observation and len(s.observation) > 20) / len(self.steps)
        backtrack_penalty = sum(1 for s in self.steps if s.metadata.backtracked) * 0.05
        self.score = round(min(1.0, conf_avg * 0.6 + obs_quality * 0.4 - backtrack_penalty), 3)
        return self.score


class ReasoningTree:
    """Dallanmalı reasoning ağacı — birden fazla yol dener, en iyisini seçer."""
    def __init__(self, question: str):
        self.question = question
        self.branches: list[ReasoningBranch] = []
        self._next_id = 0

    def create_branch(self, description: str = "") -> ReasoningBranch:
        """Yeni dal oluştur."""
        branch = ReasoningBranch(self._next_id, description)
        self._next_id += 1
        self.branches.append(branch)
        return branch

    def best_branch(self) -> Optional[ReasoningBranch]:
        """En yüksek skorlu dalı döndür."""
        if not self.branches:
            return None
        for b in self.branches:
            b.compute_score()
        return max(self.branches, key=lambda b: b.score)

    def to_dict(self) -> dict:
        return {
            "question": self.question,
            "branches": [
                {
                    "id": b.branch_id,
                    "desc": b.description,
                    "steps": len(b.steps),
                    "score": b.compute_score(),
                }
                for b in self.branches
            ],
            "best_branch_id": self.best_branch().branch_id if self.branches else None,
        }


# ---------------------------------------------------------------------------
# Karmaşıklık & planlama fonksiyonları
# ---------------------------------------------------------------------------

def _compute_complexity_score(question: str, context: dict) -> int:
    """Sorunun karmaşıklık puanını hesapla (0-15 arası)."""
    q = question.lower()
    signals = [
        # Karşılaştırma
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
        # v2: Veri referansı (tablo, grafik, excel, rapor)
        bool(re.search(r'(tablo|grafik|excel|rapor|veri\s*seti|csv|json)', q)),
        # v2: Çoklu metrik analizi
        bool(re.search(r'(oran.*oran|metrik.*metrik|kpi.*kpi)', q)),
        # v2: Zamansal karşılaştırma
        bool(re.search(r'(geçen\s*(ay|yıl|hafta).*bu\s*(ay|yıl|hafta)|dönem.*karşılaştır)', q)),
        # v2: Çapraz referans (birden fazla kaynak)
        bool(re.search(r'(kaynak.*kaynak|sistem.*sistem|farklı.*veri)', q)),
        # v2: Derinlemesine analiz isteği
        bool(re.search(r'(detay|derinlemesine|kapsamlı|ayrıntılı)', q)),
        # v2: Çoklu soru cümlesi (birden fazla soru işareti)
        q.count('?') >= 2,
        # v2: Optimizasyon / iyileştirme sorusu
        bool(re.search(r'(optimiz|iyileştir|verimlilik|minimize|maksimize)', q)),
    ]
    return sum(signals)


def _compute_dynamic_max_steps(complexity_score: int) -> int:
    """Karmaşıklığa göre dinamik adım limiti (5-10 arası)."""
    if complexity_score <= 2:
        return 5
    elif complexity_score <= 4:
        return 6
    elif complexity_score <= 6:
        return 7
    elif complexity_score <= 8:
        return 8
    elif complexity_score <= 10:
        return 9
    else:
        return 10


def needs_multi_step(question: str, context: dict) -> bool:
    """Bu soru çok adımlı reasoning gerektiriyor mu?"""
    complexity_score = _compute_complexity_score(question, context)

    # Intent iş/analiz ise ve 2+ sinyal varsa multi-step
    intent = context.get("intent", "sohbet")
    if intent in ("iş", "bilgi") and complexity_score >= 2:
        return True
    if complexity_score >= 3:
        return True

    return False


# Eylem tipleri — v2 genişletilmiş
_ACTION_TYPES = {
    "analyze_question": "Soruyu analiz et",
    "analyze_data": "Veri analizi yap",
    "search_documents": "Bilgi tabanında ara",
    "web_search": "Güncel bilgi ara (web)",
    "calculate": "Hesaplama yap",
    "interpret": "Sonuçları yorumla",
    "synthesize": "Bulguları sentezle",
    # v2 yeni eylem tipleri
    "verify_result": "Sonucu doğrula / çapraz kontrol",
    "compare": "Değerleri karşılaştır",
    "deep_dive": "Derinlemesine analiz yap",
    "cross_reference": "Çapraz referans kontrolü",
}

# Alternatif eylemler — backtracking sırasında kullanılır
_FALLBACK_ACTIONS = {
    "search_documents": "web_search",
    "web_search": "search_documents",
    "calculate": "interpret",
    "analyze_data": "search_documents",
    "verify_result": "interpret",
    "compare": "interpret",
    "deep_dive": "analyze_data",
    "cross_reference": "search_documents",
}


def plan_reasoning_steps(question: str, context: dict) -> list[dict]:
    """Soru için reasoning planı oluştur (v2 zenginleştirilmiş)."""
    q = question.lower()
    steps = []

    # Karmaşıklık & dinamik derinlik
    complexity = _compute_complexity_score(question, context)
    max_steps = _compute_dynamic_max_steps(complexity)

    # Adım 1: Her zaman — soruyu analiz et
    steps.append({
        "thought": "Soruyu analiz ediyorum: Ne soruluyor, hangi veriler gerekli?",
        "action": "analyze_question",
    })

    # Adım 2: Veri toplama — duruma göre
    if re.search(r'(veri|dosya|tablo|rapor|excel|csv)', q):
        steps.append({"thought": "Veri analizi gerekiyor", "action": "analyze_data"})

    if re.search(r'(bilgi\s*taban|doküman|kaynak)', q):
        steps.append({"thought": "Bilgi tabanında aranmalı", "action": "search_documents"})

    if context.get("needs_web"):
        steps.append({"thought": "Güncel bilgi gerekiyor", "action": "web_search"})

    # Adım 3: Hesaplama varsa
    if re.search(r'(hesapla|oran|yüzde|toplam|ortalama|fire|oee|maliyet)', q):
        steps.append({"thought": "Hesaplama yapılmalı", "action": "calculate"})

    # v2: Karşılaştırma adımı
    if re.search(r'(karşılaştır|kıyasla|versus|vs|fark|benchmark)', q):
        steps.append({"thought": "Değerlerin karşılaştırılması gerekiyor", "action": "compare"})

    # v2: Derinlemesine analiz
    if re.search(r'(detay|derinlemesine|kapsamlı|ayrıntılı|neden)', q):
        steps.append({"thought": "Derinlemesine analiz yapılacak", "action": "deep_dive"})

    # v2: Çapraz referans
    if re.search(r'(kaynak|referans|doğrula|cross|çapraz)', q):
        steps.append({"thought": "Çapraz referans kontrolü gerekli", "action": "cross_reference"})

    # Adım: Yorumlama
    if re.search(r'(yorumla|değerlendir|analiz|kıyasla)', q):
        steps.append({"thought": "Sonuçları yorumla ve karşılaştır", "action": "interpret"})

    # v2: Doğrulama adımı (karmaşık sorularda)
    if complexity >= 4:
        steps.append({"thought": "Sonuçları doğrula ve tutarlılık kontrolü yap", "action": "verify_result"})

    # Son adım: Her zaman — sonuç ve tavsiye
    steps.append({
        "thought": "Tüm bulguları birleştir, tavsiye oluştur",
        "action": "synthesize",
    })

    return steps[:max_steps]


def build_reasoning_prompt(question: str, chain: ReasoningChain, step_plan: dict) -> str:
    """Reasoning adımı için LLM prompt'u oluştur."""
    dynamic_max = _compute_dynamic_max_steps(
        _compute_complexity_score(question, {})
    )
    prompt = f"""## Çok Adımlı Analiz — Adım {len(chain.steps) + 1}/{dynamic_max}

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
                bt_flag = " ↩️" if step.metadata.backtracked else ""
                output += f"**{step.step_num}.** {step.thought}{bt_flag}\n"
            if step.observation:
                output += f"   → {step.observation[:200]}\n"
        output += "\n---\n\n"

    # Son yanıt
    output += chain.final_answer

    return output


def summarize_reasoning(chain: ReasoningChain) -> str:
    """Reasoning zincirinin kompakt özeti — dashboard ve log için."""
    total_steps = len(chain.steps)
    bt = chain.backtrack_count()
    dur = chain.total_duration_ms()
    avg_conf = chain.get_avg_step_confidence()
    tools = ", ".join(chain.tools_used) if chain.tools_used else "yok"
    lines = [
        f"📊 Reasoning Özeti",
        f"  Soru     : {chain.question[:80]}",
        f"  Adım     : {total_steps}",
        f"  Süre     : {dur:.0f} ms",
        f"  Ort.Güven: {avg_conf:.2f}",
        f"  Backtrack: {bt}",
        f"  Araçlar  : {tools}",
        f"  Sonuç    : {chain.final_answer[:120] if chain.final_answer else '-'}",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Backtracking yardımcıları
# ---------------------------------------------------------------------------

def _is_step_failed(step: ReasoningStep) -> bool:
    """Adım başarısız mı? (boş veya hata gözlemi)"""
    obs = step.observation.strip() if step.observation else ""
    if not obs:
        return True
    fail_patterns = ["hata", "error", "bulunamadı", "sonuç vermedi", "başarısız", "timeout"]
    return any(p in obs.lower() for p in fail_patterns)


def _get_fallback_action(action: str) -> Optional[str]:
    """Başarısız eylem için alternatif eylem döndür."""
    return _FALLBACK_ACTIONS.get(action)


# ---------------------------------------------------------------------------
# Güven hesaplama
# ---------------------------------------------------------------------------

def _estimate_step_confidence(step: ReasoningStep) -> float:
    """Bir adımın güven skorunu tahmin et (0-1)."""
    if not step.observation:
        return 0.1
    obs = step.observation
    length_score = min(1.0, len(obs) / 300)  # Daha uzun gözlem → daha fazla bilgi
    # Sayısal veri içeriyorsa güven artar
    has_numbers = bool(re.search(r'\d+[\.,]\d+|\d{2,}', obs))
    numeric_bonus = 0.1 if has_numbers else 0.0
    # Hata/olumsuz ifade varsa güven düşer
    negative = bool(re.search(r'(hata|error|bulunamadı|yok|başarısız)', obs.lower()))
    negative_penalty = 0.2 if negative else 0.0
    # Kaynak referansı varsa güven artar
    has_source = bool(re.search(r'(kaynak|doküman|tablo|rapor)', obs.lower()))
    source_bonus = 0.1 if has_source else 0.0

    conf = 0.3 + length_score * 0.4 + numeric_bonus + source_bonus - negative_penalty
    return round(max(0.05, min(1.0, conf)), 3)


def _should_stop_early(chain: ReasoningChain) -> bool:
    """Güven yeterince yüksekse erken durma kararı."""
    if len(chain.steps) < 2:
        return False
    avg = chain.get_avg_step_confidence()
    # Son adımın güveni çok yüksekse ve ortalama da iyiyse dur
    last_conf = chain.steps[-1].metadata.confidence if chain.steps else 0
    return avg > 0.85 and last_conf > 0.9


def _should_add_extra_steps(chain: ReasoningChain) -> bool:
    """Güven düşükse ek adım eklensin mi?"""
    if len(chain.steps) < 2:
        return False
    avg = chain.get_avg_step_confidence()
    return avg < 0.5


# ---------------------------------------------------------------------------
# Ana çalıştırma fonksiyonu
# ---------------------------------------------------------------------------

async def execute_reasoning_chain(
    question: str,
    context: dict,
    llm_generate,
    tool_execute=None,
    rag_search=None,
    web_search=None,
    session_history: list = None,
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
        session_history: Önceki konuşma geçmişi (conversation-aware reasoning)

    Returns:
        {"answer": str, "reasoning": ReasoningChain, "tools_used": list}
    """
    chain_start = time.time()

    # Conversation-aware: Önceki soru-cevapları reasoning bağlamına ekle
    conv_context = ""
    if session_history:
        recent = session_history[-3:]  # Son 3 mesaj
        for msg in recent:
            role = msg.get("role", "user")
            content = msg.get("content", "")[:300]
            if role == "user":
                conv_context += f"**Kullanıcı**: {content}\n"
            elif role == "assistant":
                conv_context += f"**AI**: {content}\n"

    chain = ReasoningChain(question, conversation_context=conv_context)
    step_plans = plan_reasoning_steps(question, context)

    # Dinamik derinlik
    complexity = _compute_complexity_score(question, context)
    dynamic_max = _compute_dynamic_max_steps(complexity)

    logger.info("reasoning_chain_started",
                question=question[:80],
                planned_steps=len(step_plans),
                dynamic_max=dynamic_max,
                complexity=complexity)

    # Step-to-step data chaining: önceki adım çıktıları bir sonrakine aktarılır
    accumulated_context = ""

    for i, step_plan in enumerate(step_plans):
        # Güven bazlı erken durma
        if _should_stop_early(chain):
            logger.info("reasoning_early_stop", step=i, avg_conf=chain.get_avg_step_confidence())
            break

        step_start = time.time()
        step = ReasoningStep(step_num=i + 1, thought=step_plan.get("thought", ""))
        action = step_plan.get("action", "")
        step.action = action

        try:
            await _execute_step_action(
                step, action, question, chain, accumulated_context,
                llm_generate, tool_execute, rag_search, web_search,
            )
        except Exception as e:
            step.observation = f"Hata: {str(e)}"
            logger.warning("reasoning_step_error", step=i + 1, error=str(e))

        # Adım süresini kaydet
        step.metadata.duration_ms = round((time.time() - step_start) * 1000, 1)

        # Güven skoru hesapla
        step.metadata.confidence = _estimate_step_confidence(step)

        # Backtracking: adım başarısızsa alternatif dene
        if _is_step_failed(step):
            fallback = _get_fallback_action(action)
            if fallback:
                logger.info("reasoning_backtrack", original=action, fallback=fallback)
                step.metadata.backtracked = True
                step.metadata.alternative_action = fallback
                bt_start = time.time()
                try:
                    await _execute_step_action(
                        step, fallback, question, chain, accumulated_context,
                        llm_generate, tool_execute, rag_search, web_search,
                    )
                except Exception as e:
                    step.observation = f"Backtrack hatası ({fallback}): {str(e)}"
                step.metadata.duration_ms += round((time.time() - bt_start) * 1000, 1)
                step.metadata.confidence = _estimate_step_confidence(step)

        # Step-to-step data chaining — observation'ı bir sonraki adıma aktar
        if step.observation and not step.observation.startswith(f"Adım tamamlandı"):
            accumulated_context += f"\n### Adım {step.step_num} ({action}):\n{step.observation[:500]}\n"

        chain.add_step(step)

    # Güven düşükse ve plan limiti dolmadıysa ek adım ekle
    if _should_add_extra_steps(chain) and len(chain.steps) < dynamic_max:
        extra_step = ReasoningStep(
            step_num=len(chain.steps) + 1,
            thought="Güven düşük — ek doğrulama ve sentez yapılıyor",
        )
        extra_step.action = "verify_result"
        es_start = time.time()
        try:
            await _execute_step_action(
                extra_step, "verify_result", question, chain, accumulated_context,
                llm_generate, tool_execute, rag_search, web_search,
            )
        except Exception as e:
            extra_step.observation = f"Ek doğrulama hatası: {str(e)}"
        extra_step.metadata.duration_ms = round((time.time() - es_start) * 1000, 1)
        extra_step.metadata.confidence = _estimate_step_confidence(extra_step)
        chain.add_step(extra_step)

    # Confidence hesapla
    base_conf = 0.6
    tool_bonus = len(chain.tools_used) * 0.05
    step_bonus = len(chain.steps) * 0.05
    avg_step_conf = chain.get_avg_step_confidence()
    chain.confidence = min(0.95, base_conf + tool_bonus + step_bonus + avg_step_conf * 0.1)

    total_ms = round((time.time() - chain_start) * 1000, 1)

    logger.info("reasoning_chain_completed",
                steps=len(chain.steps),
                tools_used=chain.tools_used,
                confidence=chain.confidence,
                duration_ms=total_ms,
                backtracks=chain.backtrack_count())

    # Singleton istatistik güncelle
    ReasoningEngine.instance()._record_chain(chain, total_ms)

    return {
        "reasoning_chain": chain,
        "reasoning_context": chain.get_context_for_llm(),
        "tools_used": chain.tools_used,
        "confidence": chain.confidence,
    }


# ---------------------------------------------------------------------------
# Adım eylem çalıştırıcı (tekrarlanan kodu merkezileştir)
# ---------------------------------------------------------------------------

async def _execute_step_action(
    step: ReasoningStep,
    action: str,
    question: str,
    chain: ReasoningChain,
    accumulated_context: str,
    llm_generate,
    tool_execute,
    rag_search,
    web_search,
):
    """Tek bir reasoning adımının eylemini çalıştır."""
    if action == "search_documents" and rag_search:
        docs = rag_search(question, n_results=5)
        if docs:
            step.observation = f"{len(docs)} ilgili doküman bulundu"
            for doc in docs[:3]:
                step.observation += f"\n- {doc.get('source', '?')}: {doc.get('content', '')[:200]}"
        else:
            step.observation = "Bilgi tabanında ilgili doküman bulunamadı"

    elif action == "web_search" and web_search:
        web_result, _ = await web_search(question)
        step.observation = web_result[:500] if web_result else "Web araması sonuç vermedi"

    elif action == "calculate" and tool_execute:
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

    elif action == "analyze_question" and llm_generate:
        analysis_prompt = (
            f"Aşağıdaki soruyu analiz et. Ne soruluyor, hangi veriler gerekli, "
            f"hangi metrikler hesaplanmalı? Kısa ve yapısal cevap ver.\n\n"
            f"Soru: {question}"
        )
        if accumulated_context:
            analysis_prompt += f"\n\nÖnceki adım bulguları:\n{accumulated_context}"
        try:
            result = await llm_generate(
                prompt=analysis_prompt,
                system_prompt="Kısa ve somut analiz yap. Madde madde yaz.",
                temperature=0.2,
                max_tokens=400,
            )
            step.observation = result if result else "Soru analizi tamamlandı"
            step.metadata.tokens_used = len(result.split()) * 2 if result else 0
        except Exception:
            step.observation = "Soru analiz edildi — devam ediliyor"

    elif action == "interpret" and llm_generate:
        interpret_prompt = (
            f"Aşağıdaki analiz sonuçlarını Türkçe olarak yorumla. "
            f"Sayısal veriler varsa trend ve anomali belirt. "
            f"Somut ve kısa yaz.\n\n"
            f"Soru: {question}\n\n"
            f"Şimdiye kadar toplanan bulgular:\n{accumulated_context}\n\n"
            f"Reasoning süreci:\n{chain.get_context_for_llm()}"
        )
        try:
            result = await llm_generate(
                prompt=interpret_prompt,
                system_prompt="Veri yorumlama uzmanısın. Benchmarkla karşılaştır, risk belirt.",
                temperature=0.3,
                max_tokens=500,
            )
            step.observation = result if result else "Yorumlama tamamlandı"
            step.metadata.tokens_used = len(result.split()) * 2 if result else 0
        except Exception as e:
            step.observation = f"Yorumlama hatası: {str(e)}"

    elif action == "synthesize" and llm_generate:
        synthesize_prompt = (
            f"Aşağıdaki çok adımlı analizin tüm bulgularını sentezle. "
            f"Nihai sonuç ve tavsiyeni yaz. Somut aksiyon öner.\n\n"
            f"Orijinal soru: {question}\n\n"
            f"Tüm adım bulguları:\n{accumulated_context}\n\n"
            f"Tam reasoning zinciri:\n{chain.get_context_for_llm()}"
        )
        try:
            result = await llm_generate(
                prompt=synthesize_prompt,
                system_prompt="Sentez uzmanısın. Tüm bulguları birleştir, çelişkileri çöz, net tavsiye ver.",
                temperature=0.3,
                max_tokens=600,
            )
            step.observation = result if result else "Sentez tamamlandı"
            chain.final_answer = result or chain.final_answer
            step.metadata.tokens_used = len(result.split()) * 2 if result else 0
        except Exception as e:
            step.observation = f"Sentez hatası: {str(e)}"

    elif action == "verify_result" and llm_generate:
        verify_prompt = (
            f"Aşağıdaki analiz bulgularını doğrula. Tutarsızlık var mı? "
            f"Sayısal veriler mantıklı mı? Sonuçlar güvenilir mi?\n\n"
            f"Soru: {question}\n\nBulgular:\n{accumulated_context}"
        )
        try:
            result = await llm_generate(
                prompt=verify_prompt,
                system_prompt="Kalite kontrol uzmanısın. Veri tutarlılığını kontrol et.",
                temperature=0.2,
                max_tokens=400,
            )
            step.observation = result if result else "Doğrulama tamamlandı"
            step.metadata.tokens_used = len(result.split()) * 2 if result else 0
        except Exception as e:
            step.observation = f"Doğrulama hatası: {str(e)}"

    elif action == "compare" and llm_generate:
        compare_prompt = (
            f"Aşağıdaki verileri karşılaştır. Temel farkları, avantaj/dezavantajları "
            f"ve önemli değişimleri vurgula.\n\n"
            f"Soru: {question}\n\nMevcut veriler:\n{accumulated_context}"
        )
        try:
            result = await llm_generate(
                prompt=compare_prompt,
                system_prompt="Karşılaştırma uzmanısın. Tablo formatında, net farkları göster.",
                temperature=0.3,
                max_tokens=500,
            )
            step.observation = result if result else "Karşılaştırma tamamlandı"
            step.metadata.tokens_used = len(result.split()) * 2 if result else 0
        except Exception as e:
            step.observation = f"Karşılaştırma hatası: {str(e)}"

    elif action == "deep_dive" and llm_generate:
        deep_prompt = (
            f"Aşağıdaki konuyu derinlemesine analiz et. Kök nedenleri bul, "
            f"gizli kalıpları tespit et, detaylı içgörü sun.\n\n"
            f"Soru: {question}\n\nMevcut bulgular:\n{accumulated_context}"
        )
        try:
            result = await llm_generate(
                prompt=deep_prompt,
                system_prompt="Derin analiz uzmanısın. Yüzeyin altına in, kök nedenleri bul.",
                temperature=0.4,
                max_tokens=600,
            )
            step.observation = result if result else "Derin analiz tamamlandı"
            step.metadata.tokens_used = len(result.split()) * 2 if result else 0
        except Exception as e:
            step.observation = f"Derin analiz hatası: {str(e)}"

    elif action == "cross_reference" and llm_generate:
        xref_prompt = (
            f"Farklı kaynaklardan gelen bilgileri çapraz kontrol et. "
            f"Tutarlılık ve çelişkileri belirle.\n\n"
            f"Soru: {question}\n\nKaynaklar:\n{accumulated_context}"
        )
        try:
            result = await llm_generate(
                prompt=xref_prompt,
                system_prompt="Çapraz referans uzmanısın. Farklı kaynakları karşılaştır, tutarsızlıkları bul.",
                temperature=0.2,
                max_tokens=400,
            )
            step.observation = result if result else "Çapraz kontrol tamamlandı"
            step.metadata.tokens_used = len(result.split()) * 2 if result else 0
        except Exception as e:
            step.observation = f"Çapraz kontrol hatası: {str(e)}"

    else:
        step.observation = f"Adım tamamlandı: {action}"


# ---------------------------------------------------------------------------
# ReasoningEngine — Singleton
# ---------------------------------------------------------------------------

class ReasoningEngine:
    """Merkezi reasoning yöneticisi — singleton pattern.

    Tüm reasoning işlemlerini yönetir, istatistik toplar ve dashboard sunar.
    """
    _instance: Optional["ReasoningEngine"] = None

    def __init__(self):
        """Doğrudan kullanmayın, ReasoningEngine.instance() ile erişin."""
        self._stats: dict = {
            "total_chains": 0,
            "total_steps": 0,
            "avg_steps": 0.0,
            "avg_confidence": 0.0,
            "avg_duration_ms": 0.0,
            "tool_calls": 0,
            "backtrack_count": 0,
            "early_stops": 0,
            "extra_steps_added": 0,
            "action_counts": {},        # eylem tipi → sayı
            "confidence_history": [],    # son 50 zincir güveni
            "duration_history": [],      # son 50 zincir süresi
        }
        self._history: list[dict] = []  # son N zincir özeti

    @classmethod
    def instance(cls) -> "ReasoningEngine":
        """Singleton erişim noktası."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls):
        """Test amaçlı — singleton'ı sıfırla."""
        cls._instance = None

    # --- Kayıt & istatistik ------------------------------------------------

    def _record_chain(self, chain: ReasoningChain, total_ms: float):
        """Tamamlanan zinciri istatistiklere kaydet."""
        s = self._stats
        s["total_chains"] += 1
        s["total_steps"] += len(chain.steps)
        s["tool_calls"] += len(chain.tools_used)
        s["backtrack_count"] += chain.backtrack_count()

        # Çalışan ortalama
        n = s["total_chains"]
        s["avg_steps"] = round(((s["avg_steps"] * (n - 1)) + len(chain.steps)) / n, 2)
        s["avg_confidence"] = round(((s["avg_confidence"] * (n - 1)) + chain.confidence) / n, 3)
        s["avg_duration_ms"] = round(((s["avg_duration_ms"] * (n - 1)) + total_ms) / n, 1)

        # Eylem dağılımı
        for step in chain.steps:
            act = step.action
            s["action_counts"][act] = s["action_counts"].get(act, 0) + 1

        # Son N geçmiş (max 50)
        s["confidence_history"].append(chain.confidence)
        s["duration_history"].append(total_ms)
        if len(s["confidence_history"]) > 50:
            s["confidence_history"] = s["confidence_history"][-50:]
            s["duration_history"] = s["duration_history"][-50:]

        # Özet geçmişi (max 20)
        self._history.append({
            "question": chain.question[:80],
            "steps": len(chain.steps),
            "confidence": chain.confidence,
            "tools": chain.tools_used[:],
            "backtracks": chain.backtrack_count(),
            "duration_ms": total_ms,
        })
        if len(self._history) > 20:
            self._history = self._history[-20:]

    # --- Dashboard ---------------------------------------------------------

    def get_dashboard(self) -> dict:
        """Reasoning istatistik dashboard'u döndür."""
        s = self._stats
        return {
            "total_chains": s["total_chains"],
            "total_steps": s["total_steps"],
            "avg_steps_per_chain": s["avg_steps"],
            "avg_confidence": s["avg_confidence"],
            "avg_duration_ms": s["avg_duration_ms"],
            "tool_calls": s["tool_calls"],
            "backtrack_count": s["backtrack_count"],
            "action_distribution": dict(s["action_counts"]),
            "recent_confidence": s["confidence_history"][-10:],
            "recent_duration_ms": s["duration_history"][-10:],
            "recent_chains": self._history[-5:],
        }

    def get_stats(self) -> dict:
        """Ham istatistik sözlüğü."""
        return dict(self._stats)

    # --- Yüksek seviye API -------------------------------------------------

    async def run(
        self,
        question: str,
        context: dict,
        llm_generate,
        **kwargs,
    ) -> dict:
        """execute_reasoning_chain'i sarmalayan yüksek seviye API."""
        return await execute_reasoning_chain(
            question=question,
            context=context,
            llm_generate=llm_generate,
            **kwargs,
        )

    def should_reason(self, question: str, context: dict) -> bool:
        """needs_multi_step'i sarmalayan yüksek seviye API."""
        return needs_multi_step(question, context)

    def get_complexity(self, question: str, context: dict = None) -> dict:
        """Soru karmaşıklık analizi döndür."""
        ctx = context or {}
        score = _compute_complexity_score(question, ctx)
        return {
            "score": score,
            "max_steps": _compute_dynamic_max_steps(score),
            "needs_multi_step": needs_multi_step(question, ctx),
            "level": "basit" if score <= 2 else "orta" if score <= 5 else "karmaşık",
        }
