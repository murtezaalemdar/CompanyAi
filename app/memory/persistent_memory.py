"""Kalıcı Konuşma Hafızası — PostgreSQL tabanlı

Kullanıcı "unut" diyene kadar TÜM konuşmaları ve kullanıcı bilgilerini saklar.
Her oturum açıldığında geçmiş yüklenir, LLM her zaman bağlamı bilir.
Şirket kültürünü TÜM konuşmalardan öğrenir (rapor tarzı, iletişim dili, araç tercihleri vb.)
"""

import re
import structlog
from datetime import datetime
from typing import Optional
from sqlalchemy import select, delete, desc, and_, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ConversationMemory, UserPreference, ChatSession, CompanyCulture

logger = structlog.get_logger()

# ── Kullanıcı bilgi çıkarma kalıpları ──

# Soru cümlelerinde geçen kelimeler — isim OLARAK kaydedilmemeli
_QUESTION_WORDS = {
    "ne", "kim", "nasıl", "nere", "nerede", "neden", "niçin", "hangi",
    "kaç", "niye", "mi", "mı", "mu", "mü", "hayır", "evet", "yok",
    "var", "bu", "şu", "o", "sen", "ben", "biz", "siz", "onlar",
    "benim", "senin", "kendi", "da", "de", "ki", "ama", "fakat",
    "beni", "seni", "tamam", "peki", "acaba", "galiba",
}

PREFERENCE_PATTERNS = [
    # İsim bildirme — soru kalıplarını dışla
    (r"(?:benim\s+)?ad[\u0131i]m\s+([A-ZÇĞİÖŞÜ][a-zçğıöşü]+(?:\s+[A-ZÇĞİÖŞÜ][a-zçğıöşü]+)?)", "user_name", "İsmini söyledi"),
    (r"bana\s+([A-ZÇĞİÖŞÜ][a-zçğıöşü]+)\s+(?:de|diye|diyebilirsin|derler)", "user_name", "İsmini söyledi"),
    (r"ismim\s+([A-ZÇĞİÖŞÜ][a-zçğıöşü]+(?:\s+[A-ZÇĞİÖŞÜ][a-zçğıöşü]+)?)", "user_name", "İsmini söyledi"),
    (r"ben\s+([A-ZÇĞİÖŞÜ][a-zçğıöşü]{2,}(?:\s+[A-ZÇĞİÖŞÜ][a-zçğıöşü]{2,})?)\b(?!\s*(?:mi|mı|mu|mü|de|da|\?))", "user_name", "Kendini tanıttı"),
    # Departman bildirme
    (r"(?:ben\s+)?([A-ZÇĞİÖŞÜa-zçğıöşü]+)\s+departmanında(?:yım|çalışıyorum)", "user_department", "Departman söyledi"),
    (r"(?:ben\s+)?([A-ZÇĞİÖŞÜa-zçğıöşü]+)\s+bölümünde(?:yim|çalışıyorum)", "user_department", "Departman söyledi"),
    # Rol bildirme
    (r"(?:ben\s+)?([A-ZÇĞİÖŞÜa-zçğıöşü\s]+?)\s+olarak\s+çalışıyorum", "user_role", "Rolünü söyledi"),
    (r"görevim\s+([A-ZÇĞİÖŞÜa-zçğıöşü\s]+)", "user_role", "Görevini söyledi"),
]

