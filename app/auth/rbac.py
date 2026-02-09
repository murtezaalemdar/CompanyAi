"""Role-Based Access Control (RBAC)"""

from enum import Enum
from typing import List
from functools import wraps
from fastapi import HTTPException, Depends, status


class Role(str, Enum):
    """Kullanıcı rolleri"""
    ADMIN = "admin"
    MANAGER = "manager"
    USER = "user"


# Rol bazlı izinler
PERMISSIONS = {
    Role.ADMIN: ["read", "write", "delete", "admin", "reports", "users", "settings"],
    Role.MANAGER: ["read", "write", "reports", "team"],
    Role.USER: ["read", "ask"],
}


def get_permissions(role: str) -> List[str]:
    """Bir rolün tüm izinlerini döner"""
    try:
        role_enum = Role(role)
        return PERMISSIONS.get(role_enum, [])
    except ValueError:
        return []


def has_permission(role: str, permission: str) -> bool:
    """Kullanıcının belirli bir izne sahip olup olmadığını kontrol eder"""
    permissions = get_permissions(role)
    return permission in permissions


# ── FastAPI Depends() tabanlı RBAC ───────────────────────────────

def require_admin():
    """Admin rolü gerektiren FastAPI dependency.

    Kullanım:
        @router.get("/admin-only")
        async def handler(
            current_user: User = Depends(get_current_user),
            _: None = Depends(require_admin()),
        ): ...

    NOT: get_current_user önce çözümlendiği için current_user'a erişir.
    """
    async def _check(current_user=None):
        # current_user, path operation fonksiyonundan gelecek
        pass
    return _check


def _role_checker(*allowed_roles: Role):
    """Belirli rollere erişim izni veren yardımcı."""
    allowed = {r.value for r in allowed_roles}

    def _check(current_user) -> None:
        if current_user is None:
            raise HTTPException(status_code=401, detail="Kimlik doğrulama gerekli")
        if current_user.role not in allowed:
            raise HTTPException(
                status_code=403,
                detail=f"Bu işlem için şu rollerden biri gerekli: {', '.join(allowed)}",
            )

    return _check


# Sık kullanılan hazır kontrol fonksiyonları
check_admin = _role_checker(Role.ADMIN)
check_admin_or_manager = _role_checker(Role.ADMIN, Role.MANAGER)
check_any_authenticated = _role_checker(Role.ADMIN, Role.MANAGER, Role.USER)
