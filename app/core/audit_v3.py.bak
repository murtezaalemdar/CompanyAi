"""Audit Logging Utility — Denetim Kaydı Servisi

Tüm önemli kullanıcı aksiyonlarını AuditLog tablosuna yazar.
"""

from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import AuditLog, User
import structlog

logger = structlog.get_logger()


async def log_action(
    db: AsyncSession,
    *,
    user: Optional[User] = None,
    user_id: Optional[int] = None,
    action: str,
    resource: Optional[str] = None,
    details: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> None:
    """
    Denetim kaydı oluşturur.

    Args:
        db: Async session
        user: User nesnesi (opsiyonel, user_id ile de çağrılabilir)
        user_id: Kullanıcı ID
        action: Aksiyon tipi (login, logout, query, admin_action, ...)
        resource: Etkilenen kaynak
        details: JSON formatında detaylar
        ip_address: İstek IP adresi
        user_agent: Tarayıcı bilgisi
    """
    uid = user_id or (user.id if user else None)

    entry = AuditLog(
        user_id=uid,
        action=action,
        resource=resource,
        details=details,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    db.add(entry)

    try:
        await db.flush()  # commit dışarıda yapılır
    except Exception as e:
        logger.error("audit_log_write_failed", action=action, error=str(e))
