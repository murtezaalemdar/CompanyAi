"""
CompanyAI — Workflow Orchestrator
====================================
Temporal-inspired durable workflow engine.

SORUMLULUKLAR:
  ┌──────────────────────────────────────────────────────────────────┐
  │ Katman                │ İşlev                                    │
  ├───────────────────────┼────────────────────────────────────────────┤
  │ WorkflowDefinition    │ Deklaratif iş akışı tanımı               │
  │ WorkflowEngine        │ State machine execution                  │
  │ StepExecutor          │ Adım yürütme + retry + timeout           │
  │ WorkflowStore         │ Durable state persistence                │
  │ SagaCompensation      │ Hata durumunda geri sarma                │
  └───────────────────────┴────────────────────────────────────────────┘

KULLANIM:
  from app.core.orchestrator import workflow_engine

  # Pipeline workflow'u çalıştır
  result = await workflow_engine.execute("ai_decision_pipeline", {
      "question": "...",
      "user_id": "admin",
  })

  # Dashboard
  dashboard = workflow_engine.get_dashboard()

ÖN-TANIMLI WORKFLOW'LAR:
  • ai_decision_pipeline  — Tam AI karar süreci
  • risk_assessment        — Risk değerlendirme
  • executive_report       — Yönetici raporu
  • model_evaluation       — Model performans değerlendirme
"""

import asyncio
import json
import time
import traceback
import uuid
from collections import deque
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Coroutine, Optional

import structlog

logger = structlog.get_logger()

DATA_DIR = Path("data/workflows")
DATA_DIR.mkdir(parents=True, exist_ok=True)

WORKFLOW_HISTORY_FILE = DATA_DIR / "workflow_history.json"


# ═══════════════════════════════════════════════════════════════════
#  Enum'lar & Sabitler
# ═══════════════════════════════════════════════════════════════════

class StepStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    COMPENSATED = "compensated"   # Saga rollback sonrası


class WorkflowStatus(Enum):
    CREATED = "created"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    COMPENSATING = "compensating"  # Saga rollback
    TIMED_OUT = "timed_out"


# ═══════════════════════════════════════════════════════════════════
#  Veri Yapıları
# ═══════════════════════════════════════════════════════════════════

@dataclass
class StepResult:
    """Tek bir adımın sonucu."""
    step_name: str
    status: str
    output: Any = None
    error: Optional[str] = None
    duration_ms: float = 0.0
    retries: int = 0
    started_at: str = ""
    completed_at: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class WorkflowStep:
    """Workflow adım tanımı."""
    name: str
    handler: str                          # Fonksiyon referansı (string)
    timeout: float = 30.0                 # Saniye
    max_retries: int = 2
    retry_delay: float = 1.0             # Saniye
    condition: Optional[str] = None       # Koşullu çalıştırma (eval string)
    compensate_handler: Optional[str] = None  # Saga compensation
    required: bool = True                 # False ise hata workflow'u durdurmaz
    depends_on: list[str] = field(default_factory=list)  # Bağımlı adımlar

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class WorkflowDefinition:
    """Deklaratif workflow tanımı."""
    name: str
    description: str
    steps: list[WorkflowStep]
    timeout: float = 300.0               # Toplam workflow timeout (saniye)
    version: str = "1.0"

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "steps": [s.to_dict() for s in self.steps],
            "timeout": self.timeout,
            "version": self.version,
        }


@dataclass
class WorkflowInstance:
    """Çalışan/tamamlanmış workflow instance."""
    workflow_id: str
    workflow_name: str
    status: str
    input_data: dict
    step_results: list[dict]
    output: Any = None
    error: Optional[str] = None
    started_at: str = ""
    completed_at: str = ""
    duration_ms: float = 0.0
    current_step: str = ""
    correlation_id: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


# ═══════════════════════════════════════════════════════════════════
#  Step Handler Registry
# ═══════════════════════════════════════════════════════════════════

# Step fonksiyonları buraya kaydedilir
_step_handlers: dict[str, Callable] = {}


def register_step(name: str):
    """Step handler decorator."""
    def decorator(fn):
        _step_handlers[name] = fn
        return fn
    return decorator


# ── Ön-tanımlı Step Handler'lar ──
# Bu adımlar engine.py'den çağrılır, burada sadece proxy tanımlar var
# Gerçek implementasyon engine entegrasyonunda yapılır

