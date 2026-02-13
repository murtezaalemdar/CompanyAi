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

@router.get("/stats/system-resources")
async def get_system_resources(
    current_user: User = Depends(get_current_user),
):
    """CPU ve Bellek kullanım yüzdelerini döner."""
    check_admin_or_manager(current_user)

    try:
        import psutil
        cpu_percent = psutil.cpu_percent(interval=0.5)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage("/")
        return {
            "cpu_percent": round(cpu_percent, 1),
            "memory_percent": round(mem.percent, 1),
            "memory_used_gb": round(mem.used / (1024 ** 3), 1),
            "memory_total_gb": round(mem.total / (1024 ** 3), 1),
            "disk_percent": round(disk.percent, 1),
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
