"""Memory Management Routes"""

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Dict, Any, Optional
from pydantic import BaseModel

from app.memory import vector_memory
from app.api.routes.auth import get_current_user
from app.db.models import User
from app.auth.rbac import Role

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