@register_step("validate_input")
async def step_validate_input(ctx: dict) -> dict:
    """Girdi doğrulama adımı."""
    question = ctx.get("question", "")
    if not question or len(question.strip()) < 2:
        raise ValueError("Soru çok kısa veya boş")
    return {"valid": True, "question_length": len(question)}


@register_step("route_intent")
async def step_route_intent(ctx: dict) -> dict:
    """Niyet yönlendirme adımı."""
    return {"routed": True, "intent": ctx.get("intent", "genel")}


@register_step("gather_context")
async def step_gather_context(ctx: dict) -> dict:
    """Bağlam toplama (RAG + memory)."""
    return {"context_gathered": True}


@register_step("policy_check")
async def step_policy_check(ctx: dict) -> dict:
    """Policy değerlendirme adımı."""
    return {"policy_passed": True, "violations": []}


@register_step("generate_response")
async def step_generate_response(ctx: dict) -> dict:
    """LLM yanıt üretme adımı."""
    return {"response_generated": True}


@register_step("quality_assessment")
async def step_quality_assessment(ctx: dict) -> dict:
    """Kalite değerlendirme adımı."""
    return {"quality_checked": True}


@register_step("governance_review")
async def step_governance_review(ctx: dict) -> dict:
    """Governance değerlendirme adımı."""
    return {"governance_passed": True}


@register_step("audit_log")
async def step_audit_log(ctx: dict) -> dict:
    """Audit kayıt adımı."""
    return {"audited": True}


@register_step("risk_analysis")
async def step_risk_analysis(ctx: dict) -> dict:
    """Risk analizi adımı."""
    return {"risk_analyzed": True, "risk_score": ctx.get("risk_score", 0.0)}


@register_step("executive_summary")
async def step_executive_summary(ctx: dict) -> dict:
    """Yönetici özeti adımı."""
    return {"summary_generated": True}


@register_step("model_benchmark")
async def step_model_benchmark(ctx: dict) -> dict:
    """Model benchmark adımı."""
    return {"benchmark_complete": True}


# ═══════════════════════════════════════════════════════════════════
#  Ön-Tanımlı Workflow Tanımları
# ═══════════════════════════════════════════════════════════════════

DEFAULT_WORKFLOWS: dict[str, WorkflowDefinition] = {
    "ai_decision_pipeline": WorkflowDefinition(
        name="ai_decision_pipeline",
        description="Tam AI karar süreci — girdiden audite kadar",
        steps=[
            WorkflowStep(name="validate_input", handler="validate_input", timeout=5),
            WorkflowStep(name="route_intent", handler="route_intent", timeout=10),
            WorkflowStep(name="policy_check", handler="policy_check", timeout=10,
                         depends_on=["validate_input"]),
            WorkflowStep(name="gather_context", handler="gather_context", timeout=30,
                         depends_on=["route_intent"]),
            WorkflowStep(name="generate_response", handler="generate_response", timeout=180,
                         depends_on=["gather_context", "policy_check"]),
            WorkflowStep(name="quality_assessment", handler="quality_assessment", timeout=15,
                         depends_on=["generate_response"], required=False),
            WorkflowStep(name="governance_review", handler="governance_review", timeout=15,
                         depends_on=["generate_response"], required=False),
            WorkflowStep(name="audit_log", handler="audit_log", timeout=5,
                         depends_on=["generate_response"]),
        ],
        timeout=300,
    ),
    "risk_assessment": WorkflowDefinition(
        name="risk_assessment",
        description="Risk değerlendirme workflow'u",
        steps=[
            WorkflowStep(name="validate_input", handler="validate_input", timeout=5),
            WorkflowStep(name="risk_analysis", handler="risk_analysis", timeout=30),
            WorkflowStep(name="policy_check", handler="policy_check", timeout=10,
                         depends_on=["risk_analysis"]),
            WorkflowStep(name="audit_log", handler="audit_log", timeout=5,
                         depends_on=["risk_analysis"]),
        ],
        timeout=120,
    ),
    "executive_report": WorkflowDefinition(
        name="executive_report",
        description="Yönetici raporu oluşturma workflow'u",
        steps=[
            WorkflowStep(name="validate_input", handler="validate_input", timeout=5),
            WorkflowStep(name="gather_context", handler="gather_context", timeout=30),
            WorkflowStep(name="generate_response", handler="generate_response", timeout=120),
            WorkflowStep(name="executive_summary", handler="executive_summary", timeout=30,
                         depends_on=["generate_response"]),
            WorkflowStep(name="quality_assessment", handler="quality_assessment", timeout=15,
                         depends_on=["executive_summary"], required=False),
        ],
        timeout=240,
    ),
    "model_evaluation": WorkflowDefinition(
        name="model_evaluation",
        description="Model performans değerlendirme workflow'u",
        steps=[
            WorkflowStep(name="model_benchmark", handler="model_benchmark", timeout=60),
            WorkflowStep(name="quality_assessment", handler="quality_assessment", timeout=30,
                         depends_on=["model_benchmark"]),
            WorkflowStep(name="audit_log", handler="audit_log", timeout=5,
                         depends_on=["quality_assessment"]),
        ],
        timeout=120,
    ),
}