# ── Şirket kültürü çıkarma kalıpları ──
CULTURE_PATTERNS = [
    # Rapor format tercihi
    (r"(?:raporu?|dosya[yı]?|çıktı[yı]?)\s+(?:excel|xlsx)\s+(?:olarak|formatında|şeklinde)", "report_style", "excel_format", "Excel formatında rapor tercih ediliyor"),
    (r"(?:excel|xlsx)\s+(?:olarak|formatında|şeklinde)\s+(?:hazırla|gönder|yap|oluştur|istiyorum)", "report_style", "excel_format", "Excel formatında rapor tercih ediliyor"),
    (r"(?:raporu?|dosya[yı]?|çıktı[yı]?)\s+(?:pdf)\s+(?:olarak|formatında)", "report_style", "pdf_format", "PDF formatında rapor tercih ediliyor"),
    (r"(?:tablo|çizelge)\s+(?:halinde|formatında|olarak|şeklinde)", "report_style", "tablo_format", "Tablo formatı tercih ediliyor"),
    (r"(?:madde|liste)\s+(?:halinde|formatında|olarak|şeklinde)", "report_style", "liste_format", "Madde/liste formatı tercih ediliyor"),
    (r"(?:grafik|chart|görsel)\s+(?:olarak|ile|ekleyerek)", "report_style", "grafik_format", "Grafik/görsel rapor tercih ediliyor"),
    (r"(?:özet|kısa|summary)\s+(?:halinde|olarak|şeklinde|bir)", "report_style", "ozet_format", "Özet/kısa format tercih ediliyor"),
    (r"(?:detaylı|ayrıntılı|kapsamlı)\s+(?:rapor|analiz|inceleme)", "report_style", "detayli_format", "Detaylı/kapsamlı rapor tercih ediliyor"),
    
    # İletişim tarzı
    (r"(?:resmi|formal)\s+(?:dil|üslup|ton|yazım)", "comm_style", "formal_dil", "Resmi iletişim dili tercih ediliyor"),
    (r"(?:samimi|rahat|informal)\s+(?:dil|üslup|ton|yazım|konuş)", "comm_style", "samimi_dil", "Samimi iletişim dili tercih ediliyor"),
    (r"(?:kısa|öz|net)\s+(?:cevap|yanıt|tut|yaz)", "comm_style", "kisa_cevap", "Kısa ve öz yanıtlar tercih ediliyor"),
    (r"(?:uzun|detaylı|açıklayıcı)\s+(?:cevap|yanıt|anlat|yaz)", "comm_style", "uzun_cevap", "Detaylı açıklamalar tercih ediliyor"),
    (r"(?:türkçe|ingilizce|english)\s+(?:yaz|cevapla|anlat|olsun)", "comm_style", "dil_tercih", "Dil tercihi belirtildi"),
    
    # Araç/yazılım tercihleri
    (r"(?:excel|word|powerpoint|ppt)\s+(?:kullanıyoruz|kullanıyorum|tercih ediyoruz|ile çalışıyoruz)", "tool_preference", "office_araclari", "Office araçları kullanılıyor"),
    (r"(?:sap|erp|crm|mes|scada)\s+(?:sistem|kullan|entegre)", "tool_preference", "is_yazilimi", "İş yazılımı/ERP kullanımı"),
    (r"(?:whatsapp|teams|slack|mail|e-posta)\s+(?:üzerinden|ile|kullanarak)\s+(?:iletişim|yazış|gönder)", "tool_preference", "iletisim_araci", "İletişim aracı tercihi"),
    
    # İş akışı / Süreç kalıpları
    (r"(?:her\s+)?(?:hafta|ay|gün|pazartesi|cuma)\s+(?:rapor|toplantı|sunum|analiz)", "workflow", "periyodik_is", "Periyodik iş akışı tespit edildi"),
    (r"(?:onay|approval)\s+(?:süreci|akışı|gerekiyor|lazım|alınmalı)", "workflow", "onay_sureci", "Onay süreci var"),
    (r"(?:üretim|sevkiyat|depo|stok|kalite|bakım)\s+(?:raporu|takibi|kontrolü|planı)", "workflow", "uretim_sureci", "Üretim/operasyon süreci"),
    (r"(?:müşteri|tedarikçi|bayi)\s+(?:raporu|analizi|takibi|listesi)", "workflow", "musteri_sureci", "Müşteri/tedarik süreci"),
    
    # Sektör/departman terminolojisi
    (r"(?:lot|parti|batch)\s+(?:numarası|takibi|üretim)", "terminology", "uretim_terimi", "Üretim terminolojisi kullanılıyor"),
    (r"(?:iplik|kumaş|boya|dokuma|örme|konfeksiyon|apre|terbiye)", "terminology", "tekstil_terimi", "Tekstil terminolojisi kullanılıyor"),
    (r"(?:sipariş|order|po|proforma|fatura|irsaliye)", "terminology", "ticari_terim", "Ticari terminoloji kullanılıyor"),
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
            # Soru kelimeleri ve çok kısa değerleri filtrele
            if len(value) < 2:
                continue
            if value.lower() in _QUESTION_WORDS:
                continue
            # "adım ne" / "ismim ne" gibi soruları atla
            remaining = text[match.end():].strip()[:20].lower()
            if remaining.startswith("?") or value.lower().endswith("mi") or value.lower().endswith("mı"):
                continue
            found.append({"key": key, "value": value, "source": source})
    return found


def extract_culture_signals(text: str) -> list[dict]:
    """Konuşmadan şirket kültürü sinyallerini çıkar"""
    found = []
    text_lower = text.lower()
    for pattern, category, key, description in CULTURE_PATTERNS:
        if re.search(pattern, text_lower):
            found.append({
                "category": category,
                "key": key,
                "value": description,
                "source_text": text[:200],
            })
    return found


# ═══════════════════════════════════════════════
#  Sohbet Oturumu — Session CRUD
# ═══════════════════════════════════════════════

async def create_session(db: AsyncSession, user_id: int, title: str = "Yeni Sohbet") -> int:
    """Yeni sohbet oturumu oluştur, eski aktifi kapat"""
    try:
        # Mevcut aktif oturumları kapat
        stmt = (
            update(ChatSession)
            .where(and_(ChatSession.user_id == user_id, ChatSession.is_active == True))
            .values(is_active=False)
        )
        await db.execute(stmt)
        
        session = ChatSession(user_id=user_id, title=title, is_active=True)
        db.add(session)
        await db.flush()
        logger.info("session_created", user_id=user_id, session_id=session.id)
        return session.id
    except Exception as e:
        logger.error("session_create_failed", error=str(e))
        return 0


async def get_active_session(db: AsyncSession, user_id: int) -> Optional[dict]:
    """Kullanıcının aktif oturumunu getir (yoksa oluştur)"""
    try:
        stmt = (
            select(ChatSession)
            .where(and_(ChatSession.user_id == user_id, ChatSession.is_active == True))
            .order_by(desc(ChatSession.created_at))
            .limit(1)
        )
        result = await db.execute(stmt)
        session = result.scalar_one_or_none()
        
        if session:
            return {
                "id": session.id,
                "title": session.title,
                "created_at": session.created_at.isoformat(),
            }
        
        # Aktif oturum yoksa yeni oluştur
        new_id = await create_session(db, user_id)
        await db.commit()
        return {"id": new_id, "title": "Yeni Sohbet", "created_at": datetime.utcnow().isoformat()}
    except Exception as e:
        logger.error("get_active_session_failed", error=str(e))
        return None


async def get_session_messages(db: AsyncSession, session_id: int) -> list[dict]:
    """Belirli bir oturumun mesajlarını getir"""
    try:
        stmt = (
            select(ConversationMemory)
            .where(ConversationMemory.session_id == session_id)
            .order_by(ConversationMemory.created_at)
        )
        result = await db.execute(stmt)
        rows = result.scalars().all()
        return [
            {
                "id": r.id,
                "question": r.question,
                "answer": r.answer,
                "department": r.department,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]
    except Exception as e:
        logger.error("get_session_messages_failed", error=str(e))
        return []


async def list_user_sessions(db: AsyncSession, user_id: int, limit: int = 30) -> list[dict]:
    """Kullanıcının sohbet oturumlarını listele (en yeni önce, mesaj sayısı + önizleme dahil)"""
    try:
        # Mesaj sayısı subquery
        msg_count_sq = (
            select(func.count(ConversationMemory.id))
            .where(ConversationMemory.session_id == ChatSession.id)
            .correlate(ChatSession)
            .scalar_subquery()
            .label("message_count")
        )
        stmt = (
            select(ChatSession, msg_count_sq)
            .where(ChatSession.user_id == user_id)
            .order_by(desc(ChatSession.updated_at))
            .limit(limit)
        )
        result = await db.execute(stmt)
        rows = result.all()
        return [
            {
                "id": s.id,
                "title": s.title,
                "is_active": s.is_active,
                "created_at": s.created_at.isoformat(),
                "updated_at": s.updated_at.isoformat() if s.updated_at else None,
                "message_count": msg_count or 0,
            }
            for s, msg_count in rows
        ]
    except Exception as e:
        logger.error("list_sessions_failed", error=str(e))
        return []


async def delete_session(db: AsyncSession, user_id: int, session_id: int) -> bool:
    """Tekil sohbet oturumunu ve mesajlarını sil"""
    try:
        # Oturumun bu kullanıcıya ait olduğunu doğrula
        stmt = select(ChatSession).where(
            and_(ChatSession.id == session_id, ChatSession.user_id == user_id)
        )
        result = await db.execute(stmt)
        session = result.scalar_one_or_none()
        if not session:
            return False

        # Önce mesajları sil
        await db.execute(
            delete(ConversationMemory).where(ConversationMemory.session_id == session_id)
        )
        # Sonra oturumu sil
        await db.execute(
            delete(ChatSession).where(ChatSession.id == session_id)
        )
        await db.flush()
        logger.info("session_deleted", user_id=user_id, session_id=session_id)
        return True
    except Exception as e:
        logger.error("session_delete_failed", error=str(e))
        return False


async def switch_to_session(db: AsyncSession, user_id: int, session_id: int) -> bool:
    """Belirli bir oturuma geç (eski aktifi kapat, yeniyi aç)"""
    try:
        # Tüm oturumları kapat
        await db.execute(
            update(ChatSession)
            .where(and_(ChatSession.user_id == user_id, ChatSession.is_active == True))
            .values(is_active=False)
        )
        # Hedef oturumu aç
        await db.execute(
            update(ChatSession)
            .where(and_(ChatSession.id == session_id, ChatSession.user_id == user_id))
            .values(is_active=True, updated_at=datetime.utcnow())
        )
        await db.flush()
        return True
    except Exception as e:
        logger.error("switch_session_failed", error=str(e))
        return False


async def update_session_title(db: AsyncSession, session_id: int, question: str):
    """Oturum başlığını ilk sorudan otomatik oluştur"""
    try:
        stmt = select(ChatSession).where(ChatSession.id == session_id)
        result = await db.execute(stmt)
        session = result.scalar_one_or_none()
        if session and session.title == "Yeni Sohbet":
            # İlk sorudan kısa başlık oluştur
            title = question[:60].strip()
            if len(question) > 60:
                title += "..."
            session.title = title
            await db.flush()
    except Exception:
        pass


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
    session_id: int = None,
):
    """Konuşmayı kalıcı hafızaya kaydet"""
    try:
        mem = ConversationMemory(
            user_id=user_id,
            session_id=session_id,
            question=question,
            answer=answer,
            department=department,
            intent=intent,
        )
        db.add(mem)
        # auto-commit by get_db dependency, ama explicit flush yapalım
        await db.flush()
        logger.debug("conversation_saved", user_id=user_id, session_id=session_id, q=question[:50])
    except Exception as e:
        logger.error("conversation_save_failed", error=str(e))


async def get_conversation_history(
    db: AsyncSession,
    user_id: int,
    limit: int = 20,
    session_id: int = None,
) -> list[dict]:
    """
    Kullanıcının son N konuşmasını getir (en eski → en yeni).
    session_id verilmişse sadece o oturumun mesajları döner.
    Engine'in beklediği format: [{"q": "...", "a": "..."}, ...]
    """
    try:
        if session_id:
            # Aktif oturumun mesajları
            stmt = (
                select(ConversationMemory)
                .where(
                    ConversationMemory.user_id == user_id,
                    ConversationMemory.session_id == session_id,
                )
                .order_by(desc(ConversationMemory.created_at))
                .limit(limit)
            )
        else:
            # Tüm konuşmalar (geriye uyumluluk)
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
    # Oturumları da sil
    try:
        stmt = delete(ChatSession).where(ChatSession.user_id == user_id)
        await db.execute(stmt)
        await db.flush()
    except Exception:
        pass
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
    Kullanıcı bilgileri + şirket kültürü + son konuşmaların kısa özeti.
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
    
    # 2. Şirket kültürü bilgisi
    culture_ctx = await get_culture_context(db)
    if culture_ctx:
        parts.append(culture_ctx)
    
    # 3. Son konuşmalar — kompakt özet
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


# ═══════════════════════════════════════════════
#  Şirket Kültürü — Tüm konuşmalardan öğrenilen kalıplar
# ═══════════════════════════════════════════════

async def extract_and_save_culture(
    db: AsyncSession,
    user_id: int,
    question: str,
    answer: str,
):
    """Konuşmadan (soru + cevap) şirket kültürü sinyallerini çıkar ve kaydet"""
    # Hem sorudan hem cevaptan sinyal çıkar
    combined = f"{question} {answer}"
    signals = extract_culture_signals(combined)
    
    for signal in signals:
        await save_culture_signal(
            db, 
            category=signal["category"],
            key=signal["key"],
            value=signal["value"],
            source_user_id=user_id,
            source_text=signal["source_text"],
        )


async def save_culture_signal(
    db: AsyncSession,
    category: str,
    key: str,
    value: str,
    source_user_id: int = None,
    source_text: str = None,
):
    """Kültür sinyalini kaydet (varsa frekansını artır — upsert)"""
    try:
        stmt = select(CompanyCulture).where(
            and_(CompanyCulture.category == category, CompanyCulture.key == key)
        )
        result = await db.execute(stmt)
        existing = result.scalar_one_or_none()
        
        if existing:
            existing.frequency += 1
            existing.updated_at = datetime.utcnow()
            # Açıklamayı güncelleme — daha bilgi verici olabilir
        else:
            culture = CompanyCulture(
                category=category,
                key=key,
                value=value,
                frequency=1,
                source_user_id=source_user_id,
                source_text=source_text[:300] if source_text else None,
            )
            db.add(culture)
        
        await db.flush()
        logger.debug("culture_signal_saved", category=category, key=key)
    except Exception as e:
        logger.error("culture_save_failed", error=str(e))


async def get_culture_context(db: AsyncSession) -> str:
    """Şirket kültürü özetini LLM için oluştur"""
    try:
        # En sık gözlemlenen kültür sinyallerini getir (min 2 kez görülmüş VEYA son 10)
        stmt = (
            select(CompanyCulture)
            .order_by(desc(CompanyCulture.frequency), desc(CompanyCulture.updated_at))
            .limit(15)
        )
        result = await db.execute(stmt)
        cultures = result.scalars().all()
        
        if not cultures:
            return ""
        
        # Kategorilere göre grupla
        categories = {}
        category_labels = {
            "report_style": "Rapor Tercihleri",
            "comm_style": "İletişim Tarzı",
            "tool_preference": "Araç Tercihleri",
            "workflow": "İş Akışları",
            "terminology": "Sektör Terminolojisi",
        }
        
        for c in cultures:
            label = category_labels.get(c.category, c.category)
            if label not in categories:
                categories[label] = []
            freq_note = f" (x{c.frequency})" if c.frequency > 1 else ""
            categories[label].append(f"{c.value}{freq_note}")
        
        lines = ["Şirket kültürü ve çalışma tarzı:"]
        for cat, items in categories.items():
            lines.append(f"  {cat}: {', '.join(items)}")
        
        return "\n".join(lines)
    except Exception as e:
        logger.error("culture_context_failed", error=str(e))
        return ""
