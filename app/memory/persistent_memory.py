"""Kalıcı Konuşma Hafızası — PostgreSQL tabanlı

Kullanıcı "unut" diyene kadar TÜM konuşmaları ve kullanıcı bilgilerini saklar.
Her oturum açıldığında geçmiş yüklenir, LLM her zaman bağlamı bilir.
"""

import re
import structlog
from datetime import datetime
from typing import Optional
from sqlalchemy import select, delete, desc, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ConversationMemory, UserPreference

logger = structlog.get_logger()

# ── Kullanıcı bilgi çıkarma kalıpları ──
PREFERENCE_PATTERNS = [
    # İsim bildirme
    (r"(?:benim\s+)?ad[ıi]m\s+([A-ZÇĞİÖŞÜa-zçğıöşü]+)", "user_name", "İsmini söyledi"),
    (r"ben\s+([A-ZÇĞİÖŞÜ][a-zçğıöşü]+)\b", "user_name", "Kendini tanıttı"),
    (r"ismim\s+([A-ZÇĞİÖŞÜa-zçğıöşü]+)", "user_name", "İsmini söyledi"),
    # Departman bildirme
    (r"(?:ben\s+)?([A-ZÇĞİÖŞÜa-zçğıöşü]+)\s+departmanında(?:yım|çalışıyorum)", "user_department", "Departman söyledi"),
    (r"(?:ben\s+)?([A-ZÇĞİÖŞÜa-zçğıöşü]+)\s+bölümünde(?:yim|çalışıyorum)", "user_department", "Departman söyledi"),
    # Rol bildirme
    (r"(?:ben\s+)?([A-ZÇĞİÖŞÜa-zçğıöşü\s]+?)\s+olarak\s+çalışıyorum", "user_role", "Rolünü söyledi"),
    (r"görevim\s+([A-ZÇĞİÖŞÜa-zçğıöşü\s]+)", "user_role", "Görevini söyledi"),
]

# "Unut" komut kalıpları
FORGET_PATTERNS = [
    r"\bunut\b",
    r"\bhafıza(?:yı)?\s*(?:sil|temizle)\b",
    r"\bgeçmişi?\s*(?:sil|temizle|unut)\b",
    r"\bher\s*şeyi?\s*unut\b",
    r"\bbeni\s*unut\b",
    r"\bkonuşmaları?\s*(?:sil|temizle|unut)\b",
    r"\bunuttum\s*de\b",
]


def is_forget_command(text: str) -> bool:
    """Kullanıcı 'unut' tarzı bir komut mu verdi?"""
    text_lower = text.lower().strip()
    return any(re.search(p, text_lower) for p in FORGET_PATTERNS)


def extract_preferences(text: str) -> list[dict]:
    """Kullanıcı metninden kişisel bilgileri çıkar"""
    found = []
    for pattern, key, source in PREFERENCE_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            value = match.group(1).strip()
            if len(value) >= 2:  # Çok kısa eşleşmeleri atla
                found.append({"key": key, "value": value, "source": source})
    return found


# ═══════════════════════════════════════════════
#  Konuşma Hafızası — CRUD
# ═══════════════════════════════════════════════

async def save_conversation(
    db: AsyncSession,
    user_id: int,
    question: str,
    answer: str,
    department: str = None,
    intent: str = None,
):
    """Konuşmayı kalıcı hafızaya kaydet"""
    try:
        mem = ConversationMemory(
            user_id=user_id,
            question=question,
            answer=answer,
            department=department,
            intent=intent,
        )
        db.add(mem)
        # auto-commit by get_db dependency, ama explicit flush yapalım
        await db.flush()
        logger.debug("conversation_saved", user_id=user_id, q=question[:50])
    except Exception as e:
        logger.error("conversation_save_failed", error=str(e))


async def get_conversation_history(
    db: AsyncSession,
    user_id: int,
    limit: int = 20,
) -> list[dict]:
    """
    Kullanıcının son N konuşmasını getir (en eski → en yeni).
    Engine'in beklediği format: [{"q": "...", "a": "..."}, ...]
    """
    try:
        stmt = (
            select(ConversationMemory)
            .where(ConversationMemory.user_id == user_id)
            .order_by(desc(ConversationMemory.created_at))
            .limit(limit)
        )
        result = await db.execute(stmt)
        rows = result.scalars().all()
        
        # Ters çevir: en eski ilk
        history = [{"q": r.question, "a": r.answer} for r in reversed(rows)]
        return history
    except Exception as e:
        logger.error("conversation_history_failed", error=str(e))
        return []


async def get_conversation_count(db: AsyncSession, user_id: int) -> int:
    """Kullanıcının toplam konuşma sayısı"""
    try:
        from sqlalchemy import func
        stmt = select(func.count()).where(ConversationMemory.user_id == user_id)
        result = await db.execute(stmt)
        return result.scalar() or 0
    except Exception:
        return 0


