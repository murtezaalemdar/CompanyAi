"""Memory Management Routes"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Dict, Any, Optional
from pydantic import BaseModel

from app.memory import vector_memory
from app.api.routes.auth import get_current_user
from app.db.database import get_db
from app.db.models import User
from app.auth.rbac import Role
from app.memory.persistent_memory import (
    get_conversation_history, get_conversation_count,
    get_preferences, forget_everything, save_preference,
)

router = APIRouter()


class MemoryStats(BaseModel):
    storage_type: str
    total_entries: int
    by_department: Dict[str, int]
    persist_directory: Optional[str] = None
    embedding_model: Optional[str] = None


@router.get("/stats", response_model=MemoryStats)
async def get_memory_stats(
    current_user: User = Depends(get_current_user),
):
    """
    Get memory statistics. Requires authentication.
    """
    stats = vector_memory.get_stats()
    return stats


@router.delete("/clear")
async def clear_memory(
    current_user: User = Depends(get_current_user),
):
    """
    Clear all memory (Admin only).
    """
    if current_user.role != Role.ADMIN.value:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    count = vector_memory.clear()
    return {"message": "Memory cleared", "cleared_entries": count}


@router.get("/search")
async def search_memory(
    q: str = Query(..., min_length=3),
    limit: int = 10,
    current_user: User = Depends(get_current_user),
):
    """
    Search memory content.
    """
    if current_user.role not in [Role.ADMIN.value, Role.MANAGER.value]:
        raise HTTPException(status_code=403, detail="Privileged access required")
    
    results = vector_memory.search_memory(q, limit)
    return results


# ═══════════════════════════════════════════════
#  Kalıcı Hafıza API'leri (PostgreSQL)
# ═══════════════════════════════════════════════

@router.get("/persistent/status")
async def get_persistent_memory_status(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Kullanıcının kalıcı hafıza durumunu getir"""
    conv_count = await get_conversation_count(db, current_user.id)
    prefs = await get_preferences(db, current_user.id)
    return {
        "user_id": current_user.id,
        "conversation_count": conv_count,
        "preferences": prefs,
        "memory_active": True,
    }


@router.get("/persistent/history")
async def get_persistent_history(
    limit: int = 20,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Kullanıcının kalıcı konuşma geçmişini getir"""
    history = await get_conversation_history(db, current_user.id, limit=limit)
    return {"history": history, "count": len(history)}


@router.delete("/persistent/forget")
async def forget_all(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Kullanıcının tüm kalıcı hafızasını sil ('unut' komutu)"""
    stats = await forget_everything(db, current_user.id)
    await db.commit()
    return {
        "message": "Tüm hafıza silindi",
        **stats,
    }


@router.delete("/persistent/admin/clear-all")
async def admin_clear_all_memory(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Tüm kullanıcıların hafızasını sil (sadece admin)"""
    if current_user.role != Role.ADMIN.value:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    from sqlalchemy import delete
    from app.db.models import ConversationMemory, UserPreference
    
    r1 = await db.execute(delete(ConversationMemory))
    r2 = await db.execute(delete(UserPreference))
    await db.commit()
    
    return {
        "message": "Tüm kullanıcıların hafızaları silindi",
        "conversations_deleted": r1.rowcount,
        "preferences_deleted": r2.rowcount,
    }
