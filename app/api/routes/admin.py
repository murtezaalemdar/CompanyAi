"""Admin API Routes"""

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, extract
from pydantic import BaseModel, EmailStr
from typing import List, Optional
from datetime import datetime, timedelta
import json
import base64

from app.db.database import get_db
from app.db.models import User, Query, SystemSettings
from app.api.routes.auth import get_current_user
from app.auth.rbac import Role, check_admin, check_admin_or_manager
from app.auth.jwt_handler import hash_password
from app.core.audit import log_action, audit_compliance_engine, data_retention_policy

# v3.4.0 modülleri
try:
    from app.core.model_registry import model_registry
except ImportError:
    model_registry = None

try:
    from app.core.data_versioning import data_version_manager
except ImportError:
    data_version_manager = None

try:
    from app.core.hitl import hitl_manager
except ImportError:
    hitl_manager = None

try:
    from app.core.monitoring import metrics_collector, alert_manager, get_full_telemetry, calculate_health_score, sla_monitor
except ImportError:
    metrics_collector = None
    alert_manager = None

try:
    from app.core.textile_vision import analyze_colors, analyze_pattern, compare_images, generate_quality_report, get_textile_vision_capabilities
except ImportError:
    analyze_colors = None

try:
    from app.core.explainability import decision_explainer
except ImportError:
    decision_explainer = None

# Meta Learning Engine (v4.6.0)
try:
    from app.core.meta_learning import meta_learning_engine, get_meta_dashboard, get_improvement_opportunities
    META_LEARNING_AVAILABLE = True
except ImportError:
    META_LEARNING_AVAILABLE = False
    meta_learning_engine = None

# Self-Improvement Loop (v4.6.0)
try:
    from app.core.self_improvement import self_improvement_loop, get_self_improvement_dashboard, run_improvement_cycle
    SELF_IMPROVEMENT_AVAILABLE = True
except ImportError:
    SELF_IMPROVEMENT_AVAILABLE = False
    self_improvement_loop = None

# Multi-Agent Debate (v4.7.0)
try:
    from app.core.multi_agent_debate import debate_engine, get_debate_dashboard
    MULTI_AGENT_DEBATE_AVAILABLE = True
except ImportError:
    MULTI_AGENT_DEBATE_AVAILABLE = False
    debate_engine = None

# Causal Inference Engine (v4.7.0)
try:
    from app.core.causal_inference import causal_engine, get_causal_dashboard
    CAUSAL_INFERENCE_AVAILABLE = True
except ImportError:
    CAUSAL_INFERENCE_AVAILABLE = False
    causal_engine = None

# Strategic Planner (v5.0.0)
try:
    from app.core.strategic_planner import strategic_planner, get_strategic_dashboard
    STRATEGIC_PLANNER_AVAILABLE = True
except ImportError:
    STRATEGIC_PLANNER_AVAILABLE = False
    strategic_planner = None

# Executive Intelligence (v5.0.0)
try:
    from app.core.executive_intelligence import executive_intelligence, get_executive_dashboard
    EXECUTIVE_INTELLIGENCE_AVAILABLE = True
except ImportError:
    EXECUTIVE_INTELLIGENCE_AVAILABLE = False
    executive_intelligence = None

# Knowledge Graph (v5.0.0)
try:
    from app.core.knowledge_graph import knowledge_graph, get_kg_dashboard
    KNOWLEDGE_GRAPH_AVAILABLE = True
except ImportError:
    KNOWLEDGE_GRAPH_AVAILABLE = False
    knowledge_graph = None

# Decision Risk Gatekeeper (v5.1.0)
try:
    from app.core.decision_gatekeeper import decision_gatekeeper, get_gate_dashboard
    DECISION_GATEKEEPER_AVAILABLE = True
except ImportError:
    DECISION_GATEKEEPER_AVAILABLE = False
    decision_gatekeeper = None

# Uncertainty Quantification (v5.1.0)
try:
    from app.core.uncertainty_quantification import uncertainty_quantifier, get_uncertainty_dashboard
    UNCERTAINTY_AVAILABLE = True
except ImportError:
    UNCERTAINTY_AVAILABLE = False
    uncertainty_quantifier = None

# Graph Impact (v5.2.0)
try:
    from app.core.graph_impact import impact_graph as graph_impact_engine
    from app.core.graph_impact import get_dashboard as get_graph_impact_dashboard
    GRAPH_IMPACT_AVAILABLE = True
except ImportError:
    GRAPH_IMPACT_AVAILABLE = False
    graph_impact_engine = None

# Numerical Validation (v5.2.0)
try:
    from app.core.numerical_validation import get_dashboard as get_numerical_validation_dashboard
    NUMERICAL_VALIDATION_AVAILABLE = True
except ImportError:
    NUMERICAL_VALIDATION_AVAILABLE = False

# Experiment Layer (v5.2.0)
try:
    from app.core.experiment_layer import get_dashboard as get_experiment_dashboard
    EXPERIMENT_DASHBOARD_AVAILABLE = True
except ImportError:
    EXPERIMENT_DASHBOARD_AVAILABLE = False

# Scenario Engine (v5.2.0)
try:
    from app.core.scenario_engine import get_dashboard as get_scenario_dashboard
    SCENARIO_DASHBOARD_AVAILABLE = True
except ImportError:
    SCENARIO_DASHBOARD_AVAILABLE = False

# Decision Quality Score (v5.3.0)
try:
    from app.core.decision_quality import get_dashboard as get_decision_quality_dashboard
    DECISION_QUALITY_AVAILABLE = True
except ImportError:
    DECISION_QUALITY_AVAILABLE = False

# KPI Impact Mapping (v5.3.0)
try:
    from app.core.kpi_impact import get_dashboard as get_kpi_impact_dashboard
    KPI_IMPACT_AVAILABLE = True
except ImportError:
    KPI_IMPACT_AVAILABLE = False

# Decision Memory (v5.3.0)
try:
    from app.core.decision_memory import get_dashboard as get_decision_memory_dashboard
    DECISION_MEMORY_AVAILABLE = True
except ImportError:
    DECISION_MEMORY_AVAILABLE = False

# Executive Digest (v5.3.0)
try:
    from app.core.executive_digest import get_dashboard as get_executive_digest_dashboard
    EXECUTIVE_DIGEST_AVAILABLE = True
except ImportError:
    EXECUTIVE_DIGEST_AVAILABLE = False

# OOD Detector (v5.3.0)
try:
    from app.core.ood_detector import get_dashboard as get_ood_dashboard
    OOD_DETECTOR_AVAILABLE = True
except ImportError:
    OOD_DETECTOR_AVAILABLE = False

# Module Synapse Network (v5.4.0)
try:
    from app.core.module_synapse import get_dashboard as get_synapse_dashboard
    SYNAPSE_AVAILABLE = True
except ImportError:
    SYNAPSE_AVAILABLE = False

# ── v5.5.0 Enterprise Platform Katmanları ──

# Event Bus (v5.5.0)
try:
    from app.core.event_bus import event_bus
    EVENT_BUS_AVAILABLE = True
except ImportError:
    EVENT_BUS_AVAILABLE = False
    event_bus = None

# Workflow Orchestrator (v5.5.0)
try:
    from app.core.orchestrator import workflow_engine
    ORCHESTRATOR_AVAILABLE = True
except ImportError:
    ORCHESTRATOR_AVAILABLE = False
    workflow_engine = None

# Policy Engine (v5.5.0)
try:
    from app.core.policy_engine import policy_engine as enterprise_policy_engine
    POLICY_ENGINE_AVAILABLE = True
except ImportError:
    POLICY_ENGINE_AVAILABLE = False
    enterprise_policy_engine = None

# Observability 2.0 (v5.5.0)
try:
    from app.core.observability import observability
    OBSERVABILITY_AVAILABLE = True
except ImportError:
    OBSERVABILITY_AVAILABLE = False
    observability = None

# Security Layer (v5.5.0)
try:
    from app.core.security import security_layer
    SECURITY_AVAILABLE = True
except ImportError:
    SECURITY_AVAILABLE = False
    security_layer = None

router = APIRouter()


# ── Public Endpoints (auth gerektirmez) ───────────────────────────

@router.get("/public/logo")
async def get_public_logo(db: AsyncSession = Depends(get_db)):
    """Login sayfasi icin sirket logosunu doner (auth gerektirmez)."""
    result = await db.execute(
        select(SystemSettings).where(SystemSettings.key == "company_logo")
    )
    setting = result.scalar_one_or_none()
    if not setting or not setting.value:
        return {"logo": None}
    return {"logo": setting.value}


@router.post("/upload-logo")
async def upload_logo(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Sirket logosunu yukler ve SystemSettings'e base64 olarak kaydeder (admin only)."""
    check_admin(current_user)

    # Dosya tipi kontrolu
    allowed_types = ["image/png", "image/jpeg", "image/jpg", "image/svg+xml", "image/webp"]
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"Desteklenmeyen dosya tipi: {file.content_type}. Izin verilenler: PNG, JPEG, SVG, WebP"
        )

    # Boyut kontrolu (max 2MB)
    content = await file.read()
    if len(content) > 2 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Logo dosyasi 2MB'dan buyuk olamaz")

    # Base64'e cevir
    b64 = base64.b64encode(content).decode("utf-8")
    data_uri = f"data:{file.content_type};base64,{b64}"

    # SystemSettings'e kaydet (upsert)
    result = await db.execute(
        select(SystemSettings).where(SystemSettings.key == "company_logo")
    )
    existing = result.scalar_one_or_none()

    if existing:
        existing.value = data_uri
        existing.updated_by = current_user.id
    else:
        db.add(SystemSettings(
            key="company_logo",
            value=data_uri,
            description="Sirket logosu (base64 data URI)",
            updated_by=current_user.id,
        ))

    await log_action(
        db, user=current_user, action="admin_upload_logo",
        resource="setting:company_logo",
        details=json.dumps({"filename": file.filename, "size_kb": round(len(content) / 1024, 1)}),
    )
    await db.commit()
    return {"success": True, "logo": data_uri}


