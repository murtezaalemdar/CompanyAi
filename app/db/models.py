"""SQLAlchemy VeritabanÄ± Modelleri"""

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Float, Boolean
from sqlalchemy.orm import relationship
from app.db.database import Base


def _utcnow():
    """UTC zaman damgası (Python 3.12+ uyumlu, timezone-naive for DB compat)"""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(Base):
    """KullanÄ±cÄ± modeli"""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255))
    department = Column(String(100))  # Ãœretim, SatÄ±ÅŸ, Ä°K, vb.
    role = Column(String(50), default="user")  # admin, manager, user
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)
    
    # Ä°liÅŸkiler
    queries = relationship("Query", back_populates="user")
    audit_logs = relationship("AuditLog", back_populates="user")


class Query(Base):
    """AI sorgu geÃ§miÅŸi modeli"""
    __tablename__ = "queries"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    question = Column(Text, nullable=False)
    answer = Column(Text)
    department = Column(String(100))
    mode = Column(String(100))
    risk_level = Column(String(50))
    confidence = Column(Float)
    processing_time_ms = Column(Integer)  # Ä°ÅŸlem sÃ¼resi (ms)
    created_at = Column(DateTime, default=_utcnow, index=True)
    
    # Ä°liÅŸkiler
    user = relationship("User", back_populates="queries")


class AuditLog(Base):
    """Denetim kaydÄ± modeli"""
    __tablename__ = "audit_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    action = Column(String(100), nullable=False)  # login, logout, query, admin_action
    resource = Column(String(100))  # Etkilenen kaynak
    details = Column(Text)  # JSON formatÄ±nda detaylar
    ip_address = Column(String(50))
    user_agent = Column(String(255))
    created_at = Column(DateTime, default=_utcnow, index=True)
    
    # Ä°liÅŸkiler
    user = relationship("User", back_populates="audit_logs")


class SystemSettings(Base):
    """Sistem ayarlarÄ± modeli"""
    __tablename__ = "system_settings"
    
    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(100), unique=True, nullable=False)
    value = Column(Text)
    description = Column(String(255))
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)
    updated_by = Column(Integer, ForeignKey("users.id"))


class ChatSession(Base):
    """Sohbet oturumu â€” sayfa yenilense bile korunur, logout ile yeni oturum aÃ§Ä±lÄ±r"""
    __tablename__ = "chat_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    title = Column(String(255), default="Yeni Sohbet")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=_utcnow, index=True)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)
    
    user = relationship("User", backref="chat_sessions")
    messages = relationship("ConversationMemory", back_populates="session", order_by="ConversationMemory.created_at")


class ConversationMemory(Base):
    """KalÄ±cÄ± konuÅŸma hafÄ±zasÄ± â€” 'unut' denene kadar saklanÄ±r"""
    __tablename__ = "conversation_memory"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    session_id = Column(Integer, ForeignKey("chat_sessions.id"), nullable=True, index=True)
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)
    department = Column(String(100))
    intent = Column(String(50))
    created_at = Column(DateTime, default=_utcnow, index=True)
    
    user = relationship("User", backref="conversation_memories")
    session = relationship("ChatSession", back_populates="messages")


class UserPreference(Base):
    """KullanÄ±cÄ± tercihleri ve bilgileri â€” AI'Ä±n hatÄ±rlamasÄ± gereken ÅŸeyler"""
    __tablename__ = "user_preferences"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    key = Column(String(100), nullable=False)       # Ã–r: "name", "favorite_topic", "style"
    value = Column(Text, nullable=False)
    source = Column(String(200))                     # Hangi konuÅŸmadan Ã§Ä±karÄ±ldÄ±
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)
    
    user = relationship("User", backref="preferences")


class CompanyCulture(Base):
    """Åirket kÃ¼ltÃ¼rÃ¼ â€” TÃœM konuÅŸmalardan Ã§Ä±karÄ±lan ÅŸirket Ã§alÄ±ÅŸma kalÄ±plarÄ±"""
    __tablename__ = "company_culture"
    
    id = Column(Integer, primary_key=True, index=True)
    category = Column(String(100), nullable=False, index=True)   # report_style, comm_style, tool_preference, workflow
    key = Column(String(200), nullable=False)                     # Ã–r: "excel_tercih", "rapor_format"
    value = Column(Text, nullable=False)                          # Ã–r: "Tablo formatÄ±nda Excel"
    frequency = Column(Integer, default=1)                        # KaÃ§ kez gÃ¶zlemlendi
    source_user_id = Column(Integer, ForeignKey("users.id"))      # Ä°lk gÃ¶zlemleyen
    source_text = Column(String(300))                             # Hangi konuÅŸmadan
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)