async def clear_conversation_history(db: AsyncSession, user_id: int) -> int:
    """Kullanıcının TÜM konuşma geçmişini sil. 'Unut' komutu için."""
    try:
        stmt = delete(ConversationMemory).where(ConversationMemory.user_id == user_id)
        result = await db.execute(stmt)
        await db.flush()
        count = result.rowcount
        logger.info("conversation_history_cleared", user_id=user_id, deleted=count)
        return count
    except Exception as e:
        logger.error("conversation_clear_failed", error=str(e))
        return 0


# ═══════════════════════════════════════════════
#  Kullanıcı Tercihleri — CRUD
# ═══════════════════════════════════════════════

async def save_preference(
    db: AsyncSession,
    user_id: int,
    key: str,
    value: str,
    source: str = None,
):
    """Kullanıcı bilgisi kaydet/güncelle (upsert)"""
    try:
        # Mevcut tercih var mı?
        stmt = select(UserPreference).where(
            and_(UserPreference.user_id == user_id, UserPreference.key == key)
        )
        result = await db.execute(stmt)
        existing = result.scalar_one_or_none()
        
        if existing:
            existing.value = value
            existing.source = source
            existing.updated_at = datetime.utcnow()
        else:
            pref = UserPreference(
                user_id=user_id,
                key=key,
                value=value,
                source=source,
            )
            db.add(pref)
        
        await db.flush()
        logger.info("preference_saved", user_id=user_id, key=key, value=value)
    except Exception as e:
        logger.error("preference_save_failed", error=str(e))


async def get_preferences(db: AsyncSession, user_id: int) -> dict:
    """Kullanıcının tüm tercihlerini getir {key: value}"""
    try:
        stmt = select(UserPreference).where(UserPreference.user_id == user_id)
        result = await db.execute(stmt)
        rows = result.scalars().all()
        return {r.key: r.value for r in rows}
    except Exception as e:
        logger.error("preferences_get_failed", error=str(e))
        return {}


async def clear_preferences(db: AsyncSession, user_id: int) -> int:
    """Kullanıcının TÜM tercihlerini sil. 'Unut' komutu için."""
    try:
        stmt = delete(UserPreference).where(UserPreference.user_id == user_id)
        result = await db.execute(stmt)
        await db.flush()
        count = result.rowcount
        logger.info("preferences_cleared", user_id=user_id, deleted=count)
        return count
    except Exception as e:
        logger.error("preferences_clear_failed", error=str(e))
        return 0


# ═══════════════════════════════════════════════
#  Unut Komutu
# ═══════════════════════════════════════════════

async def forget_everything(db: AsyncSession, user_id: int) -> dict:
    """Kullanıcının tüm hafızasını sil — 'unut' komutu"""
    conv_count = await clear_conversation_history(db, user_id)
    pref_count = await clear_preferences(db, user_id)
    logger.info("memory_forgotten", user_id=user_id, 
                conversations=conv_count, preferences=pref_count)
    return {
        "conversations_deleted": conv_count,
        "preferences_deleted": pref_count,
    }


# ═══════════════════════════════════════════════
#  Hafıza Özeti — LLM'e gönderilecek kompakt bilgi
# ═══════════════════════════════════════════════

async def build_memory_context(db: AsyncSession, user_id: int) -> str:
    """
    LLM system prompt'una eklenecek hafıza özeti oluştur.
    Kullanıcı bilgileri + son konuşmaların kısa özeti.
    """
    parts = []
    
    # 1. Kullanıcı tercihleri
    prefs = await get_preferences(db, user_id)
    if prefs:
        pref_lines = []
        # Bilinen anahtar türlerini oku
        name_keys = {"user_name": "Adı", "user_department": "Departmanı", "user_role": "Görevi"}
        for k, label in name_keys.items():
            if k in prefs:
                pref_lines.append(f"{label}: {prefs[k]}")
        # Diğer tercihler
        for k, v in prefs.items():
            if k not in name_keys:
                pref_lines.append(f"{k}: {v}")
        if pref_lines:
            parts.append("Kullanıcı bilgileri: " + ", ".join(pref_lines))
    
    # 2. Son konuşmalar — kompakt özet
    history = await get_conversation_history(db, user_id, limit=30)
    if history:
        # Son birkaç konuşmayı özetle
        recent = history[-8:]  # Son 8 konuşma
        conv_summary = []
        for h in recent:
            q = h["q"][:80]
            a = h["a"][:100]
            conv_summary.append(f"K: {q}\nY: {a}")
        if conv_summary:
            parts.append("Son konuşmalar:\n" + "\n---\n".join(conv_summary))
    
    return "\n\n".join(parts) if parts else ""


async def extract_and_save_preferences(
    db: AsyncSession, 
    user_id: int, 
    question: str
):
    """Kullanıcının mesajından bilgi çıkar ve kaydet"""
    prefs = extract_preferences(question)
    for p in prefs:
        await save_preference(db, user_id, p["key"], p["value"], p["source"])
