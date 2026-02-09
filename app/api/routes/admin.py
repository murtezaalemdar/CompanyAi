"""Admin API Routes"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, extract
from pydantic import BaseModel, EmailStr
from typing import List, Optional
from datetime import datetime, timedelta
import json

from app.db.database import get_db
from app.db.models import User, Query, SystemSettings
from app.api.routes.auth import get_current_user
from app.auth.rbac import Role, check_admin, check_admin_or_manager
from app.auth.jwt_handler import hash_password
from app.core.audit import log_action

router = APIRouter()


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