# ═══════════════════════════════════════════════════════════════════
#  Workflow Engine
# ═══════════════════════════════════════════════════════════════════

class WorkflowEngine:
    """
    Temporal-inspired durable workflow engine.

    Özellikler:
      • Deklaratif workflow tanımı
      • DAG-based adım bağımlılıkları
      • Timeout & retry per step
      • Saga compensation (rollback)
      • Durable state (JSON persistence)
      • Koşullu adım çalıştırma
      • Workflow geçmişi & replay
    """

    def __init__(self):
        self._workflows: dict[str, WorkflowDefinition] = dict(DEFAULT_WORKFLOWS)
        self._active: dict[str, WorkflowInstance] = {}
        self._history: deque[dict] = deque(maxlen=500)
        self._metrics: dict[str, Any] = {
            "total_executed": 0,
            "total_completed": 0,
            "total_failed": 0,
            "avg_duration_ms": 0.0,
            "by_workflow": {},
        }
        self._load_history()

    def _load_history(self):
        """Geçmiş workflow'ları yükle."""
        if WORKFLOW_HISTORY_FILE.exists():
            try:
                data = json.loads(WORKFLOW_HISTORY_FILE.read_text(encoding="utf-8"))
                for item in data[-500:]:
                    self._history.append(item)
            except Exception:
                pass

    def _save_history(self):
        """Geçmişi kaydet."""
        try:
            WORKFLOW_HISTORY_FILE.write_text(
                json.dumps(list(self._history)[-200:], ensure_ascii=False, default=str, indent=2),
                encoding="utf-8",
            )
        except Exception as e:
            logger.warning("workflow_history_save_error", error=str(e))

    # ── Workflow Yönetimi ──

    def register_workflow(self, definition: WorkflowDefinition):
        """Yeni workflow tanımı kaydet."""
        self._workflows[definition.name] = definition

    def list_workflows(self) -> list[dict]:
        """Kayıtlı workflow'ları listele."""
        return [
            {
                "name": w.name,
                "description": w.description,
                "step_count": len(w.steps),
                "timeout": w.timeout,
                "version": w.version,
                "steps": [s.name for s in w.steps],
            }
            for w in self._workflows.values()
        ]

    # ── Workflow Çalıştırma ──

    async def execute(
        self,
        workflow_name: str,
        input_data: dict,
        correlation_id: str = "",
    ) -> WorkflowInstance:
        """
        Workflow'u çalıştır.

        Args:
            workflow_name: Kayıtlı workflow adı
            input_data: Girdi verileri (step'ler arası paylaşılır)
            correlation_id: İzleme ID'si

        Returns:
            WorkflowInstance — tamamlanmış veya hatalı
        """
        definition = self._workflows.get(workflow_name)
        if not definition:
            raise ValueError(f"Workflow bulunamadı: {workflow_name}")

        workflow_id = str(uuid.uuid4())[:16]
        if not correlation_id:
            correlation_id = workflow_id

        instance = WorkflowInstance(
            workflow_id=workflow_id,
            workflow_name=workflow_name,
            status=WorkflowStatus.RUNNING.value,
            input_data=input_data,
            step_results=[],
            started_at=datetime.now(timezone.utc).isoformat(),
            correlation_id=correlation_id,
        )
        self._active[workflow_id] = instance

        start_time = time.monotonic()
        completed_steps: dict[str, StepResult] = {}
        ctx = dict(input_data)  # Mutable context — step'ler arası paylaşım

        try:
            # Toplam timeout ile çalıştır
            await asyncio.wait_for(
                self._run_steps(definition, instance, ctx, completed_steps),
                timeout=definition.timeout,
            )
            instance.status = WorkflowStatus.COMPLETED.value
            instance.output = ctx
            self._metrics["total_completed"] = self._metrics.get("total_completed", 0) + 1

        except asyncio.TimeoutError:
            instance.status = WorkflowStatus.TIMED_OUT.value
            instance.error = f"Workflow timeout ({definition.timeout}s)"
            self._metrics["total_failed"] = self._metrics.get("total_failed", 0) + 1

        except Exception as e:
            instance.status = WorkflowStatus.FAILED.value
            instance.error = str(e)
            self._metrics["total_failed"] = self._metrics.get("total_failed", 0) + 1

            # Saga compensation
            await self._compensate(definition, completed_steps, ctx)

        finally:
            instance.duration_ms = (time.monotonic() - start_time) * 1000
            instance.completed_at = datetime.now(timezone.utc).isoformat()
            self._active.pop(workflow_id, None)

            # Metrikleri güncelle
            self._metrics["total_executed"] = self._metrics.get("total_executed", 0) + 1
            wf_key = workflow_name
            if wf_key not in self._metrics.get("by_workflow", {}):
                self._metrics.setdefault("by_workflow", {})[wf_key] = {
                    "count": 0, "avg_ms": 0.0, "failures": 0,
                }
            wf_stats = self._metrics["by_workflow"][wf_key]
            wf_stats["count"] += 1
            wf_stats["avg_ms"] = (
                (wf_stats["avg_ms"] * (wf_stats["count"] - 1) + instance.duration_ms)
                / wf_stats["count"]
            )
            if instance.status != WorkflowStatus.COMPLETED.value:
                wf_stats["failures"] += 1

            # Ortalama süre
            total = self._metrics.get("total_executed", 1)
            self._metrics["avg_duration_ms"] = (
                (self._metrics.get("avg_duration_ms", 0) * (total - 1) + instance.duration_ms)
                / total
            )

            # Geçmişe ekle
            self._history.append(instance.to_dict())
            self._save_history()

            logger.info(
                "workflow_completed",
                workflow_id=workflow_id,
                workflow_name=workflow_name,
                status=instance.status,
                duration_ms=round(instance.duration_ms, 1),
                steps_completed=len(instance.step_results),
            )

        return instance

    async def _run_steps(
        self,
        definition: WorkflowDefinition,
        instance: WorkflowInstance,
        ctx: dict,
        completed_steps: dict[str, StepResult],
    ):
        """Adımları bağımlılık sırasına göre çalıştır."""
        remaining = list(definition.steps)

        while remaining:
            # Çalıştırılabilir adımları bul (bağımlılıkları tamamlanmış olanlar)
            runnable = []
            still_waiting = []

            for step in remaining:
                if step.depends_on:
                    all_deps_done = all(
                        d in completed_steps and completed_steps[d].status == StepStatus.COMPLETED.value
                        for d in step.depends_on
                    )
                    if not all_deps_done:
                        # Bağımlılık başarısız mı kontrol et
                        any_dep_failed = any(
                            d in completed_steps and completed_steps[d].status == StepStatus.FAILED.value
                            for d in step.depends_on
                        )
                        if any_dep_failed and step.required:
                            raise RuntimeError(
                                f"Step '{step.name}' bağımlılığı başarısız"
                            )
                        elif any_dep_failed:
                            # Opsiyonel step, skip et
                            result = StepResult(
                                step_name=step.name,
                                status=StepStatus.SKIPPED.value,
                            )
                            completed_steps[step.name] = result
                            instance.step_results.append(result.to_dict())
                            continue
                        still_waiting.append(step)
                        continue
                runnable.append(step)

            if not runnable and still_waiting:
                # Deadlock — kalan step'ler hiçbir zaman çalışamaz
                raise RuntimeError(
                    f"Workflow deadlock: {[s.name for s in still_waiting]}"
                )

            if not runnable:
                break

            # Paralel çalıştırılabilir step'ler (bağımsız olanlar)
            tasks = []
            for step in runnable:
                remaining.remove(step)
                tasks.append(self._execute_step(step, ctx, instance))

            results = await asyncio.gather(*tasks, return_exceptions=True)

            for step, result in zip(runnable, results):
                if isinstance(result, Exception):
                    step_result = StepResult(
                        step_name=step.name,
                        status=StepStatus.FAILED.value,
                        error=str(result),
                    )
                    completed_steps[step.name] = step_result
                    instance.step_results.append(step_result.to_dict())
                    if step.required:
                        raise result
                else:
                    completed_steps[step.name] = result
                    instance.step_results.append(result.to_dict())

            remaining = still_waiting

    async def _execute_step(
        self,
        step: WorkflowStep,
        ctx: dict,
        instance: WorkflowInstance,
    ) -> StepResult:
        """Tek bir adımı çalıştır (retry + timeout)."""
        instance.current_step = step.name
        handler = _step_handlers.get(step.handler)

        if not handler:
            if not step.required:
                return StepResult(
                    step_name=step.name,
                    status=StepStatus.SKIPPED.value,
                )
            raise RuntimeError(f"Step handler bulunamadı: {step.handler}")

        # Koşullu çalıştırma
        if step.condition:
            try:
                if not eval(step.condition, {"ctx": ctx}):
                    return StepResult(
                        step_name=step.name,
                        status=StepStatus.SKIPPED.value,
                    )
            except Exception:
                pass

        last_error = None
        for attempt in range(step.max_retries + 1):
            start = time.monotonic()
            started_at = datetime.now(timezone.utc).isoformat()

            try:
                output = await asyncio.wait_for(
                    handler(ctx),
                    timeout=step.timeout,
                )

                # Step output'unu context'e merge et
                if isinstance(output, dict):
                    ctx.update(output)

                duration = (time.monotonic() - start) * 1000
                return StepResult(
                    step_name=step.name,
                    status=StepStatus.COMPLETED.value,
                    output=output,
                    duration_ms=round(duration, 1),
                    retries=attempt,
                    started_at=started_at,
                    completed_at=datetime.now(timezone.utc).isoformat(),
                )

            except asyncio.TimeoutError:
                last_error = f"Step timeout ({step.timeout}s)"
            except Exception as e:
                last_error = str(e)

            if attempt < step.max_retries:
                await asyncio.sleep(step.retry_delay * (attempt + 1))

        return StepResult(
            step_name=step.name,
            status=StepStatus.FAILED.value,
            error=last_error,
            retries=step.max_retries,
        )

    async def _compensate(
        self,
        definition: WorkflowDefinition,
        completed_steps: dict[str, StepResult],
        ctx: dict,
    ):
        """Saga compensation — tamamlanmış adımları ters sırada geri al."""
        compensable = [
            s for s in reversed(definition.steps)
            if s.name in completed_steps
            and completed_steps[s.name].status == StepStatus.COMPLETED.value
            and s.compensate_handler
        ]

        for step in compensable:
            handler = _step_handlers.get(step.compensate_handler or "")
            if handler:
                try:
                    await asyncio.wait_for(handler(ctx), timeout=10)
                    completed_steps[step.name].status = StepStatus.COMPENSATED.value
                    logger.info("workflow_step_compensated", step=step.name)
                except Exception as e:
                    logger.error("workflow_compensation_error",
                                 step=step.name, error=str(e))

    # ── Sorgu & Dashboard ──

    def get_active_workflows(self) -> list[dict]:
        """Aktif workflow'ları listele."""
        return [w.to_dict() for w in self._active.values()]

    def get_history(
        self,
        workflow_name: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> list[dict]:
        """Workflow geçmişini filtreli getir."""
        items = list(self._history)
        if workflow_name:
            items = [i for i in items if i.get("workflow_name") == workflow_name]
        if status:
            items = [i for i in items if i.get("status") == status]
        return items[-limit:]

    def get_dashboard(self) -> dict:
        """Orchestrator dashboard — admin paneli için."""
        return {
            "status": "active",
            "registered_workflows": len(self._workflows),
            "workflow_list": self.list_workflows(),
            "active_count": len(self._active),
            "active_workflows": [
                {
                    "workflow_id": w.workflow_id,
                    "name": w.workflow_name,
                    "status": w.status,
                    "current_step": w.current_step,
                    "started_at": w.started_at,
                }
                for w in self._active.values()
            ],
            "metrics": dict(self._metrics),
            "recent_history": self.get_history(limit=10),
            "step_handlers": list(_step_handlers.keys()),
        }


# ═══════════════════════════════════════════════════════════════════
#  Singleton
# ═══════════════════════════════════════════════════════════════════

workflow_engine = WorkflowEngine()