@router.delete("/logo")
async def delete_logo(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Sirket logosunu siler (admin only)."""
    check_admin(current_user)

    result = await db.execute(
        select(SystemSettings).where(SystemSettings.key == "company_logo")
    )
    setting = result.scalar_one_or_none()
    if setting:
        await db.delete(setting)
        await log_action(
            db, user=current_user, action="admin_delete_logo",
            resource="setting:company_logo",
        )
        await db.commit()
    return {"success": True}


# Pydantic Schemas

class UserList(BaseModel):
    id: int
    email: str
    full_name: str | None
    department: str | None
    role: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class UserCreateRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: str | None = None
    department: str | None = None
    role: str = "user"


class UserUpdateRequest(BaseModel):
    full_name: Optional[str] = None
    department: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None
    password: Optional[str] = None


class QueryStats(BaseModel):
    total_queries: int
    queries_today: int
    avg_confidence: float
    top_departments: List[dict]


class DashboardStats(BaseModel):
    total_users: int
    active_users: int
    total_queries: int
    queries_today: int
    avg_response_time_ms: float
    users_change_pct: float = 0.0
    queries_change_pct: float = 0.0
    response_time_change_pct: float = 0.0


# Routes

@router.get("/users", response_model=List[UserList])
async def list_users(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Tüm kullanıcıları listele (sadece admin)"""
    if current_user.role != Role.ADMIN.value:
        raise HTTPException(status_code=403, detail="Admin yetkisi gerekli")
    
    result = await db.execute(select(User).order_by(User.created_at.desc()))
    users = result.scalars().all()
    return users


@router.post("/users", response_model=UserList)
async def create_user(
    user_data: UserCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Yeni kullanıcı oluştur (sadece admin)"""
    check_admin(current_user)
    
    # Email kontrolü
    result = await db.execute(select(User).where(User.email == user_data.email))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=400,
            detail="Bu email adresi zaten kullanımda"
        )
    
    # Rol validasyonu
    if user_data.role not in [r.value for r in Role]:
        raise HTTPException(status_code=400, detail="Geçersiz rol")
    
    new_user = User(
        email=user_data.email,
        hashed_password=hash_password(user_data.password),
        full_name=user_data.full_name,
        department=user_data.department,
        role=user_data.role,
        is_active=True
    )
    
    db.add(new_user)
    await log_action(
        db, user=current_user, action="admin_create_user",
        resource=f"user:{new_user.email}",
        details=json.dumps({"role": user_data.role}),
    )
    await db.commit()
    await db.refresh(new_user)
    
    return new_user


@router.put("/users/{user_id}", response_model=UserList)
async def update_user(
    user_id: int,
    user_data: UserUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Kullanıcı güncelle (sadece admin)"""
    check_admin(current_user)
    
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="Kullanıcı bulunamadı")
    
    # Alanları güncelle
    if user_data.full_name is not None:
        user.full_name = user_data.full_name
    
    if user_data.department is not None:
        user.department = user_data.department
        
    if user_data.role is not None:
        if user_data.role not in [r.value for r in Role]:
            raise HTTPException(status_code=400, detail="Geçersiz rol")
        user.role = user_data.role
        
    if user_data.is_active is not None:
        user.is_active = user_data.is_active
        
    if user_data.password is not None:
        user.hashed_password = hash_password(user_data.password)
    
    await log_action(
        db, user=current_user, action="admin_update_user",
        resource=f"user:{user.email}",
    )
    await db.commit()
    await db.refresh(user)
    
    return user


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Kullanıcı sil (sadece admin)"""
    check_admin(current_user)
    
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Kendinizi silemezsiniz")
    
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="Kullanıcı bulunamadı")
    
    await log_action(
        db, user=current_user, action="admin_delete_user",
        resource=f"user:{user.email}",
    )
    await db.delete(user)
    await db.commit()
    
    return {"message": "Kullanıcı başarıyla silindi", "success": True}


@router.get("/stats/dashboard", response_model=DashboardStats)
async def get_dashboard_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Dashboard istatistikleri"""
    check_admin_or_manager(current_user)
    
    now = datetime.utcnow()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    one_week_ago = today - timedelta(days=7)
    two_weeks_ago = today - timedelta(days=14)
    
    # Kullanıcı sayıları
    total_users = await db.scalar(select(func.count(User.id)))
    active_users = await db.scalar(
        select(func.count(User.id)).where(User.is_active == True)
    )
    
    # Bu hafta eklenen kullanıcılar
    users_this_week = await db.scalar(
        select(func.count(User.id)).where(User.created_at >= one_week_ago)
    )
    users_last_week = await db.scalar(
        select(func.count(User.id)).where(
            User.created_at >= two_weeks_ago,
            User.created_at < one_week_ago
        )
    )
    users_change = _calc_change_pct(users_this_week or 0, users_last_week or 0)
    
    # Sorgu sayıları
    total_queries = await db.scalar(select(func.count(Query.id)))
    queries_today = await db.scalar(
        select(func.count(Query.id)).where(Query.created_at >= today)
    )
    
    # Sorgu haftalık değişim
    queries_this_week = await db.scalar(
        select(func.count(Query.id)).where(Query.created_at >= one_week_ago)
    )
    queries_last_week = await db.scalar(
        select(func.count(Query.id)).where(
            Query.created_at >= two_weeks_ago,
            Query.created_at < one_week_ago
        )
    )
    queries_change = _calc_change_pct(queries_this_week or 0, queries_last_week or 0)
    
    # Ortalama yanıt süresi ve değişimi
    avg_time = await db.scalar(select(func.avg(Query.processing_time_ms)))
    avg_time_last_week = await db.scalar(
        select(func.avg(Query.processing_time_ms)).where(
            Query.created_at >= two_weeks_ago,
            Query.created_at < one_week_ago
        )
    )
    avg_time_this_week = await db.scalar(
        select(func.avg(Query.processing_time_ms)).where(
            Query.created_at >= one_week_ago
        )
    )
    response_change = _calc_change_pct(
        avg_time_this_week or 0, avg_time_last_week or 0
    )
    
    return DashboardStats(
        total_users=total_users or 0,
        active_users=active_users or 0,
        total_queries=total_queries or 0,
        queries_today=queries_today or 0,
        avg_response_time_ms=avg_time or 0,
        users_change_pct=users_change,
        queries_change_pct=queries_change,
        response_time_change_pct=response_change,
    )


@router.get("/queries/recent")
async def get_recent_queries(
    limit: int = 20,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Son sorguları getir"""
    # Authenticated user yeterli — roller query filtresiyle zaten kısıtlanıyor
    
    query = select(Query).order_by(Query.created_at.desc())

    # Kısıtlama: Sadece kendi departmanı (User rolü için)
    if current_user.role == Role.USER.value:
        user_depts = []
        if current_user.department:
            try:
                parsed = json.loads(current_user.department)
                if isinstance(parsed, list):
                    user_depts = parsed
                else:
                    user_depts = [current_user.department]
            except json.JSONDecodeError:
                user_depts = [current_user.department]

        if not user_depts:
            return [] # Departmanı yoksa göremez

        # Filtrele: Query departmanı kullanıcının departmanlarından biri olmalı
        query = query.where(Query.department.in_(user_depts))

    result = await db.execute(query.limit(limit))
    queries = result.scalars().all()
    
    return [
        {
            "id": q.id,
            "question": q.question[:100] + "..." if len(q.question) > 100 else q.question,
            "department": q.department,
            "risk_level": q.risk_level,
            "confidence": q.confidence,
            "processing_time_ms": q.processing_time_ms,
            "created_at": q.created_at,
        }
        for q in queries
    ]


# ── Yardımcı fonksiyonlar ────────────────────────────────────────

def _calc_change_pct(current: float, previous: float) -> float:
    """İki değer arasındaki yüzdesel değişimi hesaplar."""
    if previous == 0:
        return 100.0 if current > 0 else 0.0
    return round(((current - previous) / previous) * 100, 1)


# ── Sorgu Trafiği (saatlik) ──────────────────────────────────────

@router.get("/stats/query-traffic")
async def get_query_traffic(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Bugünün saatlik sorgu trafiğini döner (Dashboard grafik verisi)."""
    check_admin_or_manager(current_user)

    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

    rows = await db.execute(
        select(
            extract("hour", Query.created_at).label("hour"),
            func.count(Query.id).label("count"),
        )
        .where(Query.created_at >= today)
        .group_by(extract("hour", Query.created_at))
        .order_by(extract("hour", Query.created_at))
    )

    traffic_map = {int(r.hour): r.count for r in rows}
    current_hour = datetime.utcnow().hour

    result = []
    for h in range(0, current_hour + 1):
        result.append({"name": f"{h:02d}:00", "queries": traffic_map.get(h, 0)})

    return result


# ── Sistem Kaynak Kullanımı ──────────────────────────────────────

# Ollama GPU bilgisi cache — meşgul/timeout durumlarında widget kaybolmasını önler
_ollama_gpu_cache: dict = {}

@router.get("/stats/system-resources")
async def get_system_resources(
    current_user: User = Depends(get_current_user),
):
    """CPU ve Bellek kullanım yüzdelerini döner."""
    check_admin_or_manager(current_user)

    try:
        import psutil
        import subprocess
        cpu_percent = psutil.cpu_percent(interval=0.5)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage("/")

        # GPU bilgisi — nvidia-smi (multi-GPU destekli)
        gpu_info = None
        gpus_list: list = []
        try:
            nv = subprocess.run(
                ["nvidia-smi", "--query-gpu=index,name,memory.used,memory.total,memory.free,utilization.gpu,temperature.gpu,power.draw,power.limit",
                 "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=5,
            )
            if nv.returncode == 0 and nv.stdout.strip():
                for line in nv.stdout.strip().split("\n"):
                    parts = [p.strip() for p in line.split(",")]
                    if len(parts) >= 9:
                        mem_used = float(parts[2])
                        mem_total = float(parts[3])
                        gpus_list.append({
                            "index": int(parts[0]),
                            "name": parts[1],
                            "memory_used_mb": round(mem_used),
                            "memory_total_mb": round(mem_total),
                            "memory_free_mb": round(float(parts[4])),
                            "memory_percent": round(mem_used / mem_total * 100, 1) if mem_total > 0 else 0,
                            "utilization_percent": round(float(parts[5])),
                            "temperature_c": round(float(parts[6])),
                            "power_draw_w": round(float(parts[7]), 1),
                            "power_limit_w": round(float(parts[8]), 1),
                        })
                # Geriye uyumluluk: tek GPU varsa eski formatta da dön
                if gpus_list:
                    gpu_info = gpus_list[0]
        except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
            pass  # GPU yok veya nvidia-smi yüklü değil

        # Ollama model GPU bilgisi (cache ile — Ollama meşgulken timeout olursa son veri kullanılır)
        ollama_gpu = None
        try:
            import httpx
            resp = httpx.get("http://localhost:11434/api/ps", timeout=8)
            if resp.status_code == 200:
                ps_data = resp.json()
                models = ps_data.get("models", [])
                if models:
                    m = models[0]
                    size = m.get("size", 0)
                    size_vram = m.get("size_vram", 0)
                    ollama_gpu = {
                        "model": m.get("name", ""),
                        "total_size_gb": round(size / 1e9, 1),
                        "vram_size_gb": round(size_vram / 1e9, 1),
                        "ram_size_gb": round((size - size_vram) / 1e9, 1),
                        "gpu_offload_percent": round(size_vram / size * 100, 1) if size > 0 else 0,
                    }
                    # Cache başarılı sonucu — sonraki hatalarda fallback olarak kullanılır
                    _ollama_gpu_cache["data"] = ollama_gpu
        except Exception:
            pass
        # Ollama meşgulken veya timeout olduğunda cache'deki son veriyi kullan
        if ollama_gpu is None and _ollama_gpu_cache.get("data"):
            ollama_gpu = _ollama_gpu_cache["data"]

        return {
            "cpu_percent": round(cpu_percent, 1),
            "memory_percent": round(mem.percent, 1),
            "memory_used_gb": round(mem.used / (1024 ** 3), 1),
            "memory_total_gb": round(mem.total / (1024 ** 3), 1),
            "disk_percent": round(disk.percent, 1),
            "gpu": gpu_info,
            "gpus": gpus_list if gpus_list else None,
            "gpu_count": len(gpus_list),
            "total_vram_gb": round(sum(g["memory_total_mb"] for g in gpus_list) / 1024, 1) if gpus_list else 0,
            "ollama_gpu": ollama_gpu,
            "gpu_auto_config": _get_gpu_auto_config_summary(),
        }
    except ImportError:
        # psutil yoksa tahmini değer döndürme, hata dön
        return {
            "cpu_percent": None,
            "memory_percent": None,
            "error": "psutil not installed — pip install psutil",
        }


# ── Sistem Ayarları (SystemSettings) ─────────────────────────────

class SettingItem(BaseModel):
    key: str
    value: Optional[str] = None
    description: Optional[str] = None


@router.get("/settings")
async def list_settings(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Tüm sistem ayarlarını listeler (admin only)."""
    check_admin(current_user)

    result = await db.execute(select(SystemSettings).order_by(SystemSettings.key))
    settings_list = result.scalars().all()
    return [
        {
            "id": s.id,
            "key": s.key,
            "value": s.value,
            "description": s.description,
            "updated_at": s.updated_at,
        }
        for s in settings_list
    ]


@router.put("/settings")
async def upsert_setting(
    item: SettingItem,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Sistem ayarı ekler veya günceller (admin only)."""
    check_admin(current_user)

    result = await db.execute(
        select(SystemSettings).where(SystemSettings.key == item.key)
    )
    existing = result.scalar_one_or_none()

    if existing:
        existing.value = item.value
        if item.description is not None:
            existing.description = item.description
        existing.updated_by = current_user.id
    else:
        new_setting = SystemSettings(
            key=item.key,
            value=item.value,
            description=item.description,
            updated_by=current_user.id,
        )
        db.add(new_setting)

    await log_action(
        db,
        user=current_user,
        action="admin_update_setting",
        resource=f"setting:{item.key}",
        details=json.dumps({"value": item.value}),
    )
    await db.commit()
    return {"success": True, "key": item.key}


@router.delete("/settings/{key}")
async def delete_setting(
    key: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Sistem ayarını siler (admin only)."""
    check_admin(current_user)

    result = await db.execute(
        select(SystemSettings).where(SystemSettings.key == key)
    )
    setting = result.scalar_one_or_none()
    if not setting:
        raise HTTPException(status_code=404, detail="Ayar bulunamadı")

    await log_action(
        db, user=current_user, action="admin_delete_setting",
        resource=f"setting:{key}",
    )
    await db.delete(setting)
    await db.commit()
    return {"success": True, "message": f"'{key}' ayarı silindi"}


# ── Audit Log Listeleme ──────────────────────────────────────────

@router.get("/audit-logs")
async def list_audit_logs(
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Son denetim kayıtlarını listeler (admin only)."""
    check_admin(current_user)

    from app.db.models import AuditLog
    result = await db.execute(
        select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)
    )
    logs = result.scalars().all()
    return [
        {
            "id": a.id,
            "user_id": a.user_id,
            "action": a.action,
            "resource": a.resource,
            "details": a.details,
            "ip_address": a.ip_address,
            "created_at": a.created_at,
        }
        for a in logs
    ]


# ── AI Modül Durumu (v3.3.0) ─────────────────────────────────────

@router.get("/stats/ai-modules")
async def get_ai_modules_status(
    current_user: User = Depends(get_current_user),
):
    """Tüm AI modüllerinin aktiflik durumunu döner."""
    check_admin_or_manager(current_user)
    
    try:
        from app.core.engine import get_system_status
        status = await get_system_status()
        return {
            "modules": status.get("modules", {}),
            "llm_available": status.get("llm_available", False),
            "llm_model": status.get("llm_model", "N/A"),
            "memory_entries": status.get("memory_entries", 0),
            "rag": status.get("rag", {}),
        }
    except Exception as e:
        return {"error": str(e), "modules": {}}


@router.get("/stats/governance")
async def get_governance_metrics(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """AI Governance metrikleri — bias/drift/confidence istatistikleri."""
    check_admin_or_manager(current_user)
    
    try:
        from app.core.governance import governance_engine
        if governance_engine is None:
            return {"available": False, "error": "Governance modülü yüklü değil"}
        
        dashboard = governance_engine.get_dashboard()
        
        # Audit log'dan son alert'leri al
        audit_log = governance_engine.get_audit_log(20)
        recent_alerts = [
            {"message": r["alert_reason"], "type": "alert", "bias": r["bias_score"]}
            for r in audit_log if r.get("alert_triggered")
        ][-10:]
        
        return {
            "available": True,
            "total_queries_monitored": dashboard.total_queries,
            "avg_confidence": dashboard.avg_confidence / 100.0 if dashboard.avg_confidence > 1 else dashboard.avg_confidence,
            "bias_alerts": dashboard.bias_alerts,
            "drift_detected": dashboard.drift_detected,
            "drift_magnitude": dashboard.drift_magnitude,
            "confidence_trend": dashboard.confidence_trend,
            "low_confidence_alerts": dashboard.low_confidence_alerts,
            "recent_alerts": recent_alerts,
            "last_alert": dashboard.last_alert,
            # v4.0 fields
            "compliance_score": getattr(dashboard, 'compliance_score', None),
            "policy_violations_count": getattr(dashboard, 'policy_violations_count', 0),
            "prompt_version": getattr(dashboard, 'prompt_version', None),
            "active_drift_types": getattr(dashboard, 'active_drift_types', []),
            "decision_trace_count": getattr(dashboard, 'decision_trace_count', 0),
            "risk_level": getattr(dashboard, 'risk_level', None),
        }
    except Exception as e:
        return {"available": False, "error": str(e)}


@router.get("/stats/dept-queries")
async def get_department_query_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Departman bazlı sorgu dağılımını döner (kullanıcının gerçek departmanına göre)."""
    check_admin_or_manager(current_user)
    
    import json as _json
    
    # Kullanıcıların gerçek departmanlarına göre sorgu sayısı
    rows = await db.execute(
        select(
            User.department.label("user_dept"),
            func.count(Query.id).label("count"),
            func.avg(Query.processing_time_ms).label("avg_time"),
        )
        .join(User, Query.user_id == User.id)
        .group_by(User.department)
        .order_by(func.count(Query.id).desc())
    )
    
    result = []
    for r in rows:
        # User.department JSON array olabilir: '["Bilgi İşlem"]' veya düz string
        raw_dept = r.user_dept
        if raw_dept:
            try:
                parsed = _json.loads(raw_dept)
                dept_name = ", ".join(parsed) if isinstance(parsed, list) else str(parsed)
            except (ValueError, TypeError):
                dept_name = str(raw_dept)
        else:
            dept_name = "Belirtilmemiş"
        
        result.append({
            "department": dept_name,
            "count": r.count,
            "avg_time_ms": round(r.avg_time, 0) if r.avg_time else 0,
        })
    
    return result


# ══════════════════════════════════════════════════════════════════
# v3.4.0 — Yeni Modül Endpoint'leri
# ══════════════════════════════════════════════════════════════════


# ── Model Registry ─────────────────────────────────────────────

@router.get("/model-registry")
async def get_model_registry_dashboard(current_user: User = Depends(get_current_user)):
    """Model Registry dashboard verilerini döner."""
    check_admin_or_manager(current_user)
    if not model_registry:
        return {"available": False, "error": "Model Registry modülü yüklü değil"}
    try:
        return {"available": True, **model_registry.get_dashboard()}
    except Exception as e:
        return {"available": False, "error": str(e)}


@router.get("/model-registry/models")
async def list_registered_models(current_user: User = Depends(get_current_user)):
    check_admin_or_manager(current_user)
    if not model_registry:
        raise HTTPException(status_code=503, detail="Model Registry modülü yüklü değil")
    return model_registry.list_models()


@router.post("/model-registry/sync")
async def sync_models_with_ollama(current_user: User = Depends(get_current_user)):
    """Ollama modelleri ile senkronize et."""
    check_admin(current_user)
    if not model_registry:
        raise HTTPException(status_code=503, detail="Model Registry modülü yüklü değil")
    try:
        synced = await model_registry.sync_with_ollama()
        await log_action(None, current_user.id, "model_registry_sync", f"Senkronize edilen model sayısı: {synced}")
        return {"synced_count": synced}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/model-registry/promote/{model_name}")
async def promote_model(model_name: str, current_user: User = Depends(get_current_user)):
    """Modeli production'a yükselt."""
    check_admin(current_user)
    if not model_registry:
        raise HTTPException(status_code=503, detail="Model Registry modülü yüklü değil")
    result = model_registry.promote(model_name, promoted_by=current_user.username)
    if not result:
        raise HTTPException(status_code=404, detail="Model bulunamadı")
    await log_action(None, current_user.id, "model_promoted", f"Model: {model_name}")
    return result


# ── Data Versioning ────────────────────────────────────────────

@router.get("/data-versions")
async def get_data_versioning_dashboard(current_user: User = Depends(get_current_user)):
    check_admin_or_manager(current_user)
    if not data_version_manager:
        return {"available": False, "error": "Data Versioning modülü yüklü değil"}
    try:
        return {"available": True, **data_version_manager.get_dashboard()}
    except Exception as e:
        return {"available": False, "error": str(e)}


@router.get("/data-versions/datasets")
async def list_datasets(current_user: User = Depends(get_current_user)):
    check_admin_or_manager(current_user)
    if not data_version_manager:
        raise HTTPException(status_code=503, detail="Data Versioning modülü yüklü değil")
    return data_version_manager.list_datasets()


@router.post("/data-versions/snapshot")
async def create_data_snapshot(
    current_user: User = Depends(get_current_user),
):
    """Mevcut veri dosyalarının snapshot'ını al."""
    check_admin(current_user)
    if not data_version_manager:
        raise HTTPException(status_code=503, detail="Data Versioning modülü yüklü değil")
    try:
        # data/ klasöründeki tüm CSV/JSON dosyaları
        import glob
        files = glob.glob("data/*.csv") + glob.glob("data/*.json") + glob.glob("data/*.jsonl")
        results = []
        for f in files:
            snap = data_version_manager.create_snapshot(f, created_by=current_user.username)
            results.append(snap)
        await log_action(None, current_user.id, "data_snapshot", f"{len(results)} dosya snapshot'landı")
        return {"snapshots": results, "count": len(results)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Human-in-the-Loop ─────────────────────────────────────────

@router.get("/hitl")
async def get_hitl_dashboard(current_user: User = Depends(get_current_user)):
    check_admin_or_manager(current_user)
    if not hitl_manager:
        return {"available": False, "error": "HITL modülü yüklü değil"}
    try:
        pending = hitl_manager.get_pending_tasks()
        reviewed = hitl_manager.get_reviewed_tasks(limit=20)
        stats = hitl_manager.get_feedback_stats()
        return {
            "available": True,
            "pending_count": len(pending),
            "pending_tasks": pending[:10],
            "recent_reviewed": reviewed,
            "feedback_stats": stats,
        }
    except Exception as e:
        return {"available": False, "error": str(e)}


@router.post("/hitl/review/{task_id}")
async def review_hitl_task(
    task_id: str,
    current_user: User = Depends(get_current_user),
):
    """Onay kuyruğundaki görevi onayla/reddet."""
    check_admin_or_manager(current_user)
    if not hitl_manager:
        raise HTTPException(status_code=503, detail="HITL modülü yüklü değil")

    from fastapi import Request
    # Body'den action ve feedback alınacak
    # Basit implementasyon: query param
    return {"info": "POST body ile action=approve|reject|modify, feedback=... gönderin"}


@router.put("/hitl/review/{task_id}")
async def execute_hitl_review(
    task_id: str,
    action: str = "approve",
    feedback: str = "",
    current_user: User = Depends(get_current_user),
):
    """HITL görevini değerlendir."""
    check_admin_or_manager(current_user)
    if not hitl_manager:
        raise HTTPException(status_code=503, detail="HITL modülü yüklü değil")
    result = hitl_manager.review(
        task_id=task_id,
        action=action,
        reviewer=current_user.username,
        feedback=feedback,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Görev bulunamadı")
    await log_action(None, current_user.id, f"hitl_{action}", f"Task: {task_id}")
    return result


# ── Monitoring & Telemetry ─────────────────────────────────────

@router.get("/monitoring/telemetry")
async def get_telemetry(current_user: User = Depends(get_current_user)):
    """Tam telemetri raporu."""
    check_admin_or_manager(current_user)
    if not metrics_collector:
        return {"available": False, "error": "Monitoring modülü yüklü değil"}
    try:
        telemetry = await get_full_telemetry()
        return {"available": True, **telemetry}
    except Exception as e:
        return {"available": False, "error": str(e)}


@router.get("/monitoring/health")
async def get_health_score(current_user: User = Depends(get_current_user)):
    """Sistem sağlık skoru."""
    check_admin_or_manager(current_user)
    if not metrics_collector:
        return {"available": False}
    try:
        health = calculate_health_score()
        return {"available": True, **health}
    except Exception as e:
        return {"available": False, "error": str(e)}


@router.get("/monitoring/alerts")
async def get_alerts(current_user: User = Depends(get_current_user)):
    """Aktif alarmlar."""
    check_admin_or_manager(current_user)
    if not alert_manager:
        return {"alerts": [], "count": 0}
    try:
        alerts = alert_manager.get_active_alerts()
        return {"alerts": alerts, "count": len(alerts)}
    except Exception as e:
        return {"alerts": [], "error": str(e)}


@router.post("/monitoring/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(alert_id: str, current_user: User = Depends(get_current_user)):
    check_admin(current_user)
    if not alert_manager:
        raise HTTPException(status_code=503, detail="Alert Manager yüklü değil")
    result = alert_manager.acknowledge(alert_id, current_user.username)
    if not result:
        raise HTTPException(status_code=404, detail="Alarm bulunamadı")
    return result


# ── Textile Vision ─────────────────────────────────────────────

@router.get("/textile-vision/capabilities")
async def textile_vision_caps(current_user: User = Depends(get_current_user)):
    check_admin_or_manager(current_user)
    if not analyze_colors:
        return {"available": False, "error": "Textile Vision modülü yüklü değil"}
    return {"available": True, **get_textile_vision_capabilities()}


@router.post("/textile-vision/analyze-color")
async def textile_color_analysis(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    """Yüklenen kumaş görselinin renk analizini yapar."""
    check_admin_or_manager(current_user)
    if not analyze_colors:
        raise HTTPException(status_code=503, detail="Textile Vision modülü yüklü değil")

    import tempfile, os
    content = await file.read()
    with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
        tmp.write(content)
        tmp_path = tmp.name
    try:
        result = analyze_colors(tmp_path)
        pattern = analyze_pattern(tmp_path)
        return {"color": result, "pattern": pattern}
    finally:
        os.unlink(tmp_path)


@router.post("/textile-vision/quality-report")
async def textile_quality_report(
    file: UploadFile = File(...),
    order_no: str = "",
    lot_no: str = "",
    fabric_type: str = "",
    current_user: User = Depends(get_current_user),
):
    """Kumaş kalite kontrol raporu oluştur."""
    check_admin_or_manager(current_user)
    if not analyze_colors:
        raise HTTPException(status_code=503, detail="Textile Vision modülü yüklü değil")

    import tempfile, os
    content = await file.read()
    with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
        tmp.write(content)
        tmp_path = tmp.name
    try:
        report = generate_quality_report(tmp_path, order_no, lot_no, fabric_type)
        await log_action(None, current_user.id, "quality_report", f"Order: {order_no}")
        return report
    finally:
        os.unlink(tmp_path)


# ── Explainability (XAI) ──────────────────────────────────────

class XAIExplainRequest(BaseModel):
    query: str
    response: str
    mode: str = "Sohbet"
    confidence: float = 0.85
    sources: list = []
    module_source: str = "manual"


@router.get("/explainability")
async def xai_dashboard(current_user: User = Depends(get_current_user)):
    check_admin_or_manager(current_user)
    if not decision_explainer:
        return {"available": False, "error": "XAI modülü yüklü değil"}
    return {"available": True, **decision_explainer.get_dashboard()}


@router.post("/explainability/explain")
async def explain_decision(
    body: XAIExplainRequest,
    current_user: User = Depends(get_current_user),
):
    """Bir AI kararını manuel olarak açıkla."""
    check_admin_or_manager(current_user)
    if not decision_explainer:
        raise HTTPException(status_code=503, detail="XAI modülü yüklü değil")
    result = decision_explainer.explain(
        query=body.query,
        response=body.response,
        mode=body.mode,
        confidence=body.confidence,
        sources=body.sources,
        module_source=body.module_source,
    )
    return {"available": True, **result}


@router.get("/explainability/history")
async def xai_history(
    limit: int = 20,
    current_user: User = Depends(get_current_user),
):
    """Son XAI değerlendirme geçmişini getir."""
    check_admin_or_manager(current_user)
    if not decision_explainer:
        return {"available": False, "records": []}
    history = list(decision_explainer._history)[-limit:]
    records = []
    for r in reversed(history):
        records.append({
            "timestamp": r.timestamp,
            "query_preview": r.query_preview,
            "mode": r.mode,
            "weighted_confidence": round(r.weighted_confidence, 3),
            "risk_level": r.risk_level,
            "sources_used": r.sources_used,
            "reasoning_steps": r.reasoning_steps,
            "user_rating": r.user_rating,
            "token_attribution": r.token_attribution[:5] if r.token_attribution else [],
        })
    return {"available": True, "total": len(records), "records": records}


class XAIFeedbackRequest(BaseModel):
    query_hash: str
    user_rating: float  # 1-5
    factor_overrides: dict = {}
    comment: str = ""


@router.post("/explainability/feedback")
async def xai_feedback(
    body: XAIFeedbackRequest,
    current_user: User = Depends(get_current_user),
):
    """XAI sonucuna kullanıcı geri bildirimi gönder — kalibrasyon döngüsü."""
    if not decision_explainer:
        raise HTTPException(status_code=503, detail="XAI modülü yüklü değil")
    result = decision_explainer.submit_feedback(
        query_hash=body.query_hash,
        user_rating=body.user_rating,
        factor_overrides=body.factor_overrides if body.factor_overrides else None,
        comment=body.comment,
    )
    return result


@router.get("/explainability/calibration")
async def xai_calibration(current_user: User = Depends(get_current_user)):
    """Kalibrasyon durumu ve geçmişi."""
    check_admin_or_manager(current_user)
    if not decision_explainer:
        return {"available": False}
    return {"available": True, **decision_explainer.get_calibration_status()}


# ══════════════════════════════════════════════════════════════════════
# GOVERNANCE v4.0 — Decision Trace, Policy, Drift, Compliance
# ══════════════════════════════════════════════════════════════════════

@router.get("/governance/traces")
async def get_governance_traces(
    last_n: int = 50,
    current_user: User = Depends(get_current_user),
):
    """Son karar izleri (decision traces) — tam karar takibi."""
    check_admin_or_manager(current_user)
    try:
        from app.core.governance import governance_engine
        if governance_engine is None:
            return {"available": False}
        traces = governance_engine.get_decision_traces(last_n)
        return {"available": True, "traces": traces, "count": len(traces)}
    except Exception as e:
        return {"available": False, "error": str(e)}


@router.get("/governance/trace/{trace_id}")
async def get_governance_trace_detail(
    trace_id: str,
    current_user: User = Depends(get_current_user),
):
    """Belirli bir karar izinin detayı."""
    check_admin_or_manager(current_user)
    try:
        from app.core.governance import governance_engine
        if governance_engine is None:
            raise HTTPException(status_code=503, detail="Governance modülü yüklü değil")
        trace = governance_engine.get_trace_by_id(trace_id)
        if not trace:
            raise HTTPException(status_code=404, detail="İz bulunamadı")
        return {"available": True, **trace}
    except HTTPException:
        raise
    except Exception as e:
        return {"available": False, "error": str(e)}


@router.get("/governance/policy-rules")
async def get_governance_policy_rules(
    current_user: User = Depends(get_current_user),
):
    """Tüm tanımlı politika kuralları."""
    check_admin_or_manager(current_user)
    try:
        from app.core.governance import governance_engine
        if governance_engine is None:
            return {"available": False}
        rules = governance_engine.get_policy_rules()
        return {"available": True, "rules": rules, "count": len(rules)}
    except Exception as e:
        return {"available": False, "error": str(e)}


@router.get("/governance/violations")
async def get_governance_violations(
    last_n: int = 50,
    current_user: User = Depends(get_current_user),
):
    """Son politika ihlalleri."""
    check_admin_or_manager(current_user)
    try:
        from app.core.governance import governance_engine
        if governance_engine is None:
            return {"available": False}
        violations = governance_engine.get_policy_violations(last_n)
        return {"available": True, "violations": violations, "count": len(violations)}
    except Exception as e:
        return {"available": False, "error": str(e)}


@router.get("/governance/drift")
async def get_governance_drift_status(
    current_user: User = Depends(get_current_user),
):
    """Drift (kayma) analizi — 4 boyutlu drift durumu."""
    check_admin_or_manager(current_user)
    try:
        from app.core.governance import governance_engine
        if governance_engine is None:
            return {"available": False}
        drift = governance_engine.get_drift_status()
        return {"available": True, **drift}
    except Exception as e:
        return {"available": False, "error": str(e)}


@router.get("/governance/compliance")
async def get_governance_compliance_report(
    current_user: User = Depends(get_current_user),
):
    """Kapsamlı uyumluluk raporu."""
    check_admin(current_user)
    try:
        from app.core.governance import governance_engine
        if governance_engine is None:
            return {"available": False}
        report = governance_engine.get_compliance_report()
        return {"available": True, **report}
    except Exception as e:
        return {"available": False, "error": str(e)}


# ══════════════════════════════════════════════════════════════════════
# MONITORING v2.0 — Anomaly, SLA, Performance Trend
# ══════════════════════════════════════════════════════════════════════

@router.get("/monitoring/anomalies")
async def get_monitoring_anomalies(
    current_user: User = Depends(get_current_user),
):
    """Anomali tespit logları ve istatistikleri."""
    check_admin_or_manager(current_user)
    if not metrics_collector:
        return {"available": False, "error": "Monitoring modülü yüklü değil"}
    try:
        anomaly_log = metrics_collector.get_anomaly_log()
        anomaly_stats = metrics_collector.get_anomaly_stats()
        return {
            "available": True,
            "anomaly_log": anomaly_log[-50:],
            "stats": anomaly_stats,
        }
    except Exception as e:
        return {"available": False, "error": str(e)}


@router.get("/monitoring/sla")
async def get_monitoring_sla(
    current_user: User = Depends(get_current_user),
):
    """SLA uyumluluk durumu."""
    check_admin_or_manager(current_user)
    try:
        if not sla_monitor:
            return {"available": False, "error": "SLA Monitor yüklü değil"}
        compliance = sla_monitor.check_sla_compliance(metrics_collector) if metrics_collector else {}
        uptime = sla_monitor.get_uptime_percent(24)
        return {
            "available": True,
            "uptime_24h": uptime,
            "sla_compliance": compliance,
            "targets": {
                "uptime_percent": sla_monitor.targets.get("uptime_percent", 99.5),
                "response_time_p95_ms": sla_monitor.targets.get("response_time_p95_ms", 10000),
                "error_rate_percent": sla_monitor.targets.get("error_rate_percent", 2.0),
            },
        }
    except Exception as e:
        return {"available": False, "error": str(e)}


@router.get("/monitoring/trend")
async def get_monitoring_performance_trend(
    last_n: int = 100,
    current_user: User = Depends(get_current_user),
):
    """Performance trend analizi — degradasyon tespiti."""
    check_admin_or_manager(current_user)
    if not metrics_collector:
        return {"available": False, "error": "Monitoring modülü yüklü değil"}
    try:
        trend = metrics_collector.get_performance_trend(last_n)
        return {"available": True, **trend}
    except Exception as e:
        return {"available": False, "error": str(e)}


# ══════════════════════════════════════════════════════════════════════
# AUDIT v2.0 — Compliance Engine, Retention, Severity
# ══════════════════════════════════════════════════════════════════════

@router.get("/audit/compliance")
async def get_audit_compliance(
    current_user: User = Depends(get_current_user),
):
    """Audit uyumluluk skoru ve kategori analizi."""
    check_admin(current_user)
    try:
        if not audit_compliance_engine:
            return {"available": False, "error": "Compliance Engine yüklü değil"}
        score_data = audit_compliance_engine.get_compliance_score()
        violations = audit_compliance_engine.get_violations()
        return {
            "available": True,
            **score_data,
            "violations": violations[-20:],
            "violation_count": len(violations),
        }
    except Exception as e:
        return {"available": False, "error": str(e)}


# ══════════════════════════════════════════════════════════════════════
# INSIGHT ENGINE v1.0 — Otomatik İçgörü (v3.9.0)
# ══════════════════════════════════════════════════════════════════════

@router.get("/insights/demo")
async def get_insight_demo(
    current_user: User = Depends(get_current_user),
):
    """Demo verilerle Insight Engine çalıştır."""
    check_admin_or_manager(current_user)
    try:
        import pandas as pd
        import numpy as np
        from app.core.insight_engine import extract_insights, insights_to_dict

        # Demo textile veri seti
        np.random.seed(42)
        n = 100
        demo_df = pd.DataFrame({
            "departman": np.random.choice(["İplik", "Dokuma", "Boyahane", "Konfeksiyon"], n),
            "verimlilik": np.random.normal(82, 8, n).clip(50, 100),
            "fire_orani": np.random.exponential(3.5, n).clip(0.5, 20),
            "enerji_tuketim": np.random.normal(115, 15, n).clip(70, 180),
            "hata_orani": np.random.exponential(2.2, n).clip(0.1, 15),
            "kapasite_kullanimi": np.random.normal(78, 10, n).clip(40, 100),
            "maliyet_tl": np.random.normal(50000, 15000, n).clip(10000, 120000),
            "uretim_kg": np.random.normal(5000, 1500, n).clip(1000, 12000),
        })
        # Korelasyon oluştur
        demo_df["gelir_tl"] = demo_df["uretim_kg"] * np.random.normal(12, 2, n)

        report = extract_insights(demo_df, max_insights=15)
        result = insights_to_dict(report)
        return {"available": True, **result}
    except Exception as e:
        return {"available": False, "error": str(e)}


class InsightRequest(BaseModel):
    data: list = []
    max_insights: int = 20


@router.post("/insights/analyze")
async def analyze_insights(
    body: InsightRequest,
    current_user: User = Depends(get_current_user),
):
    """Kullanıcı verisiyle insight analizi çalıştır."""
    check_admin_or_manager(current_user)
    try:
        import pandas as pd
        from app.core.insight_engine import extract_insights, insights_to_dict

        if not body.data:
            raise HTTPException(status_code=400, detail="Veri listesi boş")

        df = pd.DataFrame(body.data)
        report = extract_insights(df, max_insights=body.max_insights)
        result = insights_to_dict(report)
        return {"available": True, **result}
    except HTTPException:
        raise
    except Exception as e:
        return {"available": False, "error": str(e)}


# ══════════════════════════════════════════════════════════════════════
# CEO DASHBOARD v1.0 — Birleşik CEO Paneli (v3.9.0)
# ══════════════════════════════════════════════════════════════════════

@router.get("/ceo/dashboard")
async def get_ceo_dashboard(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """CEO paneli — sağlık skoru + darboğaz + insight birleşimi."""
    check_admin_or_manager(current_user)
    result = {"available": True}

    # 1) Executive Health
    try:
        from app.core.executive_health import get_demo_health_index
        health = get_demo_health_index()
        result["health"] = {
            "overall_score": health.overall_score,
            "overall_grade": health.overall_grade,
            "overall_status": health.overall_status,
            "dimensions": [
                {"name": d.name, "score": d.score, "grade": d.grade, "color": d.color, "trend": d.trend}
                for d in health.dimensions
            ],
        }
    except Exception:
        result["health"] = None

    # 2) Bottleneck
    try:
        from app.core.bottleneck_engine import get_template_analysis
        bn = get_template_analysis("dokuma")
        result["bottleneck"] = {
            "process_name": bn.process_name,
            "bottleneck_step": bn.bottleneck_step,
            "severity": bn.severity,
            "score": bn.score,
            "recommendations": bn.recommendations[:3],
        }
    except Exception:
        result["bottleneck"] = None

    # 3) Insights (demo)
    try:
        import pandas as pd
        import numpy as np
        from app.core.insight_engine import extract_insights, insights_to_dict
        np.random.seed(42)
        n = 50
        df = pd.DataFrame({
            "departman": np.random.choice(["İplik", "Dokuma", "Boyahane", "Konfeksiyon"], n),
            "verimlilik": np.random.normal(82, 8, n).clip(50, 100),
            "fire_orani": np.random.exponential(3.5, n).clip(0.5, 20),
        })
        report = extract_insights(df, max_insights=5)
        result["insights"] = insights_to_dict(report)
    except Exception:
        result["insights"] = None

    # 4) Son 24 saat sorgu sayısı
    try:
        since = datetime.utcnow() - timedelta(hours=24)
        count_result = await db.execute(
            select(func.count()).select_from(Query).where(Query.created_at >= since)
        )
        result["queries_24h"] = count_result.scalar() or 0
    except Exception:
        result["queries_24h"] = 0

    return result


@router.get("/audit/summary")
async def get_audit_event_summary(
    hours: int = 24,
    current_user: User = Depends(get_current_user),
):
    """Audit olay özeti — son N saat."""
    check_admin_or_manager(current_user)
    try:
        if not audit_compliance_engine:
            return {"available": False}
        summary = audit_compliance_engine.get_event_summary(hours)
        return {"available": True, **summary}
    except Exception as e:
        return {"available": False, "error": str(e)}


@router.post("/audit/retention/cleanup")
async def run_audit_retention_cleanup(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Veri saklama politikasına göre eski audit kayıtlarını temizle."""
    check_admin(current_user)
    try:
        if not data_retention_policy:
            raise HTTPException(status_code=503, detail="Data Retention Policy yüklü değil")
        result = await data_retention_policy.cleanup(db)
        await log_action(db, current_user.id, "audit_retention_cleanup", json.dumps(result))
        return {"success": True, **result}
    except HTTPException:
        raise
    except Exception as e:
        return {"success": False, "error": str(e)}


# ══════════════════════════════════════════════════════════════════════
# BOTTLENECK ENGINE v1.0 — Darboğaz Tespiti (v3.8.0)
# ══════════════════════════════════════════════════════════════════════

@router.get("/bottleneck/templates")
async def get_bottleneck_templates(
    current_user: User = Depends(get_current_user),
):
    """Kullanılabilir süreç şablonlarını listele."""
    check_admin_or_manager(current_user)
    try:
        from app.core.bottleneck_engine import list_templates
        return {"available": True, "templates": list_templates()}
    except ImportError:
        return {"available": False, "error": "Bottleneck Engine yüklü değil"}


@router.get("/bottleneck/analyze/{process_type}")
async def analyze_bottleneck_template(
    process_type: str = "dokuma",
    current_user: User = Depends(get_current_user),
):
    """Hazır şablon ile darboğaz analizi çalıştır."""
    check_admin_or_manager(current_user)
    try:
        from app.core.bottleneck_engine import get_template_analysis, format_bottleneck_report
        result = get_template_analysis(process_type)
        return {
            "available": True,
            "process_name": result.process_name,
            "bottleneck_step": result.bottleneck_step,
            "bottleneck_type": result.bottleneck_type,
            "severity": result.severity,
            "score": result.score,
            "impact": result.impact_description,
            "recommendations": result.recommendations,
            "chain_effects": result.chain_effects,
            "metrics": result.metrics,
            "report": format_bottleneck_report(result),
        }
    except Exception as e:
        return {"available": False, "error": str(e)}


class BottleneckRequest(BaseModel):
    process_name: str = "Üretim Hattı"
    process_type: str = "genel_uretim"
    steps: list = []


@router.post("/bottleneck/analyze")
async def analyze_bottleneck_custom(
    body: BottleneckRequest,
    current_user: User = Depends(get_current_user),
):
    """Özel veriyle darboğaz analizi çalıştır."""
    check_admin_or_manager(current_user)
    try:
        from app.core.bottleneck_engine import analyze_from_data, format_bottleneck_report
        data = {"process_name": body.process_name, "steps": body.steps}
        result = analyze_from_data(data, body.process_type)
        return {
            "available": True,
            "process_name": result.process_name,
            "bottleneck_step": result.bottleneck_step,
            "bottleneck_type": result.bottleneck_type,
            "severity": result.severity,
            "score": result.score,
            "impact": result.impact_description,
            "recommendations": result.recommendations,
            "chain_effects": result.chain_effects,
            "metrics": result.metrics,
            "report": format_bottleneck_report(result),
        }
    except Exception as e:
        return {"available": False, "error": str(e)}


# ══════════════════════════════════════════════════════════════════════
# EXECUTIVE HEALTH INDEX v1.0 — Şirket Sağlık Skoru (v3.8.0)
# ══════════════════════════════════════════════════════════════════════

@router.get("/executive/health-demo")
async def get_executive_health_demo(
    current_user: User = Depends(get_current_user),
):
    """Demo verilerle Executive Health Index göster."""
    check_admin_or_manager(current_user)
    try:
        from app.core.executive_health import get_demo_health_index, format_health_dashboard
        index = get_demo_health_index()
        return {
            "available": True,
            "overall_score": index.overall_score,
            "overall_grade": index.overall_grade,
            "overall_status": index.overall_status,
            "dimensions": [
                {
                    "name": d.name,
                    "score": d.score,
                    "grade": d.grade,
                    "color": d.color,
                    "trend": d.trend,
                    "indicators": d.indicators,
                }
                for d in index.dimensions
            ],
            "recommendations": index.recommendations,
            "executive_summary": index.executive_summary,
            "dashboard": format_health_dashboard(index),
        }
    except Exception as e:
        return {"available": False, "error": str(e)}


class HealthIndexRequest(BaseModel):
    financial: dict = {}
    operational: dict = {}
    growth: dict = {}
    risk: dict = {}


@router.post("/executive/health")
async def calculate_executive_health(
    body: HealthIndexRequest,
    current_user: User = Depends(get_current_user),
):
    """Gerçek verilerle Executive Health Index hesapla."""
    check_admin_or_manager(current_user)
    try:
        from app.core.executive_health import calculate_health_index, format_health_dashboard
        data = {
            "financial": body.financial,
            "operational": body.operational,
            "growth": body.growth,
            "risk": body.risk,
        }
        index = calculate_health_index(data)
        return {
            "available": True,
            "overall_score": index.overall_score,
            "overall_grade": index.overall_grade,
            "overall_status": index.overall_status,
            "dimensions": [
                {
                    "name": d.name,
                    "score": d.score,
                    "grade": d.grade,
                    "color": d.color,
                    "trend": d.trend,
                    "indicators": d.indicators,
                }
                for d in index.dimensions
            ],
            "recommendations": index.recommendations,
            "executive_summary": index.executive_summary,
            "dashboard": format_health_dashboard(index),
        }
    except Exception as e:
        return {"available": False, "error": str(e)}


# ── Öğrenme İstatistikleri (v3.10.0) ────────────────────────────

@router.get("/stats/learning")
async def get_learning_stats(
    current_user: User = Depends(get_current_user),
):
    """
    Otomatik öğrenme sistemi istatistikleri.
    ChromaDB'deki kayıt sayılarını türe göre döndürür.
    """
    check_admin_or_manager(current_user)

    try:
        from app.rag.vector_store import get_collection, get_stats

        base = get_stats()
        result = {
            "available": base.get("available", False),
            "total_documents": base.get("document_count", 0),
            "embedding_model": base.get("embedding_model"),
            "by_type": {},
        }

        collection = get_collection()
        if collection:
            all_meta = collection.get(include=["metadatas"])
            if all_meta and all_meta["metadatas"]:
                type_counts: dict[str, int] = {}
                for m in all_meta["metadatas"]:
                    t = m.get("type", "unknown")
                    type_counts[t] = type_counts.get(t, 0) + 1
                result["by_type"] = dict(sorted(type_counts.items(), key=lambda x: -x[1]))

        return result
    except Exception as e:
        return {"available": False, "error": str(e), "total_documents": 0, "by_type": {}}


# ── GPU Otomatik Konfigürasyon ────────────────────────────────────

def _get_gpu_auto_config_summary() -> dict:
    """GPU auto-config özeti — system-resources ve gpu-config endpoint'lerinde kullanılır."""
    try:
        from app.llm.gpu_config import gpu_config
        return gpu_config.summary()
    except Exception:
        return {"probed": False, "error": "gpu_config not available"}


@router.get("/gpu-config")
async def get_gpu_config(
    current_user: User = Depends(get_current_user),
):
    """
    GPU otomatik algılama durumu ve uygulanan konfigürasyon.
    
    Dönen bilgiler:
    - mode: CPU-only / Single GPU / Multi-GPU
    - gpu_count: Algılanan GPU sayısı
    - total_vram_gb: Toplam VRAM
    - gpus: Her GPU'nun detay bilgisi
    - applied_config: Ollama'ya gönderilen parametreler
    """
    check_admin_or_manager(current_user)
    return _get_gpu_auto_config_summary()


@router.post("/gpu-config/reprobe")
async def reprobe_gpu(
    current_user: User = Depends(get_current_user),
):
    """
    GPU algılamayı yeniden çalıştır (restart gerekmeden).
    Yeni GPU takıldığında veya çıkarıldığında kullanılır.
    Ollama /etc/default/ollama env dosyasını da otomatik günceller.
    """
    check_admin(current_user)
    from app.llm.gpu_config import gpu_config
    from app.llm.client import ollama_client

    old_mode = gpu_config.mode
    old_timeout = gpu_config.timeout
    old_gpu_count = gpu_config.gpu_count

    await gpu_config.probe()

    # Timeout değiştiyse HTTP client'ı yenile
    if old_timeout != gpu_config.timeout:
        await ollama_client._refresh_client_if_needed()

    return {
        "previous_mode": old_mode,
        "current_mode": gpu_config.mode,
        "gpu_count_changed": old_gpu_count != gpu_config.gpu_count,
        "timeout_changed": old_timeout != gpu_config.timeout,
        **gpu_config.summary(),
    }


# ══════════════════════════════════════════════════════════════════════
# PERFORMANS AYARLARI (v5.6.0) — GPU/CPU/RAM Performans Profili
# ══════════════════════════════════════════════════════════════════════

class PerformanceProfileRequest(BaseModel):
    mode: str = "auto"  # "full" | "balanced" | "eco" | "custom" | "auto"
    gpu_percent: int = 100   # 0-100 → GPU katman yüzdesi
    cpu_percent: int = 100   # 0-100 → CPU thread yüzdesi
    ram_percent: int = 100   # 0-100 → Context window yüzdesi

_PERF_PRESETS = {
    "full": {"gpu_percent": 100, "cpu_percent": 100, "ram_percent": 100},
    "balanced": {"gpu_percent": 65, "cpu_percent": 50, "ram_percent": 60},
    "eco": {"gpu_percent": 30, "cpu_percent": 25, "ram_percent": 30},
}

# Parametre sınırları
_NUM_CTX_RANGE = (2048, 8192)
_NUM_BATCH_RANGE = (64, 2048)
_TOTAL_MODEL_LAYERS = 81  # varsayılan (dinamik güncellenir)
_ACTIVE_MODEL_NAME: str = ""  # şu an yüklü model adı


async def _detect_model_layers() -> tuple[int, str]:
    """
    Ollama'dan aktif modelin katman sayısını ve adını dinamik algıla.
    
    1. /api/ps → şu an yüklü model adını al
    2. /api/show → model detaylarından katman sayısını çıkar
    
    Döner: (layer_count, model_name)
    Hata durumunda mevcut _TOTAL_MODEL_LAYERS değerini korur.
    """
    import httpx
    from app.config import settings

    model_name = ""
    layer_count = 0

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            # 1. Aktif modeli bul (önce /api/ps, sonra settings)
            try:
                ps_resp = await client.get(f"{settings.OLLAMA_BASE_URL}/api/ps")
                if ps_resp.status_code == 200:
                    ps_data = ps_resp.json()
                    models = ps_data.get("models", [])
                    if models:
                        model_name = models[0].get("name", "")
            except Exception:
                pass

            if not model_name:
                model_name = getattr(settings, "LLM_MODEL", "qwen2.5:72b")

            # 2. /api/show ile model detaylarını al
            show_resp = await client.post(
                f"{settings.OLLAMA_BASE_URL}/api/show",
                json={"name": model_name},
            )
            if show_resp.status_code == 200:
                show_data = show_resp.json()
                model_info = show_data.get("model_info", {})

                # Katman sayısını bul — farklı mimarilerde farklı key'ler olabilir
                for key in model_info:
                    if "block_count" in key or "num_hidden_layers" in key or "n_layer" in key:
                        val = model_info[key]
                        if isinstance(val, (int, float)) and val > 0:
                            layer_count = int(val)
                            break

                # +1 (embed/output katmanları Ollama tarafında eklenir)
                if layer_count > 0:
                    layer_count += 1

    except Exception as e:
        logger.warning("model_layer_detect_failed", error=str(e))

    return (layer_count, model_name)


def _calc_perf_params(gpu_pct: int, cpu_pct: int, ram_pct: int) -> dict:
    """Yüzde değerlerini Ollama parametrelerine dönüştür."""
    import os

    physical_cores = os.cpu_count() // 2 if os.cpu_count() else 8

    # GPU → num_gpu katman sayısı
    gpu_layers = max(0, min(_TOTAL_MODEL_LAYERS, round(_TOTAL_MODEL_LAYERS * gpu_pct / 100)))
    if gpu_pct >= 95:
        num_gpu = 99  # Tamamını GPU'ya yükle (Ollama otomatik)
    elif gpu_pct <= 5:
        num_gpu = 0   # CPU-only
    else:
        num_gpu = gpu_layers

    # CPU → num_thread
    max_threads = max(1, physical_cores)
    num_thread = max(1, round(max_threads * cpu_pct / 100))

    # RAM → num_ctx (context window) + num_batch
    ctx_range = _NUM_CTX_RANGE[1] - _NUM_CTX_RANGE[0]
    num_ctx = _NUM_CTX_RANGE[0] + round(ctx_range * ram_pct / 100)
    num_ctx = max(_NUM_CTX_RANGE[0], min(_NUM_CTX_RANGE[1], num_ctx))
    # num_ctx'i 256'nın katına yuvarla
    num_ctx = (num_ctx // 256) * 256

    batch_range = _NUM_BATCH_RANGE[1] - _NUM_BATCH_RANGE[0]
    num_batch = _NUM_BATCH_RANGE[0] + round(batch_range * ram_pct / 100)
    num_batch = max(_NUM_BATCH_RANGE[0], min(_NUM_BATCH_RANGE[1], num_batch))
    num_batch = (num_batch // 64) * 64

    return {
        "num_gpu": num_gpu,
        "num_thread": num_thread,
        "num_ctx": num_ctx,
        "num_batch": num_batch,
        "gpu_layers_display": gpu_layers,
    }


@router.get("/performance-profile")
async def get_performance_profile(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Mevcut performans profilini döndür."""
    check_admin_or_manager(current_user)

    # SystemSettings'den kayıtlı profili oku
    result = await db.execute(
        select(SystemSettings).where(SystemSettings.key == "performance_profile")
    )
    setting = result.scalar_one_or_none()

    from app.llm.gpu_config import gpu_config

    if setting and setting.value:
        try:
            profile = json.loads(setting.value)
        except json.JSONDecodeError:
            profile = {"mode": "auto", "gpu_percent": 100, "cpu_percent": 100, "ram_percent": 100}
    else:
        profile = {"mode": "auto", "gpu_percent": 100, "cpu_percent": 100, "ram_percent": 100}

    # Mevcut canlı parametreleri de ekle
    params = _calc_perf_params(profile["gpu_percent"], profile["cpu_percent"], profile["ram_percent"])

    return {
        **profile,
        "calculated_params": params,
        "live_config": gpu_config.summary().get("applied_config", {}),
        "total_model_layers": _TOTAL_MODEL_LAYERS,
        "active_model": _ACTIVE_MODEL_NAME,
        "presets": _PERF_PRESETS,
    }


@router.put("/performance-profile")
async def update_performance_profile(
    req: PerformanceProfileRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Performans profilini kaydet ve uygula.
    
    Modlar:
    - auto: GPU otomatik algılama (varsayılan)
    - full: Tam performans — tüm kaynaklar maksimum
    - balanced: Dengeli — orta seviye kaynak kullanımı
    - eco: Eko — minimum kaynak, sessiz çalışma
    - custom: Özel — kullanıcının bar slider ile ayarladığı değerler
    """
    check_admin(current_user)

    # Preset modlarında yüzdeleri override et
    if req.mode in _PERF_PRESETS:
        preset = _PERF_PRESETS[req.mode]
        req.gpu_percent = preset["gpu_percent"]
        req.cpu_percent = preset["cpu_percent"]
        req.ram_percent = preset["ram_percent"]

    # Yüzdeleri sınırla
    gpu_pct = max(0, min(100, req.gpu_percent))
    cpu_pct = max(0, min(100, req.cpu_percent))
    ram_pct = max(0, min(100, req.ram_percent))

    # Parametreleri hesapla
    params = _calc_perf_params(gpu_pct, cpu_pct, ram_pct)

    # gpu_config'e uygula
    from app.llm.gpu_config import gpu_config
    from app.llm.client import ollama_client

    old_timeout = gpu_config.timeout
    gpu_config.num_gpu = params["num_gpu"]
    gpu_config.num_thread = params["num_thread"]
    gpu_config.num_ctx = params["num_ctx"]
    gpu_config.num_batch = params["num_batch"]

    # Timeout sabit 15 dakika
    gpu_config.timeout = 900.0

    # Timeout değiştiyse HTTP client'ı yenile
    if old_timeout != gpu_config.timeout:
        await ollama_client._refresh_client_if_needed()

    # Profili DB'ye kaydet
    profile_data = {
        "mode": req.mode,
        "gpu_percent": gpu_pct,
        "cpu_percent": cpu_pct,
        "ram_percent": ram_pct,
        "applied_at": datetime.utcnow().isoformat(),
    }

    result = await db.execute(
        select(SystemSettings).where(SystemSettings.key == "performance_profile")
    )
    existing = result.scalar_one_or_none()

    if existing:
        existing.value = json.dumps(profile_data)
        existing.description = f"Performans Profili: {req.mode}"
        existing.updated_by = current_user.id
    else:
        db.add(SystemSettings(
            key="performance_profile",
            value=json.dumps(profile_data),
            description=f"Performans Profili: {req.mode}",
            updated_by=current_user.id,
        ))

    await log_action(
        db,
        user=current_user,
        action="admin_update_performance_profile",
        resource="performance_profile",
        details=json.dumps(profile_data),
    )
    await db.commit()

    return {
        "success": True,
        "profile": profile_data,
        "applied_params": params,
        "live_config": gpu_config.summary().get("applied_config", {}),
    }


# ══════════════════════════════════════════════════════════════════════
# OLLAMA MODEL YÖNETİMİ v5.8.0 — İndirme / Değiştirme / Silme
# ══════════════════════════════════════════════════════════════════════

# Tüm bilinen Ollama modelleri — VRAM'e göre filtrelenir
_ALL_KNOWN_MODELS = [
    # name, vram_gb (Q4_K_M quantize tahmini), desc
    {"name": "qwen2.5:1.5b",    "vram_gb": 1.5,  "desc": "Ultra hafif, anlık yanıt"},
    {"name": "qwen2.5:3b",      "vram_gb": 2.5,  "desc": "Hafif, hızlı yanıt"},
    {"name": "phi4-mini:3.8b",   "vram_gb": 3.0,  "desc": "Microsoft Phi-4 Mini"},
    {"name": "llama3.2:3b",     "vram_gb": 2.5,  "desc": "Meta Llama 3.2 küçük"},
    {"name": "gemma3:4b",       "vram_gb": 3.0,  "desc": "Google Gemma 3 küçük"},
    {"name": "mistral:7b",      "vram_gb": 4.5,  "desc": "Mistral AI 7B"},
    {"name": "qwen2.5:7b",      "vram_gb": 5.0,  "desc": "Dengeli performans"},
    {"name": "llama3.1:8b",     "vram_gb": 5.5,  "desc": "Meta Llama 3.1 8B"},
    {"name": "gemma3:12b",      "vram_gb": 8.0,  "desc": "Google Gemma 3 12B"},
    {"name": "qwen2.5:14b",     "vram_gb": 9.5,  "desc": "Güçlü, orta hız"},
    {"name": "phi4:14b",        "vram_gb": 9.5,  "desc": "Microsoft Phi-4 14B"},
    {"name": "gemma3:27b",      "vram_gb": 17.0, "desc": "Google Gemma 3 27B"},
    {"name": "qwen2.5:32b",     "vram_gb": 20.0, "desc": "Yüksek kalite"},
    {"name": "qwen2.5:72b",     "vram_gb": 47.0, "desc": "Maksimum kalite"},
    {"name": "llama3.3:70b",    "vram_gb": 43.0, "desc": "Meta Llama 3.3 70B"},
    {"name": "deepseek-r1:7b",  "vram_gb": 5.0,  "desc": "DeepSeek R1 küçük"},
    {"name": "deepseek-r1:14b", "vram_gb": 9.5,  "desc": "DeepSeek R1 14B"},
    {"name": "deepseek-r1:32b", "vram_gb": 20.0, "desc": "DeepSeek R1 32B"},
    {"name": "deepseek-r1:70b", "vram_gb": 43.0, "desc": "DeepSeek R1 70B"},
    {"name": "command-r:35b",   "vram_gb": 22.0, "desc": "Cohere Command R"},
    {"name": "codellama:34b",   "vram_gb": 21.0, "desc": "Meta Code Llama 34B"},
]


def _get_hardware_filtered_models(total_vram_gb: float) -> list[dict]:
    """
    Donanım VRAM kapasitesine göre modelleri filtrele ve öner.
    
    - fit='full'   : Model VRAM'e tam sığar (vram_gb <= total_vram * 0.90)
    - fit='partial': Model kısmi offload ile çalışır (vram_gb <= total_vram * 1.5)
    - fit='cpu'    : VRAM yetmez, CPU offload gerekir (gösterilmez)
    
    Döner: VRAM'e göre sıralı model listesi (küçükten büyüğe)
    """
    if total_vram_gb <= 0:
        # GPU yok — sadece küçük modelleri CPU-only olarak öner
        total_vram_gb = 8  # CPU fallback: 8 GB varsay

    result = []
    for m in _ALL_KNOWN_MODELS:
        vram_need = m["vram_gb"]
        
        if vram_need <= total_vram_gb * 0.90:
            fit = "full"
            fit_label = "Tam sığar"
        elif vram_need <= total_vram_gb * 1.3:
            fit = "partial"
            fit_label = "Kısmi offload"
        else:
            continue  # Bu model donanıma uygun değil, listede gösterme

        size_label = f"~{vram_need:.0f} GB" if vram_need >= 1 else f"~{vram_need * 1024:.0f} MB"

        result.append({
            "name": m["name"],
            "vram_gb": vram_need,
            "size_label": size_label,
            "desc": m["desc"],
            "fit": fit,
            "fit_label": fit_label,
        })

    # VRAM'e göre sırala (küçükten büyüğe)
    result.sort(key=lambda x: x["vram_gb"])
    return result


@router.get("/ollama/models")
async def get_ollama_models(
    current_user: User = Depends(get_current_user),
):
    """
    Ollama'da yüklü modelleri listele + popüler indirilebilir modelleri göster.
    """
    check_admin_or_manager(current_user)

    import httpx
    from app.config import settings

    installed_models = []
    active_model = ""

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            # Yüklü modeller
            tags_resp = await client.get(f"{settings.OLLAMA_BASE_URL}/api/tags")
            if tags_resp.status_code == 200:
                tags_data = tags_resp.json()
                for m in tags_data.get("models", []):
                    installed_models.append({
                        "name": m.get("name", ""),
                        "size": m.get("size", 0),
                        "size_label": _format_size(m.get("size", 0)),
                        "modified_at": m.get("modified_at", ""),
                        "family": m.get("details", {}).get("family", ""),
                        "parameter_size": m.get("details", {}).get("parameter_size", ""),
                        "quantization": m.get("details", {}).get("quantization_level", ""),
                    })

            # Aktif model
            try:
                ps_resp = await client.get(f"{settings.OLLAMA_BASE_URL}/api/ps")
                if ps_resp.status_code == 200:
                    ps_models = ps_resp.json().get("models", [])
                    if ps_models:
                        active_model = ps_models[0].get("name", "")
            except Exception:
                pass

    except Exception as e:
        logger.warning("ollama_model_list_failed", error=str(e))
        raise HTTPException(status_code=502, detail=f"Ollama bağlantı hatası: {e}")

    if not active_model:
        active_model = getattr(settings, "LLM_MODEL", "")

    # Yüklü model isimlerini set olarak tut
    installed_names = {m["name"] for m in installed_models}
    installed_short = set()
    for n in installed_names:
        installed_short.add(n)
        if ":latest" in n:
            installed_short.add(n.replace(":latest", ""))

    # Donanım VRAM bilgisini al
    from app.llm.gpu_config import gpu_config
    total_vram = gpu_config.total_vram_gb
    gpu_count = len(gpu_config.gpus)
    gpu_names = [g.name for g in gpu_config.gpus] if gpu_config.gpus else []

    # VRAM'e göre filtrelenmiş model listesi
    hw_models = _get_hardware_filtered_models(total_vram)

    # Yüklü durumunu işaretle
    available_models = []
    for pm in hw_models:
        is_installed = pm["name"] in installed_short
        available_models.append({
            **pm,
            "installed": is_installed,
        })

    return {
        "installed": installed_models,
        "available": available_models,
        "active_model": active_model,
        "settings_model": getattr(settings, "LLM_MODEL", ""),
        "hardware": {
            "total_vram_gb": total_vram,
            "gpu_count": gpu_count,
            "gpu_names": gpu_names,
        },
    }


def _format_size(size_bytes: int) -> str:
    """Byte değerini GB/MB formatına çevir."""
    if size_bytes <= 0:
        return "?"
    gb = size_bytes / (1024 ** 3)
    if gb >= 1:
        return f"{gb:.1f} GB"
    mb = size_bytes / (1024 ** 2)
    return f"{mb:.0f} MB"


class ModelPullRequest(BaseModel):
    name: str


@router.post("/ollama/pull")
async def pull_ollama_model(
    req: ModelPullRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Ollama'dan model indir — SSE stream olarak ilerleme döndürür.
    Frontend EventSource/fetch ile bu endpoint'e bağlanır.
    """
    check_admin(current_user)

    import httpx
    from app.config import settings
    from fastapi.responses import StreamingResponse

    async def stream_pull():
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(connect=30, read=7200, write=30, pool=30)) as client:
                async with client.stream(
                    "POST",
                    f"{settings.OLLAMA_BASE_URL}/api/pull",
                    json={"name": req.name},
                ) as resp:
                    async for line in resp.aiter_lines():
                        if line.strip():
                            yield f"data: {line}\n\n"

            # Tamamlandı sinyali
            yield f"data: {json.dumps({'status': 'completed', 'model': req.name})}\n\n"

        except Exception as e:
            logger.error("ollama_pull_error", model=req.name, error=str(e))
            yield f"data: {json.dumps({'status': 'error', 'error': str(e)})}\n\n"

    await log_action(
        await get_db().__anext__() if False else None,  # placeholder
        user=current_user,
        action="admin_pull_model_start",
        resource=req.name,
        details=json.dumps({"model": req.name}),
    ) if False else None  # Audit log optional — hata vermemesi için

    return StreamingResponse(
        stream_pull(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


class ModelSwitchRequest(BaseModel):
    name: str


@router.post("/ollama/switch")
async def switch_ollama_model(
    req: ModelSwitchRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Aktif modeli değiştir:
    1. Yeni modeli Ollama'da yükle (warmup)
    2. settings.LLM_MODEL güncelle
    3. ollama_client.model güncelle
    4. Katman sayısını yeniden algıla
    5. Performans profilini yeniden uygula
    """
    check_admin(current_user)

    import httpx
    from app.config import settings
    from app.llm.client import ollama_client
    from app.llm.gpu_config import gpu_config

    global _ACTIVE_MODEL_NAME, _TOTAL_MODEL_LAYERS

    # 1. Model Ollama'da var mı kontrol et
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            tags_resp = await client.get(f"{settings.OLLAMA_BASE_URL}/api/tags")
            if tags_resp.status_code == 200:
                model_names = [m["name"] for m in tags_resp.json().get("models", [])]
                if req.name not in model_names:
                    raise HTTPException(
                        status_code=404,
                        detail=f"Model '{req.name}' Ollama'da bulunamadı. Önce indirin.",
                    )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Ollama bağlantı hatası: {e}")

    # 2. Modeli yükle (warmup — keep_alive ile bellekte tut)
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(connect=30, read=300, write=30, pool=30)) as client:
            load_resp = await client.post(
                f"{settings.OLLAMA_BASE_URL}/api/generate",
                json={"model": req.name, "prompt": "", "keep_alive": -1},
            )
            if load_resp.status_code != 200:
                logger.warning("model_warmup_non200", status=load_resp.status_code)
    except Exception as e:
        logger.warning("model_warmup_error", error=str(e))
        # Warmup hatası kritik değil, devam et

    # 3. Ayarları güncelle
    old_model = settings.LLM_MODEL
    settings.LLM_MODEL = req.name
    ollama_client.model = req.name

    # 4. Katman sayısını yeniden algıla
    layer_count, model_name = await _detect_model_layers()
    if layer_count > 0:
        _TOTAL_MODEL_LAYERS = layer_count
        _ACTIVE_MODEL_NAME = model_name
    else:
        _ACTIVE_MODEL_NAME = req.name

    # 5. Performans profilini yeniden uygula
    result = await db.execute(
        select(SystemSettings).where(SystemSettings.key == "performance_profile")
    )
    setting = result.scalar_one_or_none()

    applied_params = {}
    if setting and setting.value:
        try:
            profile = json.loads(setting.value)
            params = _calc_perf_params(
                profile.get("gpu_percent", 100),
                profile.get("cpu_percent", 100),
                profile.get("ram_percent", 100),
            )
            gpu_config.num_gpu = params["num_gpu"]
            gpu_config.num_thread = params["num_thread"]
            gpu_config.num_ctx = params["num_ctx"]
            gpu_config.num_batch = params["num_batch"]
            applied_params = params
        except Exception as e:
            logger.warning("profile_reapply_error", error=str(e))

    await log_action(
        db,
        user=current_user,
        action="admin_switch_model",
        resource=req.name,
        details=json.dumps({
            "old_model": old_model,
            "new_model": req.name,
            "layers": _TOTAL_MODEL_LAYERS,
        }),
    )
    await db.commit()

    return {
        "success": True,
        "old_model": old_model,
        "new_model": req.name,
        "total_layers": _TOTAL_MODEL_LAYERS,
        "active_model": _ACTIVE_MODEL_NAME,
        "applied_params": applied_params,
    }


class ModelDeleteRequest(BaseModel):
    name: str


@router.delete("/ollama/models")
async def delete_ollama_model(
    req: ModelDeleteRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Ollama'dan model sil."""
    check_admin(current_user)

    import httpx
    from app.config import settings

    # Aktif model silinmeye çalışılıyorsa uyar
    if req.name == getattr(settings, "LLM_MODEL", ""):
        raise HTTPException(
            status_code=400,
            detail="Aktif model silinemez. Önce başka bir modele geçiş yapın.",
        )

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            del_resp = await client.request(
                "DELETE",
                f"{settings.OLLAMA_BASE_URL}/api/delete",
                json={"name": req.name},
            )
            if del_resp.status_code != 200:
                raise HTTPException(
                    status_code=del_resp.status_code,
                    detail=f"Ollama silme hatası: {del_resp.text}",
                )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Ollama bağlantı hatası: {e}")

    await log_action(
        db,
        user=current_user,
        action="admin_delete_model",
        resource=req.name,
        details=json.dumps({"deleted_model": req.name}),
    )
    await db.commit()

    return {"success": True, "deleted": req.name}


# ── TPS (Tokens Per Second) Benchmark ────────────────────────────────

@router.get("/ollama/tps")
async def get_ollama_tps(
    current_user: User = Depends(get_current_user),
):
    """Ollama'dan gerçek TPS ölç — kısa bir prompt gönderip eval metrikleri al."""
    check_admin_or_manager(current_user)

    import httpx
    from app.config import settings

    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(connect=10, read=120, write=10, pool=10)
        ) as client:
            resp = await client.post(
                f"{settings.OLLAMA_BASE_URL}/api/generate",
                json={
                    "model": settings.LLM_MODEL,
                    "prompt": "Merhaba, 1+1 kaçtır?",
                    "stream": False,
                    "options": {"num_predict": 32},
                },
            )
            if resp.status_code != 200:
                raise HTTPException(status_code=502, detail="Ollama generate hatası")

            data = resp.json()
            eval_count = data.get("eval_count", 0)
            eval_duration = data.get("eval_duration", 0)  # nanoseconds
            prompt_eval_count = data.get("prompt_eval_count", 0)
            prompt_eval_duration = data.get("prompt_eval_duration", 0)

            tps = 0.0
            if eval_duration > 0 and eval_count > 0:
                tps = eval_count / (eval_duration / 1e9)

            prompt_tps = 0.0
            if prompt_eval_duration > 0 and prompt_eval_count > 0:
                prompt_tps = prompt_eval_count / (prompt_eval_duration / 1e9)

            return {
                "tps": round(tps, 1),
                "prompt_tps": round(prompt_tps, 1),
                "eval_count": eval_count,
                "eval_duration_ms": round(eval_duration / 1e6, 1) if eval_duration else 0,
                "model": settings.LLM_MODEL,
            }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Ollama bağlantı hatası: {e}")


# ══════════════════════════════════════════════════════════════════════
# META LEARNING ENGINE v1.0 — Üst-Seviye Öğrenme Motoru (v4.6.0)
# ══════════════════════════════════════════════════════════════════════

@router.get("/meta-learning/dashboard")
async def get_meta_learning_dashboard(
    current_user: User = Depends(get_current_user),
):
    """Meta Learning Engine dashboard — tüm öğrenme metrikleri."""
    check_admin_or_manager(current_user)
    if not META_LEARNING_AVAILABLE or not meta_learning_engine:
        return {"available": False, "error": "Meta Learning Engine yüklü değil"}
    try:
        return get_meta_dashboard()
    except Exception as e:
        return {"available": False, "error": str(e)}


@router.get("/meta-learning/quality-trend")
async def get_meta_quality_trend(
    window: int = 50,
    current_user: User = Depends(get_current_user),
):
    """Kalite eğilim analizi — iyileşme / kötüleşme tespiti."""
    check_admin_or_manager(current_user)
    if not META_LEARNING_AVAILABLE or not meta_learning_engine:
        return {"available": False}
    try:
        trend = meta_learning_engine.get_quality_trend(window)
        return {"available": True, **trend.to_dict()}
    except Exception as e:
        return {"available": False, "error": str(e)}


@router.get("/meta-learning/strategies")
async def get_meta_strategies(
    department: str = None,
    mode: str = None,
    min_queries: int = 5,
    current_user: User = Depends(get_current_user),
):
    """Strateji profilleri — hangi pipeline konfigürasyonu ne kadar başarılı."""
    check_admin_or_manager(current_user)
    if not META_LEARNING_AVAILABLE or not meta_learning_engine:
        return {"available": False}
    try:
        strategies = meta_learning_engine.get_strategy_rankings(department, mode, min_queries)
        return {"available": True, "strategies": strategies, "count": len(strategies)}
    except Exception as e:
        return {"available": False, "error": str(e)}


@router.get("/meta-learning/knowledge-gaps")
async def get_meta_knowledge_gaps(
    min_frequency: int = 3,
    department: str = None,
    current_user: User = Depends(get_current_user),
):
    """Bilgi boşlukları — RAG'da eksik alanlar."""
    check_admin_or_manager(current_user)
    if not META_LEARNING_AVAILABLE or not meta_learning_engine:
        return {"available": False}
    try:
        gaps = meta_learning_engine.get_knowledge_gaps(min_frequency, department)
        return {"available": True, "gaps": gaps, "count": len(gaps)}
    except Exception as e:
        return {"available": False, "error": str(e)}


@router.post("/meta-learning/knowledge-gaps/{gap_key}/resolve")
async def resolve_meta_knowledge_gap(
    gap_key: str,
    current_user: User = Depends(get_current_user),
):
    """Bir bilgi boşluğunu çözülmüş olarak işaretle."""
    check_admin(current_user)
    if not META_LEARNING_AVAILABLE or not meta_learning_engine:
        raise HTTPException(status_code=503, detail="Meta Learning Engine yüklü değil")
    result = meta_learning_engine.resolve_knowledge_gap(gap_key)
    if not result:
        raise HTTPException(status_code=404, detail="Bilgi boşluğu bulunamadı")
    return {"resolved": True, "gap_key": gap_key}


@router.get("/meta-learning/failure-patterns")
async def get_meta_failure_patterns(
    min_frequency: int = 3,
    department: str = None,
    current_user: User = Depends(get_current_user),
):
    """Tekrarlayan başarısızlık kalıpları."""
    check_admin_or_manager(current_user)
    if not META_LEARNING_AVAILABLE or not meta_learning_engine:
        return {"available": False}
    try:
        patterns = meta_learning_engine.get_failure_patterns(min_frequency, department)
        return {"available": True, "patterns": patterns, "count": len(patterns)}
    except Exception as e:
        return {"available": False, "error": str(e)}


@router.get("/meta-learning/domain-performance")
async def get_meta_domain_performance(
    current_user: User = Depends(get_current_user),
):
    """Departman × Mod performans haritası."""
    check_admin_or_manager(current_user)
    if not META_LEARNING_AVAILABLE or not meta_learning_engine:
        return {"available": False}
    try:
        perf_map = meta_learning_engine.get_domain_performance_map()
        weakest = meta_learning_engine.get_weakest_domains(5)
        strongest = meta_learning_engine.get_strongest_domains(5)
        return {
            "available": True,
            "performance_map": perf_map,
            "weakest_domains": weakest,
            "strongest_domains": strongest,
        }
    except Exception as e:
        return {"available": False, "error": str(e)}


@router.get("/meta-learning/criteria-analysis")
async def get_meta_criteria_analysis(
    current_user: User = Depends(get_current_user),
):
    """Reflection kriter analizi — hangi kriter sürekli düşük."""
    check_admin_or_manager(current_user)
    if not META_LEARNING_AVAILABLE or not meta_learning_engine:
        return {"available": False}
    try:
        analysis = meta_learning_engine.get_criteria_analysis()
        return {"available": True, "criteria": analysis}
    except Exception as e:
        return {"available": False, "error": str(e)}


@router.get("/meta-learning/learning-effectiveness")
async def get_meta_learning_effectiveness(
    current_user: User = Depends(get_current_user),
):
    """Otomatik öğrenme sistemi etkinlik analizi."""
    check_admin_or_manager(current_user)
    if not META_LEARNING_AVAILABLE or not meta_learning_engine:
        return {"available": False}
    try:
        effectiveness = meta_learning_engine.get_learning_effectiveness()
        return {"available": True, **effectiveness}
    except Exception as e:
        return {"available": False, "error": str(e)}


@router.get("/meta-learning/improvement-opportunities")
async def get_meta_improvement_opportunities(
    current_user: User = Depends(get_current_user),
):
    """Self-Improvement Loop için iyileştirme fırsatları."""
    check_admin_or_manager(current_user)
    if not META_LEARNING_AVAILABLE or not meta_learning_engine:
        return {"available": False}
    try:
        opportunities = get_improvement_opportunities()
        return {"available": True, "opportunities": opportunities, "count": len(opportunities)}
    except Exception as e:
        return {"available": False, "error": str(e)}


@router.post("/meta-learning/reset")
async def reset_meta_learning(
    current_user: User = Depends(get_current_user),
):
    """Meta Learning verisini sıfırla."""
    check_admin(current_user)
    if not META_LEARNING_AVAILABLE or not meta_learning_engine:
        raise HTTPException(status_code=503, detail="Meta Learning Engine yüklü değil")
    meta_learning_engine.reset()
    await log_action(None, current_user.id, "meta_learning_reset", "Tüm meta-öğrenme verisi sıfırlandı")
    return {"reset": True}


# ══════════════════════════════════════════════════════════════════════
# SELF-IMPROVEMENT LOOP v1.0 — Otomatik İyileştirme Döngüsü (v4.6.0)
# ══════════════════════════════════════════════════════════════════════

@router.get("/self-improvement/dashboard")
async def get_si_dashboard(
    current_user: User = Depends(get_current_user),
):
    """Self-Improvement Loop dashboard — aktif iyileştirmeler, istatistikler."""
    check_admin_or_manager(current_user)
    if not SELF_IMPROVEMENT_AVAILABLE or not self_improvement_loop:
        return {"available": False, "error": "Self-Improvement Loop yüklü değil"}
    try:
        return get_self_improvement_dashboard()
    except Exception as e:
        return {"available": False, "error": str(e)}


@router.post("/self-improvement/run-cycle")
async def run_si_cycle(
    current_user: User = Depends(get_current_user),
):
    """Manuel iyileştirme döngüsü çalıştır."""
    check_admin(current_user)
    if not SELF_IMPROVEMENT_AVAILABLE or not self_improvement_loop:
        raise HTTPException(status_code=503, detail="Self-Improvement Loop yüklü değil")
    if not META_LEARNING_AVAILABLE or not meta_learning_engine:
        raise HTTPException(status_code=503, detail="Meta Learning Engine gerekli")

    try:
        opportunities = get_improvement_opportunities()

        # Domain metriklerini topla
        domain_metrics = {}
        for dp in meta_learning_engine.get_domain_performance_map():
            key = f"{dp['department']}:{dp['mode']}"
            domain_metrics[key] = {
                "avg_confidence": dp.get("avg_confidence", 50),
                "success_rate": dp.get("success_rate", 50),
                "failure_rate": 100 - dp.get("success_rate", 50),
                "avg_response_time_ms": dp.get("avg_response_time_ms", 0),
                "avg_retry_count": 0,
            }

        result = run_improvement_cycle(opportunities, domain_metrics)
        await log_action(None, current_user.id, "self_improvement_cycle",
                         json.dumps({"actions_taken": result.get("actions_taken", 0)}))
        return result
    except Exception as e:
        return {"error": str(e)}


@router.get("/self-improvement/active")
async def get_si_active_improvements(
    current_user: User = Depends(get_current_user),
):
    """Aktif iyileştirmeler (gözlem sürecinde olan)."""
    check_admin_or_manager(current_user)
    if not SELF_IMPROVEMENT_AVAILABLE or not self_improvement_loop:
        return {"available": False}
    try:
        active = self_improvement_loop.tracker.get_active_improvements()
        return {"available": True, "active": active, "count": len(active)}
    except Exception as e:
        return {"available": False, "error": str(e)}


@router.get("/self-improvement/history")
async def get_si_history(
    last_n: int = 50,
    current_user: User = Depends(get_current_user),
):
    """İyileştirme geçmişi."""
    check_admin_or_manager(current_user)
    if not SELF_IMPROVEMENT_AVAILABLE or not self_improvement_loop:
        return {"available": False}
    try:
        history = self_improvement_loop.tracker.get_history(last_n)
        stats = self_improvement_loop.tracker.get_success_rate()
        return {"available": True, "history": history, "stats": stats}
    except Exception as e:
        return {"available": False, "error": str(e)}


@router.post("/self-improvement/rollback/{action_id}")
async def rollback_si_improvement(
    action_id: str,
    current_user: User = Depends(get_current_user),
):
    """Bir iyileştirmeyi geri al."""
    check_admin(current_user)
    if not SELF_IMPROVEMENT_AVAILABLE or not self_improvement_loop:
        raise HTTPException(status_code=503, detail="Self-Improvement Loop yüklü değil")

    result = self_improvement_loop.tracker.rollback(action_id, f"Admin rollback by {current_user.full_name}")
    if not result:
        raise HTTPException(status_code=404, detail="İyileştirme bulunamadı")
    await log_action(None, current_user.id, "self_improvement_rollback",
                     json.dumps({"action_id": action_id}))
    return {"rolled_back": True, **result}


class SIConfigRequest(BaseModel):
    auto_improve_enabled: bool


@router.post("/self-improvement/config")
async def update_si_config(
    body: SIConfigRequest,
    current_user: User = Depends(get_current_user),
):
    """Otomatik iyileştirme aç/kapat."""
    check_admin(current_user)
    if not SELF_IMPROVEMENT_AVAILABLE or not self_improvement_loop:
        raise HTTPException(status_code=503, detail="Self-Improvement Loop yüklü değil")
    result = self_improvement_loop.set_auto_improve(body.auto_improve_enabled)
    await log_action(None, current_user.id, "self_improvement_config",
                     json.dumps(result))
    return result


@router.get("/self-improvement/config")
async def get_si_config(
    current_user: User = Depends(get_current_user),
):
    """Self-Improvement konfigürasyonu."""
    check_admin_or_manager(current_user)
    if not SELF_IMPROVEMENT_AVAILABLE or not self_improvement_loop:
        return {"available": False}
    return {"available": True, **self_improvement_loop.get_config()}


@router.get("/self-improvement/thresholds")
async def get_si_thresholds(
    current_user: User = Depends(get_current_user),
):
    """Tüm domain bazlı threshold override'ları."""
    check_admin_or_manager(current_user)
    if not SELF_IMPROVEMENT_AVAILABLE or not self_improvement_loop:
        return {"available": False}
    try:
        overrides = self_improvement_loop.threshold_optimizer.get_all_overrides()
        return {"available": True, "overrides": overrides, "count": len(overrides)}
    except Exception as e:
        return {"available": False, "error": str(e)}


@router.get("/self-improvement/rag-overrides")
async def get_si_rag_overrides(
    current_user: User = Depends(get_current_user),
):
    """Tüm domain bazlı RAG override'ları."""
    check_admin_or_manager(current_user)
    if not SELF_IMPROVEMENT_AVAILABLE or not self_improvement_loop:
        return {"available": False}
    try:
        overrides = self_improvement_loop.rag_tuner.get_all_overrides()
        return {"available": True, "overrides": overrides, "count": len(overrides)}
    except Exception as e:
        return {"available": False, "error": str(e)}


@router.get("/self-improvement/prompt-suggestions")
async def get_si_prompt_suggestions(
    domain_key: str = None,
    current_user: User = Depends(get_current_user),
):
    """Onay bekleyen prompt iyileştirme önerileri."""
    check_admin_or_manager(current_user)
    if not SELF_IMPROVEMENT_AVAILABLE or not self_improvement_loop:
        return {"available": False}
    try:
        suggestions = self_improvement_loop.prompt_evolver.get_pending_suggestions(domain_key)
        return {"available": True, "suggestions": suggestions, "count": len(suggestions)}
    except Exception as e:
        return {"available": False, "error": str(e)}


@router.post("/self-improvement/evaluate")
async def evaluate_si_improvements(
    current_user: User = Depends(get_current_user),
):
    """Gözlem süresi dolan iyileştirmeleri değerlendir (before/after)."""
    check_admin(current_user)
    if not SELF_IMPROVEMENT_AVAILABLE or not self_improvement_loop:
        raise HTTPException(status_code=503, detail="Self-Improvement Loop yüklü değil")
    if not META_LEARNING_AVAILABLE or not meta_learning_engine:
        raise HTTPException(status_code=503, detail="Meta Learning Engine gerekli")

    try:
        # Güncel domain metriklerini topla
        domain_metrics = {}
        for dp in meta_learning_engine.get_domain_performance_map():
            key = f"{dp['department']}:{dp['mode']}"
            domain_metrics[key] = {
                "avg_confidence": dp.get("avg_confidence", 50),
                "success_rate": dp.get("success_rate", 50),
            }

        results = self_improvement_loop.evaluate_pending_improvements(domain_metrics)
        return {"evaluated": True, "results": results, "count": len(results)}
    except Exception as e:
        return {"error": str(e)}


@router.post("/self-improvement/reset")
async def reset_si_loop(
    current_user: User = Depends(get_current_user),
):
    """Self-Improvement Loop verisini sıfırla."""
    check_admin(current_user)
    if not SELF_IMPROVEMENT_AVAILABLE or not self_improvement_loop:
        raise HTTPException(status_code=503, detail="Self-Improvement Loop yüklü değil")
    self_improvement_loop.reset()
    await log_action(None, current_user.id, "self_improvement_reset",
                     "Tüm self-improvement verisi sıfırlandı")
    return {"reset": True}


# ══════════════════════════════════════════════════════════════════════
# MULTI-AGENT DEBATE v1.0 — Çok Perspektifli Tartışma (v4.7.0)
# ══════════════════════════════════════════════════════════════════════

@router.get("/debate/dashboard")
async def get_debate_dashboard_endpoint(
    current_user: User = Depends(get_current_user),
):
    """Multi-Agent Debate dashboard — tartışma metrikleri."""
    check_admin_or_manager(current_user)
    if not MULTI_AGENT_DEBATE_AVAILABLE or not debate_engine:
        return {"available": False, "error": "Multi-Agent Debate yüklü değil"}
    try:
        return get_debate_dashboard()
    except Exception as e:
        return {"available": False, "error": str(e)}


@router.get("/debate/statistics")
async def get_debate_statistics(
    current_user: User = Depends(get_current_user),
):
    """Tartışma istatistikleri — konsensüs oranları, perspektif dağılımı."""
    check_admin_or_manager(current_user)
    if not MULTI_AGENT_DEBATE_AVAILABLE or not debate_engine:
        raise HTTPException(status_code=503, detail="Multi-Agent Debate yüklü değil")
    try:
        dashboard = debate_engine.get_dashboard()
        return {
            "statistics": dashboard.get("statistics", {}),
            "consensus_distribution": dashboard.get("statistics", {}).get("consensus_distribution", {}),
        }
    except Exception as e:
        return {"error": str(e)}


@router.get("/debate/recent")
async def get_debate_recent(
    limit: int = 20,
    current_user: User = Depends(get_current_user),
):
    """Son tartışma sonuçları."""
    check_admin_or_manager(current_user)
    if not MULTI_AGENT_DEBATE_AVAILABLE or not debate_engine:
        raise HTTPException(status_code=503, detail="Multi-Agent Debate yüklü değil")
    try:
        dashboard = debate_engine.get_dashboard()
        recent = dashboard.get("recent_debates", [])
        return {"debates": recent[:limit], "total": len(recent)}
    except Exception as e:
        return {"error": str(e)}


@router.post("/debate/config")
async def update_debate_config(
    enabled: bool = True,
    current_user: User = Depends(get_current_user),
):
    """Multi-Agent Debate aç/kapat."""
    check_admin(current_user)
    if not MULTI_AGENT_DEBATE_AVAILABLE or not debate_engine:
        raise HTTPException(status_code=503, detail="Multi-Agent Debate yüklü değil")
    result = debate_engine.set_enabled(enabled)
    action = "debate_enabled" if enabled else "debate_disabled"
    await log_action(None, current_user.id, action, f"Multi-Agent Debate {'açıldı' if enabled else 'kapatıldı'}")
    return result


@router.post("/debate/reset")
async def reset_debate_engine(
    current_user: User = Depends(get_current_user),
):
    """Multi-Agent Debate verisini sıfırla."""
    check_admin(current_user)
    if not MULTI_AGENT_DEBATE_AVAILABLE or not debate_engine:
        raise HTTPException(status_code=503, detail="Multi-Agent Debate yüklü değil")
    debate_engine.reset()
    await log_action(None, current_user.id, "debate_reset", "Tüm tartışma verisi sıfırlandı")
    return {"reset": True}


# ══════════════════════════════════════════════════════════════════════
# CAUSAL INFERENCE ENGINE v1.0 — Nedensellik Analizi (v4.7.0)
# ══════════════════════════════════════════════════════════════════════

@router.get("/causal/dashboard")
async def get_causal_dashboard_endpoint(
    current_user: User = Depends(get_current_user),
):
    """Causal Inference Engine dashboard — nedensellik analiz metrikleri."""
    check_admin_or_manager(current_user)
    if not CAUSAL_INFERENCE_AVAILABLE or not causal_engine:
        return {"available": False, "error": "Causal Inference Engine yüklü değil"}
    try:
        return get_causal_dashboard()
    except Exception as e:
        return {"available": False, "error": str(e)}


@router.get("/causal/statistics")
async def get_causal_statistics(
    current_user: User = Depends(get_current_user),
):
    """Nedensellik istatistikleri — kategori dağılımı, kök neden trendleri."""
    check_admin_or_manager(current_user)
    if not CAUSAL_INFERENCE_AVAILABLE or not causal_engine:
        raise HTTPException(status_code=503, detail="Causal Inference Engine yüklü değil")
    try:
        return causal_engine.tracker.get_statistics()
    except Exception as e:
        return {"error": str(e)}


@router.get("/causal/recent")
async def get_causal_recent(
    limit: int = 20,
    current_user: User = Depends(get_current_user),
):
    """Son nedensellik analizleri."""
    check_admin_or_manager(current_user)
    if not CAUSAL_INFERENCE_AVAILABLE or not causal_engine:
        raise HTTPException(status_code=503, detail="Causal Inference Engine yüklü değil")
    try:
        recent = causal_engine.tracker.get_recent(limit)
        return {"analyses": recent, "total": len(recent)}
    except Exception as e:
        return {"error": str(e)}


@router.get("/causal/categories")
async def get_causal_categories(
    current_user: User = Depends(get_current_user),
):
    """Ishikawa kategori bazlı içgörüler — hangi kategoriden en sık kök neden çıkıyor."""
    check_admin_or_manager(current_user)
    if not CAUSAL_INFERENCE_AVAILABLE or not causal_engine:
        raise HTTPException(status_code=503, detail="Causal Inference Engine yüklü değil")
    try:
        return {"categories": causal_engine.tracker.get_category_insights()}
    except Exception as e:
        return {"error": str(e)}


@router.post("/causal/config")
async def update_causal_config(
    enabled: bool = True,
    current_user: User = Depends(get_current_user),
):
    """Causal Inference Engine aç/kapat."""
    check_admin(current_user)
    if not CAUSAL_INFERENCE_AVAILABLE or not causal_engine:
        raise HTTPException(status_code=503, detail="Causal Inference Engine yüklü değil")
    result = causal_engine.set_enabled(enabled)
    action = "causal_enabled" if enabled else "causal_disabled"
    await log_action(None, current_user.id, action, f"Causal Inference {'açıldı' if enabled else 'kapatıldı'}")
    return result


@router.post("/causal/reset")
async def reset_causal_engine(
    current_user: User = Depends(get_current_user),
):
    """Causal Inference Engine verisini sıfırla."""
    check_admin(current_user)
    if not CAUSAL_INFERENCE_AVAILABLE or not causal_engine:
        raise HTTPException(status_code=503, detail="Causal Inference Engine yüklü değil")
    causal_engine.reset()
    await log_action(None, current_user.id, "causal_reset", "Tüm nedensellik analiz verisi sıfırlandı")
    return {"reset": True}


# ══════════════════════════════════════════════════════════════════════
# STRATEGIC PLANNER v1.0 — Stratejik Planlama Motoru (v5.0.0)
# ══════════════════════════════════════════════════════════════════════

@router.get("/strategic/dashboard")
async def get_strategic_dashboard_endpoint(
    current_user: User = Depends(get_current_user),
):
    """Strategic Planner dashboard — stratejik planlama metrikleri."""
    check_admin_or_manager(current_user)
    if not STRATEGIC_PLANNER_AVAILABLE or not strategic_planner:
        return {"available": False, "error": "Strategic Planner yüklü değil"}
    try:
        return get_strategic_dashboard()
    except Exception as e:
        return {"available": False, "error": str(e)}


@router.get("/strategic/statistics")
async def get_strategic_statistics(
    current_user: User = Depends(get_current_user),
):
    """Stratejik planlama istatistikleri — SWOT, hedef, strateji dağılımları."""
    check_admin_or_manager(current_user)
    if not STRATEGIC_PLANNER_AVAILABLE or not strategic_planner:
        raise HTTPException(status_code=503, detail="Strategic Planner yüklü değil")
    try:
        return strategic_planner.tracker.get_statistics()
    except Exception as e:
        return {"error": str(e)}


@router.get("/strategic/recent")
async def get_strategic_recent(
    limit: int = 20,
    current_user: User = Depends(get_current_user),
):
    """Son stratejik analizler."""
    check_admin_or_manager(current_user)
    if not STRATEGIC_PLANNER_AVAILABLE or not strategic_planner:
        raise HTTPException(status_code=503, detail="Strategic Planner yüklü değil")
    try:
        recent = strategic_planner.tracker.get_recent(limit)
        return {"analyses": recent, "total": len(recent)}
    except Exception as e:
        return {"error": str(e)}


@router.post("/strategic/config")
async def update_strategic_config(
    enabled: bool = True,
    current_user: User = Depends(get_current_user),
):
    """Strategic Planner aç/kapat."""
    check_admin(current_user)
    if not STRATEGIC_PLANNER_AVAILABLE or not strategic_planner:
        raise HTTPException(status_code=503, detail="Strategic Planner yüklü değil")
    result = strategic_planner.set_enabled(enabled)
    action = "strategic_enabled" if enabled else "strategic_disabled"
    await log_action(None, current_user.id, action, f"Strategic Planner {'açıldı' if enabled else 'kapatıldı'}")
    return result


@router.post("/strategic/reset")
async def reset_strategic_engine(
    current_user: User = Depends(get_current_user),
):
    """Strategic Planner verisini sıfırla."""
    check_admin(current_user)
    if not STRATEGIC_PLANNER_AVAILABLE or not strategic_planner:
        raise HTTPException(status_code=503, detail="Strategic Planner yüklü değil")
    strategic_planner.reset()
    await log_action(None, current_user.id, "strategic_reset", "Tüm stratejik planlama verisi sıfırlandı")
    return {"reset": True}


# ══════════════════════════════════════════════════════════════════════
# EXECUTIVE INTELLIGENCE v1.0 — Yönetici Zekası (v5.0.0)
# ══════════════════════════════════════════════════════════════════════

@router.get("/executive/dashboard")
async def get_executive_dashboard_endpoint(
    current_user: User = Depends(get_current_user),
):
    """Executive Intelligence dashboard — yönetici zekası metrikleri."""
    check_admin_or_manager(current_user)
    if not EXECUTIVE_INTELLIGENCE_AVAILABLE or not executive_intelligence:
        return {"available": False, "error": "Executive Intelligence yüklü değil"}
    try:
        return get_executive_dashboard()
    except Exception as e:
        return {"available": False, "error": str(e)}


@router.get("/executive/statistics")
async def get_executive_statistics(
    current_user: User = Depends(get_current_user),
):
    """Yönetici zekası istatistikleri — brifing türleri, KPI korelasyonları."""
    check_admin_or_manager(current_user)
    if not EXECUTIVE_INTELLIGENCE_AVAILABLE or not executive_intelligence:
        raise HTTPException(status_code=503, detail="Executive Intelligence yüklü değil")
    try:
        return executive_intelligence.tracker.get_statistics()
    except Exception as e:
        return {"error": str(e)}


@router.get("/executive/recent")
async def get_executive_recent(
    limit: int = 20,
    current_user: User = Depends(get_current_user),
):
    """Son yönetici brifingleri."""
    check_admin_or_manager(current_user)
    if not EXECUTIVE_INTELLIGENCE_AVAILABLE or not executive_intelligence:
        raise HTTPException(status_code=503, detail="Executive Intelligence yüklü değil")
    try:
        recent = executive_intelligence.tracker.get_recent(limit)
        return {"analyses": recent, "total": len(recent)}
    except Exception as e:
        return {"error": str(e)}


@router.post("/executive/config")
async def update_executive_config(
    enabled: bool = True,
    current_user: User = Depends(get_current_user),
):
    """Executive Intelligence aç/kapat."""
    check_admin(current_user)
    if not EXECUTIVE_INTELLIGENCE_AVAILABLE or not executive_intelligence:
        raise HTTPException(status_code=503, detail="Executive Intelligence yüklü değil")
    result = executive_intelligence.set_enabled(enabled)
    action = "executive_enabled" if enabled else "executive_disabled"
    await log_action(None, current_user.id, action, f"Executive Intelligence {'açıldı' if enabled else 'kapatıldı'}")
    return result


@router.post("/executive/reset")
async def reset_executive_engine(
    current_user: User = Depends(get_current_user),
):
    """Executive Intelligence verisini sıfırla."""
    check_admin(current_user)
    if not EXECUTIVE_INTELLIGENCE_AVAILABLE or not executive_intelligence:
        raise HTTPException(status_code=503, detail="Executive Intelligence yüklü değil")
    executive_intelligence.reset()
    await log_action(None, current_user.id, "executive_reset", "Tüm yönetici zekası verisi sıfırlandı")
    return {"reset": True}


# ══════════════════════════════════════════════════════════════════════
# KNOWLEDGE GRAPH v1.0 — Bilgi Grafiği (v5.0.0)
# ══════════════════════════════════════════════════════════════════════

@router.get("/knowledge-graph/dashboard")
async def get_kg_dashboard_endpoint(
    current_user: User = Depends(get_current_user),
):
    """Knowledge Graph dashboard — bilgi grafiği metrikleri."""
    check_admin_or_manager(current_user)
    if not KNOWLEDGE_GRAPH_AVAILABLE or not knowledge_graph:
        return {"available": False, "error": "Knowledge Graph yüklü değil"}
    try:
        return get_kg_dashboard()
    except Exception as e:
        return {"available": False, "error": str(e)}


@router.get("/knowledge-graph/statistics")
async def get_kg_statistics(
    current_user: User = Depends(get_current_user),
):
    """Bilgi grafiği istatistikleri — varlık/ilişki sayıları, kümeleme."""
    check_admin_or_manager(current_user)
    if not KNOWLEDGE_GRAPH_AVAILABLE or not knowledge_graph:
        raise HTTPException(status_code=503, detail="Knowledge Graph yüklü değil")
    try:
        return knowledge_graph.tracker.get_statistics()
    except Exception as e:
        return {"error": str(e)}


@router.get("/knowledge-graph/entities")
async def get_kg_entities(
    limit: int = 50,
    current_user: User = Depends(get_current_user),
):
    """Bilgi grafiğindeki varlıklar."""
    check_admin_or_manager(current_user)
    if not KNOWLEDGE_GRAPH_AVAILABLE or not knowledge_graph:
        raise HTTPException(status_code=503, detail="Knowledge Graph yüklü değil")
    try:
        store = knowledge_graph.store
        entities = list(store.entities.values())[:limit]
        return {"entities": [{"id": e.id, "name": e.name, "type": e.entity_type, "confidence": e.confidence} for e in entities], "total": len(store.entities)}
    except Exception as e:
        return {"error": str(e)}


@router.get("/knowledge-graph/relations")
async def get_kg_relations(
    limit: int = 50,
    current_user: User = Depends(get_current_user),
):
    """Bilgi grafiğindeki ilişkiler."""
    check_admin_or_manager(current_user)
    if not KNOWLEDGE_GRAPH_AVAILABLE or not knowledge_graph:
        raise HTTPException(status_code=503, detail="Knowledge Graph yüklü değil")
    try:
        store = knowledge_graph.store
        relations = store.relations[:limit]
        return {"relations": [{"source": r.source_id, "target": r.target_id, "type": r.relation_type, "confidence": r.confidence} for r in relations], "total": len(store.relations)}
    except Exception as e:
        return {"error": str(e)}


@router.get("/knowledge-graph/recent")
async def get_kg_recent(
    limit: int = 20,
    current_user: User = Depends(get_current_user),
):
    """Son bilgi grafiği işlemleri."""
    check_admin_or_manager(current_user)
    if not KNOWLEDGE_GRAPH_AVAILABLE or not knowledge_graph:
        raise HTTPException(status_code=503, detail="Knowledge Graph yüklü değil")
    try:
        recent = knowledge_graph.tracker.get_recent(limit)
        return {"operations": recent, "total": len(recent)}
    except Exception as e:
        return {"error": str(e)}


@router.post("/knowledge-graph/config")
async def update_kg_config(
    enabled: bool = True,
    current_user: User = Depends(get_current_user),
):
    """Knowledge Graph aç/kapat."""
    check_admin(current_user)
    if not KNOWLEDGE_GRAPH_AVAILABLE or not knowledge_graph:
        raise HTTPException(status_code=503, detail="Knowledge Graph yüklü değil")
    result = knowledge_graph.set_enabled(enabled)
    action = "kg_enabled" if enabled else "kg_disabled"
    await log_action(None, current_user.id, action, f"Knowledge Graph {'açıldı' if enabled else 'kapatıldı'}")
    return result


@router.post("/knowledge-graph/reset")
async def reset_kg_engine(
    current_user: User = Depends(get_current_user),
):
    """Knowledge Graph verisini sıfırla."""
    check_admin(current_user)
    if not KNOWLEDGE_GRAPH_AVAILABLE or not knowledge_graph:
        raise HTTPException(status_code=503, detail="Knowledge Graph yüklü değil")
    knowledge_graph.reset()
    await log_action(None, current_user.id, "kg_reset", "Tüm bilgi grafiği verisi sıfırlandı")
    return {"reset": True}


# ─────────────────────────────────────────────────────────
# DECISION RISK GATEKEEPER (v5.1.0)
# ─────────────────────────────────────────────────────────

@router.get("/gate/dashboard")
async def gate_dashboard(current_user: User = Depends(get_current_user)):
    """Decision Risk Gatekeeper dashboard verisi."""
    check_admin(current_user)
    if not DECISION_GATEKEEPER_AVAILABLE:
        raise HTTPException(status_code=503, detail="Decision Gatekeeper yüklü değil")
    return get_gate_dashboard()


@router.get("/gate/statistics")
async def gate_statistics(current_user: User = Depends(get_current_user)):
    """Gate istatistikleri."""
    check_admin(current_user)
    if not DECISION_GATEKEEPER_AVAILABLE or not decision_gatekeeper:
        raise HTTPException(status_code=503, detail="Decision Gatekeeper yüklü değil")
    return decision_gatekeeper.tracker.get_statistics()


@router.get("/gate/recent")
async def gate_recent(
    limit: int = 20,
    current_user: User = Depends(get_current_user),
):
    """Son gate kararları."""
    check_admin(current_user)
    if not DECISION_GATEKEEPER_AVAILABLE or not decision_gatekeeper:
        raise HTTPException(status_code=503, detail="Decision Gatekeeper yüklü değil")
    return decision_gatekeeper.tracker.get_recent(limit)


@router.get("/gate/escalations")
async def gate_escalations(current_user: User = Depends(get_current_user)):
    """Bekleyen eskalasyonlar."""
    check_admin(current_user)
    if not DECISION_GATEKEEPER_AVAILABLE or not decision_gatekeeper:
        raise HTTPException(status_code=503, detail="Decision Gatekeeper yüklü değil")
    return {
        "pending": decision_gatekeeper.escalation_manager.get_pending(),
        "total_pending": len(decision_gatekeeper.escalation_manager.pending_escalations),
    }


@router.post("/gate/config")
async def gate_config(
    enabled: bool = True,
    block_threshold: float = None,
    warning_threshold: float = None,
    escalate_threshold: float = None,
    current_user: User = Depends(get_current_user),
):
    """Gate konfigürasyonunu güncelle."""
    check_admin(current_user)
    if not DECISION_GATEKEEPER_AVAILABLE or not decision_gatekeeper:
        raise HTTPException(status_code=503, detail="Decision Gatekeeper yüklü değil")
    result = decision_gatekeeper.set_enabled(enabled)
    if block_threshold is not None:
        decision_gatekeeper.config["block_threshold"] = block_threshold
    if warning_threshold is not None:
        decision_gatekeeper.config["warning_threshold"] = warning_threshold
    if escalate_threshold is not None:
        decision_gatekeeper.config["escalate_threshold"] = escalate_threshold
    action = "gate_enabled" if enabled else "gate_disabled"
    await log_action(None, current_user.id, action, f"Decision Gatekeeper {'açıldı' if enabled else 'kapatıldı'}")
    return result


@router.post("/gate/reset")
async def reset_gate(current_user: User = Depends(get_current_user)):
    """Gate istatistiklerini sıfırla."""
    check_admin(current_user)
    if not DECISION_GATEKEEPER_AVAILABLE or not decision_gatekeeper:
        raise HTTPException(status_code=503, detail="Decision Gatekeeper yüklü değil")
    decision_gatekeeper.reset()
    await log_action(None, current_user.id, "gate_reset", "Gate verileri sıfırlandı")
    return {"reset": True}


@router.post("/gate/resolve-escalation")
async def resolve_escalation(
    escalation_id: str = "",
    resolution: str = "approved",
    current_user: User = Depends(get_current_user),
):
    """Bekleyen eskalasyonu çöz."""
    check_admin(current_user)
    if not DECISION_GATEKEEPER_AVAILABLE or not decision_gatekeeper:
        raise HTTPException(status_code=503, detail="Decision Gatekeeper yüklü değil")
    result = decision_gatekeeper.escalation_manager.resolve(escalation_id, resolution, current_user.id)
    if result:
        await log_action(None, current_user.id, "gate_escalation_resolved", f"Eskalasyon çözüldü: {escalation_id} → {resolution}")
    return {"resolved": result, "escalation_id": escalation_id, "resolution": resolution}


# ─────────────────────────────────────────────────────────
# UNCERTAINTY QUANTIFICATION (v5.1.0)
# ─────────────────────────────────────────────────────────

@router.get("/uncertainty/dashboard")
async def uncertainty_dashboard(current_user: User = Depends(get_current_user)):
    """Uncertainty Quantification dashboard verisi."""
    check_admin(current_user)
    if not UNCERTAINTY_AVAILABLE:
        raise HTTPException(status_code=503, detail="Uncertainty Quantification yüklü değil")
    return get_uncertainty_dashboard()


@router.get("/uncertainty/statistics")
async def uncertainty_statistics(current_user: User = Depends(get_current_user)):
    """Belirsizlik istatistikleri."""
    check_admin(current_user)
    if not UNCERTAINTY_AVAILABLE or not uncertainty_quantifier:
        raise HTTPException(status_code=503, detail="Uncertainty Quantification yüklü değil")
    return uncertainty_quantifier.tracker.get_statistics()


@router.get("/uncertainty/recent")
async def uncertainty_recent(
    limit: int = 20,
    current_user: User = Depends(get_current_user),
):
    """Son belirsizlik ölçümleri."""
    check_admin(current_user)
    if not UNCERTAINTY_AVAILABLE or not uncertainty_quantifier:
        raise HTTPException(status_code=503, detail="Uncertainty Quantification yüklü değil")
    return uncertainty_quantifier.tracker.get_recent(limit)


@router.post("/uncertainty/config")
async def uncertainty_config(
    enabled: bool = True,
    current_user: User = Depends(get_current_user),
):
    """Uncertainty konfigürasyonunu güncelle."""
    check_admin(current_user)
    if not UNCERTAINTY_AVAILABLE or not uncertainty_quantifier:
        raise HTTPException(status_code=503, detail="Uncertainty Quantification yüklü değil")
    result = uncertainty_quantifier.set_enabled(enabled)
    action = "uncertainty_enabled" if enabled else "uncertainty_disabled"
    await log_action(None, current_user.id, action, f"Uncertainty Quantification {'açıldı' if enabled else 'kapatıldı'}")
    return result


@router.post("/uncertainty/reset")
async def reset_uncertainty(current_user: User = Depends(get_current_user)):
    """Uncertainty istatistiklerini sıfırla."""
    check_admin(current_user)
    if not UNCERTAINTY_AVAILABLE or not uncertainty_quantifier:
        raise HTTPException(status_code=503, detail="Uncertainty Quantification yüklü değil")
    uncertainty_quantifier.reset()
    await log_action(None, current_user.id, "uncertainty_reset", "Uncertainty verileri sıfırlandı")
    return {"reset": True}


# ══════════════════════════════════════════════════════════════
# v5.2.0 — Geliştirilmiş Modül Dashboard Endpoints
# ══════════════════════════════════════════════════════════════

@router.get("/graph-impact/dashboard")
async def graph_impact_dashboard(current_user: User = Depends(get_current_user)):
    """Graph Impact Mapping dashboard verileri."""
    check_admin_or_manager(current_user)
    if not GRAPH_IMPACT_AVAILABLE:
        return {"available": False, "message": "Graph Impact modülü yüklü değil"}
    return {"available": True, **get_graph_impact_dashboard()}


@router.get("/numerical-validation/dashboard")
async def numerical_validation_dashboard(current_user: User = Depends(get_current_user)):
    """Sayısal Doğrulama dashboard verileri."""
    check_admin_or_manager(current_user)
    if not NUMERICAL_VALIDATION_AVAILABLE:
        return {"available": False, "message": "Numerical Validation modülü yüklü değil"}
    return {"available": True, **get_numerical_validation_dashboard()}


@router.get("/experiment/dashboard")
async def experiment_dashboard(current_user: User = Depends(get_current_user)):
    """Experiment Layer (A/B Test) dashboard verileri."""
    check_admin_or_manager(current_user)
    if not EXPERIMENT_DASHBOARD_AVAILABLE:
        return {"available": False, "message": "Experiment Layer modülü yüklü değil"}
    return {"available": True, **get_experiment_dashboard()}


@router.get("/scenario/dashboard")
async def scenario_dashboard(current_user: User = Depends(get_current_user)):
    """Senaryo Motoru dashboard verileri."""
    check_admin_or_manager(current_user)
    if not SCENARIO_DASHBOARD_AVAILABLE:
        return {"available": False, "message": "Scenario Engine modülü yüklü değil"}
    return {"available": True, **get_scenario_dashboard()}


# ══════════════════════════════════════════════════════════════
# v5.3.0 — Karar Destek Modülleri Dashboard Endpoints
# ══════════════════════════════════════════════════════════════

@router.get("/decision-quality/dashboard")
async def decision_quality_dashboard(current_user: User = Depends(get_current_user)):
    """Decision Quality Score dashboard verileri."""
    check_admin_or_manager(current_user)
    if not DECISION_QUALITY_AVAILABLE:
        return {"available": False, "message": "Decision Quality modülü yüklü değil"}
    return {"available": True, **get_decision_quality_dashboard()}


@router.get("/kpi-impact/dashboard")
async def kpi_impact_dashboard(current_user: User = Depends(get_current_user)):
    """KPI Impact Mapping dashboard verileri."""
    check_admin_or_manager(current_user)
    if not KPI_IMPACT_AVAILABLE:
        return {"available": False, "message": "KPI Impact modülü yüklü değil"}
    return {"available": True, **get_kpi_impact_dashboard()}


@router.get("/decision-memory/dashboard")
async def decision_memory_dashboard(current_user: User = Depends(get_current_user)):
    """Decision Memory dashboard verileri."""
    check_admin_or_manager(current_user)
    if not DECISION_MEMORY_AVAILABLE:
        return {"available": False, "message": "Decision Memory modülü yüklü değil"}
    return {"available": True, **get_decision_memory_dashboard()}


@router.get("/executive-digest/dashboard")
async def executive_digest_dashboard(current_user: User = Depends(get_current_user)):
    """Executive Digest dashboard verileri."""
    check_admin_or_manager(current_user)
    if not EXECUTIVE_DIGEST_AVAILABLE:
        return {"available": False, "message": "Executive Digest modülü yüklü değil"}
    return {"available": True, **get_executive_digest_dashboard()}


@router.get("/ood-detector/dashboard")
async def ood_detector_dashboard(current_user: User = Depends(get_current_user)):
    """OOD Detector dashboard verileri."""
    check_admin_or_manager(current_user)
    if not OOD_DETECTOR_AVAILABLE:
        return {"available": False, "message": "OOD Detector modülü yüklü değil"}
    return {"available": True, **get_ood_dashboard()}


# ── v5.4.0: Module Synapse Network Dashboard ──────────────────

@router.get("/synapse/dashboard")
async def synapse_network_dashboard(current_user: User = Depends(get_current_user)):
    """Module Synapse Network dashboard — sinaps ağı istatistikleri, bağlantılar ve kaskad bilgileri."""
    check_admin_or_manager(current_user)
    if not SYNAPSE_AVAILABLE:
        return {"available": False, "message": "Module Synapse Network modülü yüklü değil"}
    return {"available": True, **get_synapse_dashboard()}


# ── v5.5.0: Enterprise Platform Dashboard Endpoints ──────────────

@router.get("/event-bus/dashboard")
async def event_bus_dashboard(current_user: User = Depends(get_current_user)):
    """Event Bus dashboard — olay sayıları, subscriber'lar, dead letter queue."""
    check_admin_or_manager(current_user)
    if not EVENT_BUS_AVAILABLE or not event_bus:
        return {"available": False, "message": "Event Bus modülü yüklü değil"}
    try:
        return {"available": True, **event_bus.get_dashboard()}
    except Exception as e:
        return {"available": True, "error": str(e)}


@router.get("/orchestrator/dashboard")
async def orchestrator_dashboard(current_user: User = Depends(get_current_user)):
    """Workflow Orchestrator dashboard — iş akışları, adımlar, durum özeti."""
    check_admin_or_manager(current_user)
    if not ORCHESTRATOR_AVAILABLE or not workflow_engine:
        return {"available": False, "message": "Workflow Orchestrator modülü yüklü değil"}
    try:
        return {"available": True, **workflow_engine.get_dashboard()}
    except Exception as e:
        return {"available": True, "error": str(e)}


@router.get("/policy-engine/dashboard")
async def policy_engine_dashboard(current_user: User = Depends(get_current_user)):
    """Policy Engine dashboard — kurallar, ihlaller, denetim istatistikleri."""
    check_admin_or_manager(current_user)
    if not POLICY_ENGINE_AVAILABLE or not enterprise_policy_engine:
        return {"available": False, "message": "Policy Engine modülü yüklü değil"}
    try:
        return {"available": True, **enterprise_policy_engine.get_dashboard()}
    except Exception as e:
        return {"available": True, "error": str(e)}


@router.get("/observability/dashboard")
async def observability_dashboard(current_user: User = Depends(get_current_user)):
    """Observability 2.0 dashboard — drift algılama, latency profil, kalite trend."""
    check_admin_or_manager(current_user)
    if not OBSERVABILITY_AVAILABLE or not observability:
        return {"available": False, "message": "Observability modülü yüklü değil"}
    try:
        return {"available": True, **observability.get_dashboard()}
    except Exception as e:
        return {"available": True, "error": str(e)}


@router.get("/security/dashboard")
async def security_dashboard(current_user: User = Depends(get_current_user)):
    """Security Layer dashboard — tehdit skoru, engellenen istekler, injection algılama."""
    check_admin(current_user)
    if not SECURITY_AVAILABLE or not security_layer:
        return {"available": False, "message": "Security Layer modülü yüklü değil"}
    try:
        return {"available": True, **security_layer.get_dashboard()}
    except Exception as e:
        return {"available": True, "error": str(e)}